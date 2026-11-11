import unittest

from aak_f2.shared import Case, F2Client, F2LinkNotFoundError, Matter, _xml
from tests.fakes import BASE, make_config, make_response, standard_session
from tests.fixtures import CASE_XML, EXTENSIONS_XML, MATTER_XML

CASE_EXTENSIONS = f"{BASE}/cases/1046444/extension-data"
CASE_UPDATE = f"{BASE}/cases/1046444/update-extension-data"
MATTER_UPDATE = f"{BASE}/matters/517886/update-extension-data"


def case():
    return Case.from_element(_xml.parse(CASE_XML.encode()))


def matter():
    return Matter.from_element(_xml.parse(MATTER_XML.encode()))


def client_with(session):
    return F2Client(make_config(), session=session)


class GetExtensionDataTest(unittest.TestCase):
    def test_parses_extensions(self):
        session = standard_session()
        session.add("GET", CASE_EXTENSIONS, make_response(200, EXTENSIONS_XML))
        extensions = client_with(session).get_extension_data(case())
        self.assertEqual(
            [e.process_name for e in extensions], ["Abc", "CaseExtensionData", "Xyz"]
        )
        (size,) = list(extensions[0].data)
        self.assertEqual(_xml.local_name(size.tag), "Size")
        self.assertEqual(size.text, "10")
        self.assertEqual(extensions[0].fields, {})
        self.assertEqual(extensions[1].fields, {"Sagstype": "Borger", "Tom": None})

    def test_extension_fields_are_merged(self):
        session = standard_session()
        session.add("GET", CASE_EXTENSIONS, make_response(200, EXTENSIONS_XML))
        fields = client_with(session).get_extension_fields(case())
        self.assertEqual(fields, {"Sagstype": "Borger", "Tom": None})

    def test_missing_link(self):
        bare = Case(id=1)
        with self.assertRaises(F2LinkNotFoundError):
            client_with(standard_session()).get_extension_data(bare)


class SetExtensionFieldsTest(unittest.TestCase):
    def test_case_fields_are_posted_as_json(self):
        session = standard_session()
        session.add("POST", CASE_UPDATE, make_response(200))
        client_with(session).set_extension_fields(
            case(), {"Sagstype": "Borger", "Andet": None}
        )
        (call,) = session.calls_to("POST", CASE_UPDATE)
        self.assertEqual(
            call["json"],
            {
                "Fields": [
                    {"Name": "Sagstype", "Value": "Borger"},
                    {"Name": "Andet", "Value": None},
                ]
            },
        )

    def test_matter_uses_matter_link(self):
        session = standard_session()
        session.add("POST", MATTER_UPDATE, make_response(204))
        client_with(session).set_extension_fields(matter(), {"x": "y"})
        self.assertEqual(len(session.calls_to("POST", MATTER_UPDATE)), 1)

    def test_invalid_fields_send_nothing(self):
        session = standard_session()
        client = client_with(session)
        for fields in ({}, "Sagstype", {"": "x"}, {" ": "x"}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                client.set_extension_fields(case(), fields)
        self.assertEqual(session.calls_to("POST", CASE_UPDATE), [])


if __name__ == "__main__":
    unittest.main()
