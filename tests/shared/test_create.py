import json
import tempfile
import unittest
import warnings
from pathlib import Path

import requests

from aak_f2.shared import (
    F2AccessWarning,
    F2Client,
    F2Error,
    F2HTTPError,
    Matter,
    PartyItem,
    _xml,
)
from tests.fakes import BASE, make_config, make_response, standard_session
from tests.fixtures import CASE_XML, DOCUMENT_XML, MATTER_XML

CASE_FACTORY = f"{BASE}/cases/create"
CASE_URL = f"{BASE}/cases/1046444"
MATTER_FACTORY = f"{CASE_URL}/create-matter"
MATTER_URL = f"{BASE}/matters/517886"
DOCUMENT_FACTORY = f"{MATTER_URL}/create-document"
DOCUMENT_URL = f"{BASE}/documents/378054"

HIDDEN_MATTER_XML = MATTER_XML.replace(
    "<AccessLevel>All</AccessLevel>", "<AccessLevel>Involved</AccessLevel>"
)
INVOLVED_MATTER_XML = HIDDEN_MATTER_XML.replace(
    "<Receivers>",
    "<InvolvedParties><InvolvedParty><Name>Lise</Name>"
    "<PartyNumber>118</PartyNumber></InvolvedParty></InvolvedParties><Receivers>",
)


def redirect(status, location):
    response = make_response(status)
    response.headers["Location"] = location
    return response


def add_poe(session, factory, created_url, *, poe_status=201, created_status=201):
    """Serve both POE steps: factory -> POE URL -> created resource."""
    poe_url = f"{factory}/poe-1"
    session.add("POST", factory, redirect(poe_status, poe_url))
    session.add("POST", poe_url, redirect(created_status, created_url))
    return poe_url


def client_with(session):
    return F2Client(make_config(), session=session)


def with_matter_create(session, matter_xml=MATTER_XML):
    session.add("GET", f"{BASE}/cases/1046444", make_response(200, CASE_XML))
    poe_url = add_poe(session, MATTER_FACTORY, MATTER_URL)
    session.add("GET", MATTER_URL, make_response(200, matter_xml))
    return poe_url


class PostOnceExactlyTest(unittest.TestCase):
    def test_two_posts_then_reads_created_case(self):
        session = standard_session()
        poe_url = add_poe(session, CASE_FACTORY, CASE_URL, poe_status=303)
        session.add("GET", CASE_URL, make_response(200, CASE_XML))
        case = client_with(session).create_case("Ny sag")
        self.assertEqual(case.id, 1046444)
        (first,) = session.calls_to("POST", CASE_FACTORY)
        self.assertEqual(first["data"], b"")
        self.assertEqual(
            first["headers"]["Content-Type"], "application/x-www-form-urlencoded"
        )
        self.assertFalse(first["allow_redirects"])
        (second,) = session.calls_to("POST", poe_url)
        self.assertEqual(second["json"], {"Title": "Ny sag"})
        self.assertFalse(second["allow_redirects"])

    def test_payload_post_is_retried_after_network_error(self):
        session = standard_session()
        # A relative Location is resolved against the factory URL.
        poe_url = f"{BASE}/cases/poe-1"
        session.add("POST", CASE_FACTORY, redirect(201, "poe-1"))
        session.add(
            "POST",
            poe_url,
            requests.ConnectionError("reset"),
            redirect(303, CASE_URL),
        )
        session.add("GET", CASE_URL, make_response(200, CASE_XML))
        client = client_with(session)
        client._connection._sleep = lambda _: None
        self.assertEqual(client.create_case("Ny sag").id, 1046444)
        self.assertEqual(len(session.calls_to("POST", poe_url)), 2)

    def test_missing_location(self):
        session = standard_session()
        session.add("POST", CASE_FACTORY, make_response(201))
        with self.assertRaises(F2Error):
            client_with(session).create_case("Ny sag")

    def test_error_from_payload_post(self):
        session = standard_session()
        poe_url = f"{CASE_FACTORY}/poe-1"
        session.add("POST", CASE_FACTORY, redirect(201, poe_url))
        session.add(
            "POST",
            poe_url,
            make_response(
                400,
                json_body={"Message": "Bad", "ReasonCode": "DossierBadResponsible"},
            ),
        )
        with self.assertRaises(F2HTTPError) as caught:
            client_with(session).create_case("Ny sag", responsible="AZ1")
        self.assertEqual(caught.exception.reason_code, "DossierBadResponsible")


