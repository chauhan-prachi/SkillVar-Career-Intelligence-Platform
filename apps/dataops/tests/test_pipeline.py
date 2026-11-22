import csv
import json
import time

import pandas as pd
import pytest
from django.core.management import CommandError, call_command

from apps.dataops.models import DataQualityResult, Dataset, IngestionRun, RejectedRecord
from apps.dataops.pipeline import ingest_jobs, normalize_description, profile_frame, validate_row
from apps.dataops.synthetic import generate
from apps.jobs.models import JobDescription, JobRequirement

DESC = "Requirements:\n- Experience with Python and SQL for data pipelines\nNice to have:\n- Docker"


def write_csv(path, rows, fields=("external_id", "title", "description", "company", "years_required")):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    return path


def row(i, **kw):
    return {"external_id": f"J{i}", "title": f"Engineer {i}", "description": DESC + f"\nRef {i}", "company": "Acme", "years_required": "", **kw}


@pytest.fixture
def ds(seeded):
    return Dataset.objects.create(slug="test", name="Test", kind="jobs", source_note="synthetic")


# ---------- generator ----------
def test_generator_is_deterministic_and_seed_sensitive():
    assert generate(25, seed=3) == generate(25, seed=3) and generate(25, seed=3) != generate(25, seed=4)
    assert len({r["external_id"] for r in generate(200, 1)}) == 200


def test_generated_rows_are_clearly_synthetic():
    r = generate(1, 1)[0]
    assert r["external_id"].startswith("SYN-") and "Requirements:" in r["description"]


# ---------- pure helpers ----------
def test_profile_frame_reports_blanks_uniques_and_lengths():
    p = {c["column"]: c for c in profile_frame(pd.DataFrame({"a": ["x", "", "x"], "b": ["1", "2", "3"]}))}
    assert p["a"]["blank"] == 1 and p["a"]["unique"] == 2 and p["a"]["blank_rate"] == pytest.approx(0.3333, abs=1e-3) and p["b"]["max_length"] == 1


@pytest.mark.parametrize("bad,reason", [
    ({"external_id": ""}, "missing external_id"), ({"title": " "}, "missing title"), ({"title": "t" * 201}, "title longer"),
    ({"description": "short"}, "shorter than"), ({"description": "x" * 20001}, "longer than"),
    ({"years_required": "abc"}, "not a number"), ({"years_required": "99"}, "outside 0-50"),
])
def test_row_validation_reasons(bad, reason):
    clean, why = validate_row({**row(1), **bad})
    assert clean is None and reason in why


def test_valid_row_is_normalised():
    raw = "  Requirements:  \r\n\r\n   Experience   with Python and SQL for pipelines\x00  "
    clean, why = validate_row(row(1, description=raw, years_required="3"))
    assert why == "" and clean["description"] == "Requirements:\n\nExperience with Python and SQL for pipelines"
    assert clean["years"] == 3.0
    assert normalize_description("a\r\nb\rc") == "a\nb\nc"


# ---------- ingestion ----------
def test_csv_ingest_loads_analyses_and_records_quality(tmp_path, ds):
    path = write_csv(tmp_path / "j.csv", [row(i) for i in range(10)])
    run = ingest_jobs(path, ds, synthetic=True)
    assert run.status == "succeeded" and (run.rows_read, run.rows_loaded, run.rows_rejected, run.rows_duplicate) == (10, 10, 0, 0)
    job = JobDescription.objects.filter(ingestion_run=run).first()
    assert job.user is None and job.source == "dataset" and job.is_synthetic and job.requirements.filter(skill__slug="python").exists()
    assert job.requirements.get(skill__slug="docker").kind == "preferred"
    checks = {q.check_name: q.status for q in run.quality_results.all()}
    assert checks["required_columns"] == "pass" and checks["duplicate_external_id"] == "pass"
    assert run.finished_at and run.duration_seconds >= 0 and len(run.source_sha256) == 64


def test_json_formats_are_supported(tmp_path, ds):
    rows = [row(i) for i in range(3)]
    p1 = tmp_path / "a.json"; p1.write_text(json.dumps(rows))
    p2 = tmp_path / "b.json"; p2.write_text(json.dumps({"jobs": [row(i + 10) for i in range(3)]}))
    assert ingest_jobs(p1, ds).rows_loaded == 3 and ingest_jobs(p2, ds).rows_loaded == 3


def test_rejected_rows_are_tracked_with_spreadsheet_row_numbers(tmp_path, ds):
    rows = [row(1), row(2, title=""), row(3), row(4, years_required="x")]
    run = ingest_jobs(write_csv(tmp_path / "j.csv", rows), ds)
    assert run.status == "succeeded_with_rejects" and run.rows_loaded == 2 and run.rows_rejected == 2
    rej = {r.row_number: r.reason for r in RejectedRecord.objects.filter(run=run)}
    assert rej == {3: "missing title", 5: "years_required is not a number"}      # header is row 1, like a spreadsheet


def test_rerunning_the_same_file_is_idempotent(tmp_path, ds):
    path = write_csv(tmp_path / "j.csv", [row(i) for i in range(5)])
    ingest_jobs(path, ds)
    again = ingest_jobs(path, ds)
    assert again.rows_loaded == 0 and again.rows_duplicate == 5 and JobDescription.objects.filter(user__isnull=True).count() == 5


