"""Data classes for the F2 resources read by the client.

Each resource keeps its links (``links``) and the parsed XML element (``raw``),
so properties that are not modelled as attributes can still be read from
``raw``.
"""

import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Self

from . import _xml
from ._rels import full_rel


@dataclass(frozen=True)
class Link:
    """A link from a resource to a related resource.

    Attributes:
        rel: Full link relation name, e.g. ``"down"`` or
            ``"http://cbrain.com/casefile/rel/content"``.
        href: Target URL.
        type: Expected media type of the target, if given.
        title: Human-readable title, if given.
    """

    rel: str
    href: str
    type: str | None = None
    title: str | None = None


def _links(element: ET.Element) -> tuple[Link, ...]:
    return tuple(
        Link(
            rel=item.get("rel", ""),
            href=item.get("href", ""),
            type=item.get("type"),
            title=item.get("title"),
        )
        for item in _xml.children(element, "Link")
        if item.get("href")
    )


class _Linked:
    """Mixin giving resources with a ``links`` attribute a ``link()`` lookup."""

    links: tuple[Link, ...]

    def link(self, rel: str) -> Link | None:
        """Return the first link with relation ``rel``, or ``None``.

        ``rel`` may be a full relation URI, a standard relation such as
        ``"down"``, or the short name of an F2 relation such as ``"content"``.
        """
        wanted = full_rel(rel)
        return next((item for item in self.links if item.rel == wanted), None)


@dataclass(frozen=True)
class EnumerationItem:
    """A value of an F2 enumeration, e.g. a keyword (KLE number).

    Attributes:
        title: Displayed title.
        path: Path in the enumeration hierarchy.
        code: Identifier of the value.
        abbreviation: Abbreviation of the title.
    """

    title: str | None
    path: str | None
    code: str | None
    abbreviation: str | None

    @classmethod
    def from_element(cls, element: ET.Element) -> Self:
        """Build the item from an enumeration element such as ``<Keyword>``."""
        return cls(
            title=_xml.text(element, "Title"),
            path=_xml.text(element, "Path"),
            code=_xml.text(element, "Code"),
            abbreviation=_xml.text(element, "Abbreviation"),
        )


@dataclass(frozen=True)
class PartyItem(_Linked):
    """A party (user, unit, external contact, ...) related to a resource.

    Attributes:
        name: Displayed name.
        email: Contact e-mail.
        type: Party type: ``User``, ``Unit``, ``Team``, ``External``,
            ``DistributionList`` or ``Private``.
        id: Internal ID. For parties placed on a case or matter, such as
            ``responsible``, this is the ID of a party snapshot (the ``self``
            link points to ``/partysnapshots/{id}``) and differs from the
            party's ID, so it cannot be used with ``F2Client.get_party``. Use
            ``party_number`` or the ``self`` link instead.
        party_number: Party number shown in F2.
        synchronization_key: Key for synchronizing with e.g. Active Directory.
        cprcvr: CPR or CVR number.
        cvr_p: P-number extension to the CVR number.
        access: Access right (``Read``, ``WriteDocument`` or ``Write``) when the
            party is listed with access to a resource.
        links: Links, including ``self`` to the party resource.
    """

    name: str | None
    email: str | None = None
    type: str | None = None
    id: int | None = None
    party_number: int | None = None
    synchronization_key: str | None = None
    cprcvr: str | None = None
    cvr_p: str | None = None
    access: str | None = None
    links: tuple[Link, ...] = ()

    @classmethod
    def from_element(cls, element: ET.Element) -> Self:
        """Build the party from a party element such as ``<Responsible>``."""
        return cls(
            name=_xml.text(element, "Name"),
            email=_xml.text(element, "EMail"),
            type=_xml.text(element, "Type"),
            id=_xml.integer(element, "Id"),
            party_number=_xml.integer(element, "PartyNumber"),
            synchronization_key=_xml.text(element, "SynchronizationKey"),
            cprcvr=_xml.text(element, "CPRCVR"),
            cvr_p=_xml.text(element, "CVR_P"),
            access=_xml.text(element, "Access"),
            links=_links(element),
        )


def _party(element: ET.Element, name: str) -> PartyItem | None:
    item = _xml.child(element, name)
    return None if item is None else PartyItem.from_element(item)


def _parties(
    element: ET.Element, list_name: str, item_name: str
) -> tuple[PartyItem, ...]:
    container = _xml.child(element, list_name)
    if container is None:
        return ()
    return tuple(
        PartyItem.from_element(item) for item in _xml.children(container, item_name)
    )


