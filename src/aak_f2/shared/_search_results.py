"""Turn F2 search results (CSV, ATOM or JSON) into rows keyed by column name.

F2's filtered searches answer in CSV with the columns of the search result.
The full text searches are documented to answer with an ATOM feed. Both end
up as rows, so the same search hit models can be built from either.
"""

import csv
import io
import json
import re
import xml.etree.ElementTree as ET

from . import _xml
from .errors import F2Error

type Row = dict[str, str | None]

# ATOM element names mapped to the column names of F2's CSV search result.
_ATOM_COLUMNS = {"title": "Title", "updated": "Updated", "published": "Created"}

# The last number in a path segment of a resource URL, e.g. ".../cases/279666".
_TRAILING_ID = re.compile(r"/(\d+)/?(?:[?#].*)?$")


def parse_csv(text: str) -> list[Row]:
    """Return the rows of a CSV search result, keyed by the CSV header."""
    return list(csv.DictReader(io.StringIO(text)))


def parse_json(text: str) -> list[Row]:
    """Return the rows of a JSON search result (an array of objects).

    An object with an array in ``Results``, ``results``, ``items`` or
    ``entries`` is also accepted.
    """
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise F2Error(f"F2 returned an invalid JSON search result: {exc}") from exc
    if isinstance(data, dict):
        data = next(
            (
                data[key]
                for key in ("Results", "results", "items", "entries")
                if isinstance(data.get(key), list)
            ),
            [],
        )
    if not isinstance(data, list):
        raise F2Error("F2 returned a JSON search result that is not a list")
    return [
        {str(key): None if value is None else str(value) for key, value in item.items()}
        for item in data
        if isinstance(item, dict)
    ]


def parse_atom(content: bytes) -> list[Row]:
    """Return one row per entry in an ATOM feed.

    ``title``, ``updated`` and ``published`` become the columns ``Title``,
    ``Updated`` and ``Created``, the ``alternate`` link (or the first link)
    becomes ``alternate``, and the ATOM ``id`` becomes ``AtomId``. Other child
    elements, such as F2 extension elements, are kept under their local name.
    When there is no ``Id``, it is taken from the number at the end of the
    ``alternate`` URL.
    """
    try:
        root = _xml.parse(content)
    except ET.ParseError as exc:
        raise F2Error(f"F2 returned an invalid ATOM search result: {exc}") from exc
    return [_atom_row(entry) for entry in _xml.children(root, "entry")]


def _atom_row(entry: ET.Element) -> Row:
    row: Row = {}
    links: dict[str, str] = {}
    for item in entry:
        name = _xml.local_name(item.tag)
        if name == "link":
            href = item.get("href")
            if href:
                links.setdefault(item.get("rel", "alternate"), href)
            continue
        value = "".join(item.itertext()).strip() or None
        if name == "id":
            row["AtomId"] = value
        else:
            row.setdefault(_ATOM_COLUMNS.get(name, name), value)
    alternate = links.get("alternate") or next(iter(links.values()), None)
    row["alternate"] = alternate
    if not row.get("Id"):
        match = _TRAILING_ID.search(alternate or "") or _TRAILING_ID.search(
            row.get("AtomId") or ""
        )
        row["Id"] = match.group(1) if match else None
    return row
