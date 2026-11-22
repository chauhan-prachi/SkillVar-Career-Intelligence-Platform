import pytest

from apps.assessments import sandbox
from apps.assessments.models import Question
from apps.assessments.seed_bank import SQL_FIXTURE as FIX

SQL_QUESTIONS = [q for q in __import__("apps.assessments.seed_bank", fromlist=["QUESTIONS"]).QUESTIONS if q["kind"] == "sql"]


@pytest.mark.parametrize("q", SQL_QUESTIONS, ids=lambda q: q["slug"])
def test_every_reference_solution_passes_its_own_grader(q):
    c = q["sql_config"]
    assert sandbox.grade_sql(c["fixture"], c["reference"], c["reference"], c["order_matters"]).passed


def test_wrong_query_fails_with_feedback_that_does_not_leak_the_answer():
    g = sandbox.grade_sql(FIX, "SELECT COUNT(*) FROM orders WHERE status='completed'", "SELECT COUNT(*) FROM orders")
    assert g.score == 0 and "differ" in g.feedback and "8" not in g.feedback


def test_aliases_and_row_order_are_ignored_when_order_does_not_matter():
    assert sandbox.grade_sql(FIX, "SELECT name FROM customers WHERE country='IN'",
                             "SELECT name AS n FROM customers WHERE country='IN' ORDER BY name DESC").passed


def test_wrong_order_gets_partial_credit_when_order_matters():
    g = sandbox.grade_sql(FIX, "SELECT name FROM customers WHERE country='IN' ORDER BY name",
                          "SELECT name FROM customers WHERE country='IN' ORDER BY name DESC", True)
    assert g.score == 0.5


def test_wrong_column_count_is_explained():
    g = sandbox.grade_sql(FIX, "SELECT name FROM customers", "SELECT name, country FROM customers")
    assert g.score == 0 and "column" in g.feedback


@pytest.mark.parametrize("evil", [
    "DROP TABLE customers", "DELETE FROM orders", "INSERT INTO customers VALUES (9,'x','y')", "UPDATE orders SET amount = 0",
    "ATTACH DATABASE '/tmp/x.db' AS x", "PRAGMA table_info(customers)", "SELECT 1; DROP TABLE customers",
    "CREATE TABLE t(x)", "SELECT load_extension('x')", "VACUUM",
])
def test_non_select_and_dangerous_statements_are_rejected(evil):
    g = sandbox.grade_sql(FIX, "SELECT COUNT(*) FROM customers", evil)
    assert g.score == 0 and "could not run" in g.feedback


def test_the_sandbox_is_throwaway_each_time():
    sandbox.grade_sql(FIX, "SELECT 1", "SELECT COUNT(*) FROM orders")
    assert sandbox.run_query(FIX, "SELECT COUNT(*) FROM orders") == [(11,)]


def test_runaway_query_is_interrupted(monkeypatch):
    monkeypatch.setattr(sandbox, "DEADLINE_SECONDS", 0.3)
    g = sandbox.grade_sql(FIX, "SELECT 1", "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM r) SELECT COUNT(*) FROM r")
    assert g.score == 0 and "too long" in g.feedback


@pytest.mark.parametrize("big", ["SELECT length(hex(zeroblob(20000000)))", "SELECT length(randomblob(5000000))", "SELECT 1 " + "+ 1 " * 3000])
def test_resource_exhaustion_expressions_are_rejected(big):
    g = sandbox.grade_sql(FIX, "SELECT 1", big)
    assert g.score == 0 and "could not run" in g.feedback


def test_overlong_answer_rejected():
    assert "longer than" in sandbox.grade_sql(FIX, "SELECT 1", "SELECT 1 -- " + "x" * 6000).feedback


def test_result_size_is_capped(monkeypatch):
    monkeypatch.setattr(sandbox, "MAX_ROWS", 5)
    g = sandbox.grade_sql(FIX, "SELECT 1", "SELECT id FROM orders")
    assert g.score == 0 and "too large" in g.feedback


def test_sql_never_touches_the_application_database(seeded):
    # the sandbox connects only to ':memory:'; the app tables are simply not visible to submitted queries
    g = sandbox.grade_sql(FIX, "SELECT 1", "SELECT * FROM auth_user")
    assert g.score == 0 and "could not run" in g.feedback and Question.objects.exists()
