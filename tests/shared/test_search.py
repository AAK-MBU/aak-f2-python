import unittest
from datetime import datetime

from aak_f2.shared import F2Client
from tests.fakes import (
    BASE,
    INDEX_URL,
    REL,
    SERVICE_INDEX,
    make_config,
    make_response,
    standard_session,
)
from tests.fixtures import CASE_SEARCH_CSV, MATTER_SEARCH_CSV

CASE_SEARCH_URL = f"{BASE}/search/cases"
MATTER_SEARCH_URL = f"{BASE}/search/matters"


def csv_response(text, content_type="text/csv; charset=utf-8", encoding="utf-8"):
    return make_response(200, text.encode(encoding), content_type=content_type)


class CaseSearchTest(unittest.TestCase):
    def test_sends_given_criteria_as_query_parameters(self):
        session = standard_session()
        session.add("GET", CASE_SEARCH_URL, csv_response(CASE_SEARCH_CSV))
        F2Client(make_config(), session=session).search_cases(
            cpr_number="311299-1234", title=None
        )
        (call,) = session.calls_to("GET", CASE_SEARCH_URL)
        self.assertEqual(call["params"], {"cprNumber": "311299-1234"})
        self.assertEqual(call["headers"]["Accept"], "text/csv")

    def test_parses_hits(self):
        session = standard_session()
        session.add("GET", CASE_SEARCH_URL, csv_response(CASE_SEARCH_CSV))
        (hit,) = F2Client(make_config(), session=session).search_cases(
            case_number="2022 - 1172"
        )
        self.assertEqual(hit.id, 279666)
        self.assertEqual(hit.case_number, "2022 - 1172")
        self.assertEqual(hit.title, "Sag om Søren Ærø")
        self.assertEqual(hit.cpr_number, "311299-1234")
        self.assertEqual(hit.external_id, "P2103568")
        self.assertEqual(hit.created, datetime(2022, 3, 29, 11, 0, 58))
        self.assertEqual(hit.url, "https://f2.example/rest/cases/279666")
        self.assertEqual(hit.raw["Id"], "279666")

    def test_empty_result(self):
        session = standard_session()
        header = CASE_SEARCH_CSV.split("\r\n")[0] + "\r\n"
        session.add("GET", CASE_SEARCH_URL, csv_response(header))
        client = F2Client(make_config(), session=session)
        self.assertEqual(client.search_cases(cpr_number="010101-0101"), [])

    def test_requires_a_criterion(self):
        client = F2Client(make_config(), session=standard_session())
        with self.assertRaises(ValueError):
            client.search_cases()
        with self.assertRaises(ValueError):
            client.search_cases(title="")

    def test_utf8_without_charset_and_with_bom(self):
        session = standard_session()
        session.add(
            "GET",
            CASE_SEARCH_URL,
            csv_response(CASE_SEARCH_CSV, "text/csv", encoding="utf-8-sig"),
        )
        (hit,) = F2Client(make_config(), session=session).search_cases(case_id=1)
        self.assertEqual(hit.id, 279666)
        self.assertEqual(hit.title, "Sag om Søren Ærø")

    def test_declared_charset_is_used(self):
        session = standard_session()
        session.add(
            "GET",
            CASE_SEARCH_URL,
            csv_response(
                CASE_SEARCH_CSV, "text/csv; charset=iso-8859-1", encoding="latin-1"
            ),
        )
        (hit,) = F2Client(make_config(), session=session).search_cases(case_id=1)
        self.assertEqual(hit.title, "Sag om Søren Ærø")

    def test_search_published_as_url_template(self):
        session = standard_session()
        index = dict(SERVICE_INDEX)
        index[f"{REL}case-search-filter"] = {
            "href": f"{BASE}/search/cases?cprNumber={{cprNumber}}&title={{title}}"
        }
        session.routes[("GET", INDEX_URL)] = [make_response(json_body=index)]
        url = f"{BASE}/search/cases?cprNumber=311299-1234&title="
        session.add("GET", url, csv_response(CASE_SEARCH_CSV))
        F2Client(make_config(), session=session).search_cases(
            cpr_number="311299-1234", external_id="X"
        )
        (call,) = session.calls_to("GET", url)
        self.assertEqual(call["params"], {"externalId": "X"})


class MatterSearchTest(unittest.TestCase):
    def test_parses_hits(self):
        session = standard_session()
        session.add("GET", MATTER_SEARCH_URL, csv_response(MATTER_SEARCH_CSV))
        (hit,) = F2Client(make_config(), session=session).search_matters(
            case_number="2022 - 1170"
        )
        (call,) = session.calls_to("GET", MATTER_SEARCH_URL)
        self.assertEqual(call["params"], {"caseNumber": "2022 - 1170"})
        self.assertEqual(hit.id, 279655)
        self.assertEqual(hit.matter_number, 13249)
        self.assertEqual(hit.type, "Inbound")
        self.assertTrue(hit.archived)
        self.assertIsNone(hit.cpr_number)
        self.assertIsNone(hit.deadline)
        self.assertIsNone(hit.case_title)

    def test_requires_a_criterion(self):
        client = F2Client(make_config(), session=standard_session())
        with self.assertRaises(ValueError):
            client.search_matters()
