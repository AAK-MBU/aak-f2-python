import unittest

from aak_f2.shared import F2Config, F2ConfigError

ENV = {
    "F2_SERVICE_INDEX_URL": "https://f2.example/rest/index",
    "F2_CLIENT_ID": "client",
    "F2_CLIENT_SECRET": "secret",
    "F2_USERNAME": "robot",
}


class FromEnvTest(unittest.TestCase):
    def test_reads_required_values(self):
        config = F2Config.from_env(ENV)
        self.assertEqual(config.service_index_url, ENV["F2_SERVICE_INDEX_URL"])
        self.assertEqual(config.username, "robot")
        self.assertIsNone(config.password)
        self.assertIsNone(config.organization_partyno)

    def test_reads_optional_values(self):
        env = {
            **ENV,
            "F2_PASSWORD": "pw",
            "F2_ORGANIZATION_PARTYNO": "99",
            "F2_TIMEOUT": "5",
        }
        config = F2Config.from_env(env)
        self.assertEqual(config.password, "pw")
        self.assertEqual(config.organization_partyno, 99)
        self.assertEqual(config.timeout, 5.0)

    def test_missing_values_are_listed(self):
        with self.assertRaises(F2ConfigError) as ctx:
            F2Config.from_env({"F2_CLIENT_ID": "client"})
        self.assertIn("F2_SERVICE_INDEX_URL", str(ctx.exception))
        self.assertIn("F2_USERNAME", str(ctx.exception))

    def test_invalid_number(self):
        with self.assertRaises(F2ConfigError):
            F2Config.from_env({**ENV, "F2_ORGANIZATION_PARTYNO": "abc"})

    def test_repr_hides_secrets(self):
        config = F2Config.from_env({**ENV, "F2_PASSWORD": "pw"})
        self.assertNotIn("secret", repr(config))
        self.assertNotIn("pw", repr(config))
