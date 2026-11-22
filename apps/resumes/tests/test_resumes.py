import io
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.evidence.profile import build_signals
from apps.resumes import extract as ex
from apps.resumes.analysis import analyze, split_sections, years_stated
from apps.resumes.models import Resume, ResumeSkill
from apps.skills.matcher import SkillMatcher
from conftest import SAMPLE_RESUME, make_docx, make_pdf


def upload(client, name, data, ctype="application/octet-stream"):
    return client.post("/resumes/upload/", {"file": SimpleUploadedFile(name, data, content_type=ctype)})


# ---------- extraction ----------
def test_pdf_text_is_extracted():
    r = ex.extract(make_pdf(SAMPLE_RESUME))
    assert r.fmt == "pdf" and r.page_count == 1 and "Built ETL pipelines" in r.text


def test_docx_text_is_extracted():
    r = ex.extract(make_docx(SAMPLE_RESUME))
    assert r.fmt == "docx" and "PostgreSQL" in r.text


@pytest.mark.parametrize("data,msg", [
    (b"", "empty"), (b"just a text file pretending", "Unsupported"), (b"<html><script>alert(1)</script></html>", "Unsupported"),
    (b"PK\x03\x04garbage", "corrupted"), (b"MZ\x90\x00 an executable", "Unsupported"),
])
def test_invalid_or_hostile_content_is_rejected_safely(data, msg):
    with pytest.raises(ex.ResumeError, match=msg):
        ex.extract(data)


def test_zip_that_is_not_docx_is_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("notes.txt", "hello")
    with pytest.raises(ex.ResumeError, match="Unsupported"):
        ex.extract(buf.getvalue())


def test_truncated_pdf_does_not_crash():
    with pytest.raises(ex.ResumeError):
        ex.extract(make_pdf(SAMPLE_RESUME)[:60])


def test_zip_bomb_style_docx_is_rejected(monkeypatch):
    monkeypatch.setattr(ex, "MAX_ZIP_UNCOMPRESSED", 100)
    with pytest.raises(ex.ResumeError, match="unreasonable size"):
        ex.extract(make_docx(SAMPLE_RESUME))


def test_page_limit_enforced(settings):
    from pypdf import PdfWriter
    w = PdfWriter()
    for _ in range(3):
        w.add_blank_page(612, 792)
    buf = io.BytesIO(); w.write(buf)
    settings.RESUME_MAX_PAGES = 2
    with pytest.raises(ex.ResumeError, match="3 pages"):
        ex.extract(buf.getvalue())


def test_encrypted_pdf_is_rejected_with_a_helpful_message():
    from pypdf import PdfReader, PdfWriter
    w = PdfWriter()
    for page in PdfReader(io.BytesIO(make_pdf(SAMPLE_RESUME))).pages:
        w.add_page(page)
    w.encrypt("secret")
    buf = io.BytesIO(); w.write(buf)
    with pytest.raises(ex.ResumeError, match="password-protected"):
        ex.extract(buf.getvalue())


def test_image_only_pdf_warns_that_ocr_is_needed():
    from pypdf import PdfWriter
    w = PdfWriter(); w.add_blank_page(612, 792)
    buf = io.BytesIO(); w.write(buf)
    r = ex.extract(buf.getvalue())
    assert r.text == "" and any("OCR" in x for x in r.warnings)


def test_very_long_text_is_truncated_with_warning(settings):
    settings.RESUME_MAX_TEXT_CHARS = 150
    r = ex.extract(make_docx(["word " * 100]))
    assert len(r.text) <= 150 and any("very long" in w for w in r.warnings)


def test_text_normalisation_strips_control_characters():
    assert ex.normalize_text("a\x00b\x07c   d\n\n\n\ne") == "abc d\n\ne"


# ---------- analysis ----------
@pytest.fixture
def matcher(seeded):
    return SkillMatcher.from_db()


