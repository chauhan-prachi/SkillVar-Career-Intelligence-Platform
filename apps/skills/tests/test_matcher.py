import pytest

from apps.skills.matcher import SkillMatcher


@pytest.fixture
def matcher(seeded):
    return SkillMatcher.from_db()


def slugs(m, text):
    return [x.slug for x in m.find(text)]


@pytest.mark.parametrize("text,expected", [
    ("Strong Postgres and PostgreSQL skills", ["postgresql", "postgresql"]),
    ("Built RESTful APIs with Django", ["rest-apis", "django"]),
    ("Experience with C++, C# and Node.js", ["cpp", "csharp", "nodejs"]),
    ("Set up CI/CD with GitHub Actions", ["ci-cd", "ci-cd"]),
    ("I use Python.", ["python"]),
    ("worked with SQLite", ["sqlite"]),
    ("Writing SQL window functions and joins", ["sql-window-functions", "sql-joins"]),  # longest alias wins; SQL is implied via prerequisites
])
def test_finds_and_normalises_variants(matcher, text, expected):
    assert slugs(matcher, text) == expected


@pytest.mark.parametrize("text", ["JavaScript developer", "go to market strategy", "the rest of the team",
                                  "healthy lifestyle", "Mathematics degree"])
def test_no_false_positives(matcher, text):
    found = slugs(matcher, text)
    assert "java" not in found and "golang" not in found and "rest-apis" not in found
    assert "html" not in found and "ml" not in found and "machine-learning" not in found


def test_javascript_is_not_java(matcher):
    assert slugs(matcher, "JavaScript") == ["javascript"]


def test_longest_alias_wins_at_same_position(matcher):
    assert slugs(matcher, "PostgreSQL database administration") == ["postgresql"]


def test_mentions_have_offsets_into_original_text(matcher):
    text = "We use Postgres daily"
    m = matcher.find(text)[0]
    assert text[m.start:m.end] == "Postgres" == m.matched_text


def test_empty_taxonomy_is_safe(db):
    assert SkillMatcher({}).find("python") == []
