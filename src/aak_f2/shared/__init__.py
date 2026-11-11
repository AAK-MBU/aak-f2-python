"""Shared functionality that all departments can use and contribute to."""

from ._references import GroupRef, PartyRef
from .client import F2Client
from .config import F2Config
from .errors import (
    F2AccessDeniedError,
    F2AccessWarning,
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
    Extension,
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
    "F2AccessWarning",
    "CollectionItem",
    "Document",
    "EnumerationItem",
    "Extension",
    "F2Client",
    "GroupRef",
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
    "PartyRef",
]
