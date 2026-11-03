#!/usr/bin/env python3
"""Run `sre-tf-plan-summary` from a source checkout without installing. The code lives in
src/sre_ai_toolkit/tf_plan_summary.py; after `pip install .` use the `sre-tf-plan-summary` command instead."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sre_ai_toolkit.tf_plan_summary import cli

if __name__ == "__main__":
    cli()
