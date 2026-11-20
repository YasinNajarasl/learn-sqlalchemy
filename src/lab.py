"""Run learner-edited SQLAlchemy code against a copy of the lab database.

This is a local teaching tool, not a security boundary. The child process gets
a small allow-list of builtins and imports, a CPU/memory limit and a wall-clock
timeout. Only requests from the local machine are accepted by ``src.main``.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from sqlalchemy import inspect, text

from .database import engine

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TIMEOUT = float(os.getenv("LAB_TIMEOUT", "8"))

RUNNER = r'''
import json
import os
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

sys.path.insert(0, os.environ["LAB_ROOT"])
sql = []
stdout, stderr = StringIO(), StringIO()
error = None
started = __import__("time").perf_counter()

try:
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (9, 10))
    try:
        limit = 768 * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    except (ValueError, OSError):
        pass
except ImportError:
    pass

try:
    import asyncio
    import builtins as py_builtins
    from sqlalchemy import delete, event, func, insert, inspect, select, text, update
    from sqlalchemy.engine import Engine
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.orm import joinedload, selectinload
    from sqlmodel import Field, Relationship, SQLModel, Session
    from src.database import async_engine, engine
    from src.models import Post, PostTag, Tag, TagCreate, User, UserCreate, utcnow

    def capture(conn, cursor, statement, parameters, context, executemany):
        if len(sql) < 100:
            sql.append({
                "sql": " ".join(statement.split())[:4000],
                "params": str(parameters)[:600],
            })

    event.listen(Engine, "before_cursor_execute", capture)

    allowed = set(
        "abs all any bool bytes callable chr dict divmod enumerate filter float "
        "format frozenset hash hex int isinstance issubclass iter len list map max "
        "min next object ord pow print range repr reversed round set slice sorted "
        "str sum tuple type zip".split()
    )
    safe = {name: getattr(py_builtins, name) for name in allowed if hasattr(py_builtins, name)}
    safe.update({
        "Exception": Exception,
        "ValueError": ValueError,
        "TypeError": TypeError,
        "RuntimeError": RuntimeError,
        "AssertionError": AssertionError,
        "KeyError": KeyError,
        "IndexError": IndexError,
        "StopIteration": StopIteration,
        "NotImplementedError": NotImplementedError,
        "__build_class__": py_builtins.__build_class__,
        "super": super,
    })
    original_import = py_builtins.__import__
    allowed_roots = set(
        "sqlalchemy sqlmodel asyncio datetime decimal json math random itertools "
        "functools collections uuid typing enum re".split()
    )

    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level or name.split(".")[0] not in allowed_roots:
            raise ImportError("This module is not available in the lab: " + name)
        return original_import(name, globals, locals, fromlist, level)

    safe["__import__"] = safe_import
    scope = {
        "__builtins__": safe,
        "__name__": "lab",
        "__doc__": None,
        "engine": engine,
        "Session": Session,
        "select": select,
        "func": func,
        "insert": insert,
        "update": update,
        "delete": delete,
        "text": text,
        "inspect": inspect,
        "event": event,
        "IntegrityError": IntegrityError,
        "selectinload": selectinload,
        "joinedload": joinedload,
        "asyncio": asyncio,
        "create_async_engine": create_async_engine,
        "async_sessionmaker": async_sessionmaker,
        "Base": SQLModel,
        "User": User,
        "Post": Post,
        "Tag": Tag,
        "PostTag": PostTag,
        "post_tags": PostTag.__table__,
        "UserCreate": UserCreate,
        "TagCreate": TagCreate,
        "SQLModel": SQLModel,
        "Field": Field,
        "Relationship": Relationship,
        "utcnow": utcnow,
    }
    with open(os.environ["LAB_CODE"], encoding="utf-8") as handle:
        source = handle.read()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exec(compile(source, "lab.py", "exec"), scope, scope)
except BaseException as exc:
    frames = [
        frame
        for frame in traceback.extract_tb(exc.__traceback__)
        if not frame.filename.endswith("runner.py")
    ]
    error = "".join(traceback.format_list(frames[-8:]))
    error += "".join(traceback.format_exception_only(type(exc), exc))
finally:
    payload = {
        "stdout": stdout.getvalue()[-20000:],
        "stderr": stderr.getvalue()[-8000:],
        "error": error,
        "sql": sql,
        "duration_ms": round((__import__("time").perf_counter() - started) * 1000),
    }
    with open(os.environ["LAB_RESULT"], "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
'''


def _copy_sqlite(source: Path, destination: Path) -> None:
    """Use SQLite's backup API so a copy is consistent even while the app writes."""
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as origin:
        with sqlite3.connect(destination) as copy:
            origin.backup(copy)


