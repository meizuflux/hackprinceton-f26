#!/usr/bin/env python3
"""Check local MapleTrace health and send state changes to a JSON webhook."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = Path('/opt/mapletrace')
MOUNT = Path('/mnt/mapletrace-data')
MAX_BACKUP_AGE = 36 * 60 * 60
MIN_FREE_PERCENT = 15


def checks(config):
    issues = []
    for path, label in ((Path('/'), 'server disk'), (MOUNT, 'case-data disk')):
        if path == MOUNT and not os.path.ismount(path):
            issues.append('Case-data volume is not mounted')
            continue
        disk = shutil.disk_usage(path)
        if disk.total == 0 or disk.free / disk.total < MIN_FREE_PERCENT / 100:
            issues.append(f'Less than {MIN_FREE_PERCENT}% free on {label}')
    domain = config['domain']
    backup_running = subprocess.run(['systemctl', 'is-active', '--quiet', 'mapletrace-backup.service']).returncode == 0
    for path, label in (('/health', 'frontend'), ('/api/health', 'backend')):
        if label == 'backend' and backup_running:
            continue
        result = subprocess.run(['curl', '-fsS', '--max-time', '10', '--resolve', f'{domain}:443:127.0.0.1',
                                 f'https://{domain}{path}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode:
            issues.append(f'{label.capitalize()} HTTPS health check failed')
    last_backup = ROOT / 'last-backup-success'
    if not last_backup.exists() or time.time() - last_backup.stat().st_mtime > MAX_BACKUP_AGE:
        issues.append('No successful case-data backup in the last 36 hours')
    result = subprocess.run(['systemctl', 'is-failed', '--quiet', 'mapletrace-backup.service'])
    if result.returncode == 0:
        issues.append('Case-data backup service failed')
    elif result.returncode != 1:
        issues.append('Could not inspect backup service status')
    if subprocess.run(['systemctl', 'is-active', '--quiet', 'mapletrace-backup.timer']).returncode != 0:
        issues.append('Case-data backup timer is not active')
    return issues


def send(url, message):
    request = urllib.request.Request(url, data=json.dumps({'text': message}).encode(),
                                     headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=10) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError('Alert endpoint returned a non-success status')


def main():
    config = json.loads((ROOT / 'monitor.json').read_text())
    state_path = ROOT / 'monitor-state.json'
    try:
        previous = json.loads(state_path.read_text()).get('issues', [])
    except FileNotFoundError:
        previous = []
    current = sorted(checks(config))
    if current != previous:
        message = ('MapleTrace alert: ' + '; '.join(current)) if current else 'MapleTrace recovered: all local checks are healthy.'
        print(message, flush=True)
        if config.get('webhook'):
            try:
                send(config['webhook'], message)
            except Exception:
                print('Alert delivery failed; will retry on the next check', file=sys.stderr)
                return 1
        temporary = state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'issues': current}))
        os.chmod(temporary, 0o600)
        temporary.replace(state_path)
    if not current and config.get('heartbeat'):
        try:
            send(config['heartbeat'], 'MapleTrace local checks are healthy')
        except Exception:
            print('Heartbeat delivery failed', file=sys.stderr)
            return 1
    return 1 if current else 0


if __name__ == '__main__':
    sys.exit(main())
