import importlib.util
import io
import json
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('monitor', Path(__file__).with_name('monitor-vultr.py'))
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


class MonitorTests(unittest.TestCase):
    def test_failure_and_recovery_are_logged_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'monitor.json').write_text(json.dumps({'domain': 'example.com'}))
            output = io.StringIO()
            with patch.object(monitor, 'ROOT', root), redirect_stdout(output):
                with patch.object(monitor, 'checks', return_value=['backend failed']):
                    self.assertEqual(monitor.main(), 1)
                    self.assertEqual(monitor.main(), 1)
                with patch.object(monitor, 'checks', return_value=[]):
                    self.assertEqual(monitor.main(), 0)
                    self.assertEqual(monitor.main(), 0)
            self.assertEqual(output.getvalue().count('backend failed'), 1)
            self.assertEqual(output.getvalue().count('recovered'), 1)


if __name__ == '__main__':
    unittest.main()
