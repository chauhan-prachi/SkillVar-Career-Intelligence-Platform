"""Rule-based job-description analysis. Required vs preferred comes from section headings and cue words in the
text; skills implied by prerequisites are labelled 'inferred' and are NOT scored unless explicitly added."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from apps.skills.matcher import SkillMatcher

REQUIRED_HDR = re.compile(r"\b(requirements?|qualifications?|must[- ]have|what you(?:'|’)ll need|required|what we(?:'|’)re looking for|minimum qualifications|you have)\b", re.I)
PREFERRED_HDR = re.compile(r"\b(nice[- ]to[- ]have|preferred|bonus|a plus|good to have|desirable|preferred qualifications)\b", re.I)
RESP_HDR = re.compile(r"\b(responsibilities|what you(?:'|’)ll do|duties|key responsibilities|the role|your role)\b", re.I)
_PREFERRED_CUE = re.compile(r"\b(preferred|nice to have|a plus|bonus|desirable|is a plus|would be great)\b", re.I)
_YEARS = re.compile(r"(\d{1,2})\s*(?:-|–|to)?\s*(?:\d{1,2})?\s*\+?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:[a-z+#.]+\s+){0,4}?experience", re.I)
_TITLE_LABEL = re.compile(r"^(?:job\s+title|title|position|role)\s*[:\-]\s*(.+)$", re.I)
_COMPANY_LABEL = re.compile(r"^company\s*[:\-]\s*(.+)$", re.I)
_EDU = [(re.compile(r"\b(ph\.?d|doctorate)\b", re.I), "Doctorate"),
        (re.compile(r"\b(master'?s?|m\.?sc|msc)\b", re.I), "Master's degree"),
        (re.compile(r"\b(bachelor'?s?|b\.?sc|bsc|b\.?tech|btech)\b", re.I), "Bachelor's degree"),
        (re.compile(r"\b(degree|diploma)\b", re.I), "Degree (level not specified)")]


@dataclass
class ReqHit:
    slug: str
    kind: str
    origin: str
    snippet: str


@dataclass
class JobAnalysis:
    title: str = ""
    company: str = ""
    years_required: float | None = None
    education_required: str = ""
    responsibilities: list[str] = field(default_factory=list)
    requirements: list[ReqHit] = field(default_factory=list)


def _looks_like_header(line: str) -> bool:
    """A header is not a bullet and is either a short phrase or ends with a colon ("Nice to have:")."""
    if line.startswith(("-", "•", "*", "–")) or len(line) > 60:
        return False
    return line.endswith(":") or len(line.split()) <= 3


def _section_of(line: str, current: str) -> str | None:
    if not _looks_like_header(line):
        return None
    if PREFERRED_HDR.search(line):
        return "preferred"
    if REQUIRED_HDR.search(line):
        return "required"
    if RESP_HDR.search(line):
        return "responsibilities"
    if line.endswith(":"):          # capitalisation alone never makes a header ("SQL", "AWS" are skills)
        return "other"
    return None


def analyze_job_text(text: str, matcher: SkillMatcher, prerequisites: dict[str, list[str]] | None = None) -> JobAnalysis:
    out = JobAnalysis()
    section, hits = "other", {}
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for i, line in enumerate(lines):
        if m := _TITLE_LABEL.match(line):
            out.title = out.title or m.group(1).strip()[:200]
            continue
        if m := _COMPANY_LABEL.match(line):
            out.company = out.company or m.group(1).strip()[:200]
            continue
        new = _section_of(line, section)
        if new:
            section = new
            if len(line) <= 40:
                continue
        if i == 0 and not out.title and len(line) <= 80 and not line.endswith((":", ".")):
            out.title = line
        if section == "responsibilities" and len(out.responsibilities) < 12 and len(line) > 15:
            out.responsibilities.append(line.lstrip("-•* ")[:200])
        kind = "preferred" if (section == "preferred" or _PREFERRED_CUE.search(line)) else "required"
        for m in matcher.find(line):
            old = hits.get(m.slug)
            if old is None or (old.kind == "preferred" and kind == "required"):
                hits[m.slug] = ReqHit(m.slug, kind, "explicit", line[:300])
    out.requirements = list(hits.values())
    yrs = [int(a) for a in _YEARS.findall(text)]
    out.years_required = float(max(yrs)) if yrs else None
    for rx, label in _EDU:
        if rx.search(text):
            out.education_required = label
            break
    if prerequisites:
        for hit in list(out.requirements):
            for pre in prerequisites.get(hit.slug, []):
                if pre not in hits:
                    hits[pre] = ReqHit(pre, hit.kind, "inferred", f"Implied: a prerequisite of {hit.slug}")
        out.requirements = list(hits.values())
    return out
