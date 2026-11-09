"""``F2Client`` for MBU with the method names of ``GoClient``.

MBU's processes call ``GoClient`` from ``mbu-getorganized-integration``. This
client adds the same method names on top of the shared F2 client, so a process
can switch by changing its import. Return values are F2 models where GO
returned raw GO structures, because those cannot be reproduced from F2.
"""

from dataclasses import dataclass, field
from os import PathLike
from typing import Any

from aak_f2.shared import Case, F2NotFoundError, Party
from aak_f2.shared import F2Client as SharedF2Client


@dataclass(frozen=True)
class ContactResult:
    """A party looked up by CPR number, in the shape of ``GoClient``'s result.

    Attributes:
        full_name: Name of the party, or ``""`` if F2 has no party for the CPR.
        id: Internal F2 party ID as a string, or ``""`` if not found.
        raw: The F2 ``Party``, or ``None`` if not found. Its ``party_number``
            is what F2 uses to reference the party elsewhere.
    """

    full_name: str
    id: str
    raw: Party | None = field(default=None, repr=False)


class F2Client(SharedF2Client):
    """Shared ``F2Client`` plus the read and lookup methods of MBU's ``GoClient``."""

    def contact_lookup(self, ssn: str, *, site: str = "borgersager") -> ContactResult:
        """Look up the party with CPR number ``ssn``.

        Like ``GoClient``, a CPR without a party gives a result with empty
        ``full_name`` and ``id`` instead of an error.

        Args:
            ssn: CPR number.
            site: Exists for compatibility with ``GoClient`` and is not used.
        """
        del site
        try:
            party = self.get_party_by_cpr(ssn)
        except F2NotFoundError:
            return ContactResult(full_name="", id="")
        return ContactResult(
            full_name=party.name or "",
            id="" if party.id is None else str(party.id),
            raw=party,
        )

    def get_case_metadata(self, case_id: int | str) -> Case:
        """Return the case with internal ID ``case_id``.

        ``GoClient`` returned GO's raw metadata dict; this returns the F2 ``Case``.
        """
        return self.get_case(case_id)

    def document_metadata(self, dok_id: int | str) -> dict[str, Any]:
        """Return a document's metadata in ``GoClient``'s shape.

        Returns:
            A dict with ``ext`` (file extension without dot), ``version_ui``
            (always ``None``; F2 needs no version for PDF conversion) and
            ``raw`` (the F2 ``Document``).
        """
        document = self.get_document(dok_id)
        return {"ext": document.file_type, "version_ui": None, "raw": document}

    def download(self, dok_id: int | str, local_path: str | PathLike[str]) -> None:
        """Write the file content of document ``dok_id`` to ``local_path``."""
        self.save_content(dok_id, local_path)

    def convert_to_pdf(
        self,
        dok_id: int | str,
        version_ui: str | None = None,
        *,
        timeout: int | None = None,
    ) -> bytes | None:
        """Return F2's PDF rendering of document ``dok_id``, or ``None``.

        ``version_ui`` and ``timeout`` exist for compatibility with ``GoClient``
        and are not used; the request timeout comes from ``F2Config.timeout``.
        """
        del version_ui, timeout
        return self.get_pdf(dok_id)
