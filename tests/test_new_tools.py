"""Terraform plan condensation/risk floor and Kubernetes event grouping (no API calls)."""

import json
from pathlib import Path

from sre_ai_toolkit import k8s_event_triage as k8s
from sre_ai_toolkit import tf_plan_summary as tf

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_plan_condensation_drops_noop_reads_and_attribute_values():
    plan = json.loads((EXAMPLES / "sample_plan.json").read_text())
    condensed = tf.condense_plan(plan)
    addresses = [c["address"] for c in condensed["changes"]]
    assert "data.aws_caller_identity.current" not in addresses
    assert "aws_s3_bucket.assets" not in addresses
    assert condensed["counts"] == {"replace": 1, "update": 2, "create": 1}
    assert "REDACTED-IN-REAL-PLANS" not in json.dumps(condensed)  # values never leave
    assert condensed["drifted_outside_terraform"] == ["aws_ecs_service.api"]


def test_replacing_a_database_is_critical_regardless_of_model():
    condensed = tf.condense_plan(json.loads((EXAMPLES / "sample_plan.json").read_text()))
    assert tf.risk_floor(condensed) == "critical"
    assert tf.max_risk("low", "critical") == "critical"


def test_security_change_alone_is_high_and_small_additive_plan_is_low():
    sg = {
        "resource_changes": [
            {"address": "a", "type": "aws_security_group", "change": {"actions": ["update"]}}
        ]
    }
    add = {
        "resource_changes": [
            {"address": "b", "type": "aws_cloudwatch_log_group", "change": {"actions": ["create"]}}
        ]
    }
    assert tf.risk_floor(tf.condense_plan(sg)) == "high"
    assert tf.risk_floor(tf.condense_plan(add)) == "low"


def test_events_are_grouped_ranked_and_filtered():
    events = k8s.load_events((EXAMPLES / "sample_events.json").read_text())
    groups = k8s.group_events(events)
    assert [g["reason"] for g in groups] == ["BackOff", "Unhealthy", "FailedScheduling"]
    assert groups[0]["count"] == 42 and "hint" in groups[0]
    assert [g["namespace"] for g in k8s.group_events(events, namespace="batch")] == ["batch"]
    assert len(k8s.group_events(events, include_normal=True)) == 4


def test_repeated_events_for_one_object_collapse_into_one_group():
    ev = {
        "type": "Warning",
        "reason": "BackOff",
        "message": "m",
        "metadata": {"namespace": "x"},
        "involvedObject": {"kind": "Pod", "name": "p"},
    }
    groups = k8s.group_events([ev, ev, ev])
    assert len(groups) == 1 and groups[0]["count"] == 3
