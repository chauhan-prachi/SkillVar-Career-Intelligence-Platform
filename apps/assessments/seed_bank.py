"""Seed assessments. SQL items are executed in a sandbox; multiple-choice items are weighted lower (guessable)."""

SQL_FIXTURE = """
CREATE TABLE customers(id INTEGER PRIMARY KEY, name TEXT, country TEXT);
INSERT INTO customers VALUES (1,'Asha','IN'),(2,'Ben','US'),(3,'Chen','CN'),(4,'Divya','IN'),(5,'Elena','US'),(6,'Farid','IN');
CREATE TABLE orders(id INTEGER PRIMARY KEY, customer_id INTEGER, order_date TEXT, amount REAL, status TEXT);
INSERT INTO orders VALUES
 (101,1,'2026-01-05',120.0,'completed'),(102,1,'2026-02-10',80.0,'completed'),(103,1,'2026-03-15',300.0,'cancelled'),
 (104,2,'2026-01-20',250.0,'completed'),(105,2,'2026-02-25',400.0,'completed'),(106,3,'2026-01-11',60.0,'completed'),
 (107,3,'2026-04-02',90.0,'pending'),(108,4,'2026-02-02',500.0,'completed'),(109,4,'2026-03-03',150.0,'completed'),
 (110,4,'2026-04-04',50.0,'completed'),(111,5,'2026-03-09',700.0,'cancelled');
"""
SCHEMA = "customers(id, name, country)\norders(id, customer_id, order_date, amount, status)   -- status: completed | cancelled | pending"

ASSESSMENTS = [
    ("python-fundamentals", "Python fundamentals", "Core Python behaviour that trips up beginners.", 1),
    ("sql-concepts", "SQL concepts", "How SQL behaves: NULLs, joins, aggregation, windows and indexes.", 2),
    ("sql-practice", "SQL practice (executed)", "Write real queries. They run against a sandboxed sample database.", 3),
    ("database-concepts", "Database concepts", "Keys, normalization, ACID and PostgreSQL basics.", 4),
    ("data-engineering-fundamentals", "Data engineering fundamentals", "Reliable pipelines, modeling and data quality.", 5),
    ("engineering-essentials", "Engineering essentials", "Git, REST APIs, Docker and testing basics.", 6),
]


def sql(slug, assessment, skill, prompt, difficulty, reference, order_matters=False):
    return dict(slug=slug, assessment=assessment, skill=skill, kind="sql", prompt=prompt, options=[], correct_index=None,
                explanation="", difficulty=difficulty, weight=1.0,
                sql_config={"fixture": SQL_FIXTURE, "reference": reference, "order_matters": order_matters, "schema": SCHEMA})


def mcq(slug, assessment, skill, prompt, difficulty, options, answer, explanation):
    return dict(slug=slug, assessment=assessment, skill=skill, kind="mcq", prompt=prompt, options=options,
                correct_index=answer, explanation=explanation, difficulty=difficulty, weight=0.6, sql_config={})


