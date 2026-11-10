"""Live tests that CREATE data in a real F2 installation.

Skipped unless ``F2_LIVE_WRITE=1`` is set together with the F2 settings (see
``.env.example``). Only run them against a test installation: every run
creates a case with two matters and a document, which are not deleted.
"""

import os
import unittest
import warnings
from datetime import datetime

from aak_f2.mbu import F2Client as MbuF2Client
from aak_f2.shared import F2AccessWarning, F2Client

REQUIRED = (
    "F2_SERVICE_INDEX_URL",
    "F2_CLIENT_ID",
    "F2_CLIENT_SECRET",
    "F2_USERNAME",
)
CONFIGURED = all(os.environ.get(name) for name in REQUIRED)
WRITE = os.environ.get("F2_LIVE_WRITE") == "1"
LOGIN = os.environ.get("F2_LIVE_LOGIN")
KLE = os.environ.get("F2_LIVE_KLE")
FACET = os.environ.get("F2_LIVE_FACET")


@unittest.skipUnless(CONFIGURED and WRITE, "F2_LIVE_WRITE=1 is not set")
class LiveCreateTest(unittest.TestCase):
    def test_create_case_matter_and_document(self):
        client = F2Client.from_env()
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        case = client.create_case(
            f"aak-f2 live test {stamp}",
            journal_plan_code=KLE or None,
            process_instruction_code=FACET or None,
            responsible=LOGIN or None,
        )
        print(f"\ncase: {case.id} {case.case_number}")
        self.assertIsNotNone(case.id)
        if KLE:
            self.assertEqual(case.journal_plan.abbreviation, KLE)
        if FACET:
            self.assertEqual(case.process_instruction.abbreviation, FACET)

        with warnings.catch_warnings():
            warnings.simplefilter("error", F2AccessWarning)
            matter = client.create_matter(case, "Akt for alle", access_level="All")
        print(f"matter: {matter.id} AccessLevel={matter.access_level}")
        self.assertEqual(matter.access_level, "All")

        document = client.create_document(
            matter, "Hej fra aak-f2 æøå".encode(), filename="hilsen.txt"
        )
        print(f"document: {document.id} {document.title}")
        self.assertEqual(client.get_content(document.id), "Hej fra aak-f2 æøå".encode())

        updated = client.update_matter(matter, title="Akt for alle (omdøbt)")
        self.assertEqual(updated.title, "Akt for alle (omdøbt)")

        renamed = client.update_case(case, title=f"{case.title} (omdøbt)")
        self.assertEqual(renamed.title, f"{case.title} (omdøbt)")

    @unittest.skipUnless(LOGIN, "F2_LIVE_LOGIN is not set")
    def test_mbu_upload_document_with_involved_parties(self):
        client = MbuF2Client.from_env()
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        case = client.create_case(f"aak-f2 live upload {stamp}", responsible=LOGIN)
        with warnings.catch_warnings():
            warnings.simplefilter("error", F2AccessWarning)
            result = client.upload_document(
                case_id=case.id,
                filename="Upload.txt",
                data=b"upload",
                access_level="Involved",
                involved_parties=[LOGIN],
            )
        matter = client.get_matter(result.matter_id)
        print(f"\ncase {case.id}: matter {matter.id} document {result.document_id}")
        self.assertEqual(matter.access_level, "Involved")
        self.assertTrue(matter.involved_parties)
