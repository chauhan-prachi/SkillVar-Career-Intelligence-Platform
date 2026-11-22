"""Sandboxed auto-grading for SQL tasks.

The learner's query runs against a throw-away in-memory SQLite database that is
built from a fixture. Defences: read-only authorizer (SELECT only; no ATTACH,
PRAGMA, DDL, DML), single statement, wall-clock deadline, row cap. The result
set is compared with the reference solution's result set; expected rows are
never revealed in feedback.
"""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass

MAX_ROWS = 1000
MAX_ANSWER_CHARS = 5000
_LIMITS = {          # SQLite hard limits applied after the fixture is loaded
    "SQLITE_LIMIT_LENGTH": 1_000_000,          # max bytes in any string/blob value
    "SQLITE_LIMIT_SQL_LENGTH": 5_000,
    "SQLITE_LIMIT_EXPR_DEPTH": 50,
    "SQLITE_LIMIT_COMPOUND_SELECT": 10,
    "SQLITE_LIMIT_FUNCTION_ARG": 20,
}
DEADLINE_SECONDS = 1.0

_OK, _DENY = sqlite3.SQLITE_OK, sqlite3.SQLITE_DENY
_ALLOWED_ACTIONS = {
    getattr(sqlite3, "SQLITE_SELECT", 21),
    getattr(sqlite3, "SQLITE_READ", 20),
    getattr(sqlite3, "SQLITE_FUNCTION", 31),
    getattr(sqlite3, "SQLITE_RECURSIVE", 33),
}


@dataclass
class Grade:
    score: float
    feedback: str

    @property
    def passed(self) -> bool:
        return self.score >= 1.0


class QueryError(Exception):
    pass


def _norm(v):
    return round(v, 2) if isinstance(v, float) else v


def run_query(fixture_sql: str, query: str) -> list[tuple]:
    """Execute ``query`` read-only against a fresh DB built from ``fixture_sql``."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(fixture_sql)
        for name, value in _LIMITS.items():
            conn.setlimit(getattr(sqlite3, name), value)   # requires Python >= 3.11
        conn.execute("PRAGMA query_only = ON")
        conn.set_authorizer(lambda action, *_: _OK if action in _ALLOWED_ACTIONS else _DENY)
        deadline = time.monotonic() + DEADLINE_SECONDS
        conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 1000)
        try:
            rows = conn.execute(query).fetchmany(MAX_ROWS + 1)
        except sqlite3.Error as exc:
            msg = str(exc)
            if "interrupted" in msg:
                msg = "query took too long (possible infinite loop or missing join condition)"
            elif "too big" in msg or "too long" in msg or "too large" in msg or "too complex" in msg:
                msg = "query is too large or complex for the sandbox"
            elif "not authorized" in msg:
                msg = "only a single read-only SELECT query is allowed"
            raise QueryError(msg) from None
        except sqlite3.Warning as exc:  # multiple statements
            raise QueryError("only a single SELECT statement is allowed") from exc
        except sqlite3.ProgrammingError as exc:
            raise QueryError("only a single SELECT statement is allowed") from exc
        if len(rows) > MAX_ROWS:
            raise QueryError(f"result too large (more than {MAX_ROWS} rows)")
        return [tuple(_norm(v) for v in r) for r in rows]
    finally:
        conn.close()


def grade_sql(fixture_sql: str, reference_sql: str, answer: str, order_matters: bool = False) -> Grade:
    if len(answer) > MAX_ANSWER_CHARS:
        return Grade(0.0, f"Your query could not run: longer than {MAX_ANSWER_CHARS} characters.")
    expected = run_query(fixture_sql, reference_sql)
    try:
        got = run_query(fixture_sql, answer)
    except QueryError as exc:
        return Grade(0.0, f"Your query could not run: {exc}.")
    if expected and got and len(expected[0]) != len(got[0]):
        return Grade(0.0, f"Expected {len(expected[0])} column(s) but your query returns {len(got[0])}.")
    key = lambda r: tuple(repr(x) for x in r)  # noqa: E731
    same_multiset = sorted(expected, key=key) == sorted(got, key=key)
    if same_multiset and (not order_matters or expected == got):
        return Grade(1.0, "Correct.")
    if same_multiset:
        return Grade(0.5, "Right rows, but the required ordering is not satisfied.")
    if len(got) != len(expected):
        return Grade(0.0, f"Expected {len(expected)} row(s) but got {len(got)}. "
                          "Check filters, join type and duplicates.")
    return Grade(0.0, "Right number of rows, but some values differ. Check your conditions and calculations.")
