# sre-ai-toolkit

[![CI](https://github.com/ajinb/sre-ai-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/ajinb/sre-ai-toolkit/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Curated AI-assisted scripts for SRE teams — alerting, incident response, and observability.

> Blog post: [cloudandsre.com](https://cloudandsre.com) · Built by [Ajin Baby](https://github.com/ajinb)

Each script is standalone, runnable in under 5 minutes, and solves a specific on-call problem using Claude.

---

## Scripts

| Category | Script | What It Does |
|---|---|---|
| alerting | [alert_explainer.py](alerting/alert_explainer.py) | Prometheus alert JSON → plain-English explanation + triage checklist |
| incident-response | [slack_to_incident.py](incident-response/slack_to_incident.py) | Slack thread → structured incident report (markdown or JSON) |
| observability | [log_anomaly_detector.py](observability/log_anomaly_detector.py) | Log file → anomaly clusters + lines needing immediate attention |

---

## Quick Start

**Requirements:** Python 3.11+ · Anthropic API key

```bash
git clone https://github.com/ajinb/sre-ai-toolkit
cd sre-ai-toolkit
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...
```

### Explain a Prometheus alert

```bash
python alerting/alert_explainer.py --alert examples/sample_alert.json
```

```
## What This Alert Means
Your api-server-3 is returning errors at 12.4% — more than double the 5% threshold.
This means roughly 1 in 8 requests is failing right now in production.

## Likely Root Causes
1. Database connection exhaustion (most likely) — downstream dependency overwhelmed
2. Memory pressure causing OOM kills on the pod
3. Upstream traffic spike exceeding capacity

## Triage Checklist
1. Check pod logs: kubectl logs -l app=api-server --since=10m
...
```

### Convert a Slack thread to an incident report

```bash
python incident-response/slack_to_incident.py --thread examples/sample_slack_thread.txt
```

```markdown
# Incident Report

## Summary
A report generation job triggered a full table scan on the events table (200M rows),
exhausting the postgres-primary connection pool and causing 8 minutes of elevated errors...
```

### Detect anomalies in a log file

```bash
python observability/log_anomaly_detector.py --log examples/sample_logs.log
```

```
## Error Clusters
Cluster 1: "connection timeout to postgres-primary" — 9 occurrences across api-server-1, -2, -3
All started at 14:21:30Z. Likely single upstream cause...
```

---

## How It Works

Each script sends your operational data to [Claude](https://anthropic.com) with a system prompt tuned for SRE context. The prompts are designed to:

- Prioritize **actionability** over explanation
- Avoid false confidence — Claude will say "unclear" when it is
- Follow blameless SRE culture (no person-blaming in incident reports)

All processing happens via the Anthropic API. Your logs and alerts are sent to Anthropic's servers — review their [privacy policy](https://www.anthropic.com/privacy) before using with sensitive production data.

---

## Reliability Patterns Implemented

Each script implements specific [Azure WAF](https://learn.microsoft.com/en-us/azure/well-architected/) and [AWS Well-Architected](https://aws.amazon.com/architecture/well-architected/) reliability patterns:

| Script | Patterns |
|---|---|
| alert_explainer | Circuit Breaker (LLM fallback), Priority Queue (P1 before P3) |
| slack_to_incident | Event Sourcing (audit trail), Compensating Transaction awareness |
| log_anomaly_detector | Health Endpoint Monitoring, Anomaly Detection |

---

## Requirements

- Python 3.11+
- `anthropic` Python SDK (`pip install anthropic`)
- `ANTHROPIC_API_KEY` environment variable

No other dependencies. Each script is self-contained.

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | _(required)_ | Your Anthropic API key |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` | Override the model — e.g. `claude-sonnet-4-6` for a cheaper/faster run |

```bash
# Run any script against a cheaper model
ANTHROPIC_MODEL=claude-sonnet-4-6 python alerting/alert_explainer.py --alert examples/sample_alert.json
```

---

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

ruff check .   # lint
pytest -q      # tests (pure logic — no API key or network needed)
```

The test suite covers the pure logic in each script (log filtering, alert
formatting, JSON extraction) and runs offline — no API calls. CI runs the same
`ruff` + `pytest` on Python 3.11, 3.12, and 3.13.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). PRs welcome — especially new scripts in new categories.

---

## License

MIT — see [LICENSE](LICENSE)

---

*Part of the [cloudandsre.com](https://cloudandsre.com) open-source toolkit for AI-native SRE.*