@dataclass(frozen=True)
class CollectionItem(_Linked):
    """An entry in an F2 collection, e.g. one matter in a case's matter list.

    Attributes:
        id: Identifier of the item, as given by F2 (a string).
        title: Title of the item.
        links: Links, including ``self`` to the full resource.
    """

    id: str | None
    title: str | None
    links: tuple[Link, ...] = ()

    @classmethod
    def from_element(cls, element: ET.Element) -> Self:
        """Build the item from an ``<Item>`` element."""
        return cls(
            id=_xml.text(element, "Id"),
            title=_xml.text(element, "Title"),
            links=_links(element),
        )


def parse_collection(element: ET.Element) -> list[CollectionItem]:
    """Return the items of a ``<Collection>`` element."""
    items = _xml.child(element, "Items")
    if items is None:
        return []
    return [CollectionItem.from_element(item) for item in _xml.children(items, "Item")]


@dataclass(frozen=True)
class Document(_Linked):
    """Metadata of a document on a matter.

    The file content is fetched separately through the ``content`` link (see
    ``F2Client.get_content``).

    Attributes:
        id: Internal document ID.
        title: Document title.
        description: Document description.
        file_type: File extension without dot, e.g. ``"pdf"``.
        content_type: MIME type, e.g. ``"application/pdf"``.
        file_size: Size in bytes.
        modified_date: Time of last modification.
        modified_by: Party who last modified the document.
        f2_guid: Global identifier of the document.
        preferred_attachment_format: ``"PDF"`` or ``"Original"``.
        links: Links, e.g. ``content``, ``pdf-content`` and ``up`` (the matter).
        raw: The parsed ``<Document>`` element.
    """

    id: int | None
    title: str | None
    description: str | None = None
    file_type: str | None = None
    content_type: str | None = None
    file_size: int | None = None
    modified_date: datetime | None = None
    modified_by: PartyItem | None = None
    f2_guid: str | None = None
    preferred_attachment_format: str | None = None
    links: tuple[Link, ...] = ()
    raw: ET.Element | None = field(default=None, repr=False, compare=False)

    @classmethod
    def from_element(cls, element: ET.Element) -> Self:
        """Build the document from a ``<Document>`` element."""
        size = _xml.integer(element, "FileSize")
        if size is None:
            size = _xml.integer(element, "Size")
        return cls(
            id=_xml.integer(element, "Id"),
            title=_xml.text(element, "Title"),
            description=_xml.text(element, "Description"),
            file_type=_xml.text(element, "FileType"),
            content_type=_xml.text(element, "ContentType"),
            file_size=size,
            modified_date=_xml.date_time(element, "ModifiedDate"),
            modified_by=_party(element, "ModifiedBy"),
            f2_guid=_xml.text(element, "F2Guid"),
            preferred_attachment_format=_xml.text(element, "PreferredAttachmentFormat"),
            links=_links(element),
            raw=element,
        )


