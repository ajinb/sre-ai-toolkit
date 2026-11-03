"""
slack_to_incident.py — Slack thread → structured incident report via Claude

Accepts a plain-text Slack thread dump (copy-paste from Slack) and produces
a structured incident report ready for Jira, Confluence, or PagerDuty.

Usage:
    sre-slack-to-incident --thread thread.txt
    sre-slack-to-incident --thread thread.txt --format markdown
    sre-slack-to-incident --thread thread.txt --format json
    cat thread.txt | sre-slack-to-incident --stdin
"""

import argparse
import json
import re
import sys
from enum import Enum

from sre_ai_toolkit.common import add_common_args, ask, run


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

JSON_INSTRUCTION = """Fill in every field of the report. Use "Not captured in thread" for text
fields the thread does not cover, and an empty list for list fields."""

_STR = {"type": "string"}
_STR_LIST = {"type": "array", "items": _STR}
REPORT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": _STR,
        "timeline": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"time": _STR, "event": _STR},
                "required": ["time", "event"],
                "additionalProperties": False,
            },
        },
        "impact": _STR,
        "root_cause": _STR,
        "contributing_factors": _STR_LIST,
        "resolution": _STR,
        "action_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"item": _STR, "owner": _STR},
                "required": ["item", "owner"],
                "additionalProperties": False,
            },
        },
        "lessons_learned": _STR_LIST,
    },
    "required": [
        "summary",
        "timeline",
        "impact",
        "root_cause",
        "contributing_factors",
        "resolution",
        "action_items",
        "lessons_learned",
    ],
    "additionalProperties": False,
}


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


def generate_report(thread: str, fmt: OutputFormat, args: argparse.Namespace) -> str:
    is_json = fmt == OutputFormat.JSON
    content = ask(
        args,
        system=SYSTEM_PROMPT,
        user=f"{JSON_INSTRUCTION if is_json else MARKDOWN_INSTRUCTION}\n\nSlack thread:\n\n{thread}",
        json_schema=REPORT_SCHEMA if is_json else None,
    )
    if is_json and content:
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
    add_common_args(parser)
    args = parser.parse_args()

    thread = load_thread(args)
    report = generate_report(thread, OutputFormat(args.format), args)
    if report:
        print(report)


def cli() -> None:
    run(main)


if __name__ == "__main__":
    cli()
