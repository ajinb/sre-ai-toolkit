"""
k8s_event_triage.py — Kubernetes Warning events → grouped, ranked triage report.

Usage:
    kubectl get events -A -o json > events.json
    sre-k8s-event-triage --events events.json
    kubectl get events -A -o json | sre-k8s-event-triage --stdin --namespace payments
    sre-k8s-event-triage --events events.json --top 15 --model claude-sonnet-5-5

A noisy cluster emits thousands of events, most of them the same few problems
repeating. Events are grouped locally by (namespace, object, reason) and ranked
by count and recency before anything is sent, so the model reads a short list
of distinct problems instead of a firehose.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from sre_ai_toolkit.common import add_common_args, ask, run

# Well-known reasons and the first thing to check. Given to the model as hints.
REASON_HINTS = {
    "BackOff": "container restarting; check `kubectl logs --previous`",
    "CrashLoopBackOff": "container exits repeatedly; check logs and exit code",
    "OOMKilling": "node OOM killer fired; compare usage with memory limits",
    "OOMKilled": "container exceeded its memory limit",
    "FailedScheduling": "no node fits; check requests, taints, affinity, quotas",
    "ImagePullBackOff": "image pull failing; check tag, registry auth, network",
    "ErrImagePull": "image pull failing; check tag, registry auth, network",
    "FailedMount": "volume mount failing; check PVC binding, secrets, CSI driver",
    "FailedAttachVolume": "volume attach failing; check CSI driver and node limits",
    "Unhealthy": "probe failing; check probe config and app health endpoint",
    "Evicted": "pod evicted under node pressure (disk, memory, PIDs)",
    "NodeNotReady": "node lost readiness; check kubelet, network, pressure",
    "FailedCreatePodSandBox": "CNI or runtime problem creating the pod sandbox",
    "FailedSync": "kubelet failed to sync the pod",
}

SYSTEM_PROMPT = """You are a Kubernetes SRE triaging cluster Warning events.
You get event groups already aggregated by (namespace, object, reason), ranked by count and
recency, with a hint for well-known reasons.

Produce a triage report with these sections:
## Top problems
Rank the distinct problems by user impact, not raw count. Group event groups that share one
cause (e.g. a node problem causing many evictions). For each: what is happening, the likely
cause, and the exact kubectl commands to confirm it.
## Probably noise
Groups that are expected or self-healing, with one line each on why.
## Next steps
An ordered checklist for the on-call engineer.

Only reference namespaces, objects and reasons that appear in the input."""


def _ts(ev: dict[str, Any]) -> str:
    return (
        ev.get("lastTimestamp")
        or ev.get("eventTime")
        or ev.get("series", {}).get("lastObservedTime")
        or ev.get("metadata", {}).get("creationTimestamp")
        or ""
    )


def group_events(
    events: list[dict[str, Any]], *, namespace: str | None = None, include_normal: bool = False
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "last_seen": "", "messages": set()}
    )
    for ev in events:
        if not include_normal and ev.get("type") != "Warning":
            continue
        ns = ev.get("metadata", {}).get("namespace") or ev.get("involvedObject", {}).get(
            "namespace", ""
        )
        if namespace and ns != namespace:
            continue
        obj = ev.get("involvedObject") or ev.get("regarding") or {}
        key = (ns, f"{obj.get('kind', '?')}/{obj.get('name', '?')}", ev.get("reason", "Unknown"))
        g = groups[key]
        g["count"] += int(ev.get("count") or ev.get("series", {}).get("count") or 1)
        g["last_seen"] = max(g["last_seen"], _ts(ev))
        if len(g["messages"]) < 3 and ev.get("message"):
            g["messages"].add(ev["message"][:300])

    ranked = sorted(
        groups.items(), key=lambda kv: (kv[1]["count"], kv[1]["last_seen"]), reverse=True
    )
    return [
        {
            "namespace": ns,
            "object": obj,
            "reason": reason,
            "count": g["count"],
            "last_seen": g["last_seen"],
            "sample_messages": sorted(g["messages"]),
            **({"hint": REASON_HINTS[reason]} if reason in REASON_HINTS else {}),
        }
        for (ns, obj, reason), g in ranked
    ]


def load_events(raw: str) -> list[dict[str, Any]]:
    data = json.loads(raw)
    if isinstance(data, dict):
        return data.get("items", [])
    if isinstance(data, list):
        return data
    raise ValueError("expected `kubectl get events -o json` output (an object with items)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Triage Kubernetes Warning events with Claude")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--events", metavar="FILE", help="`kubectl get events -A -o json` output")
    group.add_argument("--stdin", action="store_true", help="Read events JSON from stdin")
    parser.add_argument("--namespace", help="Only this namespace")
    parser.add_argument("--top", type=int, default=25, help="Event groups to send (default: 25)")
    parser.add_argument("--include-normal", action="store_true", help="Include Normal events")
    add_common_args(parser)
    args = parser.parse_args()

    raw = sys.stdin.read() if args.stdin else Path(args.events).read_text(encoding="utf-8")
    groups = group_events(
        load_events(raw), namespace=args.namespace, include_normal=args.include_normal
    )
    if not groups:
        print("No Warning events found. Nothing to triage.")
        return

    shown = groups[: args.top]
    omitted = len(groups) - len(shown)
    print(
        f"Triaging {len(shown)} event groups ({omitted} lower-ranked omitted)...\n", file=sys.stderr
    )
    report = ask(
        args,
        system=SYSTEM_PROMPT,
        user=f"{len(groups)} distinct Warning event groups; top {len(shown)}:\n```json\n"
        f"{json.dumps(shown, indent=2)}\n```",
    )
    if report:
        print(report)


def cli() -> None:
    run(main)


if __name__ == "__main__":
    cli()
