import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class BackupScriptTests(unittest.TestCase):
    def run_backup(self, tar_failure=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            (root / "current").mkdir()
            (root / "data").mkdir()
            (root / "backup-bucket").write_text("private-bucket")
            log = root / "calls"
            docker = '''#!/bin/sh
printf 'docker %s\\n' "$*" >> "$TEST_LOG"
case "$*" in
  *"ps -q backend"*) echo container ;;
  "inspect "*) echo true ;;
esac
'''
            scripts = {
                "docker": docker,
                "mountpoint": "#!/bin/sh\nexit 0\n",
                "flock": "#!/bin/sh\nexit 0\n",
                "tar": '#!/bin/sh\nprintf "tar\\n" >> "$TEST_LOG"\nexit "${TAR_FAILURE:-0}"\n',
                "rclone": '#!/bin/sh\nprintf "upload\\n" >> "$TEST_LOG"\n',
            }
            for name, body in scripts.items():
                path = bin_dir / name
                path.write_text(body)
                path.chmod(0o755)
            source = Path(__file__).with_name("backup-vultr.sh").read_text()
            source = source.replace('/run/lock/mapletrace.lock', str(root / 'lock'))
            source = source.replace('/mnt/mapletrace-data/mapletrace', str(root / 'data'))
            source = source.replace('/mnt/mapletrace-data', str(root / 'mount'))
            source = source.replace('/opt/mapletrace', str(root))
            path = root / 'backup.sh'
            path.write_text(source)
            env = dict(os.environ, PATH=str(bin_dir) + ':' + os.environ['PATH'], TEST_LOG=str(log), TAR_FAILURE='1' if tar_failure else '0')
            result = subprocess.run(['sh', str(path)], env=env, capture_output=True, text=True)
            return result, log.read_text().splitlines()

    def test_backend_restarts_before_upload(self):
        result, calls = self.run_backup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(calls.index('docker compose --project-name mapletrace --env-file ' + self._env_path(calls) + ' -f scripts/compose.vultr.yaml start backend'), calls.index('upload'))

    @staticmethod
    def _env_path(calls):
        line = next(line for line in calls if 'start backend' in line)
        return line.split('--env-file ', 1)[1].split(' -f ', 1)[0]

    def test_archive_failure_restarts_backend_and_skips_upload(self):
        result, calls = self.run_backup(tar_failure=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(any('start backend' in line for line in calls))
        self.assertNotIn('upload', calls)


if __name__ == '__main__':
    unittest.main()
