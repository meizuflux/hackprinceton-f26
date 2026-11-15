# Vultr deployment (initial implementation)

This deploys a **single Ubuntu VM** using the Vultr v2 API and builds the repository's Docker images on it. Caddy serves the frontend and proxies `/api` to the backend on the same domain. Caddy obtains and renews a publicly trusted TLS certificate and redirects HTTP to HTTPS. The app has **no authentication**, so anyone who can reach it can access cases and upload data. Use fictional data only. There is no login, rollback, or production hardening. Docker-published ports may bypass host firewall rules; do not rely on UFW alone. The firewall must permit public TCP ports 80 and 443 for certificate issuance and renewal, SSH (22) from the deployment machine, and outbound access for packages and image builds.

## Prerequisites

- Python 3.11+, Git, and an OpenSSH client locally; a Vultr API key exported as `VULTR_API_KEY`.
- An Ubuntu instance with root SSH access, or a Vultr SSH key registered in the account and its matching local private key. Select an Ubuntu OS ID, region, and plan compatible with one another. Choose enough memory and disk for both builds and case data.
- A Vultr region and plan that support Block Storage. A new volume incurs additional charges; an existing volume must contain exactly one ext4 filesystem.
- A public DNS hostname with an A record pointing to the instance. Remove any AAAA record that does not point to the same server. A new instance prints its IP so you can update DNS during setup; retry with its ID if DNS or certificate issuance takes too long.
- A public IPv4 SSH source CIDR for a new Vultr firewall group, or an existing firewall group with appropriate rules. New groups allow TCP 80/443 from IPv4 and IPv6 and SSH only from the supplied CIDR. On existing instances, attaching a different group replaces the current group, so verify access first. Reused groups are not modified or validated.
- A pre-existing **private, unversioned** Vultr Object Storage bucket and its HTTPS endpoint and access keys. The access keys need permission to read bucket versioning and read/write its lifecycle configuration. Buckets with versioning enabled or suspended are rejected because expiration would not guarantee removal of old versions. The script does not create the subscription or bucket. Use a separate location or account for stronger isolation, and configure appropriate access, retention and lifecycle policies.
- Verify the server's SSH host key through a trusted channel and add it to your local `known_hosts`. The script uses your normal SSH host-key policy and never disables verification. When provisioning, it prints the IP before waiting for SSH, allowing you to verify and add the host key in another terminal; otherwise retry with the saved instance ID.
- Commit the desired revision first: only tracked files in `HEAD` are transferred. Tracked changes block deployment; untracked and ignored files are never transferred. The server requires internet access to install Docker and build images.

## Deploy

```sh
export VULTR_API_KEY='...'
export VULTR_OBJECT_ACCESS_KEY='...'
export VULTR_OBJECT_SECRET_KEY='...'
# Optional: live LLM calls; without a key the backend uses recorded responses.
export ANTHROPIC_API_KEY='...'
# Optional: defaults to claude-sonnet-5-5; MAPLETRACE_CORS may also be set.
export MAPLETRACE_LLM_MODEL='claude-sonnet-5-5'

python3 scripts/deploy-vultr.py \
  --region REGION_ID --plan PLAN_ID --os-id UBUNTU_OS_ID \
  --ssh-key-id VULTR_SSH_KEY_ID --identity-file ~/.ssh/id_ed25519 \
  --ssh-cidr YOUR_PUBLIC_IP/32 --domain maple.example.com \
  --volume-size-gb 40 --backup-endpoint https://REGION.vultrobjects.com \
  --backup-bucket PRIVATE_BUCKET
```

Creating an instance and a block volume incurs Vultr charges. The script prints the instance, firewall group, and volume IDs immediately; retain them. A failure or interruption **does not delete any of these resources**, so retry using the same IDs rather than creating duplicates:

```sh
python3 scripts/deploy-vultr.py --instance-id INSTANCE_ID \
  --identity-file ~/.ssh/id_ed25519 --domain maple.example.com --volume-id VOLUME_ID \
  --firewall-group-id FIREWALL_GROUP_ID --backup-endpoint https://REGION.vultrobjects.com \
  --backup-bucket PRIVATE_BUCKET
```

A network error during a create request can leave the result unknown. Firewall creation can also fail after creating only some rules: inspect and complete the group before reusing its ID. Check the Vultr console before retrying to avoid duplicate billable instances. Existing instances must already have Ubuntu, root SSH, and suitable firewall rules. The script uses `root` and installs Docker using Docker's convenience installer if Docker is absent. Existing Docker installations must already include the Compose plugin. Set all desired environment variables on every invocation; omitted optional values are cleared. The backend's upload limit remains 100 MB to match Caddy. Same-origin `/api` requests do not need CORS; set `MAPLETRACE_CORS` only for additional trusted origins.

The script creates or attaches the block volume in the instance region. It formats only a newly created, completely blank disk; an existing volume must already contain one ext4 filesystem. If a retry finds a newly created but unformatted volume, format that specific volume manually after verifying its identity. The mount uses the volume’s Vultr device ID and filesystem UUID. The script configures Docker to require the mount at boot, and the backend uses a directory on the mounted filesystem as `/data`.

The script enables Vultr instance backups and schedules them daily at 03:00 UTC; this can add charges and resets the existing instance backup schedule. These backups cover the instance disk, including Caddy certificate storage, but **not** the attached case-data volume. The script also installs a separate daily case-data backup timer for 03:30 UTC and runs an initial backup before declaring deployment successful. Each backup stops the backend while archiving `/data`, then restarts it before upload. During that interval API requests fail, and running ingestion, analysis, or chat jobs may be interrupted. Ensure the server has enough free primary-disk space for a compressed case archive.

The case archive is sent to the private bucket using rclone. Each run writes a new object. After the first successful backup, deployment merges a rule that expires objects with the `mapletrace-` prefix after 60 days, including pre-existing objects with that prefix. Other lifecycle rules are preserved; avoid concurrent lifecycle edits during deployment. Vultr executes policies daily, so deletion may occur after the 60-day point. The selected bucket must support lifecycle policy changes. Rclone credentials are stored at `/opt/mapletrace/rclone.conf` with mode 0600; root and Docker administrators can read them. Restrict bucket access and set the bucket private. This is a separate backup from the block volume, but restore is not automatic.

The script transfers an archive of the committed revision, writes `/opt/mapletrace/.env` with mode 0600, builds and starts Compose, waits for a valid TLS certificate and checks `/health` and `/api/health` over HTTPS locally, and updates `/opt/mapletrace/current` after success. The Vultr API key stays on the deploying machine. The Anthropic key is sent over SSH and stored on the server; root and Docker administrators can read it. Builds can take several minutes. Failure may leave a partially updated deployment; inspect the logs and redeploy the desired revision. Releases are not automatically pruned.

## Operations

On the server, use:

```sh
cd /opt/mapletrace/current
docker compose --project-name mapletrace --env-file /opt/mapletrace/.env -f scripts/compose.vultr.yaml ps
docker compose --project-name mapletrace --env-file /opt/mapletrace/.env -f scripts/compose.vultr.yaml logs --tail 100
```

Case data persists on the separately billed Vultr block volume across deployments and instance replacement. The volume must be attached in the same region and mounted before Docker can start. Backups must be monitored and restores tested separately. Removing the instance or volume is manual and destructive. Caddy stores certificates in the `mapletrace_caddy-data` volume; preserve it across restarts and include it in backup planning. Access the app at `https://YOUR_DOMAIN/`. If certificate issuance fails, check DNS, firewall access and frontend logs, then retry using the same instance ID.

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
