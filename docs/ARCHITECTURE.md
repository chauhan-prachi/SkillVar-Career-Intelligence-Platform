# Architecture walkthrough

SkillVar is a Django project (`config/`) made of small apps under `apps/`. The rule that keeps it understandable:
**views stay thin, business logic lives in `services` modules, and the scoring maths is pure Python with no database**.

```
browser ──► views.py (thin: forms, permissions, redirects)
                │
                ▼
            services.py (transactions, orchestration)
                │                 │
                ▼                 ▼
   models (PostgreSQL)     pure functions: apps/matching/scoring.py,
                           apps/evidence/engine/*, apps/jobs/analyzer.py,
                           apps/resumes/analysis.py, apps/assessments/sandbox.py
```

| App | Responsibility | Key files |
|---|---|---|
| `accounts` | Custom user, profile, onboarding, email-or-username login | `models.py`, `services.py`, `backends.py` |
| `skills` | The one taxonomy (skills, aliases, prerequisites, roles) and the shared matcher | `matcher.py`, `normalize.py`, `seed_data.py` |
| `evidence` | Append-only evidence log; rebuilds a person's skill state; the skill engine | `profile.py`, `engine/` |
| `resumes` | Safe upload, text extraction, rule-based analysis, user review | `extract.py`, `analysis.py`, `services.py` |
| `jobs` | Job-description analysis and manual correction | `analyzer.py`, `services.py` |
| `matching` | Explainable match score and role readiness | `scoring.py`, `services.py` |
| `assessments` | Question bank, grading, repeat-attempt policy, SQL sandbox | `services.py`, `sandbox.py`, `seed_bank.py` |
| `roadmaps` | Prerequisite-aware plans, progress, next best action | `services.py` |
| `dataops` | CSV/JSON ingestion, profiling, quality results, run history | `pipeline.py`, `synthetic.py`, `management/` |
| `web` | Landing page, dashboard, read-only API, health check, rate limiter | `dashboard.py`, `api.py`, `ratelimit.py` |

## The data flow in one paragraph
You make *claims* (onboarding), upload a *resume* (skills with the sentence they came from), and answer *assessments*.
Claims and assessments are rows in `Evidence`; resume skills are `ResumeSkill` rows you can accept or reject. To score
anything, `evidence.profile.build_signals(user)` **replays** that data through the engine and produces one `SkillSignals`
object per skill. `matching.scoring` turns signals plus a list of requirements (from a job or a role) into a score and an
explanation. Nothing about a person is cached or edited in place, so every number can be explained and recomputed.

## Why event sourcing here?
If scores were stored directly they could drift from the evidence behind them. Replaying an append-only log means: a
changed formula can be re-applied to old data, an audit can show exactly why a number is what it is, and deleting a resume
automatically removes what it contributed.

## The skill engine (`apps/evidence/engine`)
Each skill is a `Beta(alpha, beta)` belief about "can do this". A correct answer adds to alpha, a wrong one to beta, weighted
by question difficulty (passing a hard item says more; failing an easy item says more) and by item reliability
(multiple choice 0.6, SQL 1.0). A self-claim adds at most one pseudo-observation and is ignored once real evidence exists.
Passing a skill lends small *inferred* support to its prerequisites, which never counts as verification. The belief's
mean and approximate 90% interval give the estimate and its uncertainty; the interval is what separates "demonstrated" from
"too little evidence to say". The recommender picks one next step: assess unverified claims, trace failures to the deepest
unproven prerequisite, practise confirmed gaps, and re-test after practice, never offering an item that cannot produce counted evidence.

## Repeat-attempt policy (stops score farming)
First attempt: full weight. Re-attempt *after completing practice* for that skill: half weight. Any other re-attempt: stored
for audit with weight 0, so retrying one question until it is right cannot raise your estimate.

## The skill matcher (`apps/skills/matcher.py`)
One regular expression built from every skill name and alias (about 175 terms), longest term first, with boundaries that
keep `c++`, `c#`, `node.js` intact and stop `SQL` matching inside `SQLite`. Resumes, job descriptions and (future) assessments
all use it, so a skill is defined exactly once.

## Where to read next
`docs/MATCHING.md` (formula with a worked example), `docs/DATABASE.md` (tables and constraints), `docs/SECURITY.md`.
