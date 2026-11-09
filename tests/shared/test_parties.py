import unittest

from aak_f2.shared import F2Client, F2NotFoundError
from tests.fakes import BASE, make_config, make_response, standard_session
from tests.fixtures import EXTERNAL_PARTY_XML, USER_XML

CPR_URL = f"{BASE}/parties/by-cvrcpr/311299-1234?cvr_p="


def client_with(session):
    return F2Client(make_config(), session=session)


class PartyTest(unittest.TestCase):
    def test_get_party_by_cpr(self):
        session = standard_session()
        session.add("GET", CPR_URL, make_response(200, EXTERNAL_PARTY_XML))
        party = client_with(session).get_party_by_cpr("311299-1234")
        self.assertEqual(party.kind, "External")
        self.assertEqual(party.id, 400775)
        self.assertEqual(party.name, "Søren Ærø")
        self.assertEqual(party.party_number, 39938)
        self.assertEqual(party.cvrcpr, "311299-1234")
        self.assertEqual(party.email, "soren@example.dk")
        self.assertFalse(party.protected_address)
        self.assertIsNone(party.address2)
        self.assertEqual(party.organization.name, "Aarhus Kommune")

    def test_cvr_p_is_filled_into_the_template(self):
        session = standard_session()
        url = f"{BASE}/parties/by-cvrcpr/12345678?cvr_p=1000"
        session.add("GET", url, make_response(200, EXTERNAL_PARTY_XML))
        client_with(session).get_party_by_cpr("12345678", "1000")
        self.assertEqual(len(session.calls_to("GET", url)), 1)

    def test_unknown_cpr_raises_not_found(self):
        session = standard_session()
        session.add("GET", CPR_URL, make_response(404, json_body={"Message": "No"}))
        with self.assertRaises(F2NotFoundError):
            client_with(session).get_party_by_cpr("311299-1234")

    def test_get_party_by_login(self):
        session = standard_session()
        session.add(
            "GET", f"{BASE}/parties/by-login/AZ12345", make_response(200, USER_XML)
        )
        party = client_with(session).get_party_by_login("AZ12345")
        self.assertEqual(party.kind, "User")
        self.assertEqual(party.initials, "AZ12345")

    def test_get_party(self):
        session = standard_session()
        session.add("GET", f"{BASE}/parties/400776", make_response(200, USER_XML))
        self.assertEqual(client_with(session).get_party(400776).name, "The Boss")
