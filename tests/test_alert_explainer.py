"""Tests for alert_explainer pure logic (no API calls)."""

import io
import json
from types import SimpleNamespace


def test_format_alert_for_prompt_wraps_json_in_code_fence(alert_explainer):
    alert = {"alertname": "HighErrorRate", "value": "12.4%"}
    out = alert_explainer.format_alert_for_prompt(alert)
    assert out.startswith("```json")
    assert out.endswith("```")
    # the JSON inside the fence round-trips
    inner = out.removeprefix("```json\n").removesuffix("\n```")
    assert json.loads(inner) == alert


def test_load_alert_from_file(alert_explainer, tmp_path):
    alert = {"alertname": "OOMKilled", "pod": "api-3"}
    path = tmp_path / "alert.json"
    path.write_text(json.dumps(alert))
    args = SimpleNamespace(stdin=False, alert=str(path))
    assert alert_explainer.load_alert(args) == alert


def test_load_alert_from_stdin(alert_explainer, monkeypatch):
    alert = {"alertname": "DiskFull"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(alert)))
    args = SimpleNamespace(stdin=True, alert=None)
    assert alert_explainer.load_alert(args) == alert