@dataclass(frozen=True)
class Matter(_Linked):
    """A matter ("akt") on a case. A matter holds documents and metadata.

    Attributes:
        id: Internal matter ID.
        matter_number: Public matter number, unique across F2.
        case_matter_number: Matter number relative to its case.
        title: Matter title.
        type: ``Internal``, ``Inbound`` or ``Outbound``.
        case_number: Number of the case the matter belongs to.
        text: The matter's text body ("dossier document"), if any.
        cpr_number: CPR/CVR number of a party related to the matter.
        access_level: ``Involved``, ``Unit`` or ``All``.
        status: ``InProgress`` or ``Closed``.
        archived: Whether the matter is archived.
        documents_locked: Whether the documents on the matter are locked.
        deadline: Deadline of the matter.
        letter_date: Letter date.
        received_date: Date the matter was received.
        sent_date: Date the matter was sent.
        created_date: Time of creation.
        modified_date: Time of last modification.
        f2_guid: Global identifier of the matter.
        responsible: Party responsible for the matter.
        sender: Sender of the matter.
        receivers: Receivers of the matter.
        involved_parties: Involved parties ("aktparter").
        documents: Documents, filled only when read via a case or matter
            structure. Use ``F2Client.list_documents`` otherwise.
        links: Links, e.g. ``down`` (documents) and ``up`` (the case).
        raw: The parsed ``<Matter>`` element.
    """

    id: int | None
    matter_number: int | None = None
    case_matter_number: int | None = None
    title: str | None = None
    type: str | None = None
    case_number: str | None = None
    text: str | None = None
    cpr_number: str | None = None
    access_level: str | None = None
    status: str | None = None
    archived: bool | None = None
    documents_locked: bool | None = None
    deadline: datetime | None = None
    letter_date: datetime | None = None
    received_date: datetime | None = None
    sent_date: datetime | None = None
    created_date: datetime | None = None
    modified_date: datetime | None = None
    f2_guid: str | None = None
    responsible: PartyItem | None = None
    sender: PartyItem | None = None
    receivers: tuple[PartyItem, ...] = ()
    involved_parties: tuple[PartyItem, ...] = ()
    documents: tuple[Document, ...] = ()
    links: tuple[Link, ...] = ()
    raw: ET.Element | None = field(default=None, repr=False, compare=False)

    @classmethod
    def from_element(cls, element: ET.Element) -> Self:
        """Build the matter from a ``<Matter>`` element."""
        documents = _xml.child(element, "Documents")
        return cls(
            id=_xml.integer(element, "Id"),
            matter_number=_xml.integer(element, "MatterNumber"),
            case_matter_number=_xml.integer(element, "CaseMatterNumber"),
            title=_xml.text(element, "Title"),
            type=_xml.text(element, "Type"),
            case_number=_xml.text(element, "CaseNumber"),
            text=_xml.text(element, "Text"),
            cpr_number=_xml.text(element, "CprNumber"),
            access_level=_xml.text(element, "AccessLevel"),
            status=_xml.text(element, "Status"),
            archived=_xml.boolean(element, "Archived"),
            documents_locked=_xml.boolean(element, "DocumentsLocked"),
            deadline=_xml.date_time(element, "Deadline"),
            letter_date=_xml.date_time(element, "LetterDate"),
            received_date=_xml.date_time(element, "ReceivedDate"),
            sent_date=_xml.date_time(element, "SentDate"),
            created_date=_xml.date_time(element, "CreatedDate"),
            modified_date=_xml.date_time(element, "ModifiedDate"),
            f2_guid=_xml.text(element, "F2Guid"),
            responsible=_party(element, "Responsible"),
            sender=_party(element, "Sender"),
            receivers=_parties(element, "Receivers", "Receiver"),
            involved_parties=_parties(element, "InvolvedParties", "InvolvedParty"),
            documents=()
            if documents is None
            else tuple(
                Document.from_element(item)
                for item in _xml.children(documents, "Document")
            ),
            links=_links(element),
            raw=element,
        )


@dataclass(frozen=True)
class Case(_Linked):
    """A case ("sag") in F2. A case holds one or more matters.

    Attributes:
        id: Internal case ID.
        case_number: Official case number, e.g. ``"2022 - 60"``.
        title: Case title.
        closed: Whether the case is closed.
        cpr_number: CPR/CVR number of a party related to the case.
        external_id: Customer-specific external ID.
        f2_guid: Global identifier of the case.
        keyword: First keyword (KLE number), if any.
        keywords: All keywords.
        responsible: Party responsible for the case.
        involved_parties: The case parties ("sagens parter").
        deadline: Deadline of the case.
        created_date: Time of creation.
        modified_date: Time of last modification.
        matters: Matters, filled only when read via ``F2Client.get_case_structure``.
            Use ``F2Client.list_matters`` otherwise.
        links: Links, e.g. ``down`` (matters) and ``structure``.
        raw: The parsed ``<Case>`` element.
    """

    id: int | None
    case_number: str | None = None
    title: str | None = None
    closed: bool | None = None
    cpr_number: str | None = None
    external_id: str | None = None
    f2_guid: str | None = None
    keyword: EnumerationItem | None = None
    keywords: tuple[EnumerationItem, ...] = ()
    responsible: PartyItem | None = None
    involved_parties: tuple[PartyItem, ...] = ()
    deadline: datetime | None = None
    created_date: datetime | None = None
    modified_date: datetime | None = None
    matters: tuple[Matter, ...] = ()
    links: tuple[Link, ...] = ()
    raw: ET.Element | None = field(default=None, repr=False, compare=False)

    @classmethod
    def from_element(cls, element: ET.Element) -> Self:
        """Build the case from a ``<Case>`` element (case or case structure)."""
        keyword = _xml.child(element, "Keyword")
        keywords = _xml.child(element, "Keywords")
        matters = _xml.child(element, "Matters")
        return cls(
            id=_xml.integer(element, "Id"),
            case_number=_xml.text(element, "CaseNumber"),
            title=_xml.text(element, "Title"),
            closed=_xml.boolean(element, "Closed"),
            cpr_number=_xml.text(element, "CprNumber"),
            external_id=_xml.text(element, "ExternalId"),
            f2_guid=_xml.text(element, "F2Guid"),
            keyword=None if keyword is None else EnumerationItem.from_element(keyword),
            keywords=()
            if keywords is None
            else tuple(
                EnumerationItem.from_element(item)
                for item in _xml.children(keywords, "Keyword")
            ),
            responsible=_party(element, "Responsible"),
            involved_parties=_parties(element, "InvolvedParties", "InvolvedParty"),
            deadline=_xml.date_time(element, "Deadline"),
            created_date=_xml.date_time(element, "CreatedDate"),
            modified_date=_xml.date_time(element, "ModifiedDate"),
            matters=()
            if matters is None
            else tuple(
                Matter.from_element(item) for item in _xml.children(matters, "Matter")
            ),
            links=_links(element),
            raw=element,
        )


