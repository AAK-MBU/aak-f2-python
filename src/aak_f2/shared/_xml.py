"""Helpers for reading F2-REST XML representations.

F2 resources use the namespace ``http://cbrain.com/casefile/schema/``. Elements
are matched on their local name, so documents with and without the namespace
are read the same way.
"""

import xml.etree.ElementTree as ET
from datetime import datetime

NAMESPACE = "http://cbrain.com/casefile/schema/"


def parse(content: bytes) -> ET.Element:
    """Parse an XML document and return its root element."""
    return ET.fromstring(content)


def local_name(tag: str) -> str:
    """Return ``tag`` without its ``{namespace}`` prefix."""
    return tag.rsplit("}", 1)[-1]


def child(element: ET.Element, name: str) -> ET.Element | None:
    """Return the first direct child named ``name``, or ``None``."""
    for item in element:
        if local_name(item.tag) == name:
            return item
    return None


def children(element: ET.Element, name: str) -> list[ET.Element]:
    """Return all direct children named ``name``."""
    return [item for item in element if local_name(item.tag) == name]


def text(element: ET.Element, name: str) -> str | None:
    """Return the stripped text of child ``name``, or ``None`` if absent or empty."""
    item = child(element, name)
    if item is None or item.text is None:
        return None
    value = item.text.strip()
    return value or None


def integer(element: ET.Element, name: str) -> int | None:
    """Return child ``name`` as an integer, or ``None`` if absent or not a number."""
    value = text(element, name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def boolean(element: ET.Element, name: str) -> bool | None:
    """Return child ``name`` as a bool (``true``/``false``), or ``None``."""
    value = text(element, name)
    if value is None:
        return None
    return value.lower() == "true"


def date_time(element: ET.Element, name: str) -> datetime | None:
    """Return child ``name`` as a datetime, or ``None`` if absent or unparsable.

    F2 stores local times without a time zone (``YYYY-MM-DDTHH:MM:SS``), so the
    result is usually a naive datetime in the server's time zone.
    """
    value = text(element, name)
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
