import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("lifecycle", Path(__file__).with_name("configure-vultr-lifecycle.py"))
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)


class LifecycleTests(unittest.TestCase):
    def test_preserves_unrelated_rules_and_is_idempotent(self):
        other = {"ID": "other", "Filter": {"Prefix": "unrelated/"}, "Status": "Enabled", "Expiration": {"Days": 7}}
        result = lifecycle.merge_rules([other])
        self.assertEqual(result, [other, lifecycle.RULE])
        self.assertEqual(lifecycle.merge_rules(result), result)

    def test_refuses_to_replace_rule_with_different_filter(self):
        with self.assertRaises(ValueError):
            lifecycle.merge_rules([{ "ID": lifecycle.RULE_ID, "Filter": {"Prefix": "other/"}}])

    def test_configure_preserves_existing_rules_and_verifies_result(self):
        other = {"ID": "retain-other", "Filter": {"Prefix": "other/"}, "Status": "Enabled", "Expiration": {"Days": 7}}
        class Client:
            def __init__(self):
                self.rules = [other]
                self.exceptions = type('Exceptions', (), {'ClientError': Exception})
            def get_bucket_versioning(self, **kwargs):
                return {}
            def get_bucket_lifecycle_configuration(self, **kwargs):
                return {"Rules": self.rules}
            def put_bucket_lifecycle_configuration(self, **kwargs):
                self.rules = kwargs['LifecycleConfiguration']['Rules']
        client = Client()
        lifecycle.configure(client, 'bucket')
        self.assertEqual(client.rules, [other, lifecycle.RULE])

    def test_missing_lifecycle_is_created_but_other_errors_propagate(self):
        class Error(Exception):
            def __init__(self, code):
                self.response = {'Error': {'Code': code}}
        class Client:
            exceptions = type('Exceptions', (), {'ClientError': Error})
            def __init__(self, code):
                self.code, self.rules = code, None
            def get_bucket_versioning(self, **kwargs):
                return {}
            def get_bucket_lifecycle_configuration(self, **kwargs):
                if self.rules is None:
                    raise Error(self.code)
                return {'Rules': self.rules}
            def put_bucket_lifecycle_configuration(self, **kwargs):
                self.rules = kwargs['LifecycleConfiguration']['Rules']
        client = Client('NoSuchLifecycleConfiguration')
        lifecycle.configure(client, 'bucket')
        self.assertEqual(client.rules, [lifecycle.RULE])
        with self.assertRaises(Error):
            lifecycle.configure(Client('AccessDenied'), 'bucket')

    def test_versioned_bucket_is_rejected(self):
        class Client:
            def get_bucket_versioning(self, **kwargs):
                return {"Status": "Enabled"}
        with self.assertRaisesRegex(ValueError, "versioning"):
            lifecycle.configure(Client(), "bucket")


if __name__ == "__main__":
    unittest.main()
