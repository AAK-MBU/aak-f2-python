import unittest
from datetime import datetime

from aak_f2.shared import F2Client, F2Error
from tests.fakes import (
    BASE,
    INDEX_URL,
    REL,
    SERVICE_INDEX,
    make_config,
    make_response,
    opensearch_description,
    standard_session,
)
from tests.fixtures import CASE_SEARCH_CSV, MATTER_SEARCH_CSV

CASES_DESCRIPTION_URL = f"{BASE}/opensearch/cases"


def cases_url(q, count=100):
    return f"{BASE}/searches/cases?q={q}&count={count}"


def matters_url(q, count=100):
    return f"{BASE}/searches/matters?q={q}&count={count}"


def atom_response(body=None, content_type="application/atom+xml"):
    return make_response(200, (body or ATOM_FEED).encode(), content_type=content_type)


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
    def test_fills_template_from_opensearch_description(self):
        session = standard_session()
        url = cases_url("UV%20sag", 1000)
        session.add("GET", url, atom_response())
        client_with(session).fulltext_search_cases("UV sag", count=1000)
        (description,) = session.calls_to("GET", CASES_DESCRIPTION_URL)
        self.assertIn(
            "application/opensearchdescription+xml", description["headers"]["Accept"]
        )
        (call,) = session.calls_to("GET", url)
        self.assertIsNone(call["params"])
        self.assertTrue(call["headers"]["Accept"].startswith("application/atom+xml"))

    def test_description_is_read_once(self):
        session = standard_session()
        session.add("GET", cases_url("UV"), atom_response())
        client = client_with(session)
        client.fulltext_search_cases("UV")
        client.fulltext_search_cases("UV")
        self.assertEqual(len(session.calls_to("GET", CASES_DESCRIPTION_URL)), 1)
        self.assertEqual(len(session.calls_to("GET", cases_url("UV"))), 2)

    def test_default_count(self):
        session = standard_session()
        session.add("GET", cases_url("UV", 100), atom_response("<feed/>"))
        self.assertEqual(client_with(session).fulltext_search_cases("UV"), [])

    def test_parses_atom(self):
        session = standard_session()
        session.add("GET", cases_url("S%C3%B8ren"), atom_response())
        first, second = client_with(session).fulltext_search_cases("Søren")
        self.assertEqual(first.id, 279666)
        self.assertEqual(first.title, "Sag om Søren Ærø")
        self.assertEqual(first.updated, datetime(2022, 3, 29, 11, 0, 58))
        self.assertEqual(first.url, "https://f2.example/rest/cases/279666")
        self.assertEqual(first.raw["summary"], "2022 - 1172")
        self.assertEqual(first.raw["AtomId"], "urn:f2:case:279666")
        self.assertEqual(second.id, 279667)

    def test_xml_body_without_xml_content_type_is_read_as_atom(self):
        session = standard_session()
        session.add("GET", cases_url("UV"), atom_response(content_type="text/plain"))
        hits = client_with(session).fulltext_search_cases("UV")
        self.assertEqual([hit.id for hit in hits], [279666, 279667])

    def test_parses_csv_and_json(self):
        session = standard_session()
        session.add(
            "GET",
            cases_url("a"),
            make_response(200, CASE_SEARCH_CSV, content_type="text/csv"),
        )
        session.add(
            "GET",
            cases_url("b"),
            make_response(json_body=[{"Id": 5, "Title": "UV-sag"}]),
        )
        client = client_with(session)
        self.assertEqual(
            client.fulltext_search_cases("a")[0].case_number, "2022 - 1172"
        )
        self.assertEqual(client.fulltext_search_cases("b")[0].id, 5)

    def test_validates_arguments(self):
        client = client_with(standard_session())
        with self.assertRaises(ValueError):
            client.fulltext_search_cases("  ")
        with self.assertRaises(ValueError):
            client.fulltext_search_cases("UV", count=0)


class OpenSearchTemplateTest(unittest.TestCase):
    def test_returns_template(self):
        client = client_with(standard_session())
        self.assertEqual(
            client.opensearch_template("case-search"),
            f"{BASE}/searches/cases?q={{searchTerms}}&count={{count}}",
        )

    def test_relative_template_and_optional_parameters(self):
        session = standard_session()
        session.routes[("GET", CASES_DESCRIPTION_URL)] = [
            opensearch_description(
                "../searches/cases?q={searchTerms}&start={startIndex?}"
            )
        ]
        url = f"{BASE}/searches/cases?q=UV&start="
        session.add("GET", url, atom_response("<feed/>"))
        client = client_with(session)
        client.fulltext_search_cases("UV")
        self.assertEqual(len(session.calls_to("GET", url)), 1)

    def test_template_in_service_index_is_used_directly(self):
        session = standard_session()
        index = dict(SERVICE_INDEX)
        index[f"{REL}case-search"] = {"href": cases_url("{searchTerms}", "{count}")}
        session.routes[("GET", INDEX_URL)] = [make_response(json_body=index)]
        session.add("GET", cases_url("UV", 5), atom_response("<feed/>"))
        client_with(session).fulltext_search_cases("UV", count=5)
        self.assertEqual(session.calls_to("GET", CASES_DESCRIPTION_URL), [])

    def test_not_an_opensearch_description(self):
        session = standard_session()
        session.routes[("GET", CASES_DESCRIPTION_URL)] = [atom_response("<feed/>")]
        with self.assertRaises(F2Error):
            client_with(session).fulltext_search_cases("UV")


class FulltextMatterSearchTest(unittest.TestCase):
    def test_parses_csv(self):
        session = standard_session()
        session.add(
            "GET",
            matters_url("UV", 250),
            make_response(200, MATTER_SEARCH_CSV, content_type="text/csv"),
        )
        hits = client_with(session).fulltext_search_matters("UV", count=250)
        self.assertEqual(hits[0].id, 279655)
