#!/usr/bin/env python3
"""
log_anomaly_detector.py — Log file → AI anomaly summary via Claude

Reads a log file (or stdin), groups lines into a sliding window,
and asks Claude to identify anomalies, error clusters, and patterns
worth investigating. Designed for logs that are too noisy to read manually.

Usage:
    python log_anomaly_detector.py --log app.log
    python log_anomaly_detector.py --log app.log --lines 200
    python log_anomaly_detector.py --log app.log --severity ERROR,WARN
    tail -n 500 /var/log/app.log | python log_anomaly_detector.py --stdin
"""

import argparse
import os
import sys
from collections import Counter

import anthropic

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")
DEFAULT_LINES = 150

SYSTEM_PROMPT = """You are an expert SRE log analyst.
You receive a batch of log lines and produce a triage-ready anomaly report.

Identify:
1. Error clusters (repeated errors that likely share a root cause)
2. Anomalous patterns (things that stand out — timing spikes, unexpected states, cascading failures)
3. Likely root causes for each cluster
4. Lines that most urgently need investigation (with exact log line quoted)
5. Lines that are likely noise and can be ignored

Format your response with these exact sections:
## Error Clusters
## Anomalous Patterns
## Root Cause Hypotheses
## Lines Needing Immediate Attention
## Safe to Ignore

Be specific. Quote exact log lines when calling attention to something."""


def load_logs(args: argparse.Namespace) -> list[str]:
    if args.stdin:
        lines = sys.stdin.readlines()
    else:
        with open(args.log) as f:
            lines = f.readlines()

    lines = [line.rstrip("\n") for line in lines if line.strip()]

    if args.severity:
        keywords = [s.strip().upper() for s in args.severity.split(",")]
        lines = [line for line in lines if any(k in line.upper() for k in keywords)]

    return lines[-args.lines :]  # tail the requested number of lines


def compute_stats(lines: list[str]) -> str:
    """Quick frequency stats to give Claude extra signal."""
    words = []
    for line in lines:
        words.extend(line.split())
    common = Counter(words).most_common(10)
    return f"Top 10 tokens by frequency: {common}"


def analyze_logs(lines: list[str]) -> str:
    client = anthropic.Anthropic()

    log_block = "\n".join(lines)
    stats = compute_stats(lines)

    message = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Analyze these {len(lines)} log lines for anomalies.\n\n"
                    f"Stats: {stats}\n\n"
                    f"Log lines:\n```\n{log_block}\n```"
                ),
            }
        ],
    )
    return message.content[0].text


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect anomalies and error patterns in log files using Claude"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--log", metavar="FILE", help="Path to log file")
    group.add_argument("--stdin", action="store_true", help="Read logs from stdin")
    parser.add_argument(
        "--lines",
        type=int,
        default=DEFAULT_LINES,
        help=f"Number of (tail) lines to analyze (default: {DEFAULT_LINES})",
    )
    parser.add_argument(
        "--severity",
        metavar="LEVELS",
        help="Comma-separated severity filter e.g. ERROR,WARN (case-insensitive)",
    )
    args = parser.parse_args()

    lines = load_logs(args)
    if not lines:
        print("No log lines found after filtering.", file=sys.stderr)
        sys.exit(1)

    print(f"Analyzing {len(lines)} log lines...\n", file=sys.stderr)
    report = analyze_logs(lines)
    print(report)


if __name__ == "__main__":
    main()
