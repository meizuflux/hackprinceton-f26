#!/usr/bin/env python3
"""Provision a Vultr instance and deploy a committed MapleTrace revision over SSH."""
import argparse
import base64
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
from urllib.parse import urlparse, urlencode

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.vultr.com/v2"
REMOTE = "/opt/mapletrace"
DEFAULT_DOMAIN = "mapletrace.work"
ENV_KEYS = {"VULTR_API_KEY", "ANTHROPIC_API_KEY", "MAPLETRACE_LLM_MODEL", "MAPLETRACE_CHAT_MODEL", "MAPLETRACE_CORS"}
DEFAULT_ENV_FILE = ROOT / "scripts" / ".env"
STATE_DIR = Path.home() / ".local" / "state" / "mapletrace-vultr"


class DeploymentState:
    """Persist resource IDs, never credentials, so retries reuse billable resources."""
    def __init__(self, path):
        self.path = Path(path).expanduser()
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {}

    def set(self, **items):
        self.data.update(items)
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(self.data, f, indent=2)
            f.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, self.path)


def list_api(path, key):
    cursor = None
    while True:
        params = {"per_page": 1000}
        if cursor:
            params["cursor"] = cursor
        result = api("GET", path + "?" + urlencode(params))
        yield from result[key]
        cursor = result.get("meta", {}).get("links", {}).get("next")
        if not cursor:
            break



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


def load_env_file(path, *, required=False):
    """Load deployment settings without executing shell code or expanding variables."""
    path = Path(path).expanduser()
    if not path.exists():
        if required:
            raise ValueError(f"Environment file does not exist: {path}")
        return
    values = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, sep, raw = line.partition("=")
        key = key.strip()
        if not sep or key not in ENV_KEYS or key in values:
            raise ValueError(f"Invalid or duplicate setting in {path} at line {number}")
        try:
            tokens = shlex.split(raw, comments=True, posix=True)
        except ValueError as exc:
            raise ValueError(f"Invalid value in {path} at line {number}") from exc
        if len(tokens) > 1:
            raise ValueError(f"Quote values containing spaces in {path} at line {number}")
        values[key] = tokens[0] if tokens else ""
    for key, value in values.items():
        os.environ.setdefault(key, value)


def env_content(domain):
    lines = [f"MAPLETRACE_DOMAIN='{domain}'"]
    for name in ("ANTHROPIC_API_KEY", "MAPLETRACE_LLM_MODEL", "MAPLETRACE_CHAT_MODEL", "MAPLETRACE_CORS"):
        value = os.environ.get(name, "")
        if "\n" in value or "\r" in value:
            raise ValueError(f"{name} must be a single line")
        # Compose dotenv supports single-quoted values without interpolation.
        lines.append(f"{name}='{value.replace(chr(39), chr(92) + chr(39))}'")
    return ("\n".join(lines) + "\n").encode()


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def ssh_base(args, host):
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=accept-new"]
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



def prepare_volume(args, instance_id, state=None):
    instance = api("GET", "/instances/" + instance_id)["instance"]
    region = instance["region"]
    created = False
    if args.volume_id:
        volume_id = args.volume_id
    else:
        volume = api("POST", "/blocks", {"region": region, "size_gb": args.volume_size_gb,
                                         "label": args.label + "-data", "block_type": args.volume_type})["block"]
        volume_id = volume["id"]
        if state:
            state.set(volume_id=volume_id, created_volume_id=volume_id)
        created = True
        print(f"Created billable Vultr block storage {volume_id}. Save this ID for retries.", flush=True)
    if state and state.data.get("created_volume_id") == volume_id:
        created = True
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



def backup_config(endpoint_url, bucket, access, secret):
    if not access or not secret or any("\n" in x or "\r" in x for x in (access, secret)):
        raise ValueError("Object Storage returned invalid credentials")
    endpoint = urlparse(endpoint_url)
    if endpoint.scheme != "https" or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.path not in ("", "/") or endpoint.query or endpoint.fragment:
        raise ValueError("Backup endpoint must be an HTTPS object-storage origin")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket) or ".." in bucket:
        raise ValueError("Invalid backup bucket name")
    config = configparser.RawConfigParser()
    config["vultr"] = {"type": "s3", "provider": "Vultr", "env_auth": "false", "access_key_id": access,
                       "secret_access_key": secret, "endpoint": endpoint_url, "acl": "private"}
    out = io.StringIO()
    config.write(out)
    return out.getvalue().encode()


