"""Test doubles for the HTTP layer."""

import json
from http import HTTPStatus

import requests

from aak_f2.shared import F2Config

BASE = "https://f2.example/rest"
INDEX_URL = f"{BASE}/index"
TOKEN_URL = f"{BASE}/oauth2/token"
REL = "http://cbrain.com/casefile/rel/"

SERVICE_INDEX = {
    f"{REL}oauth2-token": {"href": TOKEN_URL, "title": "Token endpoint"},
    f"{REL}case-by-id": {"href": f"{BASE}/cases/{{id}}", "title": "Case by ID"},
    f"{REL}case-by-case-number": {
        "href": f"{BASE}/cases/by-number/{{caseNumber}}",
        "title": "Case by number",
    },
    f"{REL}matter-by-id": {"href": f"{BASE}/matters/{{id}}"},
    f"{REL}create-case": {"href": f"{BASE}/cases/create"},
    f"{REL}document-by-id": {"href": f"{BASE}/documents/{{id}}"},
    f"{REL}case-search": {"href": f"{BASE}/opensearch/cases"},
    f"{REL}matter-search": {"href": f"{BASE}/opensearch/matters"},
    f"{REL}case-search-filter": {"href": f"{BASE}/search/cases"},
    f"{REL}matter-search-filter": {"href": f"{BASE}/search/matters"},
    f"{REL}party-by-id": {"href": f"{BASE}/parties/{{id}}"},
    f"{REL}party-by-cvrcpr-number": {
        "href": f"{BASE}/parties/by-cvrcpr/{{cvrcpr}}?cvr_p={{cvr_p}}"
    },
    f"{REL}party-by-login": {"href": f"{BASE}/parties/by-login/{{login}}"},
}


def opensearch_description(template: str) -> requests.Response:
    """Return an OpenSearch description document with the URL template."""
    body = f"""<?xml version="1.0" encoding="utf-8"?>
<?xml-stylesheet type="text/xsl" href="{BASE}/xml2html.xsl"?>
<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
  <ShortName>Case file search</ShortName>
  <Url type="application/atom+xml" template="{template.replace("&", "&amp;")}" />
</OpenSearchDescription>
"""
    return make_response(
        200, body, content_type="application/opensearchdescription+xml"
    )


def make_config(**overrides: object) -> F2Config:
    """Return a test configuration."""
    values: dict = {
        "service_index_url": INDEX_URL,
        "client_id": "client",
        "client_secret": "secret",
        "username": "robot",
    }
    values.update(overrides)
    return F2Config(**values)


def make_response(
    status: int = 200,
    body: bytes | str = b"",
    *,
    content_type: str = "application/vnd.cbrain.casefile+xml",
    json_body: object = None,
    url: str = "",
) -> requests.Response:
    """Build a ``requests.Response`` with the given status and body."""
    if json_body is not None:
        body = json.dumps(json_body)
        content_type = "application/json"
    response = requests.Response()
    response.status_code = status
    response._content = body.encode() if isinstance(body, str) else body
    response._content_consumed = True
    response.headers["Content-Type"] = content_type
    response.reason = HTTPStatus(status).phrase
    response.url = url
    return response


def token_response(access: str = "token-1", refresh: str | None = "refresh-1"):
    """Return a successful OAuth2 token response."""
    body: dict = {"access_token": access, "token_type": "bearer", "expires_in": 3600}
    if refresh:
        body["refresh_token"] = refresh
    return make_response(json_body=body)


class FakeSession:
    """Stand-in for ``requests.Session`` that answers from registered routes.

    Each route holds a queue of responses (or exceptions). Responses are used
    in order; the last one is repeated.
    """

    def __init__(self) -> None:
        self.routes: dict[tuple[str, str], list] = {}
        self.calls: list[tuple[str, str, dict]] = []

    def add(self, method: str, url: str, *responses: object) -> None:
        """Register responses for ``method url``."""
        self.routes.setdefault((method, url), []).extend(responses)

    def request(self, method: str, url: str, **kwargs: object) -> requests.Response:
        """Return the next registered response for ``method url``."""
        self.calls.append((method, url, kwargs))
        queue = self.routes.get((method, url))
        if not queue:
            raise AssertionError(f"Unexpected request: {method} {url}")
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item

    def post(self, url: str, **kwargs: object) -> requests.Response:
        """Send a POST through ``request``."""
        return self.request("POST", url, **kwargs)

    def calls_to(self, method: str, url: str) -> list[dict]:
        """Return the keyword arguments of every call to ``method url``."""
        return [kw for m, u, kw in self.calls if m == method and u == url]


def standard_session() -> FakeSession:
    """Return a session that serves the service index and a token."""
    session = FakeSession()
    session.add("GET", INDEX_URL, make_response(json_body=SERVICE_INDEX))
    session.add("POST", TOKEN_URL, token_response())
    session.add(
        "GET",
        f"{BASE}/opensearch/cases",
        opensearch_description(
            f"{BASE}/searches/cases?q={{searchTerms}}&count={{count}}"
        ),
    )
    session.add(
        "GET",
        f"{BASE}/opensearch/matters",
        opensearch_description(
            f"{BASE}/searches/matters?q={{searchTerms}}&count={{count}}"
        ),
    )
    return session
