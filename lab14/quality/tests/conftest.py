"""Спільні фікстури: версія сховища з KB_VERSION (типово clean) або KB_DIR (довільний знімок)."""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kb  # noqa: E402

VERSION = os.environ.get("KB_VERSION", "clean")


@pytest.fixture(scope="session")
def version():
    return VERSION


@pytest.fixture(scope="session")
def rdf():
    return kb.to_rdf(VERSION)


@pytest.fixture(scope="session")
def graph():
    return kb.graph(VERSION)


@pytest.fixture(scope="session")
def corpus():
    return kb.corpus(VERSION)


def pytest_configure(config):
    config.addinivalue_line("markers", "critical: порушення блокує зміну (gate)")
    config.addinivalue_line("markers", "warning: лише у звіті, не блокує")