def test_sections_and_context_vs_stated(matcher):
    result, hits = analyze(ex.normalize_text("\n".join(SAMPLE_RESUME)), matcher)
    assert {"skills", "experience", "projects", "education", "summary"} <= set(result["sections_found"])
    assert hits["sql"].contextual is False and hits["git"].contextual is False          # only listed
    assert hits["airflow"].contextual and hits["django"].contextual and hits["postgresql"].contextual   # shown in use
    assert hits["python"].contextual                                                    # listed AND used -> contextual wins
    assert "Airflow" in hits["airflow"].snippet                                          # provenance is kept


def test_years_and_education_only_when_stated():
    assert years_stated("I have 7 years of professional experience") == 7.0
    assert years_stated("Worked 2019-2024 at a company") is None
    assert years_stated("99 years of experience") is None


def test_quality_checks_explain_themselves(matcher):
    result, _ = analyze(ex.normalize_text("\n".join(SAMPLE_RESUME)), matcher)
    by = {q["key"]: q for q in result["quality"]}
    assert by["contact_email"]["passed"] and by["contact_phone"]["passed"] and by["contact_links"]["passed"]
    assert by["achievements"]["passed"] and by["projects"]["passed"]
    assert not by["length"]["passed"] and "words" in by["length"]["how"]                 # the sample is short, and says why
    assert result["checks_passed"] + sum(1 for q in result["quality"] if not q["passed"]) == result["checks_total"]


def test_empty_text_gives_no_skills_and_no_crash(matcher):
    result, hits = analyze("", matcher)
    assert hits == {} and result["checks_passed"] < result["checks_total"]


def test_section_headers_are_not_mistaken_for_content():
    lines = split_sections("Skills\nPython\nExperience\nBuilt things")
    assert lines == [("Python", "skills"), ("Built things", "experience")]


# ---------- upload view ----------
def test_upload_pdf_end_to_end(goal_client, goal_user):
    r = upload(goal_client, "cv.pdf", make_pdf(SAMPLE_RESUME))
    assert r.status_code == 302
    resume = Resume.objects.get(user=goal_user)
    assert resume.file_format == "pdf" and resume.skills.count() >= 8 and "Airflow" in resume.extracted_text
    page = goal_client.get(r.url).content.decode()
    assert "Detected skills" in page and "Airflow" in page and "not an ATS score" in page


def test_upload_docx_end_to_end(goal_client, goal_user):
    assert upload(goal_client, "cv.docx", make_docx(SAMPLE_RESUME)).status_code == 302
    assert Resume.objects.get(user=goal_user).file_format == "docx"


def test_uploaded_file_is_stored_privately_with_a_server_chosen_name(goal_client, goal_user):
    upload(goal_client, "../../evil name.pdf", make_pdf(SAMPLE_RESUME))
    resume = Resume.objects.get(user=goal_user)
    assert resume.file.name.startswith(f"resumes/{goal_user.id}/") and "evil" not in resume.file.name and ".." not in resume.file.name
    with pytest.raises(ValueError):
        _ = resume.file.url                                # no public URL exists for private files


@pytest.mark.parametrize("name,data,message", [
    ("cv.txt", b"plain text", "Only PDF and DOCX"), ("cv.exe", b"MZ....", "Only PDF and DOCX"),
    ("cv.pdf", b"this is not a pdf", "Unsupported"), ("cv.pdf", b"", "empty"),
])
def test_upload_rejects_bad_files_with_a_message(goal_client, goal_user, name, data, message):
    r = upload(goal_client, name, data)
    assert r.status_code == 200 and message.lower() in r.content.decode().lower()
    assert not Resume.objects.filter(user=goal_user).exists()


def test_upload_rejects_docx_renamed_to_pdf(goal_client, goal_user):
    r = upload(goal_client, "cv.pdf", make_docx(SAMPLE_RESUME))
    assert r.status_code == 200 and "contents are a DOCX" in r.content.decode()


def test_oversized_upload_is_rejected(goal_client, goal_user, settings):
    settings.RESUME_MAX_BYTES = 1000
    r = upload(goal_client, "cv.pdf", make_pdf(SAMPLE_RESUME) + b" " * 2000)
    assert r.status_code == 200 and "larger than" in r.content.decode() and not Resume.objects.exists()