def test_duplicates_inside_one_file_are_loaded_once(tmp_path, ds):
    run = ingest_jobs(write_csv(tmp_path / "j.csv", [row(1), row(1), row(2)]), ds)
    assert run.rows_loaded == 2 and run.rows_duplicate == 1
    dq = DataQualityResult.objects.get(run=run, check_name="duplicate_external_id")
    assert dq.status == "warn" and dq.detail["count"] == 1


def test_missing_required_column_fails_the_run_observably(tmp_path, ds):
    run = ingest_jobs(write_csv(tmp_path / "j.csv", [{"title": "x", "description": DESC}], fields=("title", "description")), ds)
    assert run.status == "failed" and "external_id" in run.error_summary and run.rows_loaded == 0
    assert DataQualityResult.objects.get(run=run, check_name="required_columns").status == "fail"
    assert IngestionRun.objects.get(pk=run.pk).finished_at is not None and not JobDescription.objects.exists()


def test_unsupported_file_type_fails_the_run(tmp_path, ds):
    p = tmp_path / "j.txt"; p.write_text("hello")
    run = ingest_jobs(p, ds)
    assert run.status == "failed" and "csv and .json" in run.error_summary.lower()


def test_blank_rate_quality_levels(tmp_path, ds):
    rows = [row(i, company="") for i in range(20)]
    run = ingest_jobs(write_csv(tmp_path / "j.csv", rows), ds)
    q = DataQualityResult.objects.get(run=run, check_name="blank_rate", column="company")
    assert q.status == "fail" and q.detail["blank_rate"] == 1.0


def test_one_bad_batch_does_not_leave_partial_jobs_without_requirements(tmp_path, ds):
    run = ingest_jobs(write_csv(tmp_path / "j.csv", [row(i) for i in range(1200)]), ds, batch_size=500)
    assert run.rows_loaded == 1200
    assert not JobDescription.objects.filter(user__isnull=True, requirements__isnull=True).exists()


def test_scale_1000_rows_is_fast_and_query_count_is_bounded(tmp_path, ds, django_assert_max_num_queries):
    path = write_csv(tmp_path / "syn.csv", generate(1000, seed=5), fields=("external_id", "title", "company", "years_required", "description"))
    start = time.perf_counter()
    with django_assert_max_num_queries(60):                  # batches, not one query per row
        run = ingest_jobs(path, ds, batch_size=500, synthetic=True)
    assert run.rows_loaded == 1000 and time.perf_counter() - start < 60
    assert JobRequirement.objects.filter(job__ingestion_run=run).count() > 3000


# ---------- management commands ----------
def test_generate_then_ingest_commands(tmp_path, seeded):
    out = tmp_path / "syn.csv"
    call_command("generate_synthetic_jobs", "--count", "30", "--seed", "2", "--out", str(out), verbosity=0)
    call_command("ingest_jobs", str(out), "--dataset", "cmd", "--synthetic", verbosity=0)
    assert JobDescription.objects.filter(user__isnull=True, is_synthetic=True).count() == 30
    assert Dataset.objects.get(slug="cmd").source_note == "Synthetic data"
    j = tmp_path / "syn.json"
    call_command("generate_synthetic_jobs", "--count", "5", "--out", str(j), verbosity=0)
    assert json.loads(j.read_text())["jobs"][0]["external_id"].startswith("SYN-")


def test_command_errors_are_clear(tmp_path, seeded):
    with pytest.raises(CommandError, match="not found"):
        call_command("ingest_jobs", str(tmp_path / "nope.csv"), verbosity=0)
    bad = write_csv(tmp_path / "bad.csv", [{"title": "t"}], fields=("title",))
    with pytest.raises(CommandError, match="Missing required"):
        call_command("ingest_jobs", str(bad), verbosity=0)


# ---------- staff-only views ----------
def test_pipeline_pages_are_staff_only(tmp_path, ds, client, user, django_user_model):
    run = ingest_jobs(write_csv(tmp_path / "j.csv", [row(1), row(2, title="")]), ds)
    client.force_login(user)
    assert client.get("/data/").status_code == 302 and client.get(f"/data/runs/{run.pk}/").status_code == 302
    staff = django_user_model.objects.create_user("st", email="st@example.com", password="a-long-strong-pass-9", is_staff=True)
    client.force_login(staff)
    page = client.get("/data/").content.decode()
    assert "Data pipeline runs" in page and "Succeeded with rejected rows" in page
    detail = client.get(f"/data/runs/{run.pk}/").content.decode()
    assert "required_columns" in detail and "missing title" in detail


def test_sample_job_list_has_no_n_plus_one(tmp_path, ds, goal_client, django_assert_max_num_queries):
    ingest_jobs(write_csv(tmp_path / "j.csv", [row(i) for i in range(25)]), ds)
    with django_assert_max_num_queries(12):
        r = goal_client.get("/jobs/samples/")
    assert r.status_code == 200 and "Page 1 of 2" in r.content.decode()
