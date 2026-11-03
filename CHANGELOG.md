# Changelog

## 0.2.0 — 2026-11

### Fixed
- Response text was read from `content[0]`; on current models that is a thinking block and the
  scripts crashed with `AttributeError`.
- The README credited the scripts with Circuit Breaker, Priority Queue and Event Sourcing, which
  they do not implement. That table is gone.

### Added
- Installable package with console scripts: `sre-alert-explain`, `sre-slack-to-incident`,
  `sre-log-anomaly`, `sre-tf-plan-summary`, `sre-k8s-event-triage` (#2). The original script paths
  still run from a clone.
- Shared model controls on every command: `--model`, `--effort`, `--max-tokens`, `--timeout`,
  `--dry-run` (#1).
- End-of-run token and cost summary on stderr (#3).
- `sre-tf-plan-summary`: Terraform plan reviewer brief with a deterministic risk floor and a
  `--fail-on` CI gate; attribute values are never sent (#4).
- `sre-k8s-event-triage`: Warning events grouped, ranked and triaged (#5).
- Structured outputs for JSON mode; refusal fallback; truncation detection; exit codes.

### Changed
- Default model `claude-opus-4-8` → `claude-opus-5-5`; `anthropic>=2.4,<3`.