def test_duplicate_upload_is_rejected(goal_client, goal_user):
    data = make_pdf(SAMPLE_RESUME)
    upload(goal_client, "cv.pdf", data)
    r = upload(goal_client, "cv2.pdf", data)
    assert r.status_code == 200 and "already uploaded" in r.content.decode() and Resume.objects.count() == 1


def test_scanned_pdf_is_saved_with_an_ocr_warning(goal_client, goal_user):
    from pypdf import PdfWriter
    w = PdfWriter(); w.add_blank_page(612, 792)
    buf = io.BytesIO(); w.write(buf)
    r = upload(goal_client, "scan.pdf", buf.getvalue())
    assert r.status_code == 302 and "OCR" in goal_client.get(r.url).content.decode()
    assert Resume.objects.get().status == "empty"


def test_upload_is_rate_limited(goal_client, goal_user):
    codes = [upload(goal_client, "x.txt", b"nope").status_code for _ in range(12)]
    assert codes[:10] == [200] * 10 and codes[10] == 429


# ---------- ownership, review, deletion ----------
@pytest.fixture
def resume(goal_client, goal_user):
    r = upload(goal_client, "cv.pdf", make_pdf(SAMPLE_RESUME))
    return Resume.objects.get(pk=r.url.strip("/").split("/")[-1])


def test_other_users_cannot_view_download_change_or_delete(resume, client, other_user):
    client.force_login(other_user)
    for method, url in [("get", f"/resumes/{resume.pk}/"), ("get", f"/resumes/{resume.pk}/download/"),
                        ("post", f"/resumes/{resume.pk}/review/"), ("post", f"/resumes/{resume.pk}/facts/"),
                        ("post", f"/resumes/{resume.pk}/delete/")]:
        assert getattr(client, method)(url).status_code == 404, url
    assert Resume.objects.filter(pk=resume.pk).exists()


def test_download_returns_the_original_bytes_to_the_owner(resume, goal_client):
    r = goal_client.get(f"/resumes/{resume.pk}/download/")
    assert r.status_code == 200 and b"".join(r.streaming_content).startswith(b"%PDF")
    assert "attachment" in r["Content-Disposition"]


def test_rejecting_a_detected_skill_removes_it_from_the_profile(resume, goal_client, goal_user):
    assert build_signals(goal_user)[0]["airflow"].resume == "contextual"
    rs = resume.skills.get(skill__slug="airflow")
    goal_client.post(f"/resumes/{resume.pk}/review/", {"action": "reject", "skill_id": rs.skill_id})
    assert build_signals(goal_user)[0]["airflow"].resume is None


def test_manual_skill_counts_as_stated_not_contextual(resume, goal_client, goal_user):
    from apps.skills.models import Skill
    goal_client.post(f"/resumes/{resume.pk}/review/", {"action": "add", "new_skill": Skill.objects.get(slug="tableau").pk})
    assert build_signals(goal_user)[0]["tableau"].resume == "stated"


def test_corrections_update_resume_and_profile(resume, goal_client, goal_user):
    goal_client.post(f"/resumes/{resume.pk}/facts/", {"years_experience_stated": "4.5", "education_stated": "MSc Data Science"})
    resume.refresh_from_db(); goal_user.profile.refresh_from_db()
    assert float(resume.years_experience_stated) == 4.5 and float(goal_user.profile.years_experience) == 4.5


def test_resume_claims_never_become_confirmed(resume, goal_user):
    from apps.matching.scoring import skill_credit
    sig = build_signals(goal_user)[0]["python"]
    status = skill_credit(sig, {"claimed": 0.2, "contextual": 0.5}, 0.5)[0]
    assert status != "confirmed"


def test_delete_removes_file_text_and_derived_rows(resume, goal_client, goal_user, tmp_path):
    path = resume.file.path
    assert goal_client.post(f"/resumes/{resume.pk}/delete/").status_code == 302
    assert not Resume.objects.exists() and not ResumeSkill.objects.exists()
    import os
    assert not os.path.exists(path)
    assert build_signals(goal_user)[0]["airflow"].resume is None


def test_resume_list_shows_only_own_resumes(resume, client, other_user):
    client.force_login(other_user)
    assert "cv.pdf" not in client.get("/resumes/").content.decode()
