"""Tests for slack_to_incident pure logic (no API calls)."""

import json

import pytest


def test_extract_json_block_passes_through_plain_json(slack_to_incident):
    raw = '{"summary": "db outage", "impact": "8 min errors"}'
    out = slack_to_incident.extract_json_block(raw)
    assert json.loads(out) == {"summary": "db outage", "impact": "8 min errors"}


def test_extract_json_block_unwraps_fenced_json(slack_to_incident):
    raw = 'Here is the report:\n```json\n{"summary": "ok", "items": [1, 2]}\n```\nDone.'
    out = slack_to_incident.extract_json_block(raw)
    assert json.loads(out) == {"summary": "ok", "items": [1, 2]}


def test_extract_json_block_pretty_prints(slack_to_incident):
    out = slack_to_incident.extract_json_block('{"a":1}')
    assert "\n" in out  # indent=2 produces multi-line output


def test_extract_json_block_raises_on_garbage(slack_to_incident):
    with pytest.raises(json.JSONDecodeError):
        slack_to_incident.extract_json_block("not json at all, no fence either")
