#!/usr/bin/env python3
"""Run `sre-slack-to-incident` from a source checkout without installing. The code lives in
src/sre_ai_toolkit/slack_to_incident.py; after `pip install .` use the `sre-slack-to-incident` command instead."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sre_ai_toolkit.slack_to_incident import cli

if __name__ == "__main__":
    cli()
