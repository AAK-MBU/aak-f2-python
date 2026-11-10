import unittest

from aak_f2.mbu import F2Client, UploadResult
from tests.fakes import BASE, make_config, make_response, standard_session
from tests.fixtures import CASE_XML, DOCUMENT_XML, MATTER_XML
from tests.shared.test_create import (
    DOCUMENT_FACTORY,
    DOCUMENT_URL,
    MATTER_FACTORY,
    MATTER_URL,
    add_poe,
)


def upload_session():
    session = standard_session()
    session.add("GET", f"{BASE}/cases/1046444", make_response(200, CASE_XML))
    session.add("GET", MATTER_URL, make_response(200, MATTER_XML))
    session.add("GET", DOCUMENT_URL, make_response(200, DOCUMENT_XML))
    document_poe = add_poe(session, DOCUMENT_FACTORY, DOCUMENT_URL)
    return session, document_poe


class UploadDocumentTest(unittest.TestCase):
    def test_creates_a_matter_per_upload(self):
        session, document_poe = upload_session()
        matter_poe = add_poe(session, MATTER_FACTORY, MATTER_URL)
        result = F2Client(make_config(), session=session).upload_document(
            case_id="1046444",
            filename="Afgørelse.pdf",
            data=b"%PDF",
            access_level="Involved",
            involved_parties=["AZ12345"],
        )
        self.assertEqual(result, UploadResult(document_id=378054, matter_id=517886))
        self.assertEqual(result.raw.id, 378054)
        (matter_call,) = session.calls_to("POST", matter_poe)
        self.assertEqual(
            matter_call["json"],
            {
                "Title": "Afgørelse",
                "Type": "Internal",
                "AccessLevel": "Involved",
                "InvolvedParties": [{"Login": "AZ12345"}],
            },
        )
        (document_call,) = session.calls_to("POST", document_poe)
        self.assertEqual(
            dict(document_call["files"])["File"],
            ("Afgørelse.pdf", b"%PDF", "application/octet-stream"),
        )

    def test_existing_matter(self):
        session, document_poe = upload_session()
        result = F2Client(make_config(), session=session).upload_document(
            case_id="1046444", filename="brev.txt", data=b"hej", matter_id=517886
        )
        self.assertEqual(result.matter_id, 517886)
        self.assertEqual(session.calls_to("POST", MATTER_FACTORY), [])
        self.assertEqual(len(session.calls_to("POST", document_poe)), 1)

    def test_matter_options_need_a_new_matter(self):
        session, _ = upload_session()
        with self.assertRaises(ValueError):
            F2Client(make_config(), session=session).upload_document(
                case_id="1046444",
                filename="brev.txt",
                data=b"hej",
                matter_id=517886,
                access_level="All",
            )
        self.assertEqual(session.calls_to("POST", DOCUMENT_FACTORY), [])
