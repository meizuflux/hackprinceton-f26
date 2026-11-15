import importlib.util
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('monitor', Path(__file__).with_name('monitor-vultr.py'))
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


class MonitorTests(unittest.TestCase):
    def test_failure_retries_and_recovery_notifies_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'monitor.json').write_text(json.dumps({'domain': 'example.com', 'webhook': 'https://example.com/hook'}))
            with patch.object(monitor, 'ROOT', root), patch.object(monitor, 'checks', return_value=['backend failed']), patch.object(monitor, 'send', side_effect=OSError('unreachable')):
                self.assertEqual(monitor.main(), 1)
                self.assertFalse((root / 'monitor-state.json').exists())
            with patch.object(monitor, 'ROOT', root), patch.object(monitor, 'checks', return_value=['backend failed']), patch.object(monitor, 'send') as send:
                self.assertEqual(monitor.main(), 1)
                self.assertEqual(monitor.main(), 1)
                self.assertEqual(send.call_count, 1)
            with patch.object(monitor, 'ROOT', root), patch.object(monitor, 'checks', return_value=[]), patch.object(monitor, 'send') as send:
                self.assertEqual(monitor.main(), 0)
                self.assertEqual(monitor.main(), 0)
                self.assertEqual(send.call_count, 1)
                self.assertIn('recovered', send.call_args.args[1])

    def test_heartbeat_only_sent_when_healthy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'monitor.json').write_text(json.dumps({'domain': 'example.com', 'webhook': 'https://example.com/hook', 'heartbeat': 'https://example.com/ping'}))
            with patch.object(monitor, 'ROOT', root), patch.object(monitor, 'checks', return_value=[]), patch.object(monitor, 'send') as send:
                self.assertEqual(monitor.main(), 0)
                self.assertEqual(send.call_args.args[0], 'https://example.com/ping')
            with patch.object(monitor, 'ROOT', root), patch.object(monitor, 'checks', return_value=['disk full']), patch.object(monitor, 'send') as send:
                self.assertEqual(monitor.main(), 1)
                self.assertEqual(send.call_count, 1)
                self.assertEqual(send.call_args.args[0], 'https://example.com/hook')


if __name__ == '__main__':
    unittest.main()
