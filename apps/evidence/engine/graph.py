"""Skill dependency graph (a DAG of prerequisites)."""
from __future__ import annotations

from collections import deque


class SkillGraph:
    def __init__(self):
        self.names: dict[str, str] = {}
        self._prereqs: dict[str, list[str]] = {}

    def add(self, skill_id: str, name: str, prereqs: list[str] | None = None) -> None:
        self.names[skill_id] = name
        self._prereqs[skill_id] = list(prereqs or [])

    def validate(self) -> None:
        """Raise if a prerequisite is undefined or the graph has a cycle."""
        for s, ps in self._prereqs.items():
            for p in ps:
                if p not in self._prereqs:
                    raise ValueError(f"{s!r} requires undefined skill {p!r}")
        state: dict[str, int] = {}

        def visit(n: str) -> None:
            if state.get(n) == 1:
                raise ValueError(f"cycle detected at {n!r}")
            if state.get(n) == 2:
                return
            state[n] = 1
            for p in self._prereqs[n]:
                visit(p)
            state[n] = 2

        for s in self._prereqs:
            visit(s)

    def prerequisites(self, skill_id: str) -> list[str]:
        return list(self._prereqs[skill_id])

    def ancestors(self, skill_id: str) -> dict[str, int]:
        """All transitive prerequisites mapped to their hop distance (nearest)."""
        dist: dict[str, int] = {}
        q = deque((p, 1) for p in self._prereqs[skill_id])
        while q:
            n, d = q.popleft()
            if n in dist and dist[n] <= d:
                continue
            dist[n] = d
            q.extend((p, d + 1) for p in self._prereqs[n])
        return dist

    def __contains__(self, skill_id: str) -> bool:
        return skill_id in self._prereqs

    def skills(self) -> list[str]:
        return list(self._prereqs)
