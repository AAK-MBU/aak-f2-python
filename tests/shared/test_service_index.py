import unittest
from http import HTTPStatus

from aak_f2.shared import F2HTTPError, F2LinkNotFoundError
from aak_f2.shared._service_index import (
    ServiceIndex,
    expand_template,
    parse_service_index,
)

REL = "http://cbrain.com/casefile/rel/"
BASE = "https://f2.example/rest/index"


class ParseTest(unittest.TestCase):
    def test_reads_href_and_resolves_relative_urls(self):
        links = parse_service_index(
            {
                f"{REL}case-by-id": {"href": "cases/{id}", "title": "Case"},
                f"{REL}oauth2-token": {"href": "https://auth.example/token"},
                "ignored": {"title": "no href"},
            },
            BASE,
        )
        case = links[f"{REL}case-by-id"]
        self.assertEqual(case.href, "https://f2.example/rest/cases/{id}")
        self.assertEqual(case.title, "Case")
        self.assertEqual(case.rel, f"{REL}case-by-id")
        token = links[f"{REL}oauth2-token"]
        self.assertEqual(token.href, "https://auth.example/token")
        self.assertIsNone(token.title)
        self.assertNotIn("ignored", links)


class ExpandTest(unittest.TestCase):
    def test_values_are_url_encoded(self):
        url = expand_template("https://x/{caseNumber}", {"caseNumber": "2022 - 60"})
        self.assertEqual(url, "https://x/2022%20-%2060")

    def test_none_becomes_empty(self):
        url = expand_template("https://x/{a}?p={b}", {"a": 1, "b": None})
        self.assertEqual(url, "https://x/1?p=")

    def test_missing_parameter(self):
        with self.assertRaises(ValueError):
            expand_template("https://x/{id}", {})


class ServiceIndexTest(unittest.TestCase):
    def test_loads_once_anonymously(self):
        calls = []

        def fetch(authenticated):
            calls.append(authenticated)
            return {f"{REL}case-by-id": {"href": "cases/{id}"}}

        index = ServiceIndex(fetch, BASE)
        index.href("case-by-id")
        url = index.expand("case-by-id", id=7)
        self.assertEqual(url, "https://f2.example/rest/cases/7")
        self.assertEqual(calls, [False])

    def test_missing_rel_reloads_with_authentication(self):
        calls = []

        def fetch(authenticated):
            calls.append(authenticated)
            data = {f"{REL}oauth2-token": {"href": "token"}}
            if authenticated:
                data[f"{REL}case-by-id"] = {"href": "cases/{id}"}
            return data

        index = ServiceIndex(fetch, BASE)
        self.assertEqual(index.href("case-by-id"), "https://f2.example/rest/cases/{id}")
        self.assertEqual(calls, [False, True])

    def test_unknown_rel_raises(self):
        index = ServiceIndex(lambda authenticated: {}, BASE)
        with self.assertRaises(F2LinkNotFoundError) as ctx:
            index.href("does-not-exist")
        self.assertEqual(ctx.exception.rel, f"{REL}does-not-exist")

    def test_anonymous_401_falls_back_to_authentication(self):
        calls = []

        def fetch(authenticated):
            calls.append(authenticated)
            if not authenticated:
                raise F2HTTPError(HTTPStatus.UNAUTHORIZED, "Unauthorized")
            return {f"{REL}case-by-id": {"href": "cases/{id}"}}

        index = ServiceIndex(fetch, BASE)
        index.href("case-by-id")
        self.assertEqual(calls, [False, True])

    def test_reload_forgets_cache(self):
        calls = []

        def fetch(authenticated):
            calls.append(authenticated)
            return {f"{REL}case-by-id": {"href": "cases/{id}"}}

        index = ServiceIndex(fetch, BASE)
        index.href("case-by-id")
        index.reload()
        index.href("case-by-id")
        self.assertEqual(calls, [False, False])


class LinksTest(unittest.TestCase):
    def test_authenticated_links_reload_once(self):
        calls = []

        def fetch(authenticated):
            calls.append(authenticated)
            data = {f"{REL}oauth2-token": {"href": "token"}}
            if authenticated:
                data[f"{REL}case-by-id"] = {"href": "cases/{id}"}
            return data

        index = ServiceIndex(fetch, BASE)
        self.assertEqual(list(index.links()), [f"{REL}oauth2-token"])
        self.assertIn(f"{REL}case-by-id", index.links(authenticated=True))
        index.links(authenticated=True)
        self.assertEqual(calls, [False, True])
