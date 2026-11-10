"""HTTP connection to F2-REST: authentication, retries and error handling."""

import json as json_module
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping
from http import HTTPStatus
from typing import Any
from urllib.parse import urljoin

import requests

from . import _search_results, _xml
from ._auth import TokenManager
from ._service_index import ServiceIndex
from .config import F2Config
from .errors import F2ConnectionError, F2Error, F2HTTPError

XML_ACCEPT = (
    "application/vnd.cbrain.casefile+xml, "
    "application/vnd.cbrain.casefile.collection+xml;q=0.9, "
    "application/xml;q=0.8"
)
JSON_ACCEPT = "application/json"
CSV_ACCEPT = "text/csv"
OPENSEARCH_ACCEPT = (
    "application/opensearchdescription+xml, application/xml;q=0.9, */*;q=0.1"
)
# F2's full text search answers only in ATOM; anything else is accepted as a
# fallback, like a client sending "*/*".
FULLTEXT_ACCEPT = "application/atom+xml, */*;q=0.1"
_CHARSET = re.compile(r"charset=([\w.-]+)", re.IGNORECASE)

# 423: the resource is locked by another user. 503: transient server problem
# such as a database deadlock. F2 recommends retrying both later.
RETRY_STATUSES = frozenset({HTTPStatus.LOCKED, HTTPStatus.SERVICE_UNAVAILABLE})
IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})


