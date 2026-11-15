#!/usr/bin/env python3
"""Provision a Vultr instance and deploy a committed MapleTrace revision over SSH."""
import argparse
import configparser
import io
import ipaddress
import json
import os
import re
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

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
            body = response.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Vultr API returned HTTP {exc.code}: {exc.read(4096).decode(errors='replace')}") from exc


def env_content(domain):
    lines = [f"MAPLETRACE_DOMAIN='{domain}'"]
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



def prepare_volume(args, instance_id):
    instance = api("GET", "/instances/" + instance_id)["instance"]
    region = instance["region"]
    created = False
    if args.volume_id:
        volume_id = args.volume_id
    else:
        volume = api("POST", "/blocks", {"region": region, "size_gb": args.volume_size_gb,
                                         "label": args.label + "-data", "block_type": args.volume_type})["block"]
        volume_id = volume["id"]
        created = True
        print(f"Created billable Vultr block storage {volume_id}. Save this ID for retries.", flush=True)
    deadline = time.monotonic() + args.timeout
    attach_requested = False
    while time.monotonic() < deadline:
        volume = api("GET", "/blocks/" + volume_id)["block"]
        if volume.get("region") != region:
            raise ValueError("Block storage and instance must be in the same region")
        attached = volume.get("attached_to_instance") or ""
        if attached and attached != instance_id:
            raise ValueError(f"Block storage {volume_id} is attached to another instance")
        if volume.get("status") == "active":
            if not attached and not attach_requested:
                api("POST", f"/blocks/{volume_id}/attach", {"instance_id": instance_id, "live": True})
                attach_requested = True
            elif attached == instance_id and volume.get("mount_id"):
                mount_id = volume["mount_id"]
                if not re.fullmatch(r"[A-Za-z0-9_-]+", mount_id):
                    raise ValueError("Invalid Vultr block storage mount ID")
                return volume_id, mount_id, created
        time.sleep(10)
    raise TimeoutError(f"Block storage {volume_id} did not become ready; retry with --volume-id {volume_id}")



def backup_config(args):
    access = os.environ.get("VULTR_OBJECT_ACCESS_KEY", "")
    secret = os.environ.get("VULTR_OBJECT_SECRET_KEY", "")
    if not access or not secret or any("\n" in x or "\r" in x for x in (access, secret)):
        raise ValueError("Set single-line VULTR_OBJECT_ACCESS_KEY and VULTR_OBJECT_SECRET_KEY")
    endpoint = urlparse(args.backup_endpoint)
    if endpoint.scheme != "https" or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.path not in ("", "/") or endpoint.query or endpoint.fragment:
        raise ValueError("Backup endpoint must be an HTTPS object-storage origin")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", args.backup_bucket) or ".." in args.backup_bucket:
        raise ValueError("Invalid backup bucket name")
    config = configparser.RawConfigParser()
    config["vultr"] = {"type": "s3", "provider": "Vultr", "env_auth": "false", "access_key_id": access,
                       "secret_access_key": secret, "endpoint": args.backup_endpoint, "acl": "private"}
    out = io.StringIO()
    config.write(out)
    return out.getvalue().encode()



def prepare_firewall(args):
    if args.firewall_group_id:
        return args.firewall_group_id
    network = ipaddress.ip_network(args.ssh_cidr, strict=False)
    group = api("POST", "/firewalls", {"description": args.label + "-firewall"})["firewall_group"]["id"]
    print(f"Created firewall group {group}. Save this ID for retries.", flush=True)
    rules = [("v4", "0.0.0.0", 0, "80"), ("v4", "0.0.0.0", 0, "443"),
             ("v6", "::", 0, "80"), ("v6", "::", 0, "443"),
             ("v4" if network.version == 4 else "v6", str(network.network_address), network.prefixlen, "22")]
    for ip_type, subnet, size, port in rules:
        api("POST", f"/firewalls/{group}/rules", {"ip_type": ip_type, "protocol": "tcp", "port": port,
                                                 "subnet": subnet, "subnet_size": size})
    return group


