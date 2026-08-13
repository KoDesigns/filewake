from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_WORKSPACE = Path(tempfile.gettempdir()) / "converter-tests"
os.environ["WORKSPACE_ROOT"] = str(TEST_WORKSPACE)
os.environ["MAX_FILE_SIZE_MB"] = "1"
os.environ["MAX_OUTPUT_SIZE_MB"] = "2"

from backend.config import get_settings  # noqa: E402
from backend.main import app  # noqa: E402


@pytest.fixture
def client():
    get_settings.cache_clear()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def workspace_root() -> Path:
    return TEST_WORKSPACE
