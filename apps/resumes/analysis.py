"""Transparent, rule-based resume analysis. Nothing here is a trained model and nothing is an ATS score:
every indicator states exactly how it is computed."""
from __future__ import annotations

import re
from dataclasses import dataclass

from apps.skills.matcher import SkillMatcher

SECTION_PATTERNS = {
    "skills": r"(technical |core |key )?(skills|technologies|tech stack|competencies|skills (&|and) tools)",
    "experience": r"(professional |work |relevant )?(experience|employment( history)?|work history|internships?)",
    "projects": r"(personal |academic |selected |key )?projects",
    "education": r"education( (&|and) training)?|academic background|qualifications",
    "summary": r"(professional )?(summary|profile|objective|about me)",
    "certifications": r"certifications?|courses|training",
}
_HEADERS = {k: re.compile(rf"^(?:{v})\s*:?$", re.I) for k, v in SECTION_PATTERNS.items()}
CONTEXTUAL_SECTIONS = {"experience", "projects"}
_YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:[a-z]+\s+){0,3}experience", re.I)
_DEGREE = re.compile(r"\b(bachelor|b\.?sc|bsc|b\.?tech|btech|master|m\.?sc|msc|mba|ph\.?d|doctorate|associate degree|diploma)\b", re.I)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?:\+?\d[\s().-]?){10,}")
_LINKS = re.compile(r"linkedin\.com|github\.com|gitlab\.com", re.I)
_ACTION = re.compile(r"\b(increased|reduced|improved|built|led|saved|delivered|launched|automated|optimi[sz]ed|migrated|designed|developed)\b", re.I)
_NUMBER = re.compile(r"\d+\s*%|\$\s*\d|\b\d{2,}\b|\b\d+x\b")


@dataclass
class SkillHit:
    slug: str
    section: str
    contextual: bool
    matched_text: str
    snippet: str


def split_sections(text: str) -> list[tuple[str, str]]:
    current, out = "other", []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        key = stripped.rstrip(":").lower()
        header = next((name for name, rx in _HEADERS.items() if len(stripped) <= 40 and rx.match(key)), None)
        if header:
            current = header
            continue
        out.append((stripped, current))
    return out


def detect_skills(lines: list[tuple[str, str]], matcher: SkillMatcher) -> dict[str, SkillHit]:
    best: dict[str, SkillHit] = {}
    for line, section in lines:
        for m in matcher.find(line):
            ctx = section in CONTEXTUAL_SECTIONS
            old = best.get(m.slug)
            if old is None or (ctx and not old.contextual):
                best[m.slug] = SkillHit(m.slug, section, ctx, m.matched_text, line[:300])
    return best


def years_stated(text: str) -> float | None:
    vals = [int(v) for v in _YEARS.findall(text) if int(v) <= 50]
    return float(max(vals)) if vals else None


def education_lines(lines: list[tuple[str, str]]) -> list[str]:
    in_section = [ln for ln, sec in lines if sec == "education" and _DEGREE.search(ln)]
    anywhere = [ln for ln, _ in lines if _DEGREE.search(ln)]
    return [ln[:160] for ln in (in_section or anywhere)[:3]]


def quality_checks(text: str, lines: list[tuple[str, str]], sections: set[str]) -> list[dict]:
    words = len(text.split())
    body = [ln for ln, _ in lines]
    achievements = [ln for ln in body if _NUMBER.search(ln) and _ACTION.search(ln)]
    project_lines = [ln for ln, sec in lines if sec == "projects"]
    avg_len = (sum(len(ln.split()) for ln in body) / len(body)) if body else 0
    checks = [
        ("contact_email", "Email address present", bool(_EMAIL.search(text)), "Looks for something@domain."),
        ("contact_phone", "Phone number present", bool(_PHONE.search(text)), "Looks for 10 or more digits."),
        ("contact_links", "LinkedIn or code-hosting link present", bool(_LINKS.search(text)), "Looks for linkedin.com, github.com or gitlab.com."),
        ("section_skills", "Skills section present", "skills" in sections, "A line that is just a skills heading."),
        ("section_experience", "Experience section present", "experience" in sections, "A line that is just an experience heading."),
        ("section_education", "Education section present", "education" in sections, "A line that is just an education heading."),
        ("projects", "Project descriptions present", len(project_lines) >= 2, "At least 2 lines under a Projects heading."),
        ("achievements", "Measurable achievements present", len(achievements) >= 2,
         "At least 2 lines combining a number or percentage with an action verb (built, reduced, improved...)."),
        ("length", "Reasonable length", 150 <= words <= 1200, f"{words} words; 150 to 1,200 is treated as reasonable."),
        ("readability", "Concise lines", 0 < avg_len <= 28, f"Average {avg_len:.0f} words per line; 28 or fewer is treated as concise."),
    ]
    return [{"key": k, "label": label, "passed": ok, "how": how} for k, label, ok, how in checks]


def analyze(text: str, matcher: SkillMatcher) -> tuple[dict, dict[str, SkillHit]]:
    lines = split_sections(text)
    sections = {sec for _, sec in lines if sec != "other"}
    hits = detect_skills(lines, matcher)
    quality = quality_checks(text, lines, sections)
    result = {
        "sections_found": sorted(sections),
        "education_lines": education_lines(lines),
        "quality": quality,
        "checks_passed": sum(1 for q in quality if q["passed"]),
        "checks_total": len(quality),
        "method": "Rule-based: section headings, keyword matching against the SkillVar taxonomy, and simple patterns.",
    }
    return result, hits
