#!/usr/bin/env python3
"""Run `sre-log-anomaly` from a source checkout without installing. The code lives in
src/sre_ai_toolkit/log_anomaly_detector.py; after `pip install .` use the `sre-log-anomaly` command instead."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sre_ai_toolkit.log_anomaly_detector import cli

if __name__ == "__main__":
    cli()
