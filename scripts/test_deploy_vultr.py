import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("deploy", Path(__file__).with_name("deploy-vultr.py"))
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class DeployTests(unittest.TestCase):
    def test_environment_quotes_and_preserves_dollars(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "a'$b", "MAPLETRACE_LLM_MODEL": "", "MAPLETRACE_CORS": ""}, clear=True):
            self.assertIn(b"ANTHROPIC_API_KEY='a\\'$b'", deploy.env_content("maple.example.org"))

    def test_environment_rejects_multiline(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "a\nb"}, clear=True):
            with self.assertRaises(ValueError):
                deploy.env_content("maple.example.org")

    def test_domain_validation(self):
        for domain in ("example.com", "maple-trace.example.org"):
            self.assertTrue(deploy.valid_domain(domain))
        for domain in ("localhost", "127.0.0.1", "https://example.com", "*.example.com", "x.example.com\nmalicious"):
            self.assertFalse(deploy.valid_domain(domain))

    def test_wait_ignores_unspecified_address(self):
        responses = [{"instance": {"main_ip": "0.0.0.0", "status": "active"}},
                     {"instance": {"main_ip": "192.0.2.1", "status": "active"}}]
        with patch.object(deploy, "api", side_effect=responses), patch.object(deploy.time, "sleep"):
            self.assertEqual(deploy.wait_instance("abc", 30), "192.0.2.1")

    def test_existing_volume_attaches_and_returns_stable_device_id(self):
        args = deploy.parser().parse_args(["--domain", "maple.example.org", "--volume-id", "block-1"])
        responses = [
            {"instance": {"region": "ewr"}},
            {"block": {"region": "ewr", "status": "active", "attached_to_instance": ""}},
            {},
            {"block": {"region": "ewr", "status": "active", "attached_to_instance": "instance-1", "mount_id": "volume-123"}},
        ]
        with patch.object(deploy, "api", side_effect=responses) as api, patch.object(deploy.time, "sleep"):
            self.assertEqual(deploy.prepare_volume(args, "instance-1"), ("block-1", "volume-123", False))
            self.assertEqual(api.call_args_list[2].args, ("POST", "/blocks/block-1/attach", {"instance_id": "instance-1", "live": True}))

    def test_volume_attached_elsewhere_is_rejected(self):
        args = deploy.parser().parse_args(["--domain", "maple.example.org", "--volume-id", "block-1"])
        responses = [{"instance": {"region": "ewr"}}, {"block": {"region": "ewr", "status": "active", "attached_to_instance": "other"}}]
        with patch.object(deploy, "api", side_effect=responses):
            with self.assertRaisesRegex(ValueError, "another instance"):
                deploy.prepare_volume(args, "instance-1")

    def test_volume_from_another_region_is_rejected(self):
        args = deploy.parser().parse_args(["--domain", "maple.example.org", "--volume-id", "block-1"])
        responses = [{"instance": {"region": "ewr"}}, {"block": {"region": "lax", "status": "active"}}]
        with patch.object(deploy, "api", side_effect=responses):
            with self.assertRaisesRegex(ValueError, "same region"):
                deploy.prepare_volume(args, "instance-1")

    def test_create_requires_instance_settings_before_api_call(self):
        args = deploy.parser().parse_args(["--domain", "maple.example.org", "--volume-id", "block-1"])
        with patch.object(deploy.subprocess, "check_output", side_effect=[b"", "abc\n"]), patch.object(deploy, "api") as api:
            with self.assertRaisesRegex(ValueError, "--region"):
                deploy.deploy(args)
            api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
