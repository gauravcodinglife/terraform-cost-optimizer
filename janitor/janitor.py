#!/usr/bin/env python3
"""
Cost Janitor — detects orphaned / wasteful AWS resources.

Usage:
    python janitor.py                   # dry-run (safe, default)
    python janitor.py --dry-run         # same as above
    python janitor.py --delete          # actually deletes (skips Protected=true)

Exit codes:
    0 — no orphans found
    1 — orphans found (causes CI to fail, which is intentional)
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any

import boto3
from dateutil import parser as dateutil_parser

from constants import (
    EBS_DEFAULT_SIZE_GB,
    EBS_GP2_COST_PER_GB_MONTH,
    EBS_GP3_COST_PER_GB_MONTH,
    EC2_HOURS_PER_MONTH,
    EC2_T3_MICRO_PER_HOUR,
    EIP_IDLE_COST_PER_MONTH,
    PROTECTED_TAG_KEY,
    PROTECTED_TAG_VALUE,
    REQUIRED_TAGS,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def get_tag(tags: list[dict], key: str) -> str | None:
    """Pull a single tag value from the AWS tags list format.
    
    AWS returns tags as: [{"Key": "Project", "Value": "NimbusKart"}, ...]
    This helper makes it easy to look up one tag by key name.
    """
    if not tags:
        return None
    for tag in tags:
        if tag.get("Key") == key:
            return tag.get("Value")
    return None


def is_protected(tags: list[dict]) -> bool:
    """Return True if the resource is tagged Protected=true.
    
    These resources must NEVER be auto-deleted, even in --delete mode.
    """
    return get_tag(tags, PROTECTED_TAG_KEY) == PROTECTED_TAG_VALUE


def get_missing_tags(tags: list[dict]) -> list[str]:
    """Return list of required tag keys that are missing from a resource."""
    present = {t["Key"] for t in (tags or [])}
    return [req for req in REQUIRED_TAGS if req not in present]


def age_in_days(timestamp: datetime | str) -> int:
    """Calculate how many days old a timestamp is from right now."""
    if isinstance(timestamp, str):
        timestamp = dateutil_parser.parse(timestamp)

    # Make sure both datetimes are timezone-aware before subtracting
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    now = datetime.now(tz=timezone.utc)
    return (now - timestamp).days


def tags_as_dict(tags: list[dict]) -> dict:
    """Convert AWS tag list format → plain dict for JSON output."""
    if not tags:
        return {}
    return {t["Key"]: t["Value"] for t in tags}


# ── Scanner functions (one per orphan type) ────────────────────────────────────

def scan_unattached_ebs(ec2_client) -> list[dict]:
    """
    Find EBS volumes in 'available' state — meaning not attached to any instance.
    
    'available' is the AWS state for a volume that exists but isn't mounted.
    These cost money every month even though nothing is using them.
    """
    findings = []

    # Filters tell AWS to only return volumes in 'available' state
    response = ec2_client.describe_volumes(
        Filters=[{"Name": "status", "Values": ["available"]}]
    )

    for vol in response.get("Volumes", []):
        vol_id    = vol["VolumeId"]
        tags      = vol.get("Tags", [])
        size_gb   = vol.get("Size", EBS_DEFAULT_SIZE_GB)
        vol_type  = vol.get("VolumeType", "gp3")
        created   = vol.get("CreateTime", datetime.now(tz=timezone.utc))

        # Calculate cost based on volume type
        if vol_type == "gp2":
            monthly_cost = size_gb * EBS_GP2_COST_PER_GB_MONTH
        else:
            monthly_cost = size_gb * EBS_GP3_COST_PER_GB_MONTH

        findings.append({
            "resource_id":                vol_id,
            "resource_type":              "ebs_volume",
            "reason":                     "unattached",
            "age_days":                   age_in_days(created),
            "estimated_monthly_cost_usd": round(monthly_cost, 2),
            "tags":                       tags_as_dict(tags),
            "suggested_action":           "delete",
            # Safe to auto-delete ONLY if not protected and older than 7 days
            # (guard against deleting volumes created seconds ago by a deploy)
            "safe_to_auto_delete":        (
                not is_protected(tags) and age_in_days(created) > 7
            ),
            # Keep raw tags list for the delete-safety check later
            "_raw_tags":                  tags,
        })

    return findings


def scan_stopped_instances(ec2_client, stopped_threshold_days: int) -> list[dict]:
    """
    Find EC2 instances that have been in 'stopped' state for too long.
    
    A stopped instance doesn't charge for compute, but it still charges for:
    - Its attached EBS volumes
    - Any Elastic IPs associated with it
    
    We flag instances stopped longer than stopped_threshold_days (default 14).
    
    Note: AWS doesn't record *when* an instance was stopped in the standard API.
    We use the launch time as a conservative proxy — the instance is at least
    that old. In production you'd use CloudTrail or CloudWatch Events for
    precise stop timestamps.
    """
    findings = []

    response = ec2_client.describe_instances(
        Filters=[{"Name": "instance-state-name", "Values": ["stopped"]}]
    )

    for reservation in response.get("Reservations", []):
        for inst in reservation.get("Instances", []):
            inst_id    = inst["InstanceId"]
            tags       = inst.get("Tags", [])
            inst_type  = inst.get("InstanceType", "t3.micro")
            launch_time = inst.get("LaunchTime", datetime.now(tz=timezone.utc))
            days_old   = age_in_days(launch_time)

            # Only flag if older than the threshold
            if days_old < stopped_threshold_days:
                continue

            # Rough cost: stopped instances still pay for EBS storage
            # We estimate based on instance type as a proxy
            monthly_cost = EC2_T3_MICRO_PER_HOUR * EC2_HOURS_PER_MONTH

            findings.append({
                "resource_id":                inst_id,
                "resource_type":              "ec2_instance",
                "reason":                     f"stopped for >{stopped_threshold_days} days",
                "age_days":                   days_old,
                "estimated_monthly_cost_usd": round(monthly_cost, 2),
                "tags":                       tags_as_dict(tags),
                "suggested_action":           "terminate or investigate",
                "safe_to_auto_delete":        False,  # Instances are NEVER auto-deleted
                "_raw_tags":                  tags,
            })

    return findings


def scan_unassociated_eips(ec2_client) -> list[dict]:
    """
    Find Elastic IPs (EIPs) not associated with any running instance.
    
    AWS charges for EIPs that are allocated but not in use.
    An idle EIP costs ~$3.60/month — small, but adds up with sprawl.
    """
    findings = []

    response = ec2_client.describe_addresses()

    for eip in response.get("Addresses", []):
        # If AssociationId is missing, the EIP is idle
        if eip.get("AssociationId"):
            continue

        alloc_id = eip.get("AllocationId", eip.get("PublicIp", "unknown"))
        tags     = eip.get("Tags", [])

        findings.append({
            "resource_id":                alloc_id,
            "resource_type":              "elastic_ip",
            "reason":                     "not associated with any instance",
            "age_days":                   0,   # AWS doesn't expose EIP allocation time
            "estimated_monthly_cost_usd": EIP_IDLE_COST_PER_MONTH,
            "tags":                       tags_as_dict(tags),
            "suggested_action":           "release",
            "safe_to_auto_delete":        not is_protected(tags),
            "_raw_tags":                  tags,
        })

    return findings


def scan_missing_tags(ec2_client) -> list[dict]:
    """
    Find any EC2 instance or EBS volume missing required tags.
    
    Required tags: Project, Environment, Owner
    Untagged resources can't be attributed to a team or project,
    which makes cost allocation impossible.
    """
    findings = []

    # ── Check EC2 instances ──
    response = ec2_client.describe_instances()
    for reservation in response.get("Reservations", []):
        for inst in reservation.get("Instances", []):
            # Skip terminated instances — they're already gone
            state = inst.get("State", {}).get("Name", "")
            if state == "terminated":
                continue

            tags    = inst.get("Tags", [])
            missing = get_missing_tags(tags)

            if missing:
                findings.append({
                    "resource_id":                inst["InstanceId"],
                    "resource_type":              "ec2_instance",
                    "reason":                     f"missing tags: {', '.join(missing)}",
                    "age_days":                   age_in_days(inst.get("LaunchTime",
                                                    datetime.now(tz=timezone.utc))),
                    "estimated_monthly_cost_usd": 0.0,
                    "tags":                       tags_as_dict(tags),
                    "suggested_action":           "add missing tags",
                    "safe_to_auto_delete":        False,  # Never delete for missing tags alone
                    "_raw_tags":                  tags,
                })

    # ── Check EBS volumes ──
    vol_response = ec2_client.describe_volumes()
    for vol in vol_response.get("Volumes", []):
        tags    = vol.get("Tags", [])
        missing = get_missing_tags(tags)

        if missing:
            findings.append({
                "resource_id":                vol["VolumeId"],
                "resource_type":              "ebs_volume",
                "reason":                     f"missing tags: {', '.join(missing)}",
                "age_days":                   age_in_days(vol.get("CreateTime",
                                                datetime.now(tz=timezone.utc))),
                "estimated_monthly_cost_usd": 0.0,
                "tags":                       tags_as_dict(tags),
                "suggested_action":           "add missing tags",
                "safe_to_auto_delete":        False,
                "_raw_tags":                  tags,
            })

    return findings


# ── Delete logic ───────────────────────────────────────────────────────────────

def delete_resources(ec2_client, findings: list[dict]) -> None:
    """
    Attempt to delete/release resources flagged as safe_to_auto_delete.
    
    Rules:
    - Only acts on resources where safe_to_auto_delete = True
    - Always skips anything tagged Protected=true (double-check here too)
    - Prints what it's doing so there's an audit trail
    """
    deleted_count = 0

    for finding in findings:
        if not finding.get("safe_to_auto_delete"):
            print(f"  SKIP (not safe): {finding['resource_id']}")
            continue

        # Double-check protection tag even if safe_to_auto_delete was True
        if is_protected(finding.get("_raw_tags", [])):
            print(f"  SKIP (Protected=true): {finding['resource_id']}")
            continue

        rtype = finding["resource_type"]
        rid   = finding["resource_id"]

        try:
            if rtype == "ebs_volume":
                ec2_client.delete_volume(VolumeId=rid)
                print(f"  DELETED EBS volume: {rid}")
                deleted_count += 1

            elif rtype == "elastic_ip":
                ec2_client.release_address(AllocationId=rid)
                print(f"  RELEASED Elastic IP: {rid}")
                deleted_count += 1

            # Note: we never auto-delete EC2 instances — too risky
            # Note: we never auto-delete resources flagged only for missing tags

        except Exception as e:
            # Don't crash the whole script if one delete fails
            print(f"  ERROR deleting {rid}: {e}")

    print(f"\nDeleted/released {deleted_count} resource(s).")


# ── Report generation ──────────────────────────────────────────────────────────

def build_report(findings: list[dict], account_id: str, region: str) -> dict:
    """
    Build the report.json structure required by the assignment spec.
    Strips the internal _raw_tags field before writing output.
    """
    # Remove internal helper fields before outputting
    clean_findings = []
    for f in findings:
        clean = {k: v for k, v in f.items() if not k.startswith("_")}
        clean_findings.append(clean)

    total_waste = sum(f["estimated_monthly_cost_usd"] for f in clean_findings)

    return {
        "scan_timestamp":             datetime.now(tz=timezone.utc).strftime(
                                          "%Y-%m-%dT%H:%M:%SZ"),
        "account_id":                 account_id,
        "region":                     region,
        "summary": {
            "total_orphans":               len(clean_findings),
            "estimated_monthly_waste_usd": round(total_waste, 2),
        },
        "findings": clean_findings,
    }


def write_markdown_summary(report: dict, path: str) -> None:
    """Write a human-readable Markdown summary of the report."""
    lines = [
        "# Cost Janitor Report",
        "",
        f"**Scan time:** {report['scan_timestamp']}",
        f"**Account:** {report['account_id']}",
        f"**Region:** {report['region']}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total orphans found | {report['summary']['total_orphans']} |",
        f"| Estimated monthly waste | ${report['summary']['estimated_monthly_waste_usd']:.2f} |",
        "",
        "## Findings",
        "",
    ]

    if not report["findings"]:
        lines.append("✅ No orphaned resources found.")
    else:
        lines.append("| Resource ID | Type | Reason | Age (days) | Est. Cost/mo | Safe to Delete |")
        lines.append("|-------------|------|--------|------------|--------------|----------------|")
        for f in report["findings"]:
            safe = "✅ Yes" if f["safe_to_auto_delete"] else "⚠️ No"
            lines.append(
                f"| {f['resource_id']} "
                f"| {f['resource_type']} "
                f"| {f['reason']} "
                f"| {f['age_days']} "
                f"| ${f['estimated_monthly_cost_usd']:.2f} "
                f"| {safe} |"
            )

    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"Markdown summary written to: {path}")


# ── Main entry point ───────────────────────────────────────────────────────────

def main():
    # ── Parse command-line arguments ──
    parser = argparse.ArgumentParser(
        description="Cost Janitor — detect and optionally clean up orphaned AWS resources"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Report findings without deleting anything (default)"
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        default=False,
        help="Delete resources marked safe_to_auto_delete (skips Protected=true)"
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region to scan (default: us-east-1)"
    )
    parser.add_argument(
        "--endpoint-url",
        default="http://localhost:4566",
        help="AWS endpoint URL — use LocalStack default or real AWS"
    )
    parser.add_argument(
        "--stopped-days",
        type=int,
        default=14,
        help="Flag EC2 instances stopped longer than this many days (default: 14)"
    )
    parser.add_argument(
        "--output-json",
        default="report.json",
        help="Path for JSON report output"
    )
    parser.add_argument(
        "--output-md",
        default="report.md",
        help="Path for Markdown report output"
    )
    args = parser.parse_args()

    # --delete overrides --dry-run
    dry_run = not args.delete

    print(f"{'='*55}")
    print(f"  Cost Janitor  |  mode: {'DRY RUN' if dry_run else '⚠️  DELETE'}")
    print(f"  Region: {args.region}  |  Endpoint: {args.endpoint_url}")
    print(f"{'='*55}\n")

    # ── Connect to AWS / LocalStack ──
    ec2_client = boto3.client(
        "ec2",
        region_name=args.region,
        endpoint_url=args.endpoint_url,
        aws_access_key_id="test",       # LocalStack accepts any value
        aws_secret_access_key="test",
    )

    # Get account ID (LocalStack returns 000000000000)
    sts_client = boto3.client(
        "sts",
        region_name=args.region,
        endpoint_url=args.endpoint_url,
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    try:
        account_id = sts_client.get_caller_identity()["Account"]
    except Exception:
        account_id = "000000000000"

    # ── Run all scanners ──
    print("🔍 Scanning for unattached EBS volumes...")
    ebs_findings = scan_unattached_ebs(ec2_client)
    print(f"   Found: {len(ebs_findings)}\n")

    print("🔍 Scanning for long-stopped EC2 instances...")
    ec2_findings = scan_stopped_instances(ec2_client, args.stopped_days)
    print(f"   Found: {len(ec2_findings)}\n")

    print("🔍 Scanning for unassociated Elastic IPs...")
    eip_findings = scan_unassociated_eips(ec2_client)
    print(f"   Found: {len(eip_findings)}\n")

    print("🔍 Scanning for missing required tags...")
    tag_findings = scan_missing_tags(ec2_client)
    print(f"   Found: {len(tag_findings)}\n")

    # Combine all findings
    all_findings = ebs_findings + ec2_findings + eip_findings + tag_findings

    # ── Delete mode ──
    if not dry_run and all_findings:
        print("⚠️  DELETE MODE — removing safe resources...\n")
        delete_resources(ec2_client, all_findings)

    # ── Build and write reports ──
    report = build_report(all_findings, account_id, args.region)

    with open(args.output_json, "w") as fh:
        json.dump(report, fh, indent=2, default=str)
    print(f"JSON report written to: {args.output_json}")

    write_markdown_summary(report, args.output_md)

    # ── Print summary ──
    print(f"\n{'='*55}")
    print(f"  Total orphans : {report['summary']['total_orphans']}")
    print(f"  Monthly waste : ${report['summary']['estimated_monthly_waste_usd']:.2f}")
    print(f"{'='*55}")

    # Exit 1 if orphans found (makes CI pipeline fail — this is intentional)
    if report["summary"]["total_orphans"] > 0:
        print("\n⚠️  Orphans found — exiting with code 1 (CI will flag this PR)")
        sys.exit(1)

    print("\n✅ No orphans found.")
    sys.exit(0)


if __name__ == "__main__":
    main()
