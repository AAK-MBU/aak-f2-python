"""Shared functionality that all departments can use and contribute to."""

from .client import F2Client
from .config import F2Config
from .errors import (
    F2AccessDeniedError,
    F2ConfigError,
    F2ConnectionError,
    F2Error,
    F2HTTPError,
    F2LinkNotFoundError,
    F2NotFoundError,
)
from .models import (
    Case,
    CaseSearchHit,
    CollectionItem,
    Document,
    EnumerationItem,
    Link,
    Matter,
    MatterSearchHit,
    Party,
    PartyItem,
)

__all__ = [
    "Case",
    "CaseSearchHit",
    "F2AccessDeniedError",
    "CollectionItem",
    "Document",
    "EnumerationItem",
    "F2Client",
    "F2Config",
    "F2ConfigError",
    "F2ConnectionError",
    "F2Error",
    "F2HTTPError",
    "F2LinkNotFoundError",
    "F2NotFoundError",
    "Link",
    "Matter",
    "MatterSearchHit",
    "Party",
    "PartyItem",
]
