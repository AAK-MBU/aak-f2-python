"""Read-only tests against a real F2 installation.

Skipped unless the F2 settings are in the environment (see ``.env.example``).
``F2_LIVE_CASE_ID`` names an existing case to read; it is only read, never
changed.
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


@unittest.skipUnless(CONFIGURED, "F2 live settings are not set")
class LiveReadTest(unittest.TestCase):
    client: F2Client

    @classmethod
    def setUpClass(cls):
        cls.client = F2Client.from_env()

    def test_health_check(self):
        self.assertTrue(self.client.health_check())

    @unittest.skipUnless(CASE_ID, "F2_LIVE_CASE_ID is not set")
    def test_read_case_matters_and_documents(self):
        client = self.client
        case = client.get_case(CASE_ID)
        self.assertEqual(str(case.id), CASE_ID)
        self.assertEqual(client.get_case_by_number(case.case_number).id, case.id)

        structure = client.get_case_structure(case)
        matters = client.list_matters(case)
        self.assertEqual(len(matters), len(structure.matters))
        if not matters:
            self.skipTest("The case has no matters")

        matter = client.get_matter(matters[0].id)
        documents = client.list_documents(matter)
        if not documents:
            self.skipTest("The first matter has no documents")

        document = client.get_document(documents[0].id)
        content = client.get_content(document)
        self.assertGreater(len(content), 0)
        pdf = client.get_pdf(document)
        if pdf is not None:
            self.assertTrue(pdf.startswith(b"%PDF"))
