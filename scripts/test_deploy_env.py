import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('deploy_env', Path(__file__).with_name('deploy-vultr.py'))
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class DeploymentEnvTests(unittest.TestCase):
    def test_loads_values_without_expansion_and_preserves_shell_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / '.env'
            env_file.write_text('''# deployment settings
VULTR_API_KEY=file-key
export ANTHROPIC_API_KEY="secret $literal # value"
MAPLETRACE_LLM_MODEL=claude-sonnet-5-5 # comment
MAPLETRACE_CHAT_MODEL='chat model'
MAPLETRACE_CORS=
''')
            with patch.dict(os.environ, {'VULTR_API_KEY': 'shell-key'}, clear=True):
                deploy.load_env_file(env_file)
                self.assertEqual(os.environ['VULTR_API_KEY'], 'shell-key')
                self.assertEqual(os.environ['ANTHROPIC_API_KEY'], 'secret $literal # value')
                self.assertEqual(os.environ['MAPLETRACE_CHAT_MODEL'], 'chat model')
                self.assertEqual(os.environ['MAPLETRACE_CORS'], '')
                payload = deploy.env_content('mapletrace.work')
                self.assertNotIn(b'shell-key', payload)
                self.assertIn(b"MAPLETRACE_CHAT_MODEL='chat model'", payload)

    def test_invalid_file_never_partially_applies_or_prints_values(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / '.env'
            env_file.write_text('VULTR_API_KEY=secret-key\nUNKNOWN=private-value\n')
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(ValueError) as error:
                    deploy.load_env_file(env_file)
                self.assertNotIn('VULTR_API_KEY', os.environ)
                self.assertNotIn('private-value', str(error.exception))

    def test_duplicate_and_malformed_values_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / '.env'
            for content in ('VULTR_API_KEY=a\nVULTR_API_KEY=b\n', 'VULTR_API_KEY="unfinished\n', 'VULTR_API_KEY=unquoted space\n'):
                env_file.write_text(content)
                with self.subTest(content=content), self.assertRaises(ValueError):
                    deploy.load_env_file(env_file)

    def test_cli_reads_explicit_file_before_deploy(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / 'deployment.env'
            env_file.write_text('VULTR_API_KEY=file-key\nANTHROPIC_API_KEY=backend-key\n')
            with patch.dict(os.environ, {}, clear=True), patch('sys.argv', ['deploy-vultr.py', '--env-file', str(env_file)]), patch.object(deploy, 'deploy') as run:
                self.assertEqual(deploy.main(), 0)
                self.assertEqual(os.environ['VULTR_API_KEY'], 'file-key')
                self.assertEqual(os.environ['ANTHROPIC_API_KEY'], 'backend-key')
                run.assert_called_once()

    def test_optional_missing_file_and_explicit_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / 'missing'
            deploy.load_env_file(env_file)
            with self.assertRaisesRegex(ValueError, 'does not exist'):
                deploy.load_env_file(env_file, required=True)


if __name__ == '__main__':
    unittest.main()