@dataclass(frozen=True)
class Party(_Linked):
    """A party from the F2 party registry: a user, unit or external party.

    Attributes:
        kind: The XML root element, telling the kind of party: ``External``,
            ``User``, ``Organization`` or another kind added by F2.
        id: Internal party ID.
        name: Name of the party.
        party_number: Party number shown in F2 (``PartyNo`` in party references).
        party_type: Customer-specific party type title.
        email: E-mail address.
        cvrcpr: CPR or CVR number.
        cvr_p: P-number extension to the CVR number.
        phone: Phone number.
        mobile_phone: Mobile phone number.
        address1: First address line.
        address2: Second address line.
        postal_code: Postal code.
        city: City.
        country_code: Country code.
        protected_address: Whether the address is protected.
        synchronization_key: External party number or AD synchronization key.
        initials: Initials (login) of a user.
        organization: The organization the party belongs to.
        links: Links, including ``self``.
        raw: The parsed root element.
    """

    kind: str
    id: int | None
    name: str | None = None
    party_number: int | None = None
    party_type: str | None = None
    email: str | None = None
    cvrcpr: str | None = None
    cvr_p: str | None = None
    phone: str | None = None
    mobile_phone: str | None = None
    address1: str | None = None
    address2: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country_code: str | None = None
    protected_address: bool | None = None
    synchronization_key: str | None = None
    initials: str | None = None
    organization: PartyItem | None = None
    links: tuple[Link, ...] = ()
    raw: ET.Element | None = field(default=None, repr=False, compare=False)

    @classmethod
    def from_element(cls, element: ET.Element) -> Self:
        """Build the party from a party resource such as ``<External>``."""
        email = _xml.text(element, "Email")
        return cls(
            kind=_xml.local_name(element.tag),
            id=_xml.integer(element, "Id"),
            name=_xml.text(element, "Name"),
            party_number=_xml.integer(element, "PartyNumber"),
            party_type=_xml.text(element, "PartyType"),
            email=email if email is not None else _xml.text(element, "EMail"),
            cvrcpr=_xml.text(element, "CVRCPR"),
            cvr_p=_xml.text(element, "CVR_P"),
            phone=_xml.text(element, "Phone"),
            mobile_phone=_xml.text(element, "MobilePhone"),
            address1=_xml.text(element, "Address1"),
            address2=_xml.text(element, "Address2"),
            postal_code=_xml.text(element, "PostalCode"),
            city=_xml.text(element, "City"),
            country_code=_xml.text(element, "CountryCode"),
            protected_address=_xml.boolean(element, "ProtectedAddress"),
            synchronization_key=_xml.text(element, "SynchronizationKey"),
            initials=_xml.text(element, "Initials"),
            organization=_party(element, "Organization"),
            links=_links(element),
            raw=element,
        )


def _cell(row: Mapping[str, str | None], name: str) -> str | None:
    value = row.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _cell_int(row: Mapping[str, str | None], name: str) -> int | None:
    value = _cell(row, name)
    try:
        return None if value is None else int(value)
    except ValueError:
        return None


def _cell_bool(row: Mapping[str, str | None], name: str) -> bool | None:
    value = _cell(row, name)
    return None if value is None else value.lower() in {"true", "1"}


