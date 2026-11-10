"""Party and party group references for creating and updating F2 resources.

F2 identifies the parties to put on a case or matter (responsible, involved
parties, ...) with a *PartyReference*, and security groups with a
*PartyGroupReference*. Both are small JSON objects.
"""

from collections.abc import Iterable, Mapping
from typing import Any

from .models import Party, PartyItem

type PartyRef = Mapping[str, Any] | str | int | Party | PartyItem
"""A party reference.

- a mapping is sent as it is, e.g. ``{"PartyNo": 26, "OrganizationNo": 5}``;
- a string with ``@`` is an e-mail (``{"EMail": ...}``), any other string a
  login (``{"Login": "AZ12345"}``);
- an integer is a party number (``{"PartyNo": ...}``);
- a ``Party`` or ``PartyItem`` is referenced by its party number.
"""

type GroupRef = Mapping[str, Any] | str
"""A security group reference: a mapping sent as it is, or a group name."""


def party_reference(ref: PartyRef) -> dict[str, Any]:
    """Return the F2 PartyReference object for ``ref``.

    Raises:
        ValueError: If ``ref`` cannot be turned into a reference.
    """
    if isinstance(ref, Mapping):
        return dict(ref)
    if isinstance(ref, bool):
        raise ValueError(f"Not a party reference: {ref!r}")
    if isinstance(ref, int):
        return {"PartyNo": ref}
    if isinstance(ref, str):
        if not ref.strip():
            raise ValueError("A party reference cannot be empty")
        return {"EMail": ref} if "@" in ref else {"Login": ref}
    if isinstance(ref, Party | PartyItem):
        if ref.party_number is None:
            raise ValueError(f"Party {ref.name!r} has no party number")
        return {"PartyNo": ref.party_number}
    raise ValueError(f"Not a party reference: {ref!r}")


def party_references(refs: Iterable[PartyRef]) -> list[dict[str, Any]]:
    """Return the F2 PartyReference objects for ``refs``."""
    if isinstance(refs, str | Mapping):
        raise ValueError('Give the parties as a list, e.g. ["AZ12345"]')
    return [party_reference(ref) for ref in refs]


def group_references(refs: Iterable[GroupRef]) -> list[dict[str, Any]]:
    """Return the F2 PartyGroupReference objects for ``refs``."""
    if isinstance(refs, str | Mapping):
        raise ValueError('Give the security groups as a list, e.g. ["SG4"]')
    return [dict(ref) if isinstance(ref, Mapping) else {"Name": ref} for ref in refs]
