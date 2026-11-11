import unittest

from aak_f2.shared import Case, F2Client, F2HTTPError, Link
from tests.fakes import BASE, make_config, make_response, standard_session
from tests.fixtures import CASE_XML

CASE_URL = f"{BASE}/cases/1046444"
EXTENSION_URL = f"{CASE_URL}/update-extension-data"


def client_with(session):
    return F2Client(make_config(), session=session)


class RequestTest(unittest.TestCase):
    def test_posts_json_to_a_link_with_token(self):
        session = standard_session()
        session.add("POST", EXTENSION_URL, make_response(204))
        link = Link(rel="x", href=EXTENSION_URL)
        response = client_with(session).request(
            "post", link, json={"Fields": [{"Name": "sagstype", "Value": "X"}]}
        )
        self.assertEqual(response.status_code, 204)
        (call,) = session.calls_to("POST", EXTENSION_URL)
        self.assertEqual(call["json"], {"Fields": [{"Name": "sagstype", "Value": "X"}]})
        self.assertEqual(call["headers"]["Accept"], "*/*")
        self.assertTrue(call["headers"]["Authorization"].startswith("Bearer "))

    def test_fills_url_template_and_passes_params(self):
        session = standard_session()
        session.add("GET", f"{BASE}/custom-queries/q%201", make_response(200, "a,b"))
        client_with(session).request(
            "GET",
            f"{BASE}/custom-queries/{{name}}",
            template_params={"name": "q 1"},
            params={"P1": "v"},
            accept="text/csv",
            headers={"X-Test": "1"},
        )
        (call,) = session.calls_to("GET", f"{BASE}/custom-queries/q%201")
        self.assertEqual(call["params"], {"P1": "v"})
        self.assertEqual(call["headers"]["Accept"], "text/csv")
        self.assertEqual(call["headers"]["X-Test"], "1")

    def test_relative_href_is_resolved_against_the_service_index(self):
        session = standard_session()
        session.add("GET", CASE_URL, make_response(200, CASE_XML))
        client_with(session).request("GET", "cases/1046444")
        self.assertEqual(len(session.calls_to("GET", CASE_URL)), 1)

    def test_missing_template_value(self):
        session = standard_session()
        with self.assertRaises(ValueError):
            client_with(session).request("GET", f"{BASE}/cases/{{id}}")

    def test_error_status_raises(self):
        session = standard_session()
        session.add("GET", CASE_URL, make_response(400, json_body={"Message": "Bad"}))
        with self.assertRaises(F2HTTPError):
            client_with(session).request("GET", CASE_URL)


class GetXmlTest(unittest.TestCase):
    def test_returns_root_element_from_template(self):
        session = standard_session()
        session.add("GET", CASE_URL, make_response(200, CASE_XML))
        element = client_with(session).get_xml(f"{BASE}/cases/{{id}}", id=1046444)
        self.assertEqual(Case.from_element(element).id, 1046444)
        (call,) = session.calls_to("GET", CASE_URL)
        self.assertIn("application/vnd.cbrain.casefile+xml", call["headers"]["Accept"])


if __name__ == "__main__":
    unittest.main()
