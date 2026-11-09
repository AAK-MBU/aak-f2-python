import tempfile
import unittest
from pathlib import Path

from aak_f2.shared import F2Client, F2LinkNotFoundError, Matter
from tests.fakes import (
    BASE,
    INDEX_URL,
    TOKEN_URL,
    make_config,
    make_response,
    standard_session,
)
from tests.fixtures import (
    CASE_STRUCTURE_XML,
    CASE_XML,
    COLLECTION_XML,
    DOCUMENT_WITHOUT_PDF_XML,
    DOCUMENT_XML,
    MATTER_XML,
)

CASE_URL = f"{BASE}/cases/1046444"
MATTER_URL = f"{BASE}/matters/517886"
DOCUMENT_URL = f"{BASE}/documents/378054"


def client_with(session):
    return F2Client(make_config(), session=session)


class CaseTest(unittest.TestCase):
    def test_get_case(self):
        session = standard_session()
        session.add("GET", CASE_URL, make_response(200, CASE_XML))
        case = client_with(session).get_case(1046444)
        self.assertEqual(case.case_number, "2022 - 60")

    def test_get_case_by_number_encodes_the_number(self):
        session = standard_session()
        url = f"{BASE}/cases/by-number/2022%20-%2060"
        session.add("GET", url, make_response(200, CASE_XML))
        case = client_with(session).get_case_by_number("2022 - 60")
        self.assertEqual(case.id, 1046444)

    def test_list_matters_follows_down_link(self):
        session = standard_session()
        session.add("GET", CASE_URL, make_response(200, CASE_XML))
        session.add("GET", f"{CASE_URL}/matters", make_response(200, COLLECTION_XML))
        items = client_with(session).list_matters(1046444)
        self.assertEqual(len(items), 2)

    def test_case_object_saves_a_request(self):
        session = standard_session()
        session.add("GET", CASE_URL, make_response(200, CASE_XML))
        session.add(
            "GET", f"{CASE_URL}/structure", make_response(200, CASE_STRUCTURE_XML)
        )
        client = client_with(session)
        case = client.get_case(1046444)
        structure = client.get_case_structure(case)
        self.assertEqual(structure.matters[0].id, 517886)
        self.assertEqual(len(session.calls_to("GET", CASE_URL)), 1)


class MatterTest(unittest.TestCase):
    def test_get_matter_and_documents(self):
        session = standard_session()
        session.add("GET", MATTER_URL, make_response(200, MATTER_XML))
        session.add(
            "GET", f"{MATTER_URL}/documents", make_response(200, COLLECTION_XML)
        )
        client = client_with(session)
        matter = client.get_matter(517886)
        items = client.list_documents(matter)
        self.assertEqual(matter.title, "Borgerhenvendelse")
        self.assertEqual(items[0].title, "DossierDocument")


class DocumentTest(unittest.TestCase):
    def test_get_content(self):
        session = standard_session()
        session.add("GET", DOCUMENT_URL, make_response(200, DOCUMENT_XML))
        session.add(
            "GET",
            f"{DOCUMENT_URL}/content",
            make_response(200, b"<html/>", content_type="text/html"),
        )
        content = client_with(session).get_content(378054)
        self.assertEqual(content, b"<html/>")
        (call,) = session.calls_to("GET", f"{DOCUMENT_URL}/content")
        self.assertEqual(call["headers"]["Accept"], "*/*")

    def test_save_content(self):
        session = standard_session()
        session.add("GET", DOCUMENT_URL, make_response(200, DOCUMENT_XML))
        session.add(
            "GET",
            f"{DOCUMENT_URL}/content",
            make_response(200, b"file data", content_type="text/html"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = client_with(session).save_content(378054, Path(tmp) / "doc.html")
            self.assertEqual(path.read_bytes(), b"file data")

    def test_get_pdf(self):
        session = standard_session()
        session.add("GET", DOCUMENT_URL, make_response(200, DOCUMENT_XML))
        session.add(
            "GET",
            f"{DOCUMENT_URL}/pdf",
            make_response(200, b"%PDF", content_type="application/pdf"),
        )
        self.assertEqual(client_with(session).get_pdf(378054), b"%PDF")

    def test_get_pdf_without_pdf_version(self):
        session = standard_session()
        session.add("GET", DOCUMENT_URL, make_response(200, DOCUMENT_WITHOUT_PDF_XML))
        self.assertIsNone(client_with(session).get_pdf(378054))

    def test_save_pdf(self):
        session = standard_session()
        session.add("GET", DOCUMENT_URL, make_response(200, DOCUMENT_XML))
        session.add(
            "GET",
            f"{DOCUMENT_URL}/pdf",
            make_response(200, b"%PDF-1.7", content_type="application/pdf"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "doc.pdf"
            path = client_with(session).save_pdf(378054, target)
            self.assertEqual(path, target)
            self.assertEqual(target.read_bytes(), b"%PDF-1.7")

    def test_save_pdf_without_pdf_version(self):
        session = standard_session()
        session.add("GET", DOCUMENT_URL, make_response(200, DOCUMENT_WITHOUT_PDF_XML))
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "doc.pdf"
            self.assertIsNone(client_with(session).save_pdf(378054, target))
            self.assertFalse(target.exists())

    def test_missing_link_raises(self):
        client = client_with(standard_session())
        with self.assertRaises(F2LinkNotFoundError):
            client.list_documents(Matter(id=1))


class HealthCheckTest(unittest.TestCase):
    def test_healthy(self):
        self.assertTrue(client_with(standard_session()).health_check())

    def test_rejected_credentials(self):
        session = standard_session()
        session.routes[("POST", TOKEN_URL)] = [
            make_response(401, json_body={"error": "invalid_client"})
        ]
        self.assertFalse(client_with(session).health_check())

    def test_unreachable_index(self):
        session = standard_session()
        session.routes[("GET", INDEX_URL)] = [make_response(500)]
        client = F2Client(make_config(), session=session)
        client._connection._sleep = lambda _: None
        self.assertFalse(client.health_check())
