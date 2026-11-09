import unittest

from aak_f2.shared import F2HTTPError
from aak_f2.shared._auth import TokenManager
from tests.fakes import (
    TOKEN_URL,
    FakeSession,
    make_config,
    make_response,
    token_response,
)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def manager(session, clock=None, **config):
    return TokenManager(
        session, make_config(**config), lambda: TOKEN_URL, clock or Clock()
    )


class TokenManagerTest(unittest.TestCase):
    def test_password_grant(self):
        session = FakeSession()
        session.add("POST", TOKEN_URL, token_response("abc"))
        tokens = manager(session, password="pw", organization_partyno=99)

        self.assertEqual(tokens.access_token(), "abc")

        (call,) = session.calls_to("POST", TOKEN_URL)
        self.assertEqual(call["auth"], ("client", "secret"))
        self.assertEqual(
            call["data"],
            {
                "grant_type": "password",
                "username": "robot",
                "password": "pw",
                "organization_partyno": "99",
            },
        )

    def test_password_is_optional(self):
        session = FakeSession()
        session.add("POST", TOKEN_URL, token_response())
        manager(session).access_token()
        (call,) = session.calls_to("POST", TOKEN_URL)
        self.assertNotIn("password", call["data"])

    def test_token_is_cached(self):
        session = FakeSession()
        session.add("POST", TOKEN_URL, token_response())
        tokens = manager(session)
        tokens.access_token()
        tokens.access_token()
        self.assertEqual(len(session.calls_to("POST", TOKEN_URL)), 1)

    def test_expired_token_is_refreshed(self):
        session = FakeSession()
        session.add(
            "POST", TOKEN_URL, token_response("first", "r1"), token_response("second")
        )
        clock = Clock()
        tokens = manager(session, clock)
        tokens.access_token()
        clock.now += 3600

        self.assertEqual(tokens.access_token(), "second")
        second_call = session.calls_to("POST", TOKEN_URL)[1]
        self.assertEqual(
            second_call["data"], {"grant_type": "refresh_token", "refresh_token": "r1"}
        )

    def test_failed_refresh_logs_in_again(self):
        session = FakeSession()
        session.add(
            "POST",
            TOKEN_URL,
            token_response("first", "r1"),
            make_response(400, json_body={"error": "invalid_grant"}),
            token_response("third"),
        )
        tokens = manager(session)
        tokens.access_token()
        tokens.invalidate()

        self.assertEqual(tokens.access_token(), "third")
        grants = [c["data"]["grant_type"] for c in session.calls_to("POST", TOKEN_URL)]
        self.assertEqual(grants, ["password", "refresh_token", "password"])

    def test_rejected_login_raises(self):
        session = FakeSession()
        session.add(
            "POST",
            TOKEN_URL,
            make_response(
                401,
                json_body={
                    "error": "invalid_client",
                    "error_description": "Unknown client",
                },
            ),
        )
        with self.assertRaises(F2HTTPError) as ctx:
            manager(session).access_token()
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.message, "Unknown client")
