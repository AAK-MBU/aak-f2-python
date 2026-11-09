"""``F2Client``: the shared client for reading F2 cases, matters and documents."""

from os import PathLike
from pathlib import Path
from typing import Self

import requests

from ._http import Connection
from .config import F2Config
from .errors import F2Error, F2LinkNotFoundError
from .models import Case, CollectionItem, Document, Matter, parse_collection

type CaseRef = Case | int | str
type MatterRef = Matter | int | str
type DocumentRef = Document | int | str

_CHUNK_SIZE = 1024 * 1024


class F2Client:
    """Client for the F2-REST service.

    F2 organises data as cases ("sager") holding matters ("akter"), which in
    turn hold documents. All URLs are discovered at runtime from the service
    index and the links in each resource.

    Methods that take a case, matter or document accept either its ID or an
    object already read with this client. Passing the object saves a request.

    Example:
        >>> client = F2Client.from_env()
        >>> case = client.get_case(1046444)
        >>> for item in client.list_matters(case):
        ...     matter = client.get_matter(item.id)
    """

    def __init__(
        self, config: F2Config, *, session: requests.Session | None = None
    ) -> None:
        """Create the client. No requests are made until first use.

        Args:
            config: Connection settings.
            session: HTTP session to use. A new one is created if omitted.
        """
        self._connection = Connection(config, session=session)

    @classmethod
    def from_env(cls) -> Self:
        """Create a client configured from environment variables.

        See ``F2Config.from_env`` for the variables.
        """
        return cls(F2Config.from_env())

    @property
    def config(self) -> F2Config:
        """The connection settings."""
        return self._connection.config

    # ------------------------------------------------------------------ health

    def health_check(self) -> bool:
        """Return whether F2 answers and the credentials are accepted.

        Reads the service index again and fetches an access token.
        """
        connection = self._connection
        try:
            connection.index.reload()
            connection.index.href("oauth2-token")
            connection.tokens.invalidate()
            connection.tokens.access_token()
        except F2Error:
            return False
        return True

    # ------------------------------------------------------------------ cases

    def get_case(self, case_id: int | str) -> Case:
        """Return the case with internal ID ``case_id``."""
        url = self._connection.index.expand("case-by-id", id=case_id)
        return Case.from_element(self._connection.get_xml(url))

    def get_case_by_number(self, case_number: str) -> Case:
        """Return the case with case number ``case_number``, e.g. ``"2022 - 60"``."""
        url = self._connection.index.expand(
            "case-by-case-number", caseNumber=case_number
        )
        return Case.from_element(self._connection.get_xml(url))

    def get_case_structure(self, case: CaseRef) -> Case:
        """Return a case with all its matters and their documents in one request.

        The structure contains a subset of the case and matter metadata. The
        matters are in ``Case.matters`` and their documents in ``Matter.documents``.
        """
        url = self._follow(self._case(case), "structure")
        return Case.from_element(self._connection.get_xml(url))

    def list_matters(self, case: CaseRef) -> list[CollectionItem]:
        """Return the matters on a case that the user can access.

        Each item has the matter's ``id`` and ``title``. Use ``get_matter`` for
        the full matter.
        """
        url = self._follow(self._case(case), "down")
        return parse_collection(self._connection.get_xml(url))

    # ------------------------------------------------------------------ matters

    def get_matter(self, matter_id: int | str) -> Matter:
        """Return the matter with internal ID ``matter_id``."""
        url = self._connection.index.expand("matter-by-id", id=matter_id)
        return Matter.from_element(self._connection.get_xml(url))

    def list_documents(self, matter: MatterRef) -> list[CollectionItem]:
        """Return the documents on a matter.

        Each item has the document's ``id`` and ``title``. Use ``get_document``
        for the full metadata.
        """
        url = self._follow(self._matter(matter), "down")
        return parse_collection(self._connection.get_xml(url))

    # ------------------------------------------------------------------ documents

    def get_document(self, document_id: int | str) -> Document:
        """Return the metadata of the document with internal ID ``document_id``."""
        url = self._connection.index.expand("document-by-id", id=document_id)
        return Document.from_element(self._connection.get_xml(url))

    def get_content(self, document: DocumentRef) -> bytes:
        """Return the file content of a document."""
        url = self._follow(self._document(document), "content")
        return self._connection.get_bytes(url)

    def save_content(self, document: DocumentRef, path: str | PathLike[str]) -> Path:
        """Stream the file content of a document to ``path`` and return the path."""
        url = self._follow(self._document(document), "content")
        target = Path(path)
        with self._connection.request(
            "GET", url, accept="*/*", stream=True
        ) as response:
            with target.open("wb") as file:
                for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
                    file.write(chunk)
        return target

    def get_pdf(self, document: DocumentRef) -> bytes | None:
        """Return F2's PDF rendering of a document, or ``None`` if there is none.

        F2 only links to a PDF version when one exists.
        """
        link = self._document(document).link("pdf-content")
        if link is None:
            return None
        return self._connection.get_bytes(link.href)

    # ------------------------------------------------------------------ helpers

    def _case(self, case: CaseRef) -> Case:
        return case if isinstance(case, Case) else self.get_case(case)

    def _matter(self, matter: MatterRef) -> Matter:
        return matter if isinstance(matter, Matter) else self.get_matter(matter)

    def _document(self, document: DocumentRef) -> Document:
        return (
            document if isinstance(document, Document) else self.get_document(document)
        )

    @staticmethod
    def _follow(resource: Case | Matter | Document, rel: str) -> str:
        link = resource.link(rel)
        if link is None:
            where = f"{type(resource).__name__} {resource.id}"
            raise F2LinkNotFoundError(rel, where)
        return link.href
