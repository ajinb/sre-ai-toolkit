"""
tf_plan_summary.py — Terraform plan → reviewer brief, with a deterministic risk floor.

Usage:
    terraform plan -out plan.out && terraform show -json plan.out > plan.json
    sre-tf-plan-summary --plan plan.json
    sre-tf-plan-summary --plan plan.json --fail-on high      # CI gate: exit 3 at/above "high"
    terraform show -json plan.out | sre-tf-plan-summary --stdin --format json

The plan is condensed locally before anything is sent: only resource addresses,
types and actions leave the machine, never attribute values (which is where
secrets live). Risk is computed from the plan first, and the model can raise it
but never lower it — a deleted database is "critical" whatever the prose says.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from sre_ai_toolkit.common import add_common_args, ask, run

RISK_LEVELS = ("low", "medium", "high", "critical")

# Resource types whose deletion or replacement loses data or access.
STATEFUL_HINTS = (
    "db_instance",
    "rds_cluster",
    "dynamodb_table",
    "s3_bucket",
    "efs_file_system",
    "ebs_volume",
    "elasticache",
    "redshift",
    "sql_database",
    "storage_account",
    "cosmosdb",
    "bigquery_dataset",
    "spanner",
    "kms_key",
    "secretsmanager_secret",
    "key_vault",
    "persistent_disk",
    "neptune",
    "opensearch",
    "elasticsearch",
)
# Resource types where any change shifts the security boundary.
SECURITY_HINTS = (
    "iam_",
    "security_group",
    "network_acl",
    "firewall",
    "role_assignment",
    "policy",
    "kms_",
    "key_vault_access",
    "public_access_block",
    "bucket_acl",
    "bucket_policy",
    "service_account",
    "vpc_endpoint",
    "waf",
    "route",
)

SYSTEM_PROMPT = """You are a senior platform engineer reviewing a Terraform plan before apply.
You get a condensed plan: change counts, every non-trivial resource change (address, type,
action), and a computed risk floor. Attribute values are deliberately withheld.

Write a review brief for the engineer approving the apply:
- summary: 2-3 sentences on what this plan does overall.
- risk: low, medium, high or critical. Never below the given risk floor.
- notable_changes: the changes a reviewer must look at, most dangerous first, each with why.
- blast_radius: what could break, and for whom, if this goes wrong.
- questions: what the reviewer should confirm before approving.
Name resources by address. Do not invent attribute values."""

BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "risk": {"type": "string", "enum": list(RISK_LEVELS)},
        "notable_changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"address": {"type": "string"}, "why": {"type": "string"}},
                "required": ["address", "why"],
                "additionalProperties": False,
            },
        },
        "blast_radius": {"type": "string"},
        "questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "risk", "notable_changes", "blast_radius", "questions"],
    "additionalProperties": False,
}


def _action(actions: list[str]) -> str:
    if actions == ["no-op"] or actions == ["read"]:
        return actions[0]
    if "delete" in actions and "create" in actions:
        return "replace"
    return actions[0] if len(actions) == 1 else "+".join(actions)


def condense_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Reduce `terraform show -json` output to addresses, types and actions."""
    changes = []
    for rc in plan.get("resource_changes", []):
        action = _action(rc.get("change", {}).get("actions", ["no-op"]))
        if action in ("no-op", "read"):
            continue
        rtype = rc.get("type", "")
        changes.append(
            {
                "address": rc.get("address", "?"),
                "type": rtype,
                "action": action,
                "stateful": any(h in rtype for h in STATEFUL_HINTS),
                "security": any(h in rtype for h in SECURITY_HINTS),
            }
        )
    drift = [d.get("address", "?") for d in plan.get("resource_drift", [])]
    return {
        "terraform_version": plan.get("terraform_version"),
        "counts": dict(Counter(c["action"] for c in changes)),
        "changes": changes,
        "drifted_outside_terraform": drift,
    }


def risk_floor(condensed: dict[str, Any]) -> str:
    changes = condensed["changes"]
    destructive = [c for c in changes if c["action"] in ("delete", "replace")]
    if any(c["stateful"] for c in destructive):
        return "critical"
    if destructive or any(c["security"] for c in changes):
        return "high"
    if changes or condensed["drifted_outside_terraform"]:
        return "medium" if len(changes) > 20 or condensed["drifted_outside_terraform"] else "low"
    return "low"


def max_risk(a: str, b: str) -> str:
    return a if RISK_LEVELS.index(a) >= RISK_LEVELS.index(b) else b


def render_markdown(brief: dict[str, Any], condensed: dict[str, Any]) -> str:
    counts = ", ".join(f"{n} {a}" for a, n in sorted(condensed["counts"].items())) or "no changes"
    lines = [
        f"# Terraform plan review — risk: **{brief['risk'].upper()}**",
        "",
        f"_{counts}_",
        "",
        "## Summary",
        brief["summary"],
        "",
        "## Notable changes",
        *(f"- `{c['address']}` — {c['why']}" for c in brief["notable_changes"]),
        "",
        "## Blast radius",
        brief["blast_radius"],
        "",
        "## Confirm before approving",
        *(f"- [ ] {q}" for q in brief["questions"]),
    ]
    if condensed["drifted_outside_terraform"]:
        lines += [
            "",
            "## Drift detected",
            *(f"- `{a}`" for a in condensed["drifted_outside_terraform"]),
        ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize a Terraform plan for review")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--plan", metavar="FILE", help="`terraform show -json` output")
    group.add_argument("--stdin", action="store_true", help="Read plan JSON from stdin")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument(
        "--fail-on", choices=RISK_LEVELS, help="Exit 3 when the final risk is at or above this"
    )
    add_common_args(parser)
    args = parser.parse_args()

    raw = sys.stdin.read() if args.stdin else Path(args.plan).read_text(encoding="utf-8")
    try:
        plan = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError("expected JSON from `terraform show -json <planfile>`") from e
    condensed = condense_plan(plan)
    floor = risk_floor(condensed)

    if not condensed["changes"] and not condensed["drifted_outside_terraform"]:
        brief = {
            "summary": "No changes.",
            "risk": "low",
            "notable_changes": [],
            "blast_radius": "None.",
            "questions": [],
        }
    else:
        reply = ask(
            args,
            system=SYSTEM_PROMPT,
            user=f"Risk floor: {floor}\n\nCondensed plan:\n```json\n"
            f"{json.dumps(condensed, indent=2)}\n```",
            json_schema=BRIEF_SCHEMA,
        )
        if not reply:  # --dry-run
            return
        brief = json.loads(reply)
        brief["risk"] = max_risk(brief["risk"], floor)

    if args.format == "json":
        print(json.dumps({"risk_floor": floor, **brief, "counts": condensed["counts"]}, indent=2))
    else:
        print(render_markdown(brief, condensed))

    if args.fail_on and RISK_LEVELS.index(brief["risk"]) >= RISK_LEVELS.index(args.fail_on):
        print(f"risk {brief['risk']} is at or above --fail-on {args.fail_on}", file=sys.stderr)
        sys.exit(3)


def cli() -> None:
    run(main)


if __name__ == "__main__":
    cli()
