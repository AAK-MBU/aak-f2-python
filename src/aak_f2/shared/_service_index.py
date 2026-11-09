"""The F2-REST service index: the entry point for discovering URLs.

The service index maps link relation names to URLs and URL templates. It is
the only URL the client is configured with; every other URL is looked up here
or in the links of the resources.
"""

import re
from collections.abc import Callable, Mapping
from http import HTTPStatus
from typing import Any
from urllib.parse import quote, urljoin

from ._rels import full_rel
from .errors import F2HTTPError, F2LinkNotFoundError

_TEMPLATE_PARAMETER = re.compile(r"\{([^{}]+)\}")


def parse_service_index(data: Mapping[str, Any], base_url: str) -> dict[str, str]:
    """Map link relations to absolute URLs from the JSON service index.

    The JSON form is an object from relation name to ``{"href": ..., "title": ...}``.
    """
    links: dict[str, str] = {}
    for rel, value in data.items():
        href = (
            value.get("href") or value.get("Href")
            if isinstance(value, Mapping)
            else value
        )
        if isinstance(href, str) and href:
            links[rel] = urljoin(base_url, href)
    return links


def template_parameters(template: str) -> list[str]:
    """Return the names of the ``{name}`` parameters in a URL template."""
    return _TEMPLATE_PARAMETER.findall(template)


def expand_template(template: str, params: Mapping[str, object]) -> str:
    """Fill the ``{name}`` parameters of a URL template.

    Values are URL-encoded. ``None`` becomes an empty string.

    Raises:
        ValueError: If the template has a parameter that is not in ``params``.
    """

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in params:
            raise ValueError(f"Missing value for URL template parameter {name!r}")
        value = params[name]
        return "" if value is None else quote(str(value), safe="")

    return _TEMPLATE_PARAMETER.sub(replace, template)


class ServiceIndex:
    """Lazily loaded, cached service index.

    The index is first read without authentication, because the OAuth2 token
    endpoint is listed in it. If a relation is missing (or the anonymous read is
    refused), the index is read again with authentication.
    """

    def __init__(
        self, fetch: Callable[[bool], Mapping[str, Any]], base_url: str
    ) -> None:
        """Create the index.

        Args:
            fetch: Function returning the JSON service index; its argument tells
                whether to authenticate the request.
            base_url: URL of the service index, used to resolve relative links.
        """
        self._fetch = fetch
        self._base_url = base_url
        self._links: dict[str, str] | None = None
        self._authenticated = False

    def href(self, rel: str) -> str:
        """Return the URL (or URL template) for link relation ``rel``.

        Raises:
            F2LinkNotFoundError: If the relation is not in the service index.
        """
        wanted = full_rel(rel)
        links = self._links if self._links is not None else self._load()
        if wanted not in links and not self._authenticated:
            links = self._load(authenticated=True)
        try:
            return links[wanted]
        except KeyError:
            raise F2LinkNotFoundError(wanted, "the service index") from None

    def expand(self, rel: str, **params: object) -> str:
        """Return the URL template for ``rel`` filled with ``params``."""
        return expand_template(self.href(rel), params)

    def reload(self) -> None:
        """Forget the cached index so it is read again on next use."""
        self._links = None
        self._authenticated = False

    def _load(self, *, authenticated: bool = False) -> dict[str, str]:
        try:
            data = self._fetch(authenticated)
        except F2HTTPError as exc:
            if authenticated or exc.status_code != HTTPStatus.UNAUTHORIZED:
                raise
            return self._load(authenticated=True)
        self._links = parse_service_index(data, self._base_url)
        self._authenticated = authenticated
        return self._links
