"""Read-only search and party lookup tests against a real F2 installation.

Skipped unless the F2 settings are in the environment (see ``.env.example``).
Each test also needs its own ``F2_LIVE_*`` variable; nothing is changed in F2.
"""

import os
import unittest

from aak_f2.shared import F2Client

REQUIRED = (
    "F2_SERVICE_INDEX_URL",
    "F2_CLIENT_ID",
    "F2_CLIENT_SECRET",
    "F2_USERNAME",
)
CONFIGURED = all(os.environ.get(name) for name in REQUIRED)
CASE_ID = os.environ.get("F2_LIVE_CASE_ID")
CPR = os.environ.get("F2_LIVE_CPR")
LOGIN = os.environ.get("F2_LIVE_LOGIN")


@unittest.skipUnless(CONFIGURED, "F2 live settings are not set")
class LiveSearchTest(unittest.TestCase):
    client: F2Client

    @classmethod
    def setUpClass(cls):
        cls.client = F2Client.from_env()

    @unittest.skipUnless(CASE_ID, "F2_LIVE_CASE_ID is not set")
    def test_search_cases_by_case_number_and_id(self):
        case = self.client.get_case(CASE_ID)
        by_number = self.client.search_cases(case_number=case.case_number)
        self.assertIn(case.id, [hit.id for hit in by_number])
        by_id = self.client.search_cases(case_id=case.id)
        self.assertEqual([hit.id for hit in by_id], [case.id])

    @unittest.skipUnless(CASE_ID, "F2_LIVE_CASE_ID is not set")
    def test_search_matters_by_case_number(self):
        case = self.client.get_case(CASE_ID)
        hits = self.client.search_matters(case_number=case.case_number)
        matters = self.client.list_matters(case)
        self.assertEqual(
            sorted(hit.id for hit in hits), sorted(int(m.id) for m in matters)
        )

    @unittest.skipUnless(CPR, "F2_LIVE_CPR is not set")
    def test_search_cases_by_cpr(self):
        hits = self.client.search_cases(cpr_number=CPR)
        self.assertGreater(len(hits), 0)

    @unittest.skipUnless(CPR, "F2_LIVE_CPR is not set")
    def test_party_by_cpr(self):
        party = self.client.get_party_by_cpr(CPR)
        self.assertIsNotNone(party.id)

    @unittest.skipUnless(LOGIN, "F2_LIVE_LOGIN is not set")
    def test_party_by_login(self):
        party = self.client.get_party_by_login(LOGIN)
        self.assertEqual(party.kind, "User")