QUESTIONS = [
    mcq("py-listcomp", "python-fundamentals", "python", "What is `[x * 2 for x in range(3)]`?", 0.2,
        ["[2, 4, 6]", "[0, 1, 2]", "[0, 2, 4]", "A SyntaxError"], 2, "range(3) yields 0, 1, 2, so the doubled values are 0, 2, 4."),
    mcq("py-mutable-default", "python-fundamentals", "python",
        "`def add(x, acc=[]): acc.append(x); return acc`. After `add(1)`, what does `add(2)` return?", 0.5,
        ["[2]", "[1, 2]", "[1]", "An error"], 1, "The default list is created once and shared between calls."),
    mcq("py-set-len", "python-fundamentals", "python", "What does `len({1, 2, 2, 3})` return?", 0.25,
        ["4", "3", "2", "TypeError"], 1, "A set stores unique values, so {1, 2, 2, 3} is {1, 2, 3}."),
    mcq("py-dict-order", "python-fundamentals", "python", "Which statement about Python (3.7+) dictionaries is true?", 0.35,
        ["Keys must be strings", "They preserve insertion order", "They are immutable", "They allow duplicate keys"], 1,
        "Insertion order is part of the language guarantee since Python 3.7."),
    mcq("py-split", "python-fundamentals", "python", "What does `'a,b,c'.split(',')` return?", 0.15,
        ["['a,b,c']", "['a', 'b', 'c']", "('a', 'b', 'c')", "'abc'"], 1, "split returns a list of the pieces between the separators."),

    mcq("sql-null", "sql-concepts", "sql", "What does `SELECT * FROM t WHERE col = NULL` return?", 0.3,
        ["Rows where col is NULL", "No rows, regardless of the data", "An error", "All rows"], 1,
        "Comparing anything with NULL gives UNKNOWN, so no row matches. Use `IS NULL`."),
    mcq("sql-having", "sql-concepts", "sql-aggregation", "Which clause filters groups after aggregation has happened?", 0.3,
        ["WHERE", "HAVING", "ORDER BY", "LIMIT"], 1, "WHERE filters rows before grouping; HAVING filters the aggregated groups."),
    mcq("sql-left-where", "sql-concepts", "sql-joins",
        "`FROM a LEFT JOIN b ON b.a_id = a.id WHERE b.status = 'x'` silently drops rows from a. Why?", 0.5,
        ["LEFT JOIN cannot be combined with WHERE", "The WHERE on b removes the NULL-extended rows",
         "The ON clause is ignored", "b.status must be indexed"], 1,
        "Unmatched rows have NULL for b.status, so the WHERE predicate removes them. Put the filter in ON."),
    mcq("sql-fanout", "sql-concepts", "sql-aggregation",
        "After joining orders to order_items, SUM(orders.amount) is far too large. Most likely cause?", 0.5,
        ["Join fan-out repeats each order once per item", "SUM ignores GROUP BY", "amount is a float", "The join was a LEFT JOIN"], 0,
        "One order matches many items, so order-level amounts are repeated. Aggregate before joining."),
    mcq("sql-dense-rank", "sql-concepts", "sql-window-functions",
        "Scores are 90, 90, 80. What does DENSE_RANK() OVER (ORDER BY score DESC) return?", 0.65,
        ["1, 1, 3", "1, 2, 3", "1, 1, 2", "1, 1, 1"], 2, "DENSE_RANK does not skip numbers after ties (RANK would return 1, 1, 3)."),
    mcq("sql-index-function", "sql-concepts", "query-optimization",
        "An index exists on users(email). Why might `WHERE LOWER(email) = 'a@b.com'` still scan the whole table?", 0.5,
        ["Indexes only work on numbers", "Wrapping the column in a function defeats a plain index",
         "LOWER is not deterministic", "Email columns cannot be indexed"], 1,
        "The index stores raw values. Use an expression index or store a normalized copy."),
    mcq("sql-composite-index", "sql-concepts", "query-optimization",
        "Query: WHERE customer_id = ? ORDER BY order_date. Which index serves it best?", 0.7,
        ["(order_date, customer_id)", "(customer_id, order_date)", "Separate indexes on each column", "No index can help"], 1,
        "Equality column first, then the sort column, lets the engine read rows already ordered."),

    sql("sqlp-india", "sql-practice", "sql", "List the names of customers whose country is 'IN', in alphabetical order.", 0.15,
        "SELECT name FROM customers WHERE country='IN' ORDER BY name", True),
    sql("sqlp-count", "sql-practice", "sql", "How many orders have status 'completed'? Return a single number.", 0.25,
        "SELECT COUNT(*) FROM orders WHERE status='completed'"),
    sql("sqlp-join", "sql-practice", "sql-joins", "Return each completed order's id and the customer's name.", 0.4,
        "SELECT o.id, c.name FROM orders o JOIN customers c ON c.id=o.customer_id WHERE o.status='completed'"),
    sql("sqlp-no-orders", "sql-practice", "sql-joins", "List the names of customers who have never placed any order (any status).", 0.55,
        "SELECT c.name FROM customers c LEFT JOIN orders o ON o.customer_id=c.id WHERE o.id IS NULL"),
    sql("sqlp-country", "sql-practice", "sql-aggregation",
        "Return each country and the total amount of its completed orders, highest total first.", 0.4,
        "SELECT c.country, SUM(o.amount) FROM customers c JOIN orders o ON o.customer_id=c.id "
        "WHERE o.status='completed' GROUP BY c.country ORDER BY 2 DESC", True),
    sql("sqlp-having", "sql-practice", "sql-aggregation", "Return the names of customers whose total completed spend is greater than 500.", 0.6,
        "SELECT c.name FROM customers c JOIN orders o ON o.customer_id=c.id WHERE o.status='completed' "
        "GROUP BY c.id, c.name HAVING SUM(o.amount) > 500"),
    sql("sqlp-running", "sql-practice", "sql-window-functions",
        "For every order (all statuses) return the order id and the running total of amount for that customer, ordered by order_date.", 0.6,
        "SELECT id, SUM(amount) OVER (PARTITION BY customer_id ORDER BY order_date) FROM orders"),
    sql("sqlp-latest", "sql-practice", "sql-window-functions",
        "For each customer that has orders, return customer_id and the id of their most recent order.", 0.7,
        "SELECT customer_id, id FROM (SELECT customer_id, id, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC) rn "
        "FROM orders) WHERE rn = 1"),

    mcq("db-primary-key", "database-concepts", "database-design", "A primary key must be…", 0.2,
        ["Unique and non-null for each row", "Always a number", "Unique but may be null", "Repeated across tables"], 0,
        "A primary key uniquely identifies each row and can never be NULL."),
    mcq("db-foreign-key", "database-concepts", "database-design", "What does a foreign key constraint enforce?", 0.3,
        ["Faster queries", "Referential integrity between tables", "Unique values in a column", "Encryption of the column"], 1,
        "It guarantees that referenced rows exist, preventing orphaned records."),
    mcq("db-normalization", "database-concepts", "database-design", "What is the main goal of normalization?", 0.35,
        ["Make queries as fast as possible", "Reduce redundancy and update anomalies", "Add more tables for their own sake", "Remove all joins"], 1,
        "Storing each fact once avoids inconsistent updates (it can cost extra joins)."),
    mcq("db-acid-durability", "database-concepts", "database-design",
        "Which ACID property guarantees that committed data survives a crash?", 0.4,
        ["Atomicity", "Consistency", "Isolation", "Durability"], 3, "Durability: once committed, data persists even after failure."),
    mcq("pg-vacuum", "database-concepts", "postgresql", "What is the main purpose of VACUUM in PostgreSQL?", 0.55,
        ["Back up the database", "Reclaim space from dead row versions left by updates and deletes", "Rebuild all indexes in parallel",
         "Compress tables to disk"], 1, "MVCC leaves dead tuples behind; VACUUM makes their space reusable."),
    mcq("pg-explain-analyze", "database-concepts", "postgresql", "What does EXPLAIN ANALYZE do in PostgreSQL?", 0.5,
        ["Only estimates the plan without running the query", "Runs the query and shows the actual plan with real timings",
         "Optimizes the query permanently", "Checks syntax only"], 1,
        "ANALYZE executes the statement, so be careful with data-changing queries."),

    mcq("de-idempotent", "data-engineering-fundamentals", "etl", "Why should ETL loads be idempotent?", 0.5,
        ["They run faster", "Re-running after a failure does not duplicate or corrupt data", "They avoid needing a schema",
         "They remove the need for monitoring"], 1, "Retries and backfills are routine, so safe re-runs matter."),
    mcq("de-late-data", "data-engineering-fundamentals", "etl",
        "An incremental load uses `updated_at > last_run`. Some source rows arrive late with older timestamps. A robust fix?", 0.7,
        ["Ignore them", "Re-read a lookback window and upsert by key", "Reload everything hourly", "Sort by id"], 1,
        "A lookback window plus key-based upserts captures late rows without duplicating."),
    mcq("de-scd2", "data-engineering-fundamentals", "data-modeling",
        "A customer changes country but historical reports must stay accurate. Which approach?", 0.6,
        ["Overwrite the country (SCD type 1)", "Add a new versioned row with validity dates (SCD type 2)",
         "Delete the old customer", "Store the country only in the fact table name"], 1, "Type 2 preserves history by versioning dimension rows."),
    mcq("de-grain", "data-engineering-fundamentals", "data-modeling", "What should you define first when designing a fact table?", 0.4,
        ["The BI tool", "The grain: what one row represents", "The number of indexes", "Column data types"], 1,
        "Dimensions and measures follow from a clearly stated grain."),
    mcq("de-test-pure", "data-engineering-fundamentals", "unit-testing", "Best way to unit-test a data transformation function?", 0.4,
        ["Run it against production", "Keep it pure and test it with small hand-made inputs and expected outputs",
         "Only test the final dashboard", "Mock the language runtime"], 1, "Pure functions with tiny fixtures give fast, deterministic tests."),
    mcq("de-dq-dupes", "data-engineering-fundamentals", "data-quality", "Which check best catches a join that silently duplicated rows?", 0.6,
        ["Column count check", "Assert key uniqueness and reconcile row counts", "Check the file size", "Check that the job ran"], 1,
        "Uniqueness plus count reconciliation exposes fan-out."),
    mcq("de-retry", "data-engineering-fundamentals", "data-pipelines", "When is automatic task retry safe in a scheduler?", 0.4,
        ["Always", "When the task is idempotent", "Never", "Only for SQL tasks"], 1, "Non-idempotent tasks can double-apply effects on retry."),
    mcq("de-backfill", "data-engineering-fundamentals", "data-pipelines",
        "A daily job failed for 2026-03-04 only. Best design to rerun just that day?", 0.65,
        ["Hard-code dates in the code", "Parameterize by logical date and overwrite that date's partition", "Delete the table and rebuild",
         "Rerun tomorrow's job twice"], 1, "Date-parameterized, partition-overwrite tasks are safe to backfill."),
    mcq("de-batch", "data-engineering-fundamentals", "data-pipelines", "Which processing style best fits a report generated once each night?", 0.25,
        ["Batch processing", "Real-time streaming only", "Interactive queries only", "Manual spreadsheets"], 0,
        "A scheduled, bounded workload is a natural fit for batch."),
    mcq("de-airflow-dag", "data-engineering-fundamentals", "airflow", "In Apache Airflow, what is a DAG?", 0.35,
        ["A database table", "A directed acyclic graph of tasks and their dependencies", "A Python package manager",
         "A type of operator that sends email"], 1, "A DAG defines tasks and the order in which they run, with no cycles."),

    mcq("eng-git-stash", "engineering-essentials", "git", "What does `git stash` do?", 0.3,
        ["Deletes uncommitted changes forever", "Temporarily shelves uncommitted changes so you can switch tasks",
         "Pushes commits to the remote", "Creates a new branch"], 1, "Stashed changes can be re-applied later with `git stash pop`."),
    mcq("eng-git-rebase", "engineering-essentials", "git", "What does `git rebase main` do on a feature branch?", 0.6,
        ["Deletes the branch", "Replays the branch's commits on top of main, rewriting them", "Merges main without a merge commit and keeps old hashes",
         "Resets the working tree to main"], 1, "Rebase creates new commits, so avoid rebasing branches others already use."),
    mcq("eng-put", "engineering-essentials", "rest-apis", "Which HTTP method is defined as idempotent and typically replaces a resource?", 0.45,
        ["POST", "PUT", "PATCH always", "CONNECT"], 1, "Sending the same PUT repeatedly leaves the resource in the same state."),
    mcq("eng-201", "engineering-essentials", "rest-apis", "Which status code indicates that a resource was created?", 0.25,
        ["200", "201", "204", "301"], 1, "201 Created is returned after successfully creating a resource."),
    mcq("eng-docker", "engineering-essentials", "docker", "What is the difference between a Docker image and a container?", 0.35,
        ["There is none", "An image is a read-only template; a container is a running instance of it", "A container is a template for images",
         "Images only exist on Linux"], 1, "You start containers from images."),
    mcq("eng-mock", "engineering-essentials", "unit-testing", "Why mock an external API call in a unit test?", 0.45,
        ["To make the test slower", "To keep the test fast and deterministic", "Because APIs cannot be tested", "To avoid writing assertions"], 1,
        "Unit tests should not depend on the network or third-party availability."),
]
