"""Tests for log_anomaly_detector pure logic (no API calls)."""

import io
from types import SimpleNamespace


def _args(stdin=False, log=None, lines=150, severity=None):
    return SimpleNamespace(stdin=stdin, log=log, lines=lines, severity=severity)


def test_load_logs_strips_blank_lines(log_anomaly_detector, tmp_path):
    path = tmp_path / "app.log"
    path.write_text("line one\n\n   \nline two\n")
    out = log_anomaly_detector.load_logs(_args(log=str(path)))
    assert out == ["line one", "line two"]


def test_load_logs_severity_filter_is_case_insensitive(log_anomaly_detector, tmp_path):
    path = tmp_path / "app.log"
    path.write_text("INFO started\nerror boom\nWARN slow\ndebug noise\n")
    out = log_anomaly_detector.load_logs(_args(log=str(path), severity="error,warn"))
    assert out == ["error boom", "WARN slow"]


def test_load_logs_tails_requested_number(log_anomaly_detector, tmp_path):
    path = tmp_path / "app.log"
    path.write_text("\n".join(f"line {i}" for i in range(10)) + "\n")
    out = log_anomaly_detector.load_logs(_args(log=str(path), lines=3))
    assert out == ["line 7", "line 8", "line 9"]


def test_load_logs_from_stdin(log_anomaly_detector, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("a\nb\n"))
    out = log_anomaly_detector.load_logs(_args(stdin=True))
    assert out == ["a", "b"]


def test_compute_stats_reports_most_common_token(log_anomaly_detector):
    lines = ["timeout postgres", "timeout postgres", "timeout redis"]
    stats = log_anomaly_detector.compute_stats(lines)
    assert "timeout" in stats
    assert stats.startswith("Top 10 tokens by frequency:")
