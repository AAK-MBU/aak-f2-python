import unittest

import requests

from aak_f2.shared import (
    F2AccessDeniedError,
    F2ConnectionError,
    F2HTTPError,
    F2NotFoundError,
)
from aak_f2.shared._http import Connection
from tests.fakes import (
    BASE,
    INDEX_URL,
    TOKEN_URL,
    make_config,
    make_response,
    standard_session,
    token_response,
)
from tests.fixtures import ERROR_XML

URL = f"{BASE}/cases/1"


def connection(session, sleeps=None):
    return Connection(
        make_config(),
        session=session,
        sleep=(sleeps.append if sleeps is not None else lambda _: None),
    )


class RequestTest(unittest.TestCase):
    def test_sends_bearer_token_and_accept(self):
        session = standard_session()
        session.add("GET", URL, make_response(200, "<Case/>"))
        connection(session).get_xml(URL)

        (call,) = session.calls_to("GET", URL)
        self.assertEqual(call["headers"]["Authorization"], "Bearer token-1")
        self.assertIn("application/vnd.cbrain.casefile+xml", call["headers"]["Accept"])

    def test_service_index_is_fetched_without_token(self):
        session = standard_session()
        session.add("GET", URL, make_response(200, "<Case/>"))
        connection(session).get_xml(URL)

        (call,) = session.calls_to("GET", INDEX_URL)
        self.assertNotIn("Authorization", call["headers"])
        self.assertEqual(call["headers"]["Accept"], "application/json")

    def test_relative_urls_resolve_against_index(self):
        session = standard_session()
        session.add("GET", URL, make_response(200, "<Case/>"))
        connection(session).get_xml("cases/1")
        self.assertEqual(len(session.calls_to("GET", URL)), 1)

    def test_retries_503_with_backoff(self):
        session = standard_session()
        session.add(
            "GET",
            URL,
            make_response(503),
            make_response(503),
            make_response(200, "<Case/>"),
        )
        sleeps = []
        connection(session, sleeps).get_xml(URL)
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_gives_up_after_max_retries(self):
        session = standard_session()
        session.add("GET", URL, make_response(423, ERROR_XML))
        sleeps = []
        with self.assertRaises(F2HTTPError) as ctx:
            connection(session, sleeps).get_xml(URL)
        self.assertEqual(ctx.exception.status_code, 423)
        self.assertEqual(len(sleeps), 3)
        self.assertEqual(len(session.calls_to("GET", URL)), 4)

    def test_error_payload_is_parsed(self):
        session = standard_session()
        session.add("GET", URL, make_response(409, ERROR_XML))
        with self.assertRaises(F2HTTPError) as ctx:
            connection(session).get_xml(URL)
        error = ctx.exception
        self.assertEqual(error.status_code, 409)
        self.assertEqual(error.message, "The case is closed.")
        self.assertEqual(error.details, "Case 1046444 is closed.")
        self.assertEqual(error.reason_code, "DossierCaseClosed")

    def test_json_error_payload_is_parsed(self):
        session = standard_session()
        session.add(
            "GET",
            URL,
            make_response(
                404,
                json_body={"Message": "Not found", "ReasonCode": "DossierNotFound"},
            ),
        )
        with self.assertRaises(F2HTTPError) as ctx:
            connection(session).get_xml(URL)
        self.assertEqual(ctx.exception.message, "Not found")
        self.assertEqual(ctx.exception.reason_code, "DossierNotFound")

    def test_404_raises_not_found(self):
        session = standard_session()
        session.add(
            "GET",
            URL,
            make_response(404, json_body={"Message": "Case with ID 1 not found."}),
        )
        with self.assertRaises(F2NotFoundError) as ctx:
            connection(session).get_xml(URL)
        self.assertIsInstance(ctx.exception, F2HTTPError)
        self.assertEqual(ctx.exception.message, "Case with ID 1 not found.")

    def test_403_raises_access_denied(self):
        session = standard_session()
        session.add(
            "GET",
            URL,
            make_response(403, json_body={"Message": "Access to ressource denied."}),
        )
        with self.assertRaises(F2AccessDeniedError) as ctx:
            connection(session).get_xml(URL)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_other_errors_are_plain_http_errors(self):
        session = standard_session()
        session.add("GET", URL, make_response(409, ERROR_XML))
        with self.assertRaises(F2HTTPError) as ctx:
            connection(session).get_xml(URL)
        self.assertIs(type(ctx.exception), F2HTTPError)

    def test_401_renews_token_once(self):
        session = standard_session()
        session.routes[("POST", TOKEN_URL)] = [
            token_response("old", "r1"),
            token_response("new"),
        ]
        session.add("GET", URL, make_response(401), make_response(200, "<Case/>"))
        connection(session).get_xml(URL)

        auths = [c["headers"]["Authorization"] for c in session.calls_to("GET", URL)]
        self.assertEqual(auths, ["Bearer old", "Bearer new"])

    def test_repeated_401_raises(self):
        session = standard_session()
        session.add("GET", URL, make_response(401))
        with self.assertRaises(F2HTTPError) as ctx:
            connection(session).get_xml(URL)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(len(session.calls_to("GET", URL)), 2)

    def test_network_error_on_get_is_retried(self):
        session = standard_session()
        session.add(
            "GET",
            URL,
            requests.ConnectionError("reset"),
            make_response(200, "<Case/>"),
        )
        connection(session).get_xml(URL)
        self.assertEqual(len(session.calls_to("GET", URL)), 2)

    def test_network_error_on_post_is_not_retried(self):
        session = standard_session()
        session.add("POST", URL, requests.ConnectionError("reset"))
        with self.assertRaises(F2ConnectionError):
            connection(session).request("POST", URL)
        self.assertEqual(len(session.calls_to("POST", URL)), 1)
