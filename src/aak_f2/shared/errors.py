"""Exceptions raised by the F2 client."""

import json
import xml.etree.ElementTree as ET
from http import HTTPStatus

import requests


class F2Error(Exception):
    """Base class for all errors raised by ``aak_f2``."""


class F2ConfigError(F2Error):
    """The client configuration is missing or invalid."""


class F2ConnectionError(F2Error):
    """F2 could not be reached (network failure or timeout)."""


class F2LinkNotFoundError(F2Error):
    """A required link relation is missing from a resource or the service index.

    Attributes:
        rel: The full link relation name that was looked up.
        where: Description of the resource that was searched.
    """

    def __init__(self, rel: str, where: str) -> None:
        super().__init__(f"Link relation {rel!r} not found in {where}")
        self.rel = rel
        self.where = where


class F2HTTPError(F2Error):
    """F2 answered with an HTTP error status.

    Attributes:
        status_code: HTTP status code of the response.
        message: The ``Message`` from F2's error payload, or a fallback text.
        details: The technical ``Details`` from F2's error payload, if any.
        reason_code: F2's ``ReasonCode`` (e.g. ``"DossierCaseClosed"``), if any.
        url: The requested URL.
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        details: str | None = None,
        reason_code: str | None = None,
        url: str | None = None,
    ) -> None:
        text = f"F2 returned HTTP {status_code}: {message}"
        if reason_code:
            text += f" (ReasonCode: {reason_code})"
        if details:
            text += f"\nDetails: {details}"
        if url:
            text += f"\nURL: {url}"
        super().__init__(text)
        self.status_code = status_code
        self.message = message
        self.details = details
        self.reason_code = reason_code
        self.url = url

    @classmethod
    def from_response(cls, response: requests.Response) -> "F2HTTPError":
        """Build the error from an F2 error response.

        A 404 becomes ``F2NotFoundError`` and a 403 ``F2AccessDeniedError``;
        other statuses become ``F2HTTPError``.

        F2 returns a JSON or XML document with ``Message``, ``Details`` and
        ``ReasonCode``. The OAuth2 token endpoint returns ``error`` and
        ``error_description`` instead. Both are understood; anything else falls
        back to the HTTP reason phrase.
        """
        fields = _error_fields(response)
        message = (
            fields.get("Message")
            or fields.get("error_description")
            or fields.get("error")
            or response.reason
            or "Unknown error"
        )
        error_class = _STATUS_ERRORS.get(response.status_code, cls)
        return error_class(
            response.status_code,
            message,
            details=fields.get("Details"),
            reason_code=fields.get("ReasonCode"),
            url=response.url,
        )


class F2NotFoundError(F2HTTPError):
    """F2 answered 404: the resource was not found.

    For cases and matters this also happens when the resource exists but the
    F2 user has no access to it; F2 does not tell the two apart. For
    documents, missing access gives ``F2AccessDeniedError`` instead.
    """


class F2AccessDeniedError(F2HTTPError):
    """F2 answered 403: the resource exists, but the F2 user has no access.

    F2 answers this way for documents. Cases and matters without access give
    ``F2NotFoundError``.
    """


_STATUS_ERRORS: dict[int, type[F2HTTPError]] = {
    HTTPStatus.NOT_FOUND: F2NotFoundError,
    HTTPStatus.FORBIDDEN: F2AccessDeniedError,
}


def _error_fields(response: requests.Response) -> dict[str, str]:
    """Extract the error fields from a JSON or XML error body."""
    body = response.content or b""
    content_type = response.headers.get("Content-Type", "")
    if not body.strip():
        return {}
    if "json" in content_type:
        return _json_fields(body)
    if "xml" in content_type:
        return _xml_fields(body)
    return {}


def _json_fields(body: bytes) -> dict[str, str]:
    try:
        data = json.loads(body)
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: str(v) for k, v in data.items() if isinstance(v, str | int)}


def _xml_fields(body: bytes) -> dict[str, str]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return {}
    return {
        child.tag.rsplit("}", 1)[-1]: child.text.strip()
        for child in root
        if child.text and child.text.strip()
    }