def prepare_object_storage(args, state):
    storage_id = args.object_storage_id or state.data.get("object_storage_id")
    if not storage_id:
        clusters = list(list_api("/object-storage/clusters", "clusters"))
        clusters = [c for c in clusters if c.get("region") == args.region and c.get("deploy") == "yes"]
        if not clusters:
            raise ValueError(f"No deployable Object Storage cluster in {args.region}; choose --object-storage-id for an existing subscription")
        tiers = api("GET", f"/object-storage/clusters/{clusters[0]['id']}/tiers")["tiers"]
        if not any(t.get("id") == 2 for t in tiers):
            raise ValueError(f"Standard Object Storage is unavailable in {args.region}")
        storage_id = api("POST", "/object-storage", {"cluster_id": clusters[0]["id"], "tier_id": 2,
                                                       "label": args.label + "-backups"})["object_storage"]["id"]
        state.set(object_storage_id=storage_id)
        print(f"Created billable Object Storage subscription {storage_id}.", flush=True)
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        storage = api("GET", "/object-storage/" + storage_id)["object_storage"]
        if storage.get("status") == "active" and all(storage.get(k) for k in ("s3_hostname", "s3_access_key", "s3_secret_key")):
            break
        time.sleep(10)
    else:
        raise TimeoutError(f"Object Storage {storage_id} did not become ready; retry with --object-storage-id {storage_id}")
    bucket = args.backup_bucket or state.data.get("backup_bucket") or "mapletrace-" + storage_id.lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket) or ".." in bucket:
        raise ValueError("Invalid backup bucket name")
    state.set(object_storage_id=storage_id, backup_bucket=bucket)
    existing = api("GET", f"/object-storage/{storage_id}/bucket").get("buckets", [])
    if not any(item.get("name") == bucket for item in existing):
        api("POST", f"/object-storage/{storage_id}/bucket", {"name": bucket})
    endpoint = "https://" + storage["s3_hostname"]
    return bucket, backup_config(endpoint, bucket, storage["s3_access_key"], storage["s3_secret_key"])


def prepare_ssh(args, state):
    if args.ssh_key_id and not (args.identity_file or state.data.get("identity_file")):
        raise ValueError("Provide --identity-file for the existing --ssh-key-id")
    identity = Path(args.identity_file or state.data.get("identity_file") or state.path.parent / "ssh_ed25519").expanduser()
    if not identity.exists():
        if args.identity_file or state.data.get("ssh_key_id"):
            raise ValueError(f"SSH private key does not exist: {identity}")
        identity.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(identity)])
    args.identity_file = str(identity)
    key_id = args.ssh_key_id or state.data.get("ssh_key_id")
    if not key_id:
        public_key = subprocess.check_output(["ssh-keygen", "-y", "-f", str(identity)], text=True).strip()
        key_parts = public_key.split()[:2]
        registered = list(list_api("/ssh-keys", "ssh_keys"))
        match = next((k for k in registered if k.get("ssh_key", "").split()[:2] == key_parts), None)
        if match:
            key_id = match["id"]
        else:
            key_id = api("POST", "/ssh-keys", {"name": args.label + "-deploy", "ssh_key": public_key})["ssh_key"]["id"]
    state.set(ssh_key_id=key_id, identity_file=str(identity))
    return key_id


