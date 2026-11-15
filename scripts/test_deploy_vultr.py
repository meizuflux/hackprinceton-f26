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
        args = deploy.parser().parse_args(["--domain", "maple.example.org", "--volume-id", "block-1", "--firewall-group-id", "fw-1", "--backup-endpoint", "https://ewr1.vultrobjects.com", "--backup-bucket", "mapletrace-backups"])
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
        args = deploy.parser().parse_args(["--domain", "maple.example.org", "--volume-id", "block-1", "--firewall-group-id", "fw-1", "--backup-endpoint", "https://ewr1.vultrobjects.com", "--backup-bucket", "mapletrace-backups"])
        responses = [{"instance": {"region": "ewr"}}, {"block": {"region": "ewr", "status": "active", "attached_to_instance": "other"}}]
        with patch.object(deploy, "api", side_effect=responses):
            with self.assertRaisesRegex(ValueError, "another instance"):
                deploy.prepare_volume(args, "instance-1")

    def test_volume_from_another_region_is_rejected(self):
        args = deploy.parser().parse_args(["--domain", "maple.example.org", "--volume-id", "block-1", "--firewall-group-id", "fw-1", "--backup-endpoint", "https://ewr1.vultrobjects.com", "--backup-bucket", "mapletrace-backups"])
        responses = [{"instance": {"region": "ewr"}}, {"block": {"region": "lax", "status": "active"}}]
        with patch.object(deploy, "api", side_effect=responses):
            with self.assertRaisesRegex(ValueError, "same region"):
                deploy.prepare_volume(args, "instance-1")

    def test_firewall_rules_restrict_ssh_and_allow_web(self):
        args = deploy.parser().parse_args(["--domain", "maple.example.org", "--volume-id", "b", "--ssh-cidr", "192.0.2.123/24", "--backup-endpoint", "https://ewr1.vultrobjects.com", "--backup-bucket", "backup-bucket"])
        with patch.object(deploy, "api", side_effect=[{"firewall_group": {"id": "fw"}}, {}, {}, {}, {}, {}]) as api:
            self.assertEqual(deploy.prepare_firewall(args), "fw")
        rules = [call.args[2] for call in api.call_args_list[1:]]
        self.assertEqual([r["port"] for r in rules], ["80", "443", "80", "443", "22"])
        self.assertEqual((rules[-1]["subnet"], rules[-1]["subnet_size"]), ("192.0.2.0", 24))

    def test_backup_configuration_requires_secure_endpoint_and_secrets(self):
        args = deploy.parser().parse_args(["--domain", "maple.example.org", "--volume-id", "b", "--firewall-group-id", "fw", "--backup-endpoint", "http://example.org", "--backup-bucket", "backup-bucket"])
        with patch.dict(os.environ, {"VULTR_OBJECT_ACCESS_KEY": "key", "VULTR_OBJECT_SECRET_KEY": "secret"}, clear=True):
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                deploy.backup_config(args)
            args.backup_endpoint = "https://ewr1.vultrobjects.com"
            config = deploy.backup_config(args)
            self.assertIn(b"access_key_id = key", config)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "VULTR_OBJECT"):
                deploy.backup_config(args)

    def test_enables_daily_instance_backups(self):
        with patch.object(deploy, "api") as api:
            deploy.enable_instance_backups("instance-1")
        self.assertEqual(api.call_args_list[0].args, ("PATCH", "/instances/instance-1", {"backups": "enabled"}))
        self.assertEqual(api.call_args_list[1].args[2]["type"], "daily")

    def test_create_requires_instance_settings_before_api_call(self):
        args = deploy.parser().parse_args(["--domain", "maple.example.org", "--volume-id", "block-1", "--firewall-group-id", "fw-1", "--backup-endpoint", "https://ewr1.vultrobjects.com", "--backup-bucket", "mapletrace-backups"])
        with patch.object(deploy.subprocess, "check_output", side_effect=[b"", "abc\n"]), patch.object(deploy, "backup_config", return_value=b"config"), patch.object(deploy, "api") as api:
            with self.assertRaisesRegex(ValueError, "--region"):
                deploy.deploy(args)
            api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
