#!/usr/bin/env python3
"""Merge a 60-day backup expiry rule into a non-versioned S3 bucket."""
import configparser
from pathlib import Path

RULE_ID = "mapletrace-backups-expire-60-days"
PREFIX = "mapletrace-"
RULE = {"ID": RULE_ID, "Filter": {"Prefix": PREFIX}, "Status": "Enabled", "Expiration": {"Days": 60}}


def merge_rules(rules):
    updated = []
    for rule in rules:
        if rule.get("ID") != RULE_ID:
            updated.append(rule)
            continue
        existing_prefix = rule.get("Filter", {}).get("Prefix", rule.get("Prefix"))
        if existing_prefix != PREFIX:
            raise ValueError("Existing MapleTrace lifecycle rule uses a different filter; refusing to replace it")
    return updated + [RULE]


def configure(client, bucket):
    versioning = client.get_bucket_versioning(Bucket=bucket)
    if versioning.get("Status") in ("Enabled", "Suspended"):
        raise ValueError("Backup bucket has or had versioning enabled; use an unversioned bucket to ensure 60-day expiry")
    try:
        rules = client.get_bucket_lifecycle_configuration(Bucket=bucket)["Rules"]
    except client.exceptions.ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "NoSuchLifecycleConfiguration":
            raise
        rules = []
    merged = merge_rules(rules)
    if merged != rules:
        client.put_bucket_lifecycle_configuration(Bucket=bucket, LifecycleConfiguration={"Rules": merged})
    applied = client.get_bucket_lifecycle_configuration(Bucket=bucket)["Rules"]
    if RULE not in applied:
        raise RuntimeError("Could not verify the backup lifecycle rule")


def main():
    import boto3
    from botocore.config import Config

    config = configparser.RawConfigParser()
    config.read("/opt/mapletrace/rclone.conf")
    settings = config["vultr"]
    bucket = Path("/opt/mapletrace/backup-bucket").read_text().strip()
    client = boto3.client("s3", endpoint_url=settings["endpoint"],
                          aws_access_key_id=settings["access_key_id"],
                          aws_secret_access_key=settings["secret_access_key"],
                          region_name="us-east-1", config=Config(s3={"addressing_style": "path"}))
    configure(client, bucket)
    print("Configured 60-day expiration for MapleTrace backups")


if __name__ == "__main__":
    main()