def _cell_datetime(row: Mapping[str, str | None], name: str) -> datetime | None:
    value = _cell(row, name)
    try:
        return None if value is None else datetime.fromisoformat(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class CaseSearchHit:
    """One case found by ``F2Client.search_cases`` or ``fulltext_search_cases``.

    Use ``F2Client.get_case(hit.id)`` for the full case.

    A full text search hit only has ``id``, ``title``, ``created``,
    ``updated`` and ``url``; the other attributes are ``None``. Its
    ``created`` and ``updated`` carry the UTC offset F2 sends, whereas the
    filtered search gives local times without a time zone.

    Attributes:
        id: Internal case ID.
        case_number: Official case number.
        title: Case title.
        cpr_number: CPR/CVR number on the case.
        external_id: Customer-specific external ID.
        created: Time of creation.
        updated: Time of last modification.
        url: URL of the case in F2-REST.
        raw: The search result row as returned by F2. For an ATOM result,
            the elements of the entry keyed by name.
    """

    id: int | None
    case_number: str | None = None
    title: str | None = None
    cpr_number: str | None = None
    external_id: str | None = None
    created: datetime | None = None
    updated: datetime | None = None
    url: str | None = None
    raw: Mapping[str, str | None] = field(default_factory=dict, repr=False)

    @classmethod
    def from_row(cls, row: Mapping[str, str | None]) -> Self:
        """Build the hit from one row of the case search result."""
        return cls(
            id=_cell_int(row, "Id"),
            case_number=_cell(row, "CaseNumber"),
            title=_cell(row, "Title"),
            cpr_number=_cell(row, "CprNumber"),
            external_id=_cell(row, "ExternalId"),
            created=_cell_datetime(row, "Created"),
            updated=_cell_datetime(row, "Updated"),
            url=_cell(row, "alternate"),
            raw=dict(row),
        )


@dataclass(frozen=True)
class MatterSearchHit:
    """One matter found by ``F2Client.search_matters`` or ``fulltext_search_matters``.

    Use ``F2Client.get_matter(hit.id)`` for the full matter.

    A full text search hit only has ``id``, ``title``, ``created``,
    ``updated`` and ``url``; the other attributes are ``None``. Its
    ``created`` and ``updated`` carry the UTC offset F2 sends, whereas the
    filtered search gives local times without a time zone.

    Attributes:
        id: Internal matter ID.
        matter_number: Public matter number.
        title: Matter title.
        case_number: Number of the case the matter belongs to.
        case_title: Title of that case, if F2 includes it.
        cpr_number: CPR/CVR number on the matter.
        type: ``Internal``, ``Inbound`` or ``Outbound``.
        access_level: ``Involved``, ``Unit`` or ``All``.
        deadline: Deadline of the matter.
        archived: Whether the matter is archived.
        status: ``InProgress`` or ``Closed``.
        created: Time of creation.
        updated: Time of last modification.
        url: URL of the matter in F2-REST.
        raw: The search result row as returned by F2. For an ATOM result,
            the elements of the entry keyed by name.
    """

    id: int | None
    matter_number: int | None = None
    title: str | None = None
    case_number: str | None = None
    case_title: str | None = None
    cpr_number: str | None = None
    type: str | None = None
    access_level: str | None = None
    deadline: datetime | None = None
    archived: bool | None = None
    status: str | None = None
    created: datetime | None = None
    updated: datetime | None = None
    url: str | None = None
    raw: Mapping[str, str | None] = field(default_factory=dict, repr=False)

    @classmethod
    def from_row(cls, row: Mapping[str, str | None]) -> Self:
        """Build the hit from one row of the matter search result."""
        return cls(
            id=_cell_int(row, "Id"),
            matter_number=_cell_int(row, "MatterNumber"),
            title=_cell(row, "Title"),
            case_number=_cell(row, "CaseNumber"),
            case_title=_cell(row, "CaseTitle"),
            cpr_number=_cell(row, "CprNumber"),
            type=_cell(row, "Type"),
            access_level=_cell(row, "AccessLevel"),
            deadline=_cell_datetime(row, "Deadline"),
            archived=_cell_bool(row, "Archived"),
            status=_cell(row, "Status"),
            created=_cell_datetime(row, "Created"),
            updated=_cell_datetime(row, "Updated"),
            url=_cell(row, "alternate"),
            raw=dict(row),
        )
