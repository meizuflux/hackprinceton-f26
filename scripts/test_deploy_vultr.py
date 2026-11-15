import importlib.util
import base64
import json
import io
from types import SimpleNamespace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('deploy', Path(__file__).with_name('deploy-vultr.py'))
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class DeployTests(unittest.TestCase):
    def test_defaults_need_no_other_arguments(self):
        args = deploy.parser().parse_args([])
        self.assertEqual((args.region, args.plan, args.os_id, args.ssh_cidr, args.volume_size_gb),
                         ('ewr', 'vc2-2c-4gb', 2284, '0.0.0.0/0', 40))
        self.assertIsNone(args.domain)

    def test_state_does_not_store_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'deployment.json'
            state = deploy.DeploymentState(path)
            state.set(instance_id='instance-1', object_storage_id='storage-1')
            self.assertEqual(deploy.DeploymentState(path).data['instance_id'], 'instance-1')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn('secret', path.read_text())

    def test_environment_quotes_and_rejects_multiline(self):
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': "a'$b"}, clear=True):
            self.assertIn(b"ANTHROPIC_API_KEY='a\\'$b'", deploy.env_content('maple.example.org'))
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'a\nb'}, clear=True):
            with self.assertRaises(ValueError):
                deploy.env_content('maple.example.org')

    def test_domain_validation(self):
        for domain in ('example.com', 'mapletrace.work'):
            self.assertTrue(deploy.valid_domain(domain))
        for domain in ('localhost', '127.0.0.1', 'https://example.com', '*.example.com', 'x.example.com\nmalicious'):
            self.assertFalse(deploy.valid_domain(domain))

    def test_wait_ignores_unspecified_address(self):
        responses = [{'instance': {'main_ip': '0.0.0.0', 'status': 'active'}},
                     {'instance': {'main_ip': '192.0.2.1', 'status': 'active'}}]
        with patch.object(deploy, 'api', side_effect=responses), patch.object(deploy.time, 'sleep'):
            self.assertEqual(deploy.wait_instance('abc', 30), '192.0.2.1')

    def test_existing_volume_attaches(self):
        args = deploy.parser().parse_args(['--volume-id', 'block-1'])
        responses = [
            {'instance': {'region': 'ewr'}},
            {'block': {'region': 'ewr', 'status': 'active', 'attached_to_instance': ''}},
            {},
            {'block': {'region': 'ewr', 'status': 'active', 'attached_to_instance': 'instance-1', 'mount_id': 'volume-123'}},
        ]
        with patch.object(deploy, 'api', side_effect=responses) as api, patch.object(deploy.time, 'sleep'):
            self.assertEqual(deploy.prepare_volume(args, 'instance-1'), ('block-1', 'volume-123', False))
            self.assertEqual(api.call_args_list[2].args, ('POST', '/blocks/block-1/attach', {'instance_id': 'instance-1', 'live': True}))

    def test_volume_attached_elsewhere_or_in_another_region_is_rejected(self):
        args = deploy.parser().parse_args(['--volume-id', 'block-1'])
        for block, message in (({'region': 'ewr', 'status': 'active', 'attached_to_instance': 'other'}, 'another instance'),
                               ({'region': 'lax', 'status': 'active'}, 'same region')):
            with patch.object(deploy, 'api', side_effect=[{'instance': {'region': 'ewr'}}, {'block': block}]):
                with self.assertRaisesRegex(ValueError, message):
                    deploy.prepare_volume(args, 'instance-1')

    def test_default_firewall_allows_ssh_everywhere(self):
        args = deploy.parser().parse_args([])
        with tempfile.TemporaryDirectory() as directory:
            state = deploy.DeploymentState(Path(directory) / 'state.json')
            responses = [{'firewall_group': {'id': 'fw'}}, {'firewall_rules': []}, {}, {}, {}, {}, {}, {}]
            with patch.object(deploy, 'api', side_effect=responses) as api:
                self.assertEqual(deploy.prepare_firewall(args, state), 'fw')
            rules = [call.args[2] for call in api.call_args_list[2:]]
            ssh = [rule for rule in rules if rule['port'] == '22']
            self.assertEqual([(rule['ip_type'], rule['subnet'], rule['subnet_size']) for rule in ssh],
                             [('v4', '0.0.0.0', 0), ('v6', '::', 0)])
            self.assertEqual(state.data['firewall_group_id'], 'fw')

    def test_creates_object_storage_bucket_and_recovers_keys(self):
        args = deploy.parser().parse_args([])
        responses = [
            {'clusters': [{'id': 1, 'region': 'ewr', 'deploy': 'yes'}]},
            {'tiers': [{'id': 2}]},
            {'object_storage': {'id': 'abc123'}},
            {'object_storage': {'status': 'active', 's3_hostname': 'ewr1.vultrobjects.com', 's3_access_key': 'key', 's3_secret_key': 'secret'}},
            {'buckets': []}, {},
        ]
        with tempfile.TemporaryDirectory() as directory:
            state = deploy.DeploymentState(Path(directory) / 'state.json')
            with patch.object(deploy, 'api', side_effect=responses) as api:
                bucket, config = deploy.prepare_object_storage(args, state)
            self.assertEqual(bucket, 'mapletrace-abc123')
            self.assertIn(b'endpoint = https://ewr1.vultrobjects.com', config)
            self.assertEqual(api.call_args_list[-1].args, ('POST', '/object-storage/abc123/bucket', {'name': bucket}))
            self.assertNotIn('secret', json.dumps(state.data))

    def test_existing_subscription_is_reused(self):
        args = deploy.parser().parse_args(['--object-storage-id', 'abc123'])
        responses = [
            {'object_storage': {'status': 'active', 's3_hostname': 'ewr1.vultrobjects.com', 's3_access_key': 'key', 's3_secret_key': 'secret'}},
            {'buckets': [{'name': 'mapletrace-abc123'}]},
        ]
        with tempfile.TemporaryDirectory() as directory:
            state = deploy.DeploymentState(Path(directory) / 'state.json')
            with patch.object(deploy, 'api', side_effect=responses) as api:
                deploy.prepare_object_storage(args, state)
            self.assertEqual(api.call_count, 2)

    def test_default_deployment_records_ids_and_disables_ssh_passwords(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            args = deploy.parser().parse_args(['--state-file', str(path)])
            def ssh(args, state):
                args.identity_file = '/tmp/mapletrace-test-key'
                state.set(identity_file=args.identity_file, ssh_key_id='ssh-1')
                return 'ssh-1'
            archive = SimpleNamespace(stdout=io.BytesIO(b'archive'), returncode=0, wait=lambda: 0)
            with patch.dict('os.environ', {'VULTR_API_KEY': 'test-key'}, clear=True), \
                 patch.object(deploy.subprocess, 'check_output', side_effect=[b'', 'abc123\n']), \
                 patch.object(deploy.subprocess, 'run', return_value=SimpleNamespace(returncode=0)), \
                 patch.object(deploy.subprocess, 'Popen', return_value=archive), \
                 patch.object(deploy, 'prepare_ssh', side_effect=ssh), \
                 patch.object(deploy, 'prepare_firewall', return_value='fw-1'), \
                 patch.object(deploy, 'prepare_volume', return_value=('volume-1', 'mount-1', False)), \
                 patch.object(deploy, 'prepare_object_storage', return_value=('bucket', b'config')), \
                 patch.object(deploy, 'wait_instance', return_value='192.0.2.10'), \
                 patch.object(deploy, 'api', return_value={'instance': {'id': 'instance-1'}}) as api, \
                 patch.object(deploy, 'run') as run:
                deploy.deploy(args)
                state = deploy.DeploymentState(path).data
                self.assertEqual(state['instance_id'], 'instance-1')
                self.assertEqual(state['volume_id'], 'volume-1')
                self.assertEqual(state['domain'], 'mapletrace.work')
                self.assertEqual(api.call_args.args[1], '/instances')
                cloud_init = base64.b64decode(api.call_args.args[2]['user_data']).decode()
                self.assertIn('PasswordAuthentication no', cloud_init)
                self.assertIn('KbdInteractiveAuthentication no', cloud_init)
                self.assertTrue(any('mapletrace.work' in str(call) for call in run.call_args_list))

    def test_retry_marks_previously_created_volume_for_safe_initialization(self):
        args = deploy.parser().parse_args(['--volume-id', 'block-1'])
        responses = [{'instance': {'region': 'ewr'}}, {'block': {'region': 'ewr', 'status': 'active', 'attached_to_instance': 'instance-1', 'mount_id': 'volume-123'}}]
        with tempfile.TemporaryDirectory() as directory:
            state = deploy.DeploymentState(Path(directory) / 'state.json')
            state.set(created_volume_id='block-1')
            with patch.object(deploy, 'api', side_effect=responses):
                self.assertEqual(deploy.prepare_volume(args, 'instance-1', state), ('block-1', 'volume-123', True))

    def test_backup_config_rejects_insecure_endpoint(self):
        with self.assertRaisesRegex(ValueError, 'HTTPS'):
            deploy.backup_config('http://example.org', 'backup-bucket', 'key', 'secret')


if __name__ == '__main__':
    unittest.main()
