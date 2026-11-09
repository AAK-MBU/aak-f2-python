"""Shared functionality that all departments can use and contribute to."""

from .client import F2Client
from .config import F2Config
from .errors import (
    F2ConfigError,
    F2ConnectionError,
    F2Error,
    F2HTTPError,
    F2LinkNotFoundError,
)
from .models import (
    Case,
    CollectionItem,
    Document,
    EnumerationItem,
    Link,
    Matter,
    PartyItem,
)

__all__ = [
    "Case",
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
    "Link",
    "Matter",
    "PartyItem",
]
