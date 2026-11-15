# Vultr deployment

This deploys a **single Ubuntu VM** using the Vultr API and builds the Docker images on it. Caddy serves the frontend and proxies `/api` to the backend on the same HTTPS domain. The app has **no authentication**, so anyone who can reach it can access cases and upload data. Use fictional data only.

## Run

Install Python 3.11+, Git, and OpenSSH locally. Commit the desired revision first: the script transfers only tracked files in `HEAD` and rejects tracked uncommitted changes. Set the Vultr API key and run:

```sh
export VULTR_API_KEY='...'
python3 scripts/deploy-vultr.py
```

The API key must be permitted to manage instances, SSH keys, firewall groups, block storage, Object Storage subscriptions and buckets. The default run creates **billable** resources: an `ewr` (New Jersey) `vc2-2c-4gb` instance, a 40 GB high-performance block volume, and a Standard Object Storage subscription. Confirm availability and pricing for your account before running it. The script provisions a private bucket and retrieves its S3 credentials from Vultr; separate object-storage credentials are not needed.

The script generates an unencrypted Ed25519 SSH key under `~/.local/state/mapletrace-vultr/`, registers its public key with Vultr, and saves resource IDs (not API or S3 credentials) in `~/.local/state/mapletrace-vultr/deployment.json`. Protect and back up the local private key. SSH uses `StrictHostKeyChecking=accept-new`: the first observed host key is trusted, then later changes are rejected. This is convenient but does not independently authenticate the first connection; for stronger verification, add the host key to `known_hosts` through a trusted channel first.

New firewall groups allow SSH and web ports from anywhere. Newly created Ubuntu instances disable SSH password and keyboard-interactive authentication through cloud-init; SSH requires the private key. Existing instances are not reconfigured, so verify their SSH settings before exposing them. Pass `--ssh-cidr YOUR_IPV4/32` to restrict SSH when your IP is stable. The script only adds managed firewall rules: changing an existing group's CIDR does not remove older rules. `--firewall-group-id` reuses an existing group without changing it; verify its rules before attaching it to an instance. Docker-published ports can bypass host firewall rules.

The default domain is `mapletrace.work`. As soon as the instance is active, the script prints its public IPv4 address and the A record to create. At your DNS provider, point the `mapletrace.work` A record (usually host `@`) to that address, and remove any AAAA record that points elsewhere. DNS must resolve to the instance before Caddy can obtain its TLS certificate. If propagation takes longer than the deployment wait, rerun the same command after DNS is ready; saved resource IDs prevent creating duplicates. To use another domain, pass `--domain your-domain.example`. Ports 80 and 443 must be publicly reachable.

Optional values can be overridden: `--region`, `--plan`, `--os-id`, `--volume-size-gb`, `--identity-file`, `--ssh-key-id`, `--firewall-group-id`, `--object-storage-id`, `--backup-bucket`, and `--domain`. The default `--os-id 2284` is Ubuntu 24.04 LTS x64. Run `python3 scripts/deploy-vultr.py --help` for all options. Existing volumes must contain one ext4 filesystem, and an existing bucket must be private and unversioned. Do not use an existing bucket unless its lifecycle rules and backup prefix are appropriate.

For live, uncached LLM calls, optionally export `ANTHROPIC_API_KEY`. `MAPLETRACE_LLM_MODEL` and `MAPLETRACE_CORS` are also optional. Set all desired optional variables on every invocation; omitted values are cleared from the server configuration. No application authentication is provided.

Re-run the same command to reuse resources recorded in the local state file. Use `--state-file PATH` for a separate deployment; changing to a different file can create additional billable resources. The script prints resource IDs as they are created. If a create request times out, the remote outcome may be unknown and an ID may not be saved; inspect the Vultr console before retrying to avoid duplicates. Resources are not automatically deleted. Existing instances must already have Ubuntu and root SSH access; when reusing one without saved state, pass `--identity-file` and `--instance-id` as well as the other existing resource IDs. A partial deployment may need manual recovery; the initial version has not been tested against a live account.

The script creates or attaches the block volume in the instance region. It formats only a newly created, completely blank disk; an existing volume must already contain one ext4 filesystem. A volume created by this deployment remains eligible for initialization on retry until it has been mounted; reused volumes are never automatically formatted. The mount uses the volume’s Vultr device ID and filesystem UUID. The script configures Docker to require the mount at boot, and the backend uses a directory on the mounted filesystem as `/data`.

The script installs a daily case-data backup timer for 03:30 UTC and runs an initial backup before declaring deployment successful. It does not configure Vultr instance backups; the instance can be rebuilt from the repository and deployment script, while Caddy obtains certificates again. Each backup stops the backend while archiving `/data`, then restarts it before upload. During that interval API requests fail, and running ingestion, analysis, or chat jobs may be interrupted. Ensure the server has enough free primary-disk space for a compressed case archive.

