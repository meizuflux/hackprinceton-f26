# Vultr deployment (initial implementation)

This deploys a **single Ubuntu VM** using the Vultr v2 API and builds the repository's Docker images on it. Caddy obtains and renews a publicly trusted TLS certificate and redirects HTTP to HTTPS. The app has **no authentication**, so anyone who can reach it can access cases and upload data. Use fictional data only. There is no login, automated backup, rollback, or production hardening. Docker-published ports may bypass host firewall rules; do not rely on UFW alone. The firewall must permit public TCP ports 80 and 443 for certificate issuance and renewal, SSH (22) from the deployment machine, and outbound access for packages and image builds.

## Prerequisites

- Python 3.11+, Git, and an OpenSSH client locally; a Vultr API key exported as `VULTR_API_KEY`.
- An Ubuntu instance with root SSH access, or a Vultr SSH key registered in the account and its matching local private key. Select an Ubuntu OS ID, region, and plan compatible with one another. Choose enough memory and disk for both builds and case data.
- A public DNS hostname with an A record pointing to the instance. Remove any AAAA record that does not point to the same server. A new instance prints its IP so you can update DNS during setup; retry with its ID if DNS or certificate issuance takes too long.
- An existing Vultr firewall group allowing public TCP 80 and 443, and SSH only from trusted IPs. Pass its ID when creating the instance; this script does not create firewall rules.
- Verify the server's SSH host key through a trusted channel and add it to your local `known_hosts`. The script uses your normal SSH host-key policy and never disables verification. When provisioning, it prints the IP before waiting for SSH, allowing you to verify and add the host key in another terminal; otherwise retry with the saved instance ID.
- Commit the desired revision first: only tracked files in `HEAD` are transferred. Tracked changes block deployment; untracked and ignored files are never transferred. The server requires internet access to install Docker and build images.

## Deploy

```sh
export VULTR_API_KEY='...'
# Optional: live LLM calls; without a key the backend uses recorded responses.
export ANTHROPIC_API_KEY='...'
# Optional: defaults to claude-sonnet-5-5; MAPLETRACE_CORS may also be set.
export MAPLETRACE_LLM_MODEL='claude-sonnet-5-5'

python3 scripts/deploy-vultr.py \
  --region REGION_ID --plan PLAN_ID --os-id UBUNTU_OS_ID \
  --ssh-key-id VULTR_SSH_KEY_ID --identity-file ~/.ssh/id_ed25519 \
  --firewall-group-id FIREWALL_GROUP_ID --domain maple.example.com
```

Creating an instance incurs Vultr charges. The script prints its ID immediately; retain it. A failure or interruption **does not delete the instance**, so retry using the same ID rather than creating another server:

```sh
python3 scripts/deploy-vultr.py --instance-id INSTANCE_ID \
  --identity-file ~/.ssh/id_ed25519 --domain maple.example.com
```

A network error during the create request can leave the result unknown. Check the Vultr console before retrying to avoid duplicate billable instances. Existing instances must already have Ubuntu, root SSH, and suitable firewall rules. The script uses `root` and installs Docker using Docker's convenience installer if Docker is absent. Existing Docker installations must already include the Compose plugin. Set all desired environment variables on every invocation; omitted optional values are cleared. The backend's upload limit remains 100 MB to match nginx. Same-origin `/api` requests do not need CORS; set `MAPLETRACE_CORS` only for additional trusted origins.

The script transfers an archive of the committed revision, writes `/opt/mapletrace/.env` with mode 0600, builds and starts Compose, waits for a valid TLS certificate and checks `/health` and `/api/health` over HTTPS locally, and updates `/opt/mapletrace/current` after success. The Vultr API key stays on the deploying machine. The Anthropic key is sent over SSH and stored on the server; root and Docker administrators can read it. Builds can take several minutes. Failure may leave a partially updated deployment; inspect the logs and redeploy the desired revision. Releases are not automatically pruned.

## Operations

On the server, use:

```sh
cd /opt/mapletrace/current
docker compose --project-name mapletrace --env-file /opt/mapletrace/.env -f scripts/compose.vultr.yaml ps
docker compose --project-name mapletrace --env-file /opt/mapletrace/.env -f scripts/compose.vultr.yaml logs --tail 100
```

Data persists in the `mapletrace_mapletrace-data` Docker volume across deployments and container restarts, but not necessarily instance deletion. Arrange and test backups separately. Removing the instance or volume is manual and destructive. Caddy stores certificates in the `mapletrace_caddy-data` volume; preserve it across restarts and include it in backup planning. Access the app at `https://YOUR_DOMAIN/`. If certificate issuance fails, check DNS, firewall access and proxy logs, then retry using the same instance ID.

Vultr reference: [instance provisioning](https://docs.vultr.com/products/compute/instances/cloud-compute/provisioning) and [firewall groups](https://docs.vultr.com/products/network/firewall-groups/provisioning).
