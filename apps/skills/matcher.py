"""The single skill-matching service reused by resumes, job analysis and assessments.

It matches canonical skill names and aliases in free text with word-boundary rules that keep tokens such as
c++, c#, node.js intact, and prefers the longest alias at any position ("postgresql database" over "postgresql").
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Skill, SkillAlias
from .normalize import normalize_term

_BEFORE = r"(?<![a-z0-9+#.])"
_AFTER = r"(?![a-z0-9+#]|\.[a-z0-9])"


@dataclass(frozen=True)
class SkillMention:
    slug: str
    matched_text: str
    start: int
    end: int


class SkillMatcher:
    def __init__(self, term_to_slug: dict[str, str]):
        self.term_to_slug = term_to_slug
        parts = []
        for term in sorted(term_to_slug, key=len, reverse=True):
            words = [re.escape(w) for w in term.split(" ")]
            parts.append(r"[\s\-/]*".join(words) if len(words) > 1 else words[0])
        self._regex = re.compile(_BEFORE + "(?:" + "|".join(parts) + ")" + _AFTER) if parts else None

    @classmethod
    def from_db(cls) -> SkillMatcher:
        terms: dict[str, str] = {}
        for slug, name in Skill.objects.filter(is_active=True).values_list("slug", "name"):
            terms[normalize_term(name)] = slug
        for slug, normalized in SkillAlias.objects.filter(skill__is_active=True).values_list("skill__slug", "normalized"):
            terms[normalized] = slug
        return cls(terms)

    def find(self, text: str) -> list[SkillMention]:
        if not self._regex:
            return []
        lowered = text.lower()
        found = []
        for m in self._regex.finditer(lowered):
            slug = self.term_to_slug.get(normalize_term(m.group(0)))
            if slug:
                found.append(SkillMention(slug, text[m.start():m.end()], m.start(), m.end()))
        return found