The case archive is sent to the private bucket using rclone. Each run writes a new object. After the first successful backup, deployment merges a rule that expires objects with the `mapletrace-` prefix after 60 days, including pre-existing objects with that prefix. Other lifecycle rules are preserved; avoid concurrent lifecycle edits during deployment. Vultr executes policies daily, so deletion may occur after the 60-day point. The selected bucket must support lifecycle policy changes. Rclone credentials are stored at `/opt/mapletrace/rclone.conf` with mode 0600; root and Docker administrators can read them. Restrict bucket access and set the bucket private. This is a separate backup from the block volume, but restore is not automatic.

The script transfers an archive of the committed revision, writes `/opt/mapletrace/.env` with mode 0600, builds and starts Compose, waits for a valid TLS certificate and checks `/health` and `/api/health` over HTTPS locally, and updates `/opt/mapletrace/current` after success. The Vultr API key stays on the deploying machine. The Anthropic key is sent over SSH and stored on the server; root and Docker administrators can read it. Builds can take several minutes. Failure may leave a partially updated deployment; inspect the logs and redeploy the desired revision. Releases are not automatically pruned.

## Operations

On the server, use:

```sh
cd /opt/mapletrace/current
docker compose --project-name mapletrace --env-file /opt/mapletrace/.env -f scripts/compose.vultr.yaml ps
docker compose --project-name mapletrace --env-file /opt/mapletrace/.env -f scripts/compose.vultr.yaml logs --tail 100
```

Case data persists on the separately billed Vultr block volume across deployments and instance replacement. The volume must be attached in the same region and mounted before Docker can start. Backups must be monitored and restores tested separately. Removing the instance or volume is manual and destructive. Caddy stores certificates in the `mapletrace_caddy-data` volume; preserve it across restarts. The script prints the app URL after deployment. If certificate issuance fails, check DNS, firewall access and frontend logs, then retry using the same instance ID.

Vultr reference: [instance provisioning](https://docs.vultr.com/products/compute/instances/cloud-compute/provisioning) and [firewall groups](https://docs.vultr.com/products/network/firewall-groups/provisioning).

## Migrating an earlier deployment

Earlier versions stored case data in the local Docker volume `mapletrace_mapletrace-data`. The deploy script refuses to switch while that volume exists unless `--local-data-migrated` is supplied. Do not remove the old volume until the copy has been verified and backed up.

1. Stop writes: `docker compose --project-name mapletrace --env-file /opt/mapletrace/.env -f /opt/mapletrace/current/scripts/compose.vultr.yaml stop backend`.
2. Attach and mount the chosen ext4 Vultr block volume at `/mnt/mapletrace-data` following [Vultr's Linux mounting guide](https://docs.vultr.com/products/storage/block-storage/mount/linux). Mount it manually for the copy; the deploy script creates its own `/etc/fstab` entry. Verify the device identity and filesystem before formatting; formatting destroys data.
3. Create `/mnt/mapletrace-data/mapletrace` and copy the old volume contents with `cp -a "$(docker volume inspect -f '{{.Mountpoint}}' mapletrace_mapletrace-data)/." /mnt/mapletrace-data/mapletrace/`. Verify the copy and its ownership; the backend runs as UID 10001. Preserve a separate backup.
4. Retry deployment with `--volume-id VOLUME_ID --local-data-migrated` and the other required arguments. Keep using that flag while the old local volume exists. The script verifies the mounted filesystem matches the selected Vultr volume before starting services.

## Backups and recovery

Inspect the timer and last run with:

```sh
systemctl status mapletrace-backup.timer
journalctl -u mapletrace-backup.service -n 100 --no-pager
sudo systemctl start mapletrace-backup.service
rclone --config /opt/mapletrace/rclone.conf lsf vultr:PRIVATE_BUCKET
```

A successful deployment runs one backup immediately; later runs follow the timer. Failed jobs are recorded in the journal. Check the journal and bucket regularly. The filesystem must be mounted and the backend running for the job to run. Backup files are stored in the bucket without client-side encryption; protect the bucket and credentials. The archive is temporarily written on the instance's primary disk and deleted after the run.

To test a restore without touching live data, download an archive with `rclone --config /opt/mapletrace/rclone.conf copyto vultr:PRIVATE_BUCKET/OBJECT_NAME /tmp/mapletrace-restore.tar.gz`, extract it into a new empty temporary directory with `tar -xzf`, and verify the case contents and database integrity. To restore live data, stop the backend and timer, preserve a backup of the current volume, verify the target mount and archive, restore to an empty directory on the mounted volume, set ownership for UID 10001, then restart the backend and timer. Never overwrite the live case directory while the backend is writing. Practice this process before relying on it.
