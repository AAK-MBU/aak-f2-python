"""Configuration of the F2 client."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from .errors import F2ConfigError

DEFAULT_TIMEOUT = 60.0


@dataclass(frozen=True)
class F2Config:
    """Connection settings for one F2-REST installation.

    Authentication uses the OAuth2 "Resource Owner Password Credentials" flow:
    the client authenticates with ``client_id``/``client_secret`` and logs in as
    the F2 user ``username``.

    Attributes:
        service_index_url: URL of the F2-REST service index. It is the only
            fixed URL; every other URL is discovered from it at runtime.
        client_id: OAuth2 client ID issued by the F2 service provider.
        client_secret: OAuth2 client secret issued by the F2 service provider.
        username: F2 user name the client works as.
        password: F2 user password. Optional, depending on the installation.
        organization_partyno: Party number of the organization to log in to,
            for users with roles in more than one organization.
        timeout: Timeout in seconds for each HTTP request.
    """

    service_index_url: str
    client_id: str
    client_secret: str = field(repr=False)
    username: str
    password: str | None = field(default=None, repr=False)
    organization_partyno: int | None = None
    timeout: float = DEFAULT_TIMEOUT

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "F2Config":
        """Read the configuration from environment variables.

        Variables:
            F2_SERVICE_INDEX_URL: Required.
            F2_CLIENT_ID: Required.
            F2_CLIENT_SECRET: Required.
            F2_USERNAME: Required.
            F2_PASSWORD: Optional.
            F2_ORGANIZATION_PARTYNO: Optional, integer.
            F2_TIMEOUT: Optional, seconds (default 60).

        Args:
            environ: Mapping to read from. Defaults to ``os.environ``.

        Raises:
            F2ConfigError: If a required variable is missing or a number is invalid.
        """
        env = os.environ if environ is None else environ
        required = (
            "F2_SERVICE_INDEX_URL",
            "F2_CLIENT_ID",
            "F2_CLIENT_SECRET",
            "F2_USERNAME",
        )
        missing = [name for name in required if not env.get(name)]
        if missing:
            raise F2ConfigError(
                f"Missing environment variable(s): {', '.join(missing)}"
            )
        try:
            partyno = env.get("F2_ORGANIZATION_PARTYNO")
            timeout = env.get("F2_TIMEOUT")
            return cls(
                service_index_url=env["F2_SERVICE_INDEX_URL"],
                client_id=env["F2_CLIENT_ID"],
                client_secret=env["F2_CLIENT_SECRET"],
                username=env["F2_USERNAME"],
                password=env.get("F2_PASSWORD") or None,
                organization_partyno=int(partyno) if partyno else None,
                timeout=float(timeout) if timeout else DEFAULT_TIMEOUT,
            )
        except ValueError as exc:
            raise F2ConfigError(f"Invalid number in F2 configuration: {exc}") from exc
