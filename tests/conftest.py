"""Shared fixtures: each tool module, imported from the installed package."""

import importlib

import pytest


@pytest.fixture(scope="session")
def alert_explainer():
    return importlib.import_module("sre_ai_toolkit.alert_explainer")


@pytest.fixture(scope="session")
def slack_to_incident():
    return importlib.import_module("sre_ai_toolkit.slack_to_incident")


@pytest.fixture(scope="session")
def log_anomaly_detector():
    return importlib.import_module("sre_ai_toolkit.log_anomaly_detector")
