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

CASES_URL = f"{BASE}/searches/cases"
MATTERS_URL = f"{BASE}/searches/matters"

ATOM_FEED = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Search</title>
  <entry>
    <id>urn:f2:case:279666</id>
    <title>Sag om Søren Ærø</title>
    <updated>2022-03-29T11:00:58</updated>
    <link rel="alternate" href="https://f2.example/rest/cases/279666" />
    <summary>2022 - 1172</summary>
  </entry>
  <entry>
    <id>urn:f2:case:279667</id>
    <title>Anden sag</title>
    <link href="https://f2.example/rest/cases/279667?x=1" />
  </entry>
</feed>
"""


def client_with(session):
    return F2Client(make_config(), session=session)


class FulltextCaseSearchTest(unittest.TestCase):
    def test_sends_q_and_count_and_parses_csv(self):
        session = standard_session()
        session.add(
            "GET",
            CASES_URL,
            make_response(200, CASE_SEARCH_CSV, content_type="text/csv"),
        )
        (hit,) = client_with(session).fulltext_search_cases("UV", count=1000)
        (call,) = session.calls_to("GET", CASES_URL)
        self.assertEqual(call["params"], {"q": "UV", "count": "1000"})
        self.assertTrue(call["headers"]["Accept"].startswith("application/atom+xml"))
        self.assertEqual(hit.id, 279666)
        self.assertEqual(hit.case_number, "2022 - 1172")

    def test_default_count(self):
        session = standard_session()
        session.add(
            "GET", CASES_URL, make_response(200, "Id\r\n", content_type="text/csv")
        )
        self.assertEqual(client_with(session).fulltext_search_cases("UV"), [])
        (call,) = session.calls_to("GET", CASES_URL)
        self.assertEqual(call["params"]["count"], "100")

    def test_parses_atom(self):
        session = standard_session()
        session.add(
            "GET",
            CASES_URL,
            make_response(200, ATOM_FEED.encode(), content_type="application/atom+xml"),
        )
        first, second = client_with(session).fulltext_search_cases("Søren")
        self.assertEqual(first.id, 279666)
        self.assertEqual(first.title, "Sag om Søren Ærø")
        self.assertEqual(first.updated, datetime(2022, 3, 29, 11, 0, 58))
        self.assertEqual(first.url, "https://f2.example/rest/cases/279666")
        self.assertEqual(first.raw["summary"], "2022 - 1172")
        self.assertEqual(first.raw["AtomId"], "urn:f2:case:279666")
        self.assertEqual(second.id, 279667)

    def test_parses_json(self):
        session = standard_session()
        session.add(
            "GET",
            CASES_URL,
            make_response(json_body=[{"Id": 5, "Title": "UV-sag", "CaseNumber": None}]),
        )
        (hit,) = client_with(session).fulltext_search_cases("UV")
        self.assertEqual(hit.id, 5)
        self.assertEqual(hit.title, "UV-sag")
        self.assertIsNone(hit.case_number)

    def test_fills_opensearch_template(self):
        session = standard_session()
        index = dict(SERVICE_INDEX)
        index[f"{REL}case-search"] = {
            "href": f"{BASE}/searches/cases?q={{searchTerms}}&count={{count}}"
        }
        session.routes[("GET", INDEX_URL)] = [make_response(json_body=index)]
        url = f"{BASE}/searches/cases?q=UV%20sag&count=5"
        session.add("GET", url, make_response(200, "Id\r\n", content_type="text/csv"))
        client_with(session).fulltext_search_cases("UV sag", count=5)
        (call,) = session.calls_to("GET", url)
        self.assertIsNone(call["params"])

    def test_validates_arguments(self):
        client = client_with(standard_session())
        with self.assertRaises(ValueError):
            client.fulltext_search_cases("  ")
        with self.assertRaises(ValueError):
            client.fulltext_search_cases("UV", count=0)


class AtomDetectionTest(unittest.TestCase):
    def test_xml_body_without_xml_content_type_is_read_as_atom(self):
        session = standard_session()
        session.add(
            "GET",
            CASES_URL,
            make_response(200, ATOM_FEED.encode(), content_type="text/plain"),
        )
        hits = client_with(session).fulltext_search_cases("UV")
        self.assertEqual([hit.id for hit in hits], [279666, 279667])


class FulltextMatterSearchTest(unittest.TestCase):
    def test_parses_csv(self):
        session = standard_session()
        session.add(
            "GET",
            MATTERS_URL,
            make_response(200, MATTER_SEARCH_CSV, content_type="text/csv"),
        )
        hits = client_with(session).fulltext_search_matters("UV", count=250)
        (call,) = session.calls_to("GET", MATTERS_URL)
        self.assertEqual(call["params"], {"q": "UV", "count": "250"})
        self.assertEqual(hits[0].id, 279655)
