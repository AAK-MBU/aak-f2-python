"""``F2Client``: the shared client for reading, searching and looking up F2 data."""

import json
import warnings
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable, Mapping
from os import PathLike
from pathlib import Path
from typing import Any, Self
from urllib.parse import urljoin

import requests

from . import _search_results
from ._http import OPENSEARCH_ACCEPT, Connection
from ._references import (
    GroupRef,
    PartyRef,
    group_references,
    party_reference,
    party_references,
)
from ._rels import CASEFILE_REL_PREFIX, full_rel
from ._service_index import expand_template, template_parameters
from .config import F2Config
from .errors import F2AccessWarning, F2Error, F2LinkNotFoundError
from .models import (
    Case,
    CaseSearchHit,
    CollectionItem,
    Document,
    Extension,
    Link,
    Matter,
    MatterSearchHit,
    Party,
    parse_collection,
    parse_extensions,
)

type CaseRef = Case | int | str
type MatterRef = Matter | int | str
type DocumentRef = Document | int | str

_CHUNK_SIZE = 1024 * 1024

MAX_TITLE_LENGTH = 255
"""Maximum length of case, matter and document titles in F2."""

DEFAULT_SEARCH_COUNT = 100
"""Default maximum number of hits from the full text searches."""


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
        self._opensearch_templates: dict[str, str] = {}

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

        Reads the service index again and fetches an access token. Cached
        OpenSearch templates are read again on next use.
        """
        connection = self._connection
        self._opensearch_templates.clear()
        try:
            connection.index.reload()
            connection.index.href("oauth2-token")
            connection.tokens.invalidate()
            connection.tokens.access_token()
        except F2Error:
            return False
        return True

    # ------------------------------------------------------------------ service index

    def service_index(self) -> dict[str, Link]:
        """Return the services of the F2 installation from the service index.

        The index is read with authentication, so it lists the services
        available to the F2 user. F2 relations are keyed by their short name,
        e.g. ``"case-by-id"``; ``Link.rel`` holds the full relation name. A
        ``Link.href`` may be a URL template with ``{name}`` parameters; fill it
        with ``service_url``.

        Example:
            >>> for name, link in sorted(client.service_index().items()):
            ...     print(name, link.href)
        """
        return {
            rel.removeprefix(CASEFILE_REL_PREFIX): link
            for rel, link in self._connection.index.links(authenticated=True).items()
        }

    def service_url(self, rel: str, **params: object) -> str:
        """Return the URL of service ``rel`` with its template parameters filled.

        Args:
            rel: Short name (``"case-by-id"``) or full relation name.
            **params: Values for the ``{name}`` parameters of the URL template.
                Values are URL-encoded.

        Raises:
            F2LinkNotFoundError: If the service is not in the service index.
            ValueError: If a template parameter has no value.

        Example:
            >>> client.service_url("case-by-id", id=1046444)
        """
        return self._connection.index.expand(rel, **params)

    def opensearch_template(self, rel: str) -> str:
        """Return the search URL template of an OpenSearch service.

        Services such as ``case-search`` and ``matter-search`` point to an
        OpenSearch description document rather than to the search itself. The
        document holds the URL template of the real search, e.g.
        ``.../searches/cases?q={searchTerms}&count={count}``. The template is
        read once and cached. If the service index already gives a URL
        template, that is returned as is.

        Args:
            rel: Short name (``"case-search"``) or full relation name.

        Raises:
            F2LinkNotFoundError: If the service is not in the service index.
            F2Error: If the service does not point to an OpenSearch description
                with a URL template.
        """
        key = full_rel(rel)
        cached = self._opensearch_templates.get(key)
        if cached is not None:
            return cached
        href = self._connection.index.href(rel)
        if template_parameters(href):
            template = href
        else:
            response = self._connection.request("GET", href, accept=OPENSEARCH_ACCEPT)
            found = _search_results.parse_opensearch_template(response.content)
            if found is None:
                raise F2Error(
                    f"Service {rel!r} at {href} is not an OpenSearch description "
                    "with a URL template"
                )
            template = urljoin(response.url or href, found)
        self._opensearch_templates[key] = template
        return template

    # ------------------------------------------------------------------ raw access

    def request(  # noqa: PLR0913 - keyword-only options of one HTTP request
        self,
        method: str,
        href: str | Link,
        *,
        template_params: Mapping[str, object] | None = None,
        accept: str = "*/*",
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Send a request to any F2-REST URL and return the response.

        For the parts of F2-REST the client has no method for yet, e.g. a link
        found on a case. The request is authenticated and handled like the
        client's own: the token is renewed on 401, 423 and 503 are retried,
        redirects are followed, and errors raise ``F2HTTPError``. Network
        errors are retried only for idempotent methods such as ``GET``.

        Args:
            method: HTTP method, e.g. ``"GET"``, ``"POST"`` or ``"PATCH"``.
            href: A ``Link`` or a URL. A relative URL is resolved against the
                service index URL. A URL template is filled with
                ``template_params``.
            template_params: Values for the ``{name}`` parameters of a URL
                template. Values are URL-encoded.
            accept: Value of the ``Accept`` header. F2 resources answer in XML
                with ``application/vnd.cbrain.casefile+xml``.
            headers: Extra headers.
            **kwargs: Passed on to ``requests``, e.g. ``params``, ``json``,
                ``data``, ``files`` or ``stream``.

        Raises:
            F2HTTPError: If F2 answers with an error status.
            F2ConnectionError: If F2 cannot be reached.
            ValueError: If a URL template parameter has no value.

        Example:
            >>> link = case.link("update-case-extension-data")
            >>> client.request(
            ...     "POST", link, json={"Fields": [{"Name": "x", "Value": "y"}]}
            ... )
        """
        return self._connection.request(
            method,
            _resolve_href(href, template_params),
            accept=accept,
            headers=headers,
            **kwargs,
        )

    def get_xml(self, href: str | Link, **template_params: object) -> ET.Element:
        """GET an F2 resource as XML and return its root element.

        Build a model from the element where one exists, e.g.
        ``Case.from_element(element)``.

        Args:
            href: A ``Link`` or a URL, as for ``request``.
            **template_params: Values for the ``{name}`` parameters of a URL
                template.

        Raises:
            F2HTTPError: If F2 answers with an error status.
            F2Error: If the response is not XML.
            ValueError: If a URL template parameter has no value.

        Example:
            >>> element = client.get_xml(case.link("extension-data"))
        """
        return self._connection.get_xml(_resolve_href(href, template_params))

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
        return self._stream_to_file(url, path)

    def get_pdf(self, document: DocumentRef) -> bytes | None:
        """Return F2's PDF rendering of a document, or ``None`` if there is none.

        F2 only links to a PDF version when one exists.
        """
        link = self._document(document).link("pdf-content")
        if link is None:
            return None
        return self._connection.get_bytes(link.href)

    def save_pdf(self, document: DocumentRef, path: str | PathLike[str]) -> Path | None:
        """Stream F2's PDF rendering of a document to ``path``.

        Returns:
            The path written to, or ``None`` if F2 has no PDF version of the
            document. Nothing is written in that case.
        """
        link = self._document(document).link("pdf-content")
        if link is None:
            return None
        return self._stream_to_file(link.href, path)

    # ------------------------------------------------------------------ search

    def fulltext_search_cases(
        self, text: str, *, count: int = DEFAULT_SEARCH_COUNT
    ) -> list[CaseSearchHit]:
        """Search cases by free text with F2's full text search (``case-search``).

        This is the primary way to search cases. Use ``search_cases`` to look
        up cases by exact properties such as case number or CPR number.

        Cases the F2 user has no access to are left out of the result.

        Args:
            text: The text to search for.
            count: The maximum number of hits F2 should return.

        Returns:
            The hits with ``id``, ``title``, ``created``, ``updated`` and
            ``url``. F2's full text result has no case number or other
            properties; read the full case by its ``id`` for those.

        Raises:
            ValueError: If ``text`` is empty or ``count`` is not positive.
        """
        rows = self._fulltext_search("case-search", text, count)
        return [CaseSearchHit.from_row(row) for row in rows]

    def fulltext_search_matters(
        self, text: str, *, count: int = DEFAULT_SEARCH_COUNT
    ) -> list[MatterSearchHit]:
        """Search matters by free text with F2's full text search (``matter-search``).

        This is the primary way to search matters. Use ``search_matters`` to
        look up matters by exact properties such as matter number or case
        number.

        Matters the F2 user has no access to are left out of the result.

        Args:
            text: The text to search for.
            count: The maximum number of hits F2 should return.

        Returns:
            The hits with ``id``, ``title``, ``created``, ``updated`` and
            ``url``. F2's full text result has no matter number or other
            properties; read the full matter by its ``id`` for those.

        Raises:
            ValueError: If ``text`` is empty or ``count`` is not positive.
        """
        rows = self._fulltext_search("matter-search", text, count)
        return [MatterSearchHit.from_row(row) for row in rows]

    def search_cases(
        self,
        *,
        case_number: str | None = None,
        case_id: int | str | None = None,
        title: str | None = None,
        cpr_number: str | None = None,
        external_id: str | None = None,
    ) -> list[CaseSearchHit]:
        """Search cases by one or more properties (F2's filtered case search).

        Cases the F2 user has no access to are left out of the result, so an
        empty result does not prove that no such case exists.

        Args:
            case_number: Case number, e.g. ``"2022 - 60"``.
            case_id: Internal case ID.
            title: Case title.
            cpr_number: CPR/CVR number on the case.
            external_id: Customer-specific external ID.

        Raises:
            ValueError: If no criterion is given.
        """
        params = {
            "caseNumber": case_number,
            "id": case_id,
            "title": title,
            "cprNumber": cpr_number,
            "externalId": external_id,
        }
        rows = self._search("case-search-filter", params)
        return [CaseSearchHit.from_row(row) for row in rows]

    def search_matters(
        self,
        *,
        matter_number: int | str | None = None,
        matter_id: int | str | None = None,
        title: str | None = None,
        case_number: str | None = None,
        cpr_number: str | None = None,
    ) -> list[MatterSearchHit]:
        """Search matters by one or more properties (F2's filtered matter search).

        Matters the F2 user has no access to are left out of the result, so
        an empty result does not prove that no such matter exists.

        Args:
            matter_number: Public matter number.
            matter_id: Internal matter ID.
            title: Matter title.
            case_number: Number of the case the matters belong to.
            cpr_number: CPR/CVR number on the matter.

        Raises:
            ValueError: If no criterion is given.
        """
        params = {
            "matterNumber": matter_number,
            "id": matter_id,
            "title": title,
            "caseNumber": case_number,
            "cprNumber": cpr_number,
        }
        rows = self._search("matter-search-filter", params)
        return [MatterSearchHit.from_row(row) for row in rows]

    # ------------------------------------------------------------------ parties

    def get_party(self, party_id: int | str) -> Party:
        """Return the party with internal ID ``party_id``."""
        url = self._connection.index.expand("party-by-id", id=party_id)
        return Party.from_element(self._connection.get_xml(url))

    def get_party_by_cpr(self, cvrcpr: str, cvr_p: str | None = None) -> Party:
        """Return the party with CPR or CVR number ``cvrcpr``.

        Args:
            cvrcpr: CPR or CVR number.
            cvr_p: P-number, to pick one branch of a company.

        Raises:
            F2NotFoundError: If F2 has no such party.
        """
        url = self._connection.index.expand(
            "party-by-cvrcpr-number", cvrcpr=cvrcpr, cvr_p=cvr_p
        )
        return Party.from_element(self._connection.get_xml(url))

    def get_party_by_login(self, login: str) -> Party:
        """Return the F2 user with login (initials) ``login``.

        Raises:
            F2NotFoundError: If F2 has no such user.
        """
        url = self._connection.index.expand("party-by-login", login=login)
        return Party.from_element(self._connection.get_xml(url))

    # ------------------------------------------------------------------ create

    def create_case(  # noqa: PLR0913 - the central case properties
        self,
        title: str,
        *,
        journal_plan_code: str | None = None,
        process_instruction_code: str | None = None,
        responsible: PartyRef | None = None,
        involved_parties: Iterable[PartyRef] | None = None,
        security_groups: Iterable[GroupRef] | None = None,
        properties: Mapping[str, Any] | None = None,
    ) -> Case:
        """Create a case and return it.

        The case is created through the ``create-case`` service. It has no
        matters; add them with ``create_matter``.

        Args:
            title: Case title (at most 255 characters).
            journal_plan_code: The KLE number of the case ("journalplan"),
                e.g. ``"00.07.00"``. Sent as F2's ``JournalPlanCode``.
            process_instruction_code: The KLE "handlingsfacet" of the case,
                e.g. ``"G01"``. Sent as F2's ``ProcessInstructionCode``.
            responsible: The party responsible for the case.
            involved_parties: The case parties ("sagens parter").
            security_groups: Security groups, users or organizations that the
                case access is restricted to. Without them, F2's own rules
                decide who can see the case.
            properties: Other input parameters of F2's case creation, by their
                F2 name, e.g. ``{"KeywordCode": "...",
                "DeletionActionCode": "B", "ExternalAccessCode": "Open"}``.
                Party and group values must be F2 reference objects here.

        Raises:
            ValueError: If ``title`` is empty or too long, or a reference is
                invalid.
        """
        payload = self._payload(
            title,
            properties,
            JournalPlanCode=journal_plan_code,
            ProcessInstructionCode=process_instruction_code,
            Responsible=_optional(party_reference, responsible),
            InvolvedParties=_optional(party_references, involved_parties),
            SecurityGroups=_optional(group_references, security_groups),
        )
        factory = self._connection.index.href("create-case")
        location = self._connection.post_once_exactly(factory, json=payload)
        return Case.from_element(self._connection.get_xml(location))

    def create_matter(  # noqa: PLR0913 - the commonly needed matter properties
        self,
        case: CaseRef,
        title: str,
        *,
        access_level: str | None = None,
        involved_parties: Iterable[PartyRef] | None = None,
        responsible: PartyRef | None = None,
        properties: Mapping[str, Any] | None = None,
    ) -> Matter:
        """Create a matter on a case and return it.

        Issues ``F2AccessWarning`` if the matter ends up with an access level
        other than ``All`` and no involved parties, since only involved
        parties can then see it in the F2 client. The matter is created
        anyway.

        Args:
            case: The case to create the matter on.
            title: Matter title (at most 255 characters).
            access_level: ``All``, ``Unit`` or ``Involved``. When omitted, F2's
                default applies.
            involved_parties: The matter parties ("aktparter").
            responsible: The party responsible for the matter.
            properties: Other input parameters of F2's matter creation, by
                their F2 name, e.g. ``{"Type": "Inbound", "Text": "<p>..</p>",
                "CprNumber": "..."}``. ``Type`` defaults to ``Internal``.

        Raises:
            ValueError: If ``title`` is empty or too long, or a reference is
                invalid.
        """
        payload = self._payload(
            title,
            {"Type": "Internal", **(properties or {})},
            AccessLevel=access_level,
            InvolvedParties=_optional(party_references, involved_parties),
            Responsible=_optional(party_reference, responsible),
        )
        factory = self._follow(self._case(case), "create-matter")
        location = self._connection.post_once_exactly(factory, json=payload)
        matter = Matter.from_element(self._connection.get_xml(location))
        _warn_if_hidden(matter, location)
        return matter

    def create_document(
        self,
        matter: MatterRef,
        file: bytes | str | PathLike[str],
        *,
        filename: str | None = None,
        title: str | None = None,
        description: str | None = None,
    ) -> Document:
        """Upload a file as a new document on a matter and return the document.

        Args:
            matter: The matter to add the document to.
            file: The file content, or the path of a file to upload.
            filename: File name sent to F2. Its extension tells F2 the file
                type. Required when ``file`` is bytes; defaults to the name
                of the file otherwise.
            title: Document title shown in F2. Defaults to the file name
                without extension, as F2 recommends.
            description: Document description.

        Raises:
            ValueError: If no file name is given for bytes, or it has no
                extension.
        """
        if isinstance(file, bytes):
            data = file
        else:
            path = Path(file)
            data = path.read_bytes()
            filename = filename or path.name
        if not filename:
            raise ValueError("Give a filename when uploading bytes")
        if not Path(filename).suffix:
            raise ValueError(
                f"The filename {filename!r} needs an extension, so F2 knows the "
                "file type"
            )
        fields: list[tuple[str, tuple[str | None, bytes, str]]] = [
            ("Title", _text_part(title or Path(filename).stem)),
        ]
        if description:
            fields.append(("Description", _text_part(description)))
        fields.append(("File", (filename, data, "application/octet-stream")))
        factory = self._follow(self._matter(matter), "create-document")
        location = self._connection.post_once_exactly(factory, files=fields)
        return Document.from_element(self._connection.get_xml(location))

    # ------------------------------------------------------------------ update

    def update_case(  # noqa: PLR0913 - the commonly changed case properties
        self,
        case: CaseRef,
        *,
        title: str | None = None,
        journal_plan_code: str | None = None,
        process_instruction_code: str | None = None,
        responsible: PartyRef | None = None,
        involved_parties: Iterable[PartyRef] | None = None,
        security_groups: Iterable[GroupRef] | None = None,
        properties: Mapping[str, Any] | None = None,
    ) -> Case:
        """Change properties of a case and return the updated case.

        The case is changed with a JSON patch sent to its ``self`` link. Only
        the given properties are changed; ``involved_parties`` and
        ``security_groups`` replace the whole list.

        Args:
            case: The case to change.
            title: New title (at most 255 characters).
            journal_plan_code: New KLE number of the case ("journalplan"),
                e.g. ``"00.07.00"``. Sent as a patch of ``/JournalPlan``.
            process_instruction_code: New KLE "handlingsfacet" of the case,
                e.g. ``"G01"``. Sent as a patch of ``/ProcessInstruction``.
            responsible: New responsible party.
            involved_parties: New list of case parties ("sagens parter").
            security_groups: New list of security groups, users or
                organizations that the case access is restricted to.
            properties: Other properties by their F2 name, encoded as F2's
                PATCH expects, e.g. ``{"Keyword": "...",
                "ExternalAccess": "Open", "ExternalId": "..."}``. The names
                are the case property names, which differ from the creation
                parameter names (``Keyword``, not ``KeywordCode``). Read-only
                properties such as ``CaseNumber`` cannot be changed.

        Raises:
            ValueError: If nothing is to be changed, ``title`` is empty or too
                long, or a reference is invalid.
        """
        operations = _replace_operations(
            title,
            properties,
            JournalPlan=journal_plan_code,
            ProcessInstruction=process_instruction_code,
            Responsible=_optional(party_reference, responsible),
            InvolvedParties=_optional(party_references, involved_parties),
            SecurityGroups=_optional(group_references, security_groups),
        )
        url = self._follow(self._case(case), "self")
        self._connection.patch_json(url, operations)
        return Case.from_element(self._connection.get_xml(url))

    def update_matter(  # noqa: PLR0913 - the commonly changed matter properties
        self,
        matter: MatterRef,
        *,
        title: str | None = None,
        access_level: str | None = None,
        involved_parties: Iterable[PartyRef] | None = None,
        responsible: PartyRef | None = None,
        properties: Mapping[str, Any] | None = None,
    ) -> Matter:
        """Change properties of a matter and return the updated matter.

        Only the given properties are changed. ``involved_parties`` replaces
        the whole list of involved parties.

        Args:
            matter: The matter to change.
            title: New title (at most 255 characters).
            access_level: New access level: ``All``, ``Unit`` or ``Involved``.
            involved_parties: New list of involved parties.
            responsible: New responsible party.
            properties: Other properties by their F2 name, encoded as F2's
                PATCH expects, e.g. ``{"Deadline": "2026-12-01T00:00:00"}``.

        Raises:
            ValueError: If nothing is to be changed, ``title`` is empty or too
                long, or a reference is invalid.
        """
        operations = _replace_operations(
            title,
            properties,
            AccessLevel=access_level,
            InvolvedParties=_optional(party_references, involved_parties),
            Responsible=_optional(party_reference, responsible),
        )
        current = self._matter(matter)
        url = self._follow(current, "self")
        self._connection.patch_json(url, operations)
        updated = Matter.from_element(self._connection.get_xml(url))
        _warn_if_hidden(updated, url)
        return updated

    # ------------------------------------------------------------------ extension data

    def get_extension_data(self, resource: Case | Matter) -> list[Extension]:
        """Return the custom XML data ("extension data") of a case or matter.

        Follows the ``extension-data`` link of the resource. Read the case or
        matter with ``get_case`` or ``get_matter`` first.

        Raises:
            F2LinkNotFoundError: If the resource has no ``extension-data`` link.
        """
        element = self._connection.get_xml(self._follow(resource, "extension-data"))
        return parse_extensions(element)

    def set_extension_fields(
        self, resource: Case | Matter, fields: Mapping[str, str | None]
    ) -> None:
        """Set extension fields on a case or matter.

        The fields are merged into the existing extension fields, so fields
        that are not given keep their value. The names must match extension
        fields set up in the F2 installation. The request may be repeated
        safely, so it is retried after network errors.

        Args:
            resource: The case or matter, read with ``get_case`` or
                ``get_matter``.
            fields: Field values by field name, e.g.
                ``{"sagstype": "Borgersag"}``.

        Raises:
            ValueError: If no fields are given or a field name is empty.
            F2LinkNotFoundError: If the resource has no link for updating
                extension fields.

        Example:
            >>> client.set_extension_fields(case, {"sagstype": "Borgersag"})
        """
        if isinstance(fields, str) or not fields:
            raise ValueError('Give the fields as a mapping, e.g. {"sagstype": "..."}')
        if any(not name or not name.strip() for name in fields):
            raise ValueError("An extension field name cannot be empty")
        rel = (
            "update-case-extension-data"
            if isinstance(resource, Case)
            else "update-matter-extension-data"
        )
        payload = {
            "Fields": [{"Name": name, "Value": value} for name, value in fields.items()]
        }
        self._connection.request(
            "POST",
            self._follow(resource, rel),
            json=payload,
            accept="*/*",
            repeatable=True,
        )

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _payload(
        title: str, properties: Mapping[str, Any] | None, **values: Any
    ) -> dict[str, Any]:
        """Build a creation payload; ``None`` values are left out."""
        _check_title(title)
        payload = {"Title": title, **(properties or {})}
        payload.update({k: v for k, v in values.items() if v is not None})
        return payload

    def _search(
        self, rel: str, criteria: dict[str, object]
    ) -> list[dict[str, str | None]]:
        """Run a filtered search and return the CSV rows.

        The search resource is a plain URL taking query parameters. Should the
        installation publish it as a URL template, the template parameters are
        filled instead.
        """
        given = {k: str(v) for k, v in criteria.items() if v is not None and v != ""}
        if not given:
            raise ValueError("Give at least one search criterion")
        href = self._connection.index.href(rel)
        names = template_parameters(href)
        url = expand_template(href, {name: given.get(name) for name in names})
        query = {k: v for k, v in given.items() if k not in names}
        return self._connection.get_csv(url, query)

    def _fulltext_search(
        self, rel: str, text: str, count: int
    ) -> list[dict[str, str | None]]:
        """Run a full text search and return the result rows.

        ``{searchTerms}`` and ``{count}`` in the service's OpenSearch URL
        template are filled; other template parameters are left empty.
        """
        if not text or not text.strip():
            raise ValueError("Give a text to search for")
        if count < 1:
            raise ValueError("count must be at least 1")
        template = self.opensearch_template(rel)
        values = {"searchTerms": text, "count": count}
        # OpenSearch marks optional parameters with "?", e.g. {startIndex?}.
        url = expand_template(
            template,
            {
                name: values.get(name.rstrip("?"))
                for name in template_parameters(template)
            },
        )
        return self._connection.get_search_rows(url)

    def _stream_to_file(self, url: str, path: str | PathLike[str]) -> Path:
        target = Path(path)
        with self._connection.request(
            "GET", url, accept="*/*", stream=True
        ) as response:
            with target.open("wb") as file:
                for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
                    file.write(chunk)
        return target

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


