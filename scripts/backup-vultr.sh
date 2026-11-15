#!/bin/sh
# Stop writes while taking the archive, then resume before transferring it.
set -eu
umask 077
exec 9>/run/lock/mapletrace.lock
flock -x 9
mountpoint -q /mnt/mapletrace-data || { echo 'Case data volume is not mounted' >&2; exit 1; }
cd /opt/mapletrace/current
compose() { docker compose --project-name mapletrace --env-file /opt/mapletrace/.env -f scripts/compose.vultr.yaml "$@"; }
container=$(compose ps -q backend)
[ -n "$container" ] || { echo 'Backend container is missing' >&2; exit 1; }
[ "$(docker inspect -f '{{.State.Running}}' "$container")" = true ] || { echo 'Backend is not running; refusing to change its state' >&2; exit 1; }
mkdir -p /opt/mapletrace/backup-tmp
archive=$(mktemp /opt/mapletrace/backup-tmp/mapletrace-XXXXXXXX.tar.gz)
restart_needed=no
cleanup() {
    if [ "$restart_needed" = yes ]; then
        compose start backend || echo 'ERROR: failed to restart backend; intervention required' >&2
    fi
    rm -f "$archive"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
restart_needed=yes
compose stop -t 60 backend
tar -czf "$archive" -C /mnt/mapletrace-data/mapletrace .
compose start backend
restart_needed=no
bucket=$(cat /opt/mapletrace/backup-bucket)
# Unique object names preserve older copies; retention is managed in the bucket.
name="mapletrace-$(date -u +%Y%m%dT%H%M%SZ)-$(basename "$archive")"
rclone --config /opt/mapletrace/rclone.conf copyto --s3-no-check-bucket "$archive" "vultr:$bucket/$name"
touch /opt/mapletrace/last-backup-success
printf 'Uploaded backup %s\n' "$name"
