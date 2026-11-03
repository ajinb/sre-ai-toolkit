# sre-ai-toolkit

[![CI](https://github.com/ajinb/sre-ai-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/ajinb/sre-ai-toolkit/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Curated AI-assisted scripts for SRE teams — alerting, incident response, and observability.

> Blog post: [cloudandsre.com](https://cloudandsre.com) · Built by [Ajin Baby](https://github.com/ajinb)

Each tool is a single command that solves one specific on-call problem using Claude, runnable in
under 5 minutes. They share one set of model controls and report what every run cost.

---

## Scripts

| Category | Command | What it does |
|---|---|---|
| alerting | `sre-alert-explain` ([source](src/sre_ai_toolkit/alert_explainer.py)) | Prometheus alert JSON → plain-English explanation + triage checklist |
| incident-response | `sre-slack-to-incident` ([source](src/sre_ai_toolkit/slack_to_incident.py)) | Slack thread → structured incident report (markdown, or schema-constrained JSON) |
| observability | `sre-log-anomaly` ([source](src/sre_ai_toolkit/log_anomaly_detector.py)) | Log file → anomaly clusters + lines needing immediate attention |
| infrastructure | `sre-tf-plan-summary` ([source](src/sre_ai_toolkit/tf_plan_summary.py)) | `terraform show -json` → reviewer brief with a deterministic risk floor and a `--fail-on` CI gate. Attribute values never leave the machine |
| kubernetes | `sre-k8s-event-triage` ([source](src/sre_ai_toolkit/k8s_event_triage.py)) | `kubectl get events -o json` → Warning events grouped by object and reason, ranked, then triaged |

---

## Quick Start

**Requirements:** Python 3.11+ · Anthropic API key

```bash
pip install "git+https://github.com/ajinb/sre-ai-toolkit@main"   # PyPI release pending
export ANTHROPIC_API_KEY=sk-ant-...
```

Working from a clone instead? `python alerting/alert_explainer.py …` and the other paths still
run without installing.

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

## Shared controls

Every command takes the same model flags and prints a one-line usage summary to stderr when it
finishes:

| Flag | Env var | Default | Purpose |
|---|---|---|---|
| `--model` | `ANTHROPIC_MODEL` | `claude-opus-5-5` | Any Claude model, e.g. `claude-sonnet-5-5` for cheaper/faster runs |
| `--effort` | `SRE_AI_EFFORT` | `medium` | Thinking depth: `low` … `max` |
| `--max-tokens` | `SRE_AI_MAX_TOKENS` | `16000` | Output cap per call (thinking included) |
| `--timeout` | `SRE_AI_TIMEOUT` | `120` | Request timeout, seconds |
| `--dry-run` | — | off | Print the exact request and exit — no API call, no cost |
| `--no-usage` | — | off | Suppress the `[usage] … in, … out · est. $…` line |

```text
[usage] claude-opus-5-5: 2,184 in, 611 out · est. $0.0210
```

The estimate uses [`cloudandsre.cost`](https://github.com/ajinb/cloudandsre-python) when it is
installed, and a built-in table of current models otherwise.

Behaviour common to every command:

- **Refusals are surfaced, not printed as output.** On models that support it, a declined request
  is re-run server-side on Anthropic's recommended fallback (`fallbacks: "default"`); a refusal
  that survives exits with code 4.
- **Truncation is an error.** A reply cut off at `--max-tokens` exits 4 instead of printing half a report.
- **JSON output is schema-constrained** by the API (structured outputs), not parsed out of prose.
- Exit codes: `0` ok · `1` bad input · `3` risk gate tripped (`sre-tf-plan-summary --fail-on`) · `4` model/API failure.

### Terraform plan review in CI

```yaml
- run: terraform plan -out plan.out && terraform show -json plan.out > plan.json
- run: sre-tf-plan-summary --plan plan.json --fail-on critical >> "$GITHUB_STEP_SUMMARY"
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

The risk floor comes from the plan itself: replacing or deleting a stateful resource (databases,
buckets, volumes, keys) is `critical`; any destroy or security-boundary change (IAM, security
groups, firewall rules, policies) is at least `high`. The model can raise the risk, never lower it.

All processing happens via the Anthropic API. Inputs are sent to Anthropic's servers — review
their [privacy policy](https://www.anthropic.com/privacy) before using with sensitive production data.

---

## Requirements

- Python 3.11+
- `anthropic` Python SDK 2.x (installed automatically)
- `ANTHROPIC_API_KEY` environment variable

---

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

ruff check .   # lint
pytest -q      # tests (pure logic — no API key or network needed)
```

The suite runs offline. Pure logic (log filtering, plan condensation, event grouping, JSON
extraction) is tested directly; the shared Claude call is exercised through the real Anthropic SDK
against a mock transport, so an SDK signature change fails CI rather than a user's first run.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). PRs welcome — especially new scripts in new categories.

---

## License

MIT — see [LICENSE](LICENSE)

---

*Part of the [cloudandsre.com](https://cloudandsre.com) open-source toolkit for AI-native SRE.*
