"""Pytest configuration.

The FastAPI app creates its engine at import time, so the database URL must be
set before any ``src.*`` import.  A session-scoped temporary directory keeps
the tests away from the real ``blog.db``.
"""

from __future__ import annotations

import os
import shutil
import tempfile

TEST_DB_DIR = tempfile.mkdtemp(prefix="sqlalchemy-lab-tests-")
TEST_DB_PATH = os.path.join(TEST_DB_DIR, "test.db")

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["ASYNC_DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH}"
os.environ["AUTO_SEED"] = "true"
os.environ["SQL_ECHO"] = "false"


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    shutil.rmtree(TEST_DB_DIR, ignore_errors=True)
