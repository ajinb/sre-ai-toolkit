"""Shared test fixtures.

The toolkit scripts live in category folders (some with hyphens, e.g.
``incident-response/``) and are run directly, not installed as a package. So we
load each module from its file path rather than importing it normally.
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relpath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def alert_explainer():
    return _load("alert_explainer", "alerting/alert_explainer.py")


@pytest.fixture(scope="session")
def slack_to_incident():
    return _load("slack_to_incident", "incident-response/slack_to_incident.py")


@pytest.fixture(scope="session")
def log_anomaly_detector():
    return _load("log_anomaly_detector", "observability/log_anomaly_detector.py")