def _check_title(title: str) -> None:
    if not title or not title.strip():
        raise ValueError("Give a title")
    if len(title) > MAX_TITLE_LENGTH:
        raise ValueError(f"The title is longer than {MAX_TITLE_LENGTH} characters")


def _replace_operations(
    title: str | None, properties: Mapping[str, Any] | None, **values: Any
) -> list[dict[str, Any]]:
    """Build JSON patch ``replace`` operations; ``None`` values are left out."""
    if title is not None:
        _check_title(title)
    merged = {"Title": title, **values, **(properties or {})}
    operations = [
        {"op": "replace", "path": f"/{name}", "value": value}
        for name, value in merged.items()
        if value is not None
    ]
    if not operations:
        raise ValueError("Give at least one property to change")
    return operations


def _resolve_href(
    href: str | Link, template_params: Mapping[str, object] | None
) -> str:
    """Return the URL of ``href``, with its URL template filled if it has one."""
    url = href.href if isinstance(href, Link) else href
    if template_parameters(url) or template_params:
        url = expand_template(url, template_params or {})
    return url


def _optional[T, R](convert: Callable[[T], R], value: T | None) -> R | None:
    return None if value is None else convert(value)


def _text_part(value: str) -> tuple[None, bytes, str]:
    return (None, value.encode("utf-8"), "text/plain; charset=utf-8")


def _warn_if_hidden(matter: Matter, url: str) -> None:
    """Warn if only involved parties can see ``matter`` and it has none."""
    if matter.access_level in (None, "All") or matter.involved_parties:
        return
    patch = json.dumps(
        [
            {
                "op": "replace",
                "path": "/InvolvedParties",
                "value": [{"Login": "<login>"}],
            }
        ]
    )
    warnings.warn(
        f"Matter {matter.id} was created or updated with AccessLevel "
        f"{matter.access_level!r} and no involved parties, so caseworkers may "
        "not see it in the F2 client. Set involved parties with:\n"
        f'  client.update_matter({matter.id}, involved_parties=["<login>"])\n'
        "or directly against F2-REST:\n"
        f"  PATCH {url}\n"
        "  Content-Type: application/json-patch\n"
        f"  {patch}",
        F2AccessWarning,
        stacklevel=3,
    )
