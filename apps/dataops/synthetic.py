"""Deterministic SYNTHETIC job postings for development, demos and load tests. They are not real vacancies."""
from __future__ import annotations

import random

from apps.skills.seed_data import ROLES, S

COMPANIES = ["Northwind Labs", "Bluebird Analytics", "Cedar Systems", "Orbit Data Co", "Maple Software", "Quanta Works",
             "Helio Digital", "Riverstone Tech", "Pinecone Studio", "Atlas Cloud"]
INTROS = ["We are growing our team and looking for a motivated engineer.", "Join a small team building reliable products.",
          "You will work closely with product and analytics colleagues."]
RESPONSIBILITIES = {
    "junior-data-engineer": ["Build and maintain data pipelines", "Monitor data quality and fix failing jobs", "Model data for analytics"],
    "data-analyst": ["Analyze data to answer business questions", "Build dashboards for stakeholders", "Present findings clearly"],
    "python-backend-developer": ["Build and maintain backend services and APIs", "Write tests and review code", "Improve performance and reliability"],
}


def generate(count: int, seed: int = 1) -> list[dict]:
    rng = random.Random(seed)
    roles = list(ROLES.items())
    rows = []
    for i in range(count):
        slug, (title, _desc, reqs) = roles[rng.randrange(len(roles))]
        required = [S[s][0] for s, _imp, req in reqs if req and rng.random() < 0.85]
        preferred = [S[s][0] for s, _imp, req in reqs if not req and rng.random() < 0.7]
        extras = [S[k][0] for k in rng.sample(sorted(S), 2)]
        years = rng.choice([None, 0, 1, 2, 3, 5])
        lines = [f"Job Title: {title}", f"Company: {rng.choice(COMPANIES)}", rng.choice(INTROS), "", "Responsibilities:"]
        lines += [f"- {r}" for r in RESPONSIBILITIES[slug]]
        lines += ["", "Requirements:"] + [f"- Experience with {s}" for s in required]
        if years is not None:
            lines.append(f"- {years}+ years of experience in a similar role")
        lines.append(rng.choice(["- Bachelor's degree or equivalent experience", "- Strong communication skills"]))
        lines += ["", "Nice to have:"] + [f"- {s}" for s in (preferred + extras[:1])]
        rows.append({"external_id": f"SYN-{seed}-{i:05d}", "title": title, "company": rng.choice(COMPANIES),
                     "years_required": "" if years is None else str(years), "description": "\n".join(lines) + f"\n\nReference: SYN-{seed}-{i:05d}"})
    return rows
