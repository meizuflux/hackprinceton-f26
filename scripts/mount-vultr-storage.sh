#!/bin/sh
# Called over SSH with Vultr's mount ID; never guesses a disk by /dev/vd* order.
set -eu
mount_id=$1
new_volume=$2
local_data_migrated=$3
mountpoint=/mnt/mapletrace-data
device=/dev/disk/by-id/virtio-$mount_id

if command -v docker >/dev/null 2>&1 && ! docker info >/dev/null 2>&1; then
    echo "Docker is installed but unavailable; cannot check for existing data" >&2
    exit 1
fi
if command -v docker >/dev/null 2>&1 && docker volume inspect mapletrace_mapletrace-data >/dev/null 2>&1 && [ "$local_data_migrated" != yes ]; then
    echo 'Existing local MapleTrace data volume found. Migrate it before deploying; see scripts/README.md.' >&2
    exit 1
fi

i=0
while [ ! -b "$device" ]; do
    i=$((i + 1))
    [ "$i" -lt 60 ] || { echo "Block device $device did not appear" >&2; exit 1; }
    sleep 5
done

# Accept a filesystem on the disk itself or a single partition. Never format a reused disk.
candidates=$(lsblk -nrpo NAME,FSTYPE "$device" | awk '$2 == "ext4" {print $1}')
count=$(printf '%s\n' "$candidates" | awk 'NF {n++} END {print n+0}')
if [ "$count" -eq 0 ] && [ "$new_volume" = yes ]; then
    # Require an entirely blank, unpartitioned and unmounted disk before formatting.
    [ "$(lsblk -nrpo NAME "$device" | wc -l | tr -d ' ')" = 1 ] || { echo 'New volume contains partitions' >&2; exit 1; }
    signatures=$(wipefs -n --noheadings "$device")
    [ -z "$signatures" ] || { echo 'New volume contains signatures' >&2; exit 1; }
    [ -z "$(lsblk -nrpo MOUNTPOINTS "$device" | tr -d '[:space:]')" ] || { echo 'New volume is mounted' >&2; exit 1; }
    mkfs.ext4 -F "$device"
    candidates=$device
    count=1
fi
[ "$count" -eq 1 ] || { echo 'Expected exactly one ext4 filesystem on the selected volume; refusing to format an existing volume.' >&2; exit 1; }
fs_uuid=$(blkid -s UUID -o value "$candidates")
[ -n "$fs_uuid" ] || { echo 'Cannot determine filesystem UUID' >&2; exit 1; }
mkdir -p "$mountpoint"
if mountpoint -q "$mountpoint"; then
    current_uuid=$(findmnt -n -o UUID --target "$mountpoint")
    [ "$current_uuid" = "$fs_uuid" ] || { echo 'Another filesystem is already mounted at the data mountpoint' >&2; exit 1; }
else
    # Refuse to hide files in an existing directory on the root disk.
    [ -z "$(ls -A "$mountpoint")" ] || { echo 'Data mountpoint is not empty' >&2; exit 1; }
    mount -U "$fs_uuid" "$mountpoint"
fi
# Fail closed on conflicting existing entries instead of changing unrelated mounts.
entry="UUID=$fs_uuid $mountpoint ext4 defaults 0 2"
existing=$(awk -v m="$mountpoint" '$1 !~ /^#/ && $2 == m {print}' /etc/fstab)
if [ -n "$existing" ] && [ "$existing" != "$entry" ]; then
    echo 'Conflicting data mount entry in /etc/fstab' >&2
    exit 1
fi
[ -n "$existing" ] || printf '%s\n' "$entry" >> /etc/fstab
mkdir -p "$mountpoint/mapletrace"
chown 10001:10001 "$mountpoint/mapletrace"
# Docker must never restart containers using the empty root-disk directory on boot.
mkdir -p /etc/systemd/system/docker.service.d
cat > /etc/systemd/system/docker.service.d/mapletrace-storage.conf <<'DROPIN'
[Unit]
RequiresMountsFor=/mnt/mapletrace-data
ConditionPathIsMountPoint=/mnt/mapletrace-data
DROPIN
systemctl daemon-reload
mountpoint -q "$mountpoint"