def enable_instance_backups(instance_id):
    api("PATCH", "/instances/" + instance_id, {"backups": "enabled"})
    api("POST", f"/instances/{instance_id}/backup-schedule", {"type": "daily", "hour": 3, "dow": 1, "dom": 1})


def deploy(args):
    # Deploy a committed snapshot: no untracked files or local secrets are uploaded.
    if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT).strip():
        raise ValueError("Commit tracked changes before deploying; only HEAD is deployed")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    config = env_content(args.domain)
    backup = backup_config(args)
    monitor = json.dumps({"domain": args.domain}).encode()
    if not args.instance_id:
        missing = [name for name in ("region", "plan", "os_id", "ssh_key_id") if not getattr(args, name)]
        if missing:
            raise ValueError("For a new instance provide: " + ", ".join("--" + x.replace("_", "-") for x in missing))
    firewall_id = prepare_firewall(args)
    if args.instance_id:
        instance_id = args.instance_id
    else:
        payload = {"region": args.region, "plan": args.plan, "os_id": args.os_id,
                   "label": args.label, "hostname": args.hostname, "sshkey_id": [args.ssh_key_id]}
        payload["firewall_group_id"] = firewall_id
        payload["backups"] = "enabled"
        instance_id = api("POST", "/instances", payload)["instance"]["id"]
        print(f"Created billable Vultr instance {instance_id}. Save this ID for retries.", flush=True)
    host = wait_instance(instance_id, args.timeout)
    if args.instance_id:
        api("PATCH", "/instances/" + instance_id, {"firewall_group_id": firewall_id})
    enable_instance_backups(instance_id)
    volume_id, mount_id, created_volume = prepare_volume(args, instance_id)
    print(f"Using block storage {volume_id} for case data.", flush=True)
    print(f"Instance {instance_id} is active at {host}; point {args.domain} to this IP and connect over SSH.", flush=True)
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
    settings = io.BytesIO()
    with tarfile.open(fileobj=settings, mode="w") as archive_file:
        for name, content in ((".env", config), ("rclone.conf", backup), ("backup-bucket", args.backup_bucket.encode()), ("monitor.json", monitor)):
            info = tarfile.TarInfo(name)
            info.mode = 0o600
            info.size = len(content)
            archive_file.addfile(info, io.BytesIO(content))
    settings_command = f"umask 077; tar -xf - -C {REMOTE}; chmod 600 {REMOTE}/.env {REMOTE}/rclone.conf {REMOTE}/backup-bucket {REMOTE}/monitor.json"
    run(ssh + ["flock -x /run/lock/mapletrace.lock sh -c " + shlex.quote(settings_command)], input=settings.getvalue())
    storage_script = (ROOT / "scripts" / "mount-vultr-storage.sh").read_bytes()
    storage_args = ["sh", "-s", "--", mount_id, "yes" if created_volume else "no",
                    "yes" if args.local_data_migrated else "no"]
    run(ssh + [" ".join(shlex.quote(arg) for arg in storage_args)], input=storage_script)
    remote_command = f'''set -eu
exec 9>/run/lock/mapletrace.lock
flock -x 9
command -v curl >/dev/null 2>&1 || {{ apt-get update; apt-get install -y curl ca-certificates; }}
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com -o /tmp/mapletrace-install-docker.sh
  sh /tmp/mapletrace-install-docker.sh
  rm -f /tmp/mapletrace-install-docker.sh
fi
docker compose version >/dev/null
if ! command -v rclone >/dev/null 2>&1 || ! /usr/bin/python3 -c 'import boto3' >/dev/null 2>&1; then
  apt-get update
  apt-get install -y rclone python3-boto3
fi
cd {shlex.quote(release)}
docker compose --project-name mapletrace --env-file {REMOTE}/.env -f scripts/compose.vultr.yaml up -d --build --remove-orphans --wait --wait-timeout 300
# Caddy obtains a certificate asynchronously after the public DNS record resolves.
i=0
until curl -fsS --max-time 10 --resolve {args.domain}:443:127.0.0.1 https://{args.domain}/health >/dev/null && \
      curl -fsS --max-time 10 --resolve {args.domain}:443:127.0.0.1 https://{args.domain}/api/health >/dev/null; do
  i=$((i+1))
  if [ "$i" -ge 60 ]; then
    echo "HTTPS health checks failed; check DNS, firewall and Caddy logs, then retry this instance." >&2
    exit 1
  fi
  sleep 5
done
ln -sfn {shlex.quote(release)} {REMOTE}/current
install -m 0644 scripts/mapletrace-backup.service /etc/systemd/system/mapletrace-backup.service
install -m 0644 scripts/mapletrace-backup.timer /etc/systemd/system/mapletrace-backup.timer
systemctl daemon-reload
systemctl enable --now mapletrace-backup.timer
'''
    run(ssh + ["sh -s"], input=remote_command.encode())
    # Run one backup now so missing bucket permissions or credentials fail deployment.
    run(ssh + ["systemctl start mapletrace-backup.service"])
    run(ssh + ["/usr/bin/python3 /opt/mapletrace/current/scripts/configure-vultr-lifecycle.py"])
    run(ssh + ["install -m 0644 /opt/mapletrace/current/scripts/mapletrace-monitor.service /opt/mapletrace/current/scripts/mapletrace-monitor.timer /etc/systemd/system/ && systemctl daemon-reload && systemctl enable --now mapletrace-monitor.timer && systemctl start mapletrace-monitor.service"])
    print(f"Deployed {revision} to https://{args.domain}/ (instance {instance_id}).", flush=True)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--instance-id", help="reuse an existing instance; avoids creating another billable server")
    p.add_argument("--region", help="Vultr region ID for a new instance")
    p.add_argument("--plan", help="Vultr plan ID for a new instance")
    p.add_argument("--os-id", type=int, help="Ubuntu OS ID for a new instance")
    p.add_argument("--ssh-key-id", help="existing Vultr SSH key ID for a new instance")
    firewall = p.add_mutually_exclusive_group(required=True)
    firewall.add_argument("--firewall-group-id", help="existing configured Vultr firewall group ID")
    firewall.add_argument("--ssh-cidr", help="IPv4 SSH source CIDR for a new firewall group")
    p.add_argument("--backup-endpoint", required=True, help="Vultr Object Storage HTTPS endpoint")
    p.add_argument("--backup-bucket", required=True, help="existing private object-storage bucket")
    p.add_argument("--label", default="mapletrace")
    p.add_argument("--hostname", default="mapletrace")
    p.add_argument("--identity-file", help="local SSH private key")
    p.add_argument("--timeout", type=int, default=600, help="seconds to wait separately for instance and SSH (default: 600)")
    storage = p.add_mutually_exclusive_group(required=True)
    storage.add_argument("--volume-id", help="existing Vultr block storage ID, formatted as ext4")
    storage.add_argument("--volume-size-gb", type=int, help="create a new billable block storage volume of this size")
    p.add_argument("--volume-type", choices=("high_perf", "storage_opt"), default="high_perf")
    p.add_argument("--local-data-migrated", action="store_true", help="confirm old local Docker volume was migrated or is not needed")
    p.add_argument("--domain", required=True, help="public DNS hostname pointing to the instance")
    return p


def valid_domain(domain):
    if len(domain) > 253 or domain.endswith("."):
        return False
    labels = domain.split(".")
    return len(labels) >= 2 and labels[-1].isalpha() and all(
        re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label)
        for label in labels
    ) and labels[-1].lower() not in {"localhost", "local", "internal"}


def main():
    args = parser().parse_args()
    if not valid_domain(args.domain):
        parser().error("--domain must be a public DNS hostname (no URL, wildcard, IP address, or localhost)")
    if args.ssh_cidr:
        try:
            if ipaddress.ip_network(args.ssh_cidr, strict=False).version != 4:
                raise ValueError("IPv4 required")
        except ValueError:
            parser().error("--ssh-cidr must be an IPv4 CIDR (deployment connects over IPv4)")
    if args.volume_size_gb is not None and args.volume_size_gb <= 0:
        parser().error("--volume-size-gb must be positive")
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