def prepare_firewall(args, state=None):
    group = args.firewall_group_id or (state.data.get("firewall_group_id") if state else None)
    managed = bool(state and group and state.data.get("managed_firewall_id") == group)
    if group and not managed:
        return group
    if not group:
        group = api("POST", "/firewalls", {"description": args.label + "-firewall"})["firewall_group"]["id"]
        if state:
            state.set(firewall_group_id=group, managed_firewall_id=group)
        print(f"Created firewall group {group}.", flush=True)
    network = ipaddress.ip_network(args.ssh_cidr, strict=False)
    rules = [("v4", "0.0.0.0", 0, "80"), ("v4", "0.0.0.0", 0, "443"),
             ("v6", "::", 0, "80"), ("v6", "::", 0, "443"),
             ("v4", str(network.network_address), network.prefixlen, "22")]
    if network.prefixlen == 0:
        rules.append(("v6", "::", 0, "22"))
    existing = list(list_api(f"/firewalls/{group}/rules", "firewall_rules"))
    for ip_type, subnet, size, port in rules:
        if any(r.get("ip_type") == ip_type and r.get("protocol") == "tcp" and str(r.get("port")) == port
               and r.get("subnet") == subnet and int(r.get("subnet_size", -1)) == size for r in existing):
            continue
        api("POST", f"/firewalls/{group}/rules", {"ip_type": ip_type, "protocol": "tcp", "port": port,
                                                 "subnet": subnet, "subnet_size": size})
    return group


