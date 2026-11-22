"""Reproducible batch ingestion of job postings (CSV or JSON). Ingestion is separate from HTTP handling and is
driven by management commands. Same file + same code => same result; re-running a file loads nothing twice."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path

import pandas as pd
from django.db import transaction
from django.utils import timezone

from apps.jobs.analyzer import analyze_job_text
from apps.jobs.models import JobDescription, JobRequirement
from apps.jobs.services import content_hash, prerequisite_map
from apps.skills.matcher import SkillMatcher
from apps.skills.models import Skill

from .models import DataQualityResult, Dataset, IngestionRun, RejectedRecord

log = logging.getLogger("skillvar.dataops")
REQUIRED_COLUMNS = ["external_id", "title", "description"]
OPTIONAL_COLUMNS = ["company", "years_required"]
MIN_DESC, MAX_DESC, MAX_TITLE = 40, 20_000, 200


def read_frame(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, dtype=str, keep_default_na=False)
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        records = data.get("jobs", data) if isinstance(data, dict) else data
        return pd.DataFrame(records).astype(str).replace({"nan": "", "None": ""})
    raise ValueError("Only .csv and .json files are supported.")


def profile_frame(df: pd.DataFrame) -> list[dict]:
    """Schema inspection + column profiling: pure, returns one dict per column."""
    out = []
    for col in df.columns:
        s = df[col].astype(str)
        blank = int((s.str.strip() == "").sum())
        out.append({"column": col, "dtype": str(df[col].dtype), "rows": len(df), "blank": blank,
                    "blank_rate": round(blank / len(df), 4) if len(df) else 0.0, "unique": int(s.nunique()),
                    "max_length": int(s.str.len().max()) if len(df) else 0})
    return out


def normalize_description(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(re.sub(r"[ \t]+", " ", ln).strip() for ln in text.split("\n")).strip()


def validate_row(row: dict) -> tuple[dict | None, str]:
    ext, title = (row.get("external_id") or "").strip(), (row.get("title") or "").strip()
    desc = normalize_description(row.get("description") or "")
    if not ext:
        return None, "missing external_id"
    if not title:
        return None, "missing title"
    if len(title) > MAX_TITLE:
        return None, f"title longer than {MAX_TITLE} characters"
    if len(desc) < MIN_DESC:
        return None, f"description shorter than {MIN_DESC} characters"
    if len(desc) > MAX_DESC:
        return None, f"description longer than {MAX_DESC:,} characters"
    years = (row.get("years_required") or "").strip()
    yrs = None
    if years:
        try:
            yrs = float(years)
        except ValueError:
            return None, "years_required is not a number"
        if not 0 <= yrs <= 50:
            return None, "years_required outside 0-50"
    return {"external_id": ext, "title": title, "description": desc, "company": (row.get("company") or "").strip()[:200],
            "years": yrs}, ""


def _quality(run: IngestionRun, df: pd.DataFrame, profile: list[dict], dup_ids: int, dup_content: int) -> None:
    rows = []
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    rows.append(DataQualityResult(run=run, check_name="required_columns", status="fail" if missing else "pass",
                                  detail={"missing": missing}))
    for p in profile:
        status = "pass" if p["blank_rate"] == 0 else ("warn" if p["blank_rate"] < 0.05 else "fail")
        if p["column"] in REQUIRED_COLUMNS or p["blank"]:
            rows.append(DataQualityResult(run=run, check_name="blank_rate", column=p["column"], status=status, detail=p))
    rows.append(DataQualityResult(run=run, check_name="duplicate_external_id", status="pass" if not dup_ids else "warn",
                                  detail={"count": dup_ids}))
    rows.append(DataQualityResult(run=run, check_name="duplicate_content", status="pass" if not dup_content else "warn",
                                  detail={"count": dup_content}))
    DataQualityResult.objects.bulk_create(rows)


def ingest_jobs(path: str | Path, dataset: Dataset, *, batch_size: int = 500, synthetic: bool = False) -> IngestionRun:
    path = Path(path)
    raw = path.read_bytes()
    run = IngestionRun.objects.create(dataset=dataset, source_name=path.name, source_sha256=hashlib.sha256(raw).hexdigest(),
                                      parameters={"batch_size": batch_size, "synthetic": synthetic})
    try:
        df = read_frame(path)
        run.rows_read = len(df)
        profile = profile_frame(df)
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            _quality(run, df, profile, 0, 0)
            raise ValueError(f"Missing required column(s): {', '.join(missing)}")
        dup_ids = int(df.duplicated(subset=["external_id"]).sum())
        matcher, prereqs = SkillMatcher.from_db(), prerequisite_map()
        skills = {s.slug: s for s in Skill.objects.all()}
        existing = set(JobDescription.objects.filter(user__isnull=True).values_list("content_hash", flat=True))
        seen_ids, seen_hashes = set(), set()
        loaded = dup_content = 0
        rejected: list[RejectedRecord] = []
        for start in range(0, len(df), batch_size):
            chunk = df.iloc[start:start + batch_size].to_dict("records")
            jobs, analyses = [], []
            for offset, row in enumerate(chunk):
                clean, reason = validate_row(row)
                rownum = start + offset + 2     # +2: header row and 1-based numbering, matching a spreadsheet
                if clean is None:
                    rejected.append(RejectedRecord(run=run, row_number=rownum, reason=reason, raw={k: str(v)[:300] for k, v in row.items()}))
                    continue
                h = content_hash(clean["description"])
                if clean["external_id"] in seen_ids or h in existing or h in seen_hashes:
                    dup_content += 1
                    continue
                seen_ids.add(clean["external_id"])
                seen_hashes.add(h)
                a = analyze_job_text(clean["description"], matcher, prereqs)
                jobs.append(JobDescription(user=None, source=JobDescription.DATASET, is_synthetic=synthetic, title=clean["title"],
                                           company=clean["company"], raw_text=clean["description"], content_hash=h,
                                           years_required=clean["years"] if clean["years"] is not None else a.years_required,
                                           education_required=a.education_required, responsibilities=a.responsibilities,
                                           ingestion_run=run))
                analyses.append(a)
            with transaction.atomic():
                created = JobDescription.objects.bulk_create(jobs)
                reqs = [JobRequirement(job=job, skill=skills[r.slug], kind=r.kind, origin=r.origin, snippet=r.snippet)
                        for job, a in zip(created, analyses, strict=True) for r in a.requirements if r.slug in skills]
                JobRequirement.objects.bulk_create(reqs)
            loaded += len(created)
        RejectedRecord.objects.bulk_create(rejected, batch_size=1000)
        run.rows_loaded, run.rows_duplicate, run.rows_rejected = loaded, dup_content, len(rejected)
        _quality(run, df, profile, dup_ids, dup_content)
        run.status = IngestionRun.REJECTS if rejected else IngestionRun.SUCCEEDED
    except Exception as exc:   # record any failure on the run so it is observable, then re-raise after saving
        run.status, run.error_summary = IngestionRun.FAILED, f"{type(exc).__name__}: {exc}"[:2000]
        log.error("ingestion failed run=%s error=%s", run.pk, type(exc).__name__)
    finally:
        run.finished_at = timezone.now()
        run.save()
    log.info("ingestion run=%s status=%s read=%d loaded=%d dup=%d rejected=%d", run.pk, run.status, run.rows_read,
             run.rows_loaded, run.rows_duplicate, run.rows_rejected)
    return run
