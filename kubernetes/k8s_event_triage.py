#!/usr/bin/env python3
"""Run `sre-k8s-event-triage` from a source checkout without installing. The code lives in
src/sre_ai_toolkit/k8s_event_triage.py; after `pip install .` use the `sre-k8s-event-triage` command instead."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sre_ai_toolkit.k8s_event_triage import cli

if __name__ == "__main__":
    cli()
