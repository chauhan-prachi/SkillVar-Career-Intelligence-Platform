from __future__ import annotations

import hashlib
import logging
from pathlib import PurePath

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction

from apps.skills.matcher import SkillMatcher
from apps.skills.models import Skill

from .analysis import analyze, education_lines, split_sections, years_stated
from .extract import ResumeError, extract
from .models import Resume, ResumeSkill

log = logging.getLogger("skillvar.resumes")
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def validate_upload(uploaded) -> bytes:
    """Cheap checks first (size, extension), then the content itself is the real validator."""
    if uploaded.size == 0:
        raise ValidationError("The file is empty.")
    if uploaded.size > settings.RESUME_MAX_BYTES:
        raise ValidationError(f"The file is larger than {settings.RESUME_MAX_BYTES // (1024 * 1024)} MB.")
    if PurePath(uploaded.name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValidationError("Only PDF and DOCX files are supported.")
    data = uploaded.read()
    if len(data) > settings.RESUME_MAX_BYTES:
        raise ValidationError("The file is too large.")
    return data


@transaction.atomic
def process_upload(user, uploaded) -> Resume:
    data = validate_upload(uploaded)
    digest = hashlib.sha256(data).hexdigest()
    if Resume.objects.filter(user=user, sha256=digest).exists():
        raise ValidationError("You have already uploaded this exact file.")
    try:
        ext = extract(data)
    except ResumeError as exc:
        raise ValidationError(str(exc))
    claimed_ext = PurePath(uploaded.name).suffix.lower().lstrip(".")
    if claimed_ext != ext.fmt:
        raise ValidationError(f"The file contents are a {ext.fmt.upper()}, but the name says .{claimed_ext}. Please upload a genuine file.")
    matcher = SkillMatcher.from_db()
    analysis, hits = analyze(ext.text, matcher)
    analysis["warnings"] = ext.warnings
    lines = split_sections(ext.text)
    safe_name = PurePath(uploaded.name).name[:200]
    resume = Resume(user=user, original_filename=safe_name, file_format=ext.fmt, size_bytes=len(data), sha256=digest,
                    status=Resume.EMPTY if ext.warnings and len(ext.text) < 100 else Resume.PROCESSED,
                    page_count=ext.page_count, extracted_text=ext.text, analysis=analysis,
                    years_experience_stated=years_stated(ext.text),
                    education_stated=(education_lines(lines) or [""])[0])
    resume.file.save(f"{digest}.{ext.fmt}", ContentFile(data), save=False)
    try:
        resume.save()
    except IntegrityError:
        raise ValidationError("You have already uploaded this exact file.")
    skills = {s.slug: s for s in Skill.objects.filter(slug__in=hits)}
    ResumeSkill.objects.bulk_create([
        ResumeSkill(resume=resume, skill=skills[slug], section=h.section, contextual=h.contextual,
                    matched_text=h.matched_text[:120], snippet=h.snippet) for slug, h in hits.items() if slug in skills])
    log.info("resume processed user=%s format=%s skills=%d", user.pk, ext.fmt, len(hits))   # never log contents
    return resume


@transaction.atomic
def delete_resume(resume: Resume) -> None:
    """Deletes the stored file, the extracted text and all derived rows (skills cascade)."""
    resume.file.delete(save=False)
    resume.delete()


def review_skill(resume: Resume, skill_id: int, action: str) -> None:
    rs = resume.skills.get(skill_id=skill_id)
    rs.review = {"confirm": ResumeSkill.CONFIRMED, "reject": ResumeSkill.REJECTED}[action]
    rs.save(update_fields=["review"])


def add_manual_skill(resume: Resume, skill: Skill) -> ResumeSkill:
    rs, _ = ResumeSkill.objects.update_or_create(resume=resume, skill=skill, defaults={
        "review": ResumeSkill.MANUAL, "section": "manual", "contextual": False, "matched_text": "", "snippet": "Added by you"})
    return rs
