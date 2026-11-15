#!/usr/bin/env python3
"""Provision a Vultr instance and deploy a committed MapleTrace revision over SSH."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.vultr.com/v2"
REMOTE = "/opt/mapletrace"


def api(method, path, payload=None):
    key = os.environ.get("VULTR_API_KEY")
    if not key:
        raise ValueError("Set VULTR_API_KEY in your environment")
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(API + path, data=data, method=method, headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Vultr API returned HTTP {exc.code}: {exc.read(4096).decode(errors='replace')}") from exc


def env_content():
    lines = []
    for name in ("ANTHROPIC_API_KEY", "MAPLETRACE_LLM_MODEL", "MAPLETRACE_CORS"):
        value = os.environ.get(name, "")
        if "\n" in value or "\r" in value:
            raise ValueError(f"{name} must be a single line")
        # Compose dotenv supports single-quoted values without interpolation.
        lines.append(f"{name}='{value.replace(chr(39), chr(92) + chr(39))}'")
    return ("\n".join(lines) + "\n").encode()


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def ssh_base(args, host):
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
    if args.identity_file:
        cmd += ["-i", args.identity_file, "-o", "IdentitiesOnly=yes"]
    return cmd + [f"root@{host}"]


def wait_instance(instance_id, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        instance = api("GET", "/instances/" + instance_id)["instance"]
        address = instance.get("main_ip", "")
        try:
            ipaddress.IPv4Address(address)
        except ipaddress.AddressValueError:
            address = ""
        if address and address != "0.0.0.0" and instance.get("status") == "active":
            return address
        time.sleep(10)
    raise TimeoutError(f"Instance {instance_id} did not become active in {timeout}s")


def deploy(args):
    # Deploy a committed snapshot: no untracked files or local secrets are uploaded.
    if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT).strip():
        raise ValueError("Commit tracked changes before deploying; only HEAD is deployed")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    config = env_content()
    if args.instance_id:
        instance_id = args.instance_id
    else:
        missing = [name for name in ("region", "plan", "os_id", "ssh_key_id") if not getattr(args, name)]
        if missing:
            raise ValueError("For a new instance provide: " + ", ".join("--" + x.replace("_", "-") for x in missing))
        payload = {"region": args.region, "plan": args.plan, "os_id": args.os_id,
                   "label": args.label, "hostname": args.hostname, "sshkey_id": [args.ssh_key_id]}
        if args.firewall_group_id:
            payload["firewall_group_id"] = args.firewall_group_id
        instance_id = api("POST", "/instances", payload)["instance"]["id"]
        print(f"Created billable Vultr instance {instance_id}. Save this ID for retries.", flush=True)
    host = wait_instance(instance_id, args.timeout)
    print(f"Instance {instance_id} is active at {host}; connecting over SSH.", flush=True)
    ssh = ssh_base(args, host)
    deadline = time.monotonic() + args.timeout
    while True:
        result = subprocess.run(ssh + ["true"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            break
        if time.monotonic() >= deadline:
            raise TimeoutError(f"SSH unavailable for {host}. Verify its host key and retry with --instance-id {instance_id}")
        time.sleep(10)
    release = f"{REMOTE}/releases/{revision}"
    # git archive streams directly to the remote and includes only tracked files.
    remote_extract = f"umask 077; mkdir -p {shlex.quote(release)}; tar -xf - -C {shlex.quote(release)}"
    archive = subprocess.Popen(["git", "archive", "--format=tar", "HEAD"], cwd=ROOT, stdout=subprocess.PIPE)
    try:
        run(ssh + [remote_extract], stdin=archive.stdout)
    finally:
        archive.stdout.close()
        archive.wait()
    if archive.returncode:
        raise RuntimeError("git archive failed")
    run(ssh + [f"umask 077; cat > {REMOTE}/.env"], input=config)
    remote_command = f'''set -eu
command -v curl >/dev/null 2>&1 || {{ apt-get update; apt-get install -y curl ca-certificates; }}
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com -o /tmp/mapletrace-install-docker.sh
  sh /tmp/mapletrace-install-docker.sh
  rm -f /tmp/mapletrace-install-docker.sh
fi
docker compose version >/dev/null
cd {shlex.quote(release)}
docker compose --project-name mapletrace --env-file {REMOTE}/.env -f scripts/compose.vultr.yaml up -d --build --wait --wait-timeout 300
curl -fsS --max-time 10 http://127.0.0.1/health >/dev/null
curl -fsS --max-time 10 http://127.0.0.1/api/health >/dev/null
ln -sfn {shlex.quote(release)} {REMOTE}/current
'''
    run(ssh + ["sh -s"], input=remote_command.encode())
    print(f"Deployed {revision} to http://{host}/ (instance {instance_id}).", flush=True)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--instance-id", help="reuse an existing instance; avoids creating another billable server")
    p.add_argument("--region", help="Vultr region ID for a new instance")
    p.add_argument("--plan", help="Vultr plan ID for a new instance")
    p.add_argument("--os-id", type=int, help="Ubuntu OS ID for a new instance")
    p.add_argument("--ssh-key-id", help="existing Vultr SSH key ID for a new instance")
    p.add_argument("--firewall-group-id", help="existing Vultr firewall group ID")
    p.add_argument("--label", default="mapletrace")
    p.add_argument("--hostname", default="mapletrace")
    p.add_argument("--identity-file", help="local SSH private key")
    p.add_argument("--timeout", type=int, default=600, help="seconds to wait separately for instance and SSH (default: 600)")
    p.add_argument("--allow-public-http", action="store_true", help="acknowledge unauthenticated, unencrypted public HTTP")
    return p


def main():
    args = parser().parse_args()
    if not args.allow_public_http:
        parser().error("deployment exposes unauthenticated HTTP; pass --allow-public-http to acknowledge")
    if args.timeout <= 0:
        parser().error("--timeout must be positive")
    try:
        deploy(args)
    except (ValueError, RuntimeError, TimeoutError, OSError, subprocess.CalledProcessError, urllib.error.URLError) as exc:
        print(f"Deployment failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
