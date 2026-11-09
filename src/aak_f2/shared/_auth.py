"""OAuth2 access tokens for F2-REST.

Uses the "Resource Owner Password Credentials" grant: the client authenticates
with HTTP Basic (client ID and secret) and asks for a token for an F2 user.
Tokens are renewed with the refresh token when possible, otherwise by logging
in again.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

import requests

from .config import F2Config
from .errors import F2ConnectionError, F2Error, F2HTTPError

# Renew the access token this many seconds before it expires.
EXPIRY_MARGIN = 60.0
DEFAULT_EXPIRES_IN = 3600


@dataclass(frozen=True)
class _Token:
    access_token: str
    expires_at: float
    refresh_token: str | None


class TokenManager:
    """Fetches, caches and renews the bearer token."""

    def __init__(
        self,
        session: requests.Session,
        config: F2Config,
        token_url: Callable[[], str],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Create the manager.

        Args:
            session: HTTP session used for token requests.
            config: Client credentials and F2 user.
            token_url: Function returning the URL of the token endpoint
                (``oauth2-token`` in the service index).
            clock: Monotonic clock in seconds, replaceable in tests.
        """
        self._session = session
        self._config = config
        self._token_url = token_url
        self._clock = clock
        self._token: _Token | None = None

    def access_token(self) -> str:
        """Return a valid access token, fetching or renewing it when needed."""
        token = self._token
        if token is not None and self._clock() < token.expires_at - EXPIRY_MARGIN:
            return token.access_token
        if token is not None and token.refresh_token:
            try:
                self._token = self._request_token(
                    {
                        "grant_type": "refresh_token",
                        "refresh_token": token.refresh_token,
                    }
                )
                return self._token.access_token
            except F2HTTPError:
                pass  # The refresh token has expired too; log in again below.
        self._token = self._request_token(self._password_grant())
        return self._token.access_token

    def invalidate(self) -> None:
        """Mark the access token as expired, e.g. after a 401 response.

        The refresh token is kept, so the next call tries to renew with it.
        """
        if self._token is not None:
            self._token = _Token(
                self._token.access_token, 0.0, self._token.refresh_token
            )

    def _password_grant(self) -> dict[str, str]:
        data = {"grant_type": "password", "username": self._config.username}
        if self._config.password:
            data["password"] = self._config.password
        if self._config.organization_partyno is not None:
            data["organization_partyno"] = str(self._config.organization_partyno)
        return data

    def _request_token(self, data: dict[str, str]) -> _Token:
        try:
            response = self._session.post(
                self._token_url(),
                data=data,
                auth=(self._config.client_id, self._config.client_secret),
                headers={"Accept": "application/json"},
                timeout=self._config.timeout,
            )
        except requests.RequestException as exc:
            raise F2ConnectionError(f"Token request failed: {exc}") from exc
        if not response.ok:
            raise F2HTTPError.from_response(response)
        try:
            body = response.json()
            access_token = body["access_token"]
        except (ValueError, KeyError, TypeError) as exc:
            raise F2Error("The token endpoint returned no access_token") from exc
        expires_in = float(body.get("expires_in") or DEFAULT_EXPIRES_IN)
        return _Token(
            access_token=access_token,
            expires_at=self._clock() + expires_in,
            refresh_token=body.get("refresh_token"),
        )
