#!/usr/bin/env python3
"""
slack_to_incident.py — Slack thread → structured incident report via Claude

Accepts a plain-text Slack thread dump (copy-paste from Slack) and produces
a structured incident report ready for Jira, Confluence, or PagerDuty.

Usage:
    python slack_to_incident.py --thread thread.txt
    python slack_to_incident.py --thread thread.txt --format markdown
    python slack_to_incident.py --thread thread.txt --format json
    cat thread.txt | python slack_to_incident.py --stdin
"""

import argparse
import json
import os
import re
import sys
from enum import Enum

import anthropic

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")


class OutputFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"


SYSTEM_PROMPT = """You are an expert SRE incident analyst specializing in blameless post-mortems.
You receive raw Slack thread messages from an incident channel and produce a structured incident report.

Extract and synthesize:
- Incident timeline (key events with approximate times)
- Impact (what was affected, estimated user/revenue impact if mentioned)
- Root cause (or "Under Investigation" if unclear)
- Contributing factors
- Resolution steps taken
- Action items (with owner if mentioned)
- Lessons learned

Rules:
- Do not assign blame to individuals
- Use "the service" or "the system" instead of person's names for errors
- If information is not present, write "Not captured in thread"
- Keep action items specific and actionable"""

MARKDOWN_INSTRUCTION = """Format the report as clean markdown with these sections:
# Incident Report

## Summary
## Timeline
## Impact
## Root Cause
## Contributing Factors
## Resolution
## Action Items
## Lessons Learned"""

JSON_INSTRUCTION = """Return a JSON object with these exact keys:
summary, timeline (list of {time, event}), impact, root_cause,
contributing_factors (list), resolution, action_items (list of {item, owner}), lessons_learned (list)"""


def load_thread(args: argparse.Namespace) -> str:
    if args.stdin:
        return sys.stdin.read()
    with open(args.thread) as f:
        return f.read()


def extract_json_block(content: str) -> str:
    """Return pretty-printed JSON from model output.

    Accepts either a bare JSON object or JSON wrapped in a ```json fenced code
    block (Claude sometimes wraps it). Raises ``json.JSONDecodeError`` if no
    valid JSON can be recovered.
    """
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", content)
        if not match:
            raise
        parsed = json.loads(match.group(1))
    return json.dumps(parsed, indent=2)


def generate_report(thread: str, fmt: OutputFormat) -> str:
    client = anthropic.Anthropic()

    format_instruction = MARKDOWN_INSTRUCTION if fmt == OutputFormat.MARKDOWN else JSON_INSTRUCTION

    message = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"{format_instruction}\n\nSlack thread:\n\n{thread}",
            }
        ],
    )
    content = message.content[0].text

    if fmt == OutputFormat.JSON:
        return extract_json_block(content)

    return content


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a Slack incident thread into a structured incident report"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--thread", metavar="FILE", help="Path to Slack thread text file")
    group.add_argument("--stdin", action="store_true", help="Read Slack thread from stdin")
    parser.add_argument(
        "--format",
        choices=[f.value for f in OutputFormat],
        default=OutputFormat.MARKDOWN,
        help="Output format (default: markdown)",
    )
    args = parser.parse_args()

    thread = load_thread(args)
    report = generate_report(thread, OutputFormat(args.format))
    print(report)


if __name__ == "__main__":
    main()
