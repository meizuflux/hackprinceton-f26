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
            self.assertIn(b"ANTHROPIC_API_KEY='a\\'$b'", deploy.env_content())

    def test_environment_rejects_multiline(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "a\nb"}, clear=True):
            with self.assertRaises(ValueError):
                deploy.env_content()

    def test_wait_ignores_unspecified_address(self):
        responses = [{"instance": {"main_ip": "0.0.0.0", "status": "active"}},
                     {"instance": {"main_ip": "192.0.2.1", "status": "active"}}]
        with patch.object(deploy, "api", side_effect=responses), patch.object(deploy.time, "sleep"):
            self.assertEqual(deploy.wait_instance("abc", 30), "192.0.2.1")

    def test_create_requires_instance_settings_before_api_call(self):
        args = deploy.parser().parse_args(["--allow-public-http"])
        with patch.object(deploy.subprocess, "check_output", side_effect=[b"", "abc\n"]), patch.object(deploy, "api") as api:
            with self.assertRaisesRegex(ValueError, "--region"):
                deploy.deploy(args)
            api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