class Connection:
    """An authenticated connection to one F2-REST installation.

    Attributes:
        config: The connection settings.
        session: The underlying ``requests`` session.
        index: The service index of the installation.
        tokens: The OAuth2 token manager.
    """

    def __init__(
        self,
        config: F2Config,
        *,
        session: requests.Session | None = None,
        max_retries: int = 3,
        backoff: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Create the connection. No requests are made until first use.

        Args:
            config: Connection settings.
            session: HTTP session to use. A new one is created if omitted.
            max_retries: Retries after a 423/503 response, or after a network
                error for idempotent methods.
            backoff: Wait before the first retry in seconds; doubled for each retry.
            sleep: Sleep function, replaceable in tests.
        """
        self.config = config
        self.session = session if session is not None else requests.Session()
        self.index = ServiceIndex(self._fetch_index, config.service_index_url)
        self.tokens = TokenManager(
            self.session, config, lambda: self.index.href("oauth2-token")
        )
        self._max_retries = max_retries
        self._backoff = backoff
        self._sleep = sleep

    def absolute(self, href: str) -> str:
        """Resolve ``href`` against the service index URL."""
        return urljoin(self.config.service_index_url, href)

    def request(  # noqa: PLR0913 - keyword-only options of one HTTP request
        self,
        method: str,
        url: str,
        *,
        authenticated: bool = True,
        accept: str = XML_ACCEPT,
        headers: Mapping[str, str] | None = None,
        repeatable: bool = False,
        **kwargs: Any,
    ) -> requests.Response:
        """Send a request and return the successful response.

        Adds the bearer token, retries on 423/503 (and on network errors for
        idempotent methods) with exponential backoff, and renews the token once
        if F2 answers 401. Redirects, such as those from the ``*-by-id``
        lookups, are followed.

        Args:
            method: HTTP method.
            url: Absolute URL or URL relative to the service index.
            authenticated: Whether to send the bearer token.
            accept: Value of the ``Accept`` header.
            headers: Extra headers.
            repeatable: Retry after network errors even though ``method`` is
                not idempotent, e.g. for a Post-Once-Exactly request.
            **kwargs: Passed on to ``requests.Session.request``.

        Raises:
            F2HTTPError: If F2 answers with an error status.
            F2ConnectionError: If F2 cannot be reached.
        """
        method = method.upper()
        url = self.absolute(url)
        attempt = 0
        renewed_token = False
        while True:
            request_headers = {"Accept": accept, **(headers or {})}
            if authenticated:
                request_headers["Authorization"] = (
                    f"Bearer {self.tokens.access_token()}"
                )
            try:
                response = self.session.request(
                    method,
                    url,
                    headers=request_headers,
                    timeout=self.config.timeout,
                    **kwargs,
                )
            except (requests.ConnectionError, requests.Timeout) as exc:
                retry = repeatable or method in IDEMPOTENT_METHODS
                if retry and attempt < self._max_retries:
                    self._wait(attempt)
                    attempt += 1
                    continue
                raise F2ConnectionError(f"{method} {url} failed: {exc}") from exc
            except requests.RequestException as exc:
                raise F2ConnectionError(f"{method} {url} failed: {exc}") from exc

            status = response.status_code
            if (
                status == HTTPStatus.UNAUTHORIZED
                and authenticated
                and not renewed_token
            ):
                self.tokens.invalidate()
                renewed_token = True
                continue
            if status in RETRY_STATUSES and attempt < self._max_retries:
                self._wait(attempt)
                attempt += 1
                continue
            if status >= HTTPStatus.BAD_REQUEST:
                raise F2HTTPError.from_response(response)
            return response

    def get_xml(self, url: str) -> ET.Element:
        """GET an XML resource and return its root element."""
        response = self.request("GET", url)
        try:
            return _xml.parse(response.content)
        except ET.ParseError as exc:
            raise F2Error(
                f"F2 returned invalid XML from {response.url}: {exc}"
            ) from exc

    def post_once_exactly(
        self,
        factory_url: str,
        *,
        json: Any = None,
        files: Any = None,
    ) -> str:
        """Create a resource with F2's Post-Once-Exactly pattern.

        An empty POST to ``factory_url`` returns the URL of a new POE resource
        in ``Location``. The payload is then POSTed to that URL; F2 answers 201
        (or 303 when the same POST is repeated) with the URL of the created
        resource in ``Location``. Because the second POST may be repeated
        safely, it is retried after network errors.

        Args:
            factory_url: The ``create-*`` link to create the resource with.
            json: Payload sent as JSON.
            files: Payload sent as ``multipart/form-data``, in the form
                ``requests`` takes for ``files``. Contents must be bytes, so
                the request can be repeated.

        Returns:
            The absolute URL of the created resource.

        Raises:
            F2Error: If F2 does not return a ``Location``.
        """
        poe = self.request(
            "POST",
            factory_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=b"",
            allow_redirects=False,
            repeatable=True,
        )
        poe_url = _location(poe, factory_url)
        created = self.request(
            "POST",
            poe_url,
            json=json,
            files=files,
            allow_redirects=False,
            repeatable=True,
        )
        return _location(created, poe_url)

    def patch_json(self, url: str, operations: list[dict[str, Any]]) -> None:
        """PATCH a resource with a JSON patch document (``replace`` operations)."""
        self.request(
            "PATCH",
            url,
            data=json_module.dumps(operations).encode("utf-8"),
            headers={"Content-Type": "application/json-patch"},
        )

    def get_bytes(self, url: str) -> bytes:
        """GET binary content, e.g. a document file."""
        return self.request("GET", url, accept="*/*").content

    def get_csv(
        self, url: str, params: Mapping[str, str] | None = None
    ) -> list[dict[str, str | None]]:
        """GET a CSV resource, such as a search result, and return its rows.

        Each row is a dict keyed by the CSV header. The body is decoded with the
        charset from ``Content-Type``, or UTF-8 when none is given.
        """
        response = self.request("GET", url, accept=CSV_ACCEPT, params=params)
        return _search_results.parse_csv(_text(response))

    def get_search_rows(
        self, url: str, params: Mapping[str, str] | None = None
    ) -> list[dict[str, str | None]]:
        """GET a full text search result and return its rows.

        ATOM is requested, as that is what F2's full text search returns. An
        XML body (by ``Content-Type`` or content) is read as ATOM, and a JSON
        or CSV body as such; see ``_search_results`` for how ATOM entries
        become rows.
        """
        response = self.request("GET", url, accept=FULLTEXT_ACCEPT, params=params)
        content_type = response.headers.get("Content-Type", "").lower()
        if "xml" in content_type or response.content.lstrip().startswith(b"<"):
            return _search_results.parse_atom(response.content)
        if "json" in content_type:
            return _search_results.parse_json(_text(response))
        return _search_results.parse_csv(_text(response))

    def _fetch_index(self, authenticated: bool) -> Mapping[str, Any]:
        response = self.request(
            "GET",
            self.config.service_index_url,
            authenticated=authenticated,
            accept=JSON_ACCEPT,
        )
        try:
            data = response.json()
        except ValueError as exc:
            raise F2Error("The service index is not valid JSON") from exc
        if not isinstance(data, Mapping):
            raise F2Error("The service index is not a JSON object")
        return data

    def _wait(self, attempt: int) -> None:
        self._sleep(self._backoff * 2**attempt)


def _location(response: requests.Response, base_url: str) -> str:
    location = response.headers.get("Location")
    if not location:
        raise F2Error(
            f"F2 answered HTTP {response.status_code} without a Location from "
            f"{base_url}"
        )
    return urljoin(base_url, location)


def _text(response: requests.Response) -> str:
    return response.content.decode(_charset(response), errors="replace")


def _charset(response: requests.Response) -> str:
    match = _CHARSET.search(response.headers.get("Content-Type", ""))
    charset = match.group(1).lower() if match else "utf-8"
    # utf-8-sig also strips a byte order mark before the first header.
    return "utf-8-sig" if charset in {"utf-8", "utf8"} else charset