class CreateCaseTest(unittest.TestCase):
    def test_payload(self):
        session = standard_session()
        poe_url = add_poe(session, CASE_FACTORY, CASE_URL)
        session.add("GET", CASE_URL, make_response(200, CASE_XML))
        client_with(session).create_case(
            "Ny sag",
            responsible="AZ12345",
            involved_parties=[26, "borger@example.com", {"PartyNo": 7}],
            security_groups=["SG4", {"PartyNumber": 9}],
            properties={"KeywordCode": "00.07.00"},
        )
        (call,) = session.calls_to("POST", poe_url)
        self.assertEqual(
            call["json"],
            {
                "Title": "Ny sag",
                "KeywordCode": "00.07.00",
                "Responsible": {"Login": "AZ12345"},
                "InvolvedParties": [
                    {"PartyNo": 26},
                    {"EMail": "borger@example.com"},
                    {"PartyNo": 7},
                ],
                "SecurityGroups": [{"Name": "SG4"}, {"PartyNumber": 9}],
            },
        )

    def test_party_objects_are_referenced_by_party_number(self):
        session = standard_session()
        poe_url = add_poe(session, CASE_FACTORY, CASE_URL)
        session.add("GET", CASE_URL, make_response(200, CASE_XML))
        party = PartyItem(name="Lise", party_number=118)
        client_with(session).create_case("Ny sag", responsible=party)
        (call,) = session.calls_to("POST", poe_url)
        self.assertEqual(call["json"]["Responsible"], {"PartyNo": 118})

    def test_invalid_input_sends_nothing(self):
        session = standard_session()
        client = client_with(session)
        for kwargs in (
            {"title": ""},
            {"title": "x" * 256},
            {"title": "Ny", "involved_parties": "AZ1"},
            {"title": "Ny", "responsible": ""},
            {"title": "Ny", "responsible": True},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                client.create_case(**kwargs)
        self.assertEqual(session.calls_to("POST", CASE_FACTORY), [])


class CreateMatterTest(unittest.TestCase):
    def test_payload_defaults_to_internal(self):
        session = standard_session()
        poe_url = with_matter_create(session)
        matter = client_with(session).create_matter(
            1046444,
            "Ny akt",
            access_level="All",
            responsible=118,
            properties={"Text": "<p>Hej</p>"},
        )
        self.assertEqual(matter.id, 517886)
        (call,) = session.calls_to("POST", poe_url)
        self.assertEqual(
            call["json"],
            {
                "Title": "Ny akt",
                "Type": "Internal",
                "Text": "<p>Hej</p>",
                "AccessLevel": "All",
                "Responsible": {"PartyNo": 118},
            },
        )

    def test_type_can_be_overridden(self):
        session = standard_session()
        poe_url = with_matter_create(session)
        client_with(session).create_matter(
            1046444, "Ny akt", properties={"Type": "Inbound"}
        )
        (call,) = session.calls_to("POST", poe_url)
        self.assertEqual(call["json"]["Type"], "Inbound")

    def test_no_warning_when_visible_to_all(self):
        session = standard_session()
        with_matter_create(session)
        with warnings.catch_warnings():
            warnings.simplefilter("error", F2AccessWarning)
            client_with(session).create_matter(1046444, "Ny akt")

    def test_warns_when_hidden_without_involved_parties(self):
        session = standard_session()
        with_matter_create(session, HIDDEN_MATTER_XML)
        with self.assertWarns(F2AccessWarning) as caught:
            matter = client_with(session).create_matter(1046444, "Ny akt")
        self.assertEqual(matter.id, 517886)
        message = str(caught.warning)
        self.assertIn("Matter 517886", message)
        self.assertIn("'Involved'", message)
        self.assertIn("client.update_matter(517886, involved_parties=", message)
        self.assertIn(f"PATCH {MATTER_URL}", message)
        self.assertIn('"path": "/InvolvedParties"', message)
        self.assertEqual(caught.filename, __file__)

    def test_no_warning_with_involved_parties(self):
        session = standard_session()
        with_matter_create(session, INVOLVED_MATTER_XML)
        with warnings.catch_warnings():
            warnings.simplefilter("error", F2AccessWarning)
            client_with(session).create_matter(
                1046444, "Ny akt", access_level="Involved", involved_parties=[118]
            )


class CreateDocumentTest(unittest.TestCase):
    def setUp(self):
        self.session = standard_session()
        self.session.add("GET", MATTER_URL, make_response(200, MATTER_XML))
        self.poe_url = add_poe(self.session, DOCUMENT_FACTORY, DOCUMENT_URL)
        self.session.add("GET", DOCUMENT_URL, make_response(200, DOCUMENT_XML))
        self.client = client_with(self.session)

    def sent_files(self):
        (call,) = self.session.calls_to("POST", self.poe_url)
        self.assertIsNone(call["json"])
        return call["files"]

    def test_bytes_with_filename(self):
        document = self.client.create_document(
            517886, b"%PDF", filename="Afgørelse.pdf", description="Svar"
        )
        self.assertEqual(document.id, 378054)
        self.assertEqual(
            self.sent_files(),
            [
                ("Title", (None, "Afgørelse".encode(), "text/plain; charset=utf-8")),
                ("Description", (None, b"Svar", "text/plain; charset=utf-8")),
                ("File", ("Afgørelse.pdf", b"%PDF", "application/octet-stream")),
            ],
        )

    def test_path_and_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "brev.docx"
            path.write_bytes(b"docx")
            self.client.create_document(
                Matter.from_element(_matter_element()), path, title="Brev til borger"
            )
        files = dict(self.sent_files())
        self.assertEqual(files["Title"][1], b"Brev til borger")
        self.assertEqual(
            files["File"], ("brev.docx", b"docx", "application/octet-stream")
        )

    def test_filename_rules(self):
        with self.assertRaises(ValueError):
            self.client.create_document(517886, b"x")
        with self.assertRaises(ValueError):
            self.client.create_document(517886, b"x", filename="uden-endelse")
        self.assertEqual(self.session.calls_to("POST", DOCUMENT_FACTORY), [])


class UpdateCaseTest(unittest.TestCase):
    def test_patches_the_self_link_and_reads_the_case_again(self):
        session = standard_session()
        session.add("GET", CASE_URL, make_response(200, CASE_XML))
        session.add("PATCH", CASE_URL, make_response(200))
        case = client_with(session).update_case(
            1046444,
            title="Ny titel",
            responsible="AZ12345",
            involved_parties=[26, "borger@example.com"],
            security_groups=["SG4"],
            properties={"Keyword": "00.07.00", "ExternalId": "X-1"},
        )
        self.assertEqual(case.id, 1046444)
        (call,) = session.calls_to("PATCH", CASE_URL)
        self.assertEqual(call["headers"]["Content-Type"], "application/json-patch")
        self.assertEqual(
            json.loads(call["data"]),
            [
                {"op": "replace", "path": "/Title", "value": "Ny titel"},
                {
                    "op": "replace",
                    "path": "/Responsible",
                    "value": {"Login": "AZ12345"},
                },
                {
                    "op": "replace",
                    "path": "/InvolvedParties",
                    "value": [{"PartyNo": 26}, {"EMail": "borger@example.com"}],
                },
                {
                    "op": "replace",
                    "path": "/SecurityGroups",
                    "value": [{"Name": "SG4"}],
                },
                {"op": "replace", "path": "/Keyword", "value": "00.07.00"},
                {"op": "replace", "path": "/ExternalId", "value": "X-1"},
            ],
        )
        # One GET to resolve the ID, one to read the updated case.
        self.assertEqual(len(session.calls_to("GET", CASE_URL)), 2)

    def test_case_object_is_not_read_before_patching(self):
        session = standard_session()
        session.add("GET", CASE_URL, make_response(200, CASE_XML))
        session.add("PATCH", CASE_URL, make_response(204))
        client = client_with(session)
        case = client.get_case(1046444)
        client.update_case(case, responsible=PartyItem(name="Lise", party_number=118))
        (call,) = session.calls_to("PATCH", CASE_URL)
        self.assertEqual(
            json.loads(call["data"]),
            [{"op": "replace", "path": "/Responsible", "value": {"PartyNo": 118}}],
        )
        self.assertEqual(len(session.calls_to("GET", CASE_URL)), 2)

    def test_invalid_input_sends_nothing(self):
        session = standard_session()
        client = client_with(session)
        for kwargs in (
            {},
            {"title": ""},
            {"title": "x" * 256},
            {"involved_parties": "AZ1"},
            {"security_groups": "SG4"},
            {"responsible": True},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                client.update_case(1046444, **kwargs)
        self.assertEqual(session.calls_to("PATCH", CASE_URL), [])


class UpdateMatterTest(unittest.TestCase):
    def test_patches_given_properties(self):
        session = standard_session()
        session.add("GET", MATTER_URL, make_response(200, MATTER_XML))
        session.add("PATCH", MATTER_URL, make_response(200))
        client_with(session).update_matter(
            517886,
            access_level="All",
            involved_parties=["AZ1", 26],
            properties={"Deadline": "2026-12-01T00:00:00"},
        )
        (call,) = session.calls_to("PATCH", MATTER_URL)
        self.assertEqual(call["headers"]["Content-Type"], "application/json-patch")
        self.assertEqual(
            json.loads(call["data"]),
            [
                {"op": "replace", "path": "/AccessLevel", "value": "All"},
                {
                    "op": "replace",
                    "path": "/InvolvedParties",
                    "value": [{"Login": "AZ1"}, {"PartyNo": 26}],
                },
                {
                    "op": "replace",
                    "path": "/Deadline",
                    "value": "2026-12-01T00:00:00",
                },
            ],
        )

    def test_requires_a_change(self):
        with self.assertRaises(ValueError):
            client_with(standard_session()).update_matter(517886)

    def test_rejects_too_long_title(self):
        with self.assertRaises(ValueError):
            client_with(standard_session()).update_matter(517886, title="x" * 256)

    def test_warns_when_still_hidden(self):
        session = standard_session()
        session.add("GET", MATTER_URL, make_response(200, HIDDEN_MATTER_XML))
        session.add("PATCH", MATTER_URL, make_response(204))
        with self.assertWarns(F2AccessWarning):
            client_with(session).update_matter(517886, title="Ny titel")


def _matter_element():
    return _xml.parse(MATTER_XML.encode())


if __name__ == "__main__":
    unittest.main()