def deploy(args):
    # Deploy a committed snapshot: no untracked files or local secrets are uploaded.
    if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT).strip():
        raise ValueError("Commit tracked changes before deploying; only HEAD is deployed")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if not os.environ.get("VULTR_API_KEY"):
        raise ValueError("Set VULTR_API_KEY in your environment")
    state = DeploymentState(args.state_file)
    for name in ("instance_id", "volume_id", "firewall_group_id", "object_storage_id", "ssh_key_id"):
        supplied = getattr(args, name)
        recorded = state.data.get(name)
        if supplied and recorded and supplied != recorded:
            raise ValueError(f"--{name.replace('_', '-')} conflicts with this deployment's saved state; use a different --state-file")
    if args.identity_file and state.data.get("identity_file") and Path(args.identity_file).expanduser() != Path(state.data["identity_file"]).expanduser():
        raise ValueError("--identity-file conflicts with saved deployment state; use a different --state-file")
    if state.data.get("region") and state.data["region"] != args.region:
        raise ValueError("Region conflicts with saved deployment state; use a different --state-file")
    state.set(region=args.region)
    args.instance_id = args.instance_id or state.data.get("instance_id")
    args.volume_id = args.volume_id or state.data.get("volume_id")
    ssh_key_id = prepare_ssh(args, state) if not args.instance_id else None
    if args.instance_id and not args.identity_file:
        args.identity_file = state.data.get("identity_file")
        if not args.identity_file:
            raise ValueError("Provide --identity-file for an existing instance without saved local state")
    firewall_id = prepare_firewall(args, state)
    if args.instance_id:
        instance_id = args.instance_id
    else:
        payload = {"region": args.region, "plan": args.plan, "os_id": args.os_id,
                   "label": args.label, "hostname": args.hostname, "sshkey_id": [ssh_key_id],
                   "firewall_group_id": firewall_id,
                   "user_data": base64.b64encode(b"#cloud-config\nssh_pwauth: false\nwrite_files:\n  - path: /etc/ssh/sshd_config.d/00-mapletrace-auth.conf\n    permissions: '0644'\n    content: |\n      PasswordAuthentication no\n      KbdInteractiveAuthentication no\n").decode()}
        instance_id = api("POST", "/instances", payload)["instance"]["id"]
        state.set(instance_id=instance_id)
        print(f"Created billable Vultr instance {instance_id}.", flush=True)
    state.set(instance_id=instance_id, firewall_group_id=firewall_id)
    host = wait_instance(instance_id, args.timeout)
    domain = args.domain or state.data.get("domain") or DEFAULT_DOMAIN
    if not valid_domain(domain):
        raise ValueError("Invalid domain in deployment state")
    state.set(domain=domain)
    print(f"Public IPv4: {host}\nDNS: point the A record for {domain} to {host}.", flush=True)
    if args.instance_id:
        api("PATCH", "/instances/" + instance_id, {"firewall_group_id": firewall_id})
    volume_id, mount_id, created_volume = prepare_volume(args, instance_id, state)
    state.set(volume_id=volume_id)
    print(f"Using block storage {volume_id} for case data.", flush=True)
    bucket, backup = prepare_object_storage(args, state)
    config = env_content(domain)
    print(f"Instance {instance_id} is active at {host}; using https://{domain}/.", flush=True)
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
        for name, content in ((".env", config), ("rclone.conf", backup), ("backup-bucket", bucket.encode())):
            info = tarfile.TarInfo(name)
            info.mode = 0o600
            info.size = len(content)
            archive_file.addfile(info, io.BytesIO(content))
    settings_command = f"umask 077; tar -xf - -C {REMOTE}; chmod 600 {REMOTE}/.env {REMOTE}/rclone.conf {REMOTE}/backup-bucket"
    run(ssh + ["flock -x /run/lock/mapletrace.lock sh -c " + shlex.quote(settings_command)], input=settings.getvalue())
    storage_script = (ROOT / "scripts" / "mount-vultr-storage.sh").read_bytes()
    storage_args = ["sh", "-s", "--", mount_id, "yes" if created_volume else "no",
                    "yes" if args.local_data_migrated else "no"]
    run(ssh + [" ".join(shlex.quote(arg) for arg in storage_args)], input=storage_script)
    if created_volume:
        state.set(created_volume_id=None)
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
until curl -fsS --max-time 10 --resolve {domain}:443:127.0.0.1 https://{domain}/health >/dev/null && \
      curl -fsS --max-time 10 --resolve {domain}:443:127.0.0.1 https://{domain}/api/health >/dev/null; do
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
    print(f"Deployed {revision} to https://{domain}/ (instance {instance_id}).", flush=True)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--env-file", help="deployment environment file (default: scripts/.env if present)")
    p.add_argument("--instance-id", help="reuse an existing instance; avoids creating another billable server")
    p.add_argument("--region", default="ewr", help="Vultr region ID for a new instance")
    p.add_argument("--plan", default="vc2-2c-4gb", help="Vultr plan ID for a new instance")
    p.add_argument("--os-id", type=int, default=2284, help="Ubuntu OS ID for a new instance")
    p.add_argument("--ssh-key-id", help="existing Vultr SSH key ID for a new instance")
    firewall = p.add_mutually_exclusive_group()
    firewall.add_argument("--firewall-group-id", help="existing configured Vultr firewall group ID")
    firewall.add_argument("--ssh-cidr", default="0.0.0.0/0", help="IPv4 SSH source CIDR for a new firewall group")
    p.add_argument("--object-storage-id", help="reuse an existing Vultr Object Storage subscription")
    p.add_argument("--backup-bucket", help="reuse or create this private bucket in the subscription")
    p.add_argument("--label", default="mapletrace")
    p.add_argument("--hostname", default="mapletrace")
    p.add_argument("--identity-file", help="local SSH private key")
    p.add_argument("--timeout", type=int, default=600, help="seconds to wait separately for instance and SSH (default: 600)")
    storage = p.add_mutually_exclusive_group()
    storage.add_argument("--volume-id", help="existing Vultr block storage ID, formatted as ext4")
    storage.add_argument("--volume-size-gb", type=int, default=40, help="create a new billable block storage volume of this size")
    p.add_argument("--volume-type", choices=("high_perf", "storage_opt"), default="high_perf")
    p.add_argument("--local-data-migrated", action="store_true", help="confirm old local Docker volume was migrated or is not needed")
    p.add_argument("--domain", help="public DNS hostname (default: mapletrace.work)")
    p.add_argument("--state-file", default=str(STATE_DIR / "deployment.json"), help="local file storing resource IDs for retries")
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
    if args.domain and not valid_domain(args.domain):
        parser().error("--domain must be a public DNS hostname (no URL, wildcard, IP address, or localhost)")
    if args.ssh_cidr:
        try:
            if ipaddress.ip_network(args.ssh_cidr, strict=False).version != 4:
                raise ValueError("IPv4 required")
        except ValueError:
            parser().error("--ssh-cidr must be an IPv4 CIDR (deployment connects over IPv4)")
    if args.backup_bucket and (not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", args.backup_bucket) or ".." in args.backup_bucket):
        parser().error("--backup-bucket must be a valid bucket name")
    if args.volume_size_gb is not None and args.volume_size_gb <= 0:
        parser().error("--volume-size-gb must be positive")
    if args.timeout <= 0:
        parser().error("--timeout must be positive")
    try:
        load_env_file(args.env_file or DEFAULT_ENV_FILE, required=bool(args.env_file))
        deploy(args)
    except (ValueError, RuntimeError, TimeoutError, OSError, subprocess.CalledProcessError, urllib.error.URLError) as exc:
        print(f"Deployment failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
