# Contributing

Contributions welcome. A few ground rules:

## What fits this repo

Scripts that:
- Solve a real SRE problem (not toy examples)
- Use an LLM in a meaningful way (not just wrapping an API call)
- Are standalone and runnable in under 5 minutes
- Include a working example in `examples/`

## Adding a script

1. Fork the repo and create a branch
2. Put your script in the right category folder (`alerting/`, `incident-response/`, `observability/`) or propose a new one
3. Include a docstring at the top with purpose, usage, and output description
4. Add a sample input file to `examples/`
5. Update the README table
6. Open a PR with a one-line description of what the script does

## Standards

- Python 3.11+
- Use `anthropic` SDK directly — no additional LLM frameworks
- No hardcoded API keys — always read from environment variables
- Scripts should fail fast with a clear error message if `ANTHROPIC_API_KEY` is not set

## Questions

Open an issue or reach out at cloudandsre.com.
