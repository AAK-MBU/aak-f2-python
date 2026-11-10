import unittest
from datetime import datetime

from aak_f2.shared import Case, Document, Matter
from aak_f2.shared._xml import parse
from aak_f2.shared.models import parse_collection
from tests.fixtures import (
    CASE_STRUCTURE_XML,
    CASE_XML,
    COLLECTION_XML,
    DOCUMENT_XML,
    MATTER_XML,
)


class CaseTest(unittest.TestCase):
    def test_properties(self):
        case = Case.from_element(parse(CASE_XML.encode()))
        self.assertEqual(case.id, 1046444)
        self.assertEqual(case.case_number, "2022 - 60")
        self.assertEqual(case.title, "Case 1")
        self.assertFalse(case.closed)
        self.assertEqual(case.cpr_number, "62419361")
        self.assertEqual(case.external_id, "AX-2468")
        self.assertEqual(case.created_date, datetime(2022, 2, 3, 15, 31, 26, 293000))
        self.assertEqual(case.keyword.code, "Emneord_Issuetyper_Change request")
        self.assertEqual(len(case.keywords), 1)
        self.assertEqual(case.journal_plan.abbreviation, "00.07.00")
        self.assertEqual(case.process_instruction.abbreviation, "G01")
        self.assertEqual(case.responsible.name, "James Wolt")
        self.assertEqual(case.responsible.party_number, 37301)
        self.assertIsNone(case.responsible.cvr_p)
        self.assertEqual(case.involved_parties[0].cprcvr, "070761-4218")
        self.assertEqual(case.matters, ())

    def test_link_lookup_accepts_short_names(self):
        case = Case.from_element(parse(CASE_XML.encode()))
        self.assertEqual(
            case.link("down").href, "https://f2.example/rest/cases/1046444/matters"
        )
        self.assertEqual(
            case.link("structure").href,
            "https://f2.example/rest/cases/1046444/structure",
        )
        self.assertIsNone(case.link("content"))

    def test_structure_has_matters_and_documents(self):
        case = Case.from_element(parse(CASE_STRUCTURE_XML.encode()))
        (matter,) = case.matters
        self.assertEqual(matter.id, 517886)
        self.assertEqual(matter.status, "InProgress")
        self.assertFalse(matter.archived)
        self.assertIsNone(matter.deadline)
        self.assertEqual(matter.documents[0].file_type, "gif")


class MatterTest(unittest.TestCase):
    def test_properties(self):
        matter = Matter.from_element(parse(MATTER_XML.encode()))
        self.assertEqual(matter.matter_number, 13249)
        self.assertEqual(matter.case_matter_number, 1)
        self.assertEqual(matter.type, "Inbound")
        self.assertEqual(matter.text, "Tekst")
        self.assertTrue(matter.archived)
        self.assertFalse(matter.documents_locked)
        self.assertEqual([r.name for r in matter.receivers], ["cBrain DK", "cBrain US"])
        self.assertEqual(
            matter.link("up").href, "https://f2.example/rest/cases/1046444"
        )


class DocumentTest(unittest.TestCase):
    def test_properties(self):
        document = Document.from_element(parse(DOCUMENT_XML.encode()))
        self.assertEqual(document.id, 378054)
        self.assertEqual(document.title, "Test document")
        self.assertEqual(document.file_type, "html")
        self.assertEqual(document.content_type, "text/html")
        self.assertEqual(document.file_size, 31)
        self.assertIsNone(document.preferred_attachment_format)
        self.assertIsNotNone(document.link("content"))
        self.assertIsNotNone(document.raw)


class CollectionTest(unittest.TestCase):
    def test_items(self):
        items = parse_collection(parse(COLLECTION_XML.encode()))
        self.assertEqual([i.id for i in items], ["378053", "378054"])
        self.assertEqual(items[1].title, "Photo2.gif")
        self.assertEqual(
            items[1].link("self").href, "https://f2.example/rest/documents/378054"
        )

    def test_empty_collection(self):
        self.assertEqual(parse_collection(parse(b"<Collection/>")), [])