def _practice_database() -> tuple[Path, Path]:
    url = engine.url
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise ValueError("Practice mode needs a file-backed SQLite database.")
    source = Path(url.database).expanduser().resolve()
    if not source.exists():
        raise ValueError("The lab database does not exist yet. Open the dashboard once.")
    directory = Path(tempfile.mkdtemp(prefix="sqlalchemy-lab-"))
    destination = directory / "practice.db"
    _copy_sqlite(source, destination)
    return directory, destination


def run_lab(code: str, live: bool = False) -> dict:
    """Execute code in a subprocess and return its output, error and SQL trace."""
    if not code.strip():
        raise ValueError("Write some Python code before running the lab.")
    if len(code) > 20000:
        raise ValueError("Keep lab code under 20,000 characters.")

    directory = Path(tempfile.mkdtemp(prefix="sqlalchemy-lab-"))
    practice_dir = None
    code_file = directory / "user_code.py"
    result_file = directory / "result.json"
    runner_file = directory / "runner.py"
    code_file.write_text(code)
    runner_file.write_text(RUNNER)

    env = os.environ.copy()
    env.update(
        {
            "LAB_ROOT": str(ROOT),
            "LAB_CODE": str(code_file),
            "LAB_RESULT": str(result_file),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    try:
        if not live:
            practice_dir, database = _practice_database()
            env["DATABASE_URL"] = f"sqlite:///{database}"
            env["ASYNC_DATABASE_URL"] = f"sqlite+aiosqlite:///{database}"

        started = time.perf_counter()
        timed_out = False
        try:
            process = subprocess.run(
                [sys.executable, "-B", str(runner_file)],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=DEFAULT_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            timed_out = True
            process = None
        duration_ms = round((time.perf_counter() - started) * 1000)

        payload = {
            "stdout": "",
            "stderr": "",
            "error": None,
            "sql": [],
            "duration_ms": duration_ms,
        }
        if result_file.exists():
            payload.update(json.loads(result_file.read_text()))
        elif process is not None:
            payload["stdout"] = process.stdout[-20000:]
            payload["stderr"] = process.stderr[-8000:]
            if process.returncode:
                payload["error"] = f"The lab process exited with code {process.returncode}."
        if timed_out:
            payload["error"] = (
                f"Execution stopped after {DEFAULT_TIMEOUT:g} seconds. "
                "Check for an infinite loop or a query that never finishes."
            )
    finally:
        shutil.rmtree(directory, ignore_errors=True)
        if practice_dir is not None:
            shutil.rmtree(practice_dir, ignore_errors=True)

    return {
        **payload,
        "mode": "live" if live else "practice",
        "timed_out": timed_out,
    }


def schema_snapshot() -> dict:
    """Describe the current database for the Learn page explorer."""
    inspector = inspect(engine)
    tables = []
    with engine.connect() as connection:
        for name in inspector.get_table_names():
            if name.startswith("sqlite_"):
                continue
            quoted = name.replace('"', '""')
            try:
                count = int(
                    connection.execute(text(f'SELECT COUNT(*) FROM "{quoted}"')).scalar_one()
                )
            except Exception:
                count = None
            tables.append(
                {
                    "name": name,
                    "rows": count,
                    "columns": [
                        {
                            "name": column["name"],
                            "type": str(column["type"]),
                            "nullable": bool(column["nullable"]),
                            "primary_key": bool(column["primary_key"]),
                        }
                        for column in inspector.get_columns(name)
                    ],
                    "foreign_keys": [
                        {
                            "column": key["constrained_columns"][0],
                            "references": (
                                f"{key['referred_table']}.{key['referred_columns'][0]}"
                            ),
                        }
                        for key in inspector.get_foreign_keys(name)
                        if key.get("constrained_columns") and key.get("referred_columns")
                    ],
                }
            )
    return {
        "dialect": engine.dialect.name,
        "url": engine.url.render_as_string(hide_password=True),
        "tables": tables,
    }
