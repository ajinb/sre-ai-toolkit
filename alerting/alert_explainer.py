#!/usr/bin/env python3
"""
alert_explainer.py — Prometheus alert → plain-English triage steps via Claude

Usage:
    python alert_explainer.py --alert alert.json
    python alert_explainer.py --stdin          # pipe JSON from stdin
    cat alert.json | python alert_explainer.py --stdin

Output: plain-English explanation + triage checklist written to stdout.
"""

import argparse
import json
import sys
from typing import Any

import anthropic

MODEL = "claude-opus-4-6"

SYSTEM_PROMPT = """You are an expert SRE on-call assistant.
When given a Prometheus alert payload, you:
1. Explain what the alert means in plain English (1-2 sentences, no jargon)
2. Identify the likely root causes (ranked by probability)
3. Provide a numbered triage checklist the on-call engineer should run through
4. State clearly if this is likely a false positive

Be concise. Every word should help the on-call engineer act faster.
Format your response with these exact headers:
## What This Alert Means
## Likely Root Causes
## Triage Checklist
## False Positive Check"""


def load_alert(args: argparse.Namespace) -> dict[str, Any]:
    if args.stdin:
        raw = sys.stdin.read()
    else:
        with open(args.alert) as f:
            raw = f.read()
    return json.loads(raw)


def format_alert_for_prompt(alert: dict[str, Any]) -> str:
    return f"```json\n{json.dumps(alert, indent=2)}\n```"


def explain_alert(alert: dict[str, Any]) -> str:
    client = anthropic.Anthropic()

    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Explain this Prometheus alert and give me triage steps:\n\n{format_alert_for_prompt(alert)}",
            }
        ],
    )
    return message.content[0].text


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Explain a Prometheus alert in plain English using Claude"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--alert", metavar="FILE", help="Path to alert JSON file")
    group.add_argument("--stdin", action="store_true", help="Read alert JSON from stdin")
    args = parser.parse_args()

    alert = load_alert(args)
    explanation = explain_alert(alert)
    print(explanation)


if __name__ == "__main__":
    main()
