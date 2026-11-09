"""HTTP connection to F2-REST: authentication, retries and error handling."""

import csv
import io
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping
from http import HTTPStatus
from typing import Any
from urllib.parse import urljoin

import requests

from . import _xml
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

    def request(
        self,
        method: str,
        url: str,
        *,
        authenticated: bool = True,
        accept: str = XML_ACCEPT,
        headers: Mapping[str, str] | None = None,
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
                if method in IDEMPOTENT_METHODS and attempt < self._max_retries:
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
        text = response.content.decode(_charset(response), errors="replace")
        return list(csv.DictReader(io.StringIO(text)))

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


def _charset(response: requests.Response) -> str:
    match = _CHARSET.search(response.headers.get("Content-Type", ""))
    charset = match.group(1).lower() if match else "utf-8"
    # utf-8-sig also strips a byte order mark before the first header.
    return "utf-8-sig" if charset in {"utf-8", "utf8"} else charset
