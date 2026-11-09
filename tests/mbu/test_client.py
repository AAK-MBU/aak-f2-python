import tempfile
import unittest
from pathlib import Path

from aak_f2.mbu import F2Client
from aak_f2.shared import Case, Document
from aak_f2.shared import F2Client as SharedF2Client
from tests.fakes import BASE, make_config, make_response, standard_session
from tests.fixtures import CASE_XML, DOCUMENT_WITHOUT_PDF_XML, DOCUMENT_XML

DOCUMENT_URL = f"{BASE}/documents/378054"


def client_with(session):
    return F2Client(make_config(), session=session)


class GoCompatibilityTest(unittest.TestCase):
    def test_is_a_shared_client(self):
        self.assertTrue(issubclass(F2Client, SharedF2Client))

    def test_get_case_metadata(self):
        session = standard_session()
        session.add("GET", f"{BASE}/cases/1046444", make_response(200, CASE_XML))
        case = client_with(session).get_case_metadata("1046444")
        self.assertIsInstance(case, Case)
        self.assertEqual(case.id, 1046444)

    def test_document_metadata_has_go_keys(self):
        session = standard_session()
        session.add("GET", DOCUMENT_URL, make_response(200, DOCUMENT_XML))
        meta = client_with(session).document_metadata("378054")
        self.assertEqual(meta["ext"], "html")
        self.assertIsNone(meta["version_ui"])
        self.assertIsInstance(meta["raw"], Document)

    def test_download_writes_file(self):
        session = standard_session()
        session.add("GET", DOCUMENT_URL, make_response(200, DOCUMENT_XML))
        session.add(
            "GET",
            f"{DOCUMENT_URL}/content",
            make_response(200, b"data", content_type="text/html"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "raw"
            result = client_with(session).download("378054", str(target))
            self.assertIsNone(result)
            self.assertEqual(target.read_bytes(), b"data")

    def test_convert_to_pdf_accepts_go_arguments(self):
        session = standard_session()
        session.add("GET", DOCUMENT_URL, make_response(200, DOCUMENT_XML))
        session.add(
            "GET",
            f"{DOCUMENT_URL}/pdf",
            make_response(200, b"%PDF", content_type="application/pdf"),
        )
        pdf = client_with(session).convert_to_pdf("378054", "1.0", timeout=10)
        self.assertEqual(pdf, b"%PDF")

    def test_convert_to_pdf_without_pdf_version(self):
        session = standard_session()
        session.add("GET", DOCUMENT_URL, make_response(200, DOCUMENT_WITHOUT_PDF_XML))
        self.assertIsNone(client_with(session).convert_to_pdf("378054"))
