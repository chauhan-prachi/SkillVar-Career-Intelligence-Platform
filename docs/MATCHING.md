# How SkillVar scores matches and readiness

Everything here is a **product-specific heuristic**. It is not a trained model, not the probability of being hired, and not
the internal scoring of any applicant-tracking system. The numbers are starting values chosen to be explainable; they are
configurable in `config/settings.py` and should be validated against representative cases before anyone relies on them.

## 1. Evidence tiers and credit

Each skill requirement earns *credit* between 0 and 1 depending on the strongest evidence you have for it:

| Evidence | Class shown | Credit (expected) | Credit (conservative) |
|---|---|---|---|
| Assessment evidence, model says demonstrated | Confirmed match | model estimate | lower bound of the model interval |
| Assessment evidence, still developing | Possible match | model estimate | lower bound |
| Assessment evidence, too thin to decide | Possible match (insufficient evidence) | estimate capped at `UNDECIDED_ASSESSMENT_CAP` (0.5) | min(lower bound, cap) |
| Assessment evidence shows a gap | Not demonstrated | model estimate (low) | lower bound |
| Resume shows it in experience/projects | Possible match (evidence-supported) | `MATCH_CREDITS["contextual"]` = 0.5 | 0 |
| Self-reported and/or listed on resume only | Insufficient evidence | `MATCH_CREDITS["claimed"]` = 0.2 | 0 |
| Nothing | Missing | 0 | 0 |

Resume and self-reported evidence never reach "Confirmed": only assessments can. The **conservative** score counts
unverified evidence as zero.

The assessment estimate comes from the skill engine (`apps/evidence/engine`): a Beta belief per skill, updated by
difficulty-weighted results, with a small, separate prior from a claim. "Demonstrated" means mean >= 0.70 and the
approximate 90% interval's lower bound >= 0.50; "gap" means the interval's upper bound < 0.65. Thresholds are hand-set.

## 2. Combining skills

```
required_coverage  = sum(importance * credit over required skills)  / sum(importance over required skills)
preferred_coverage = same over preferred skills
experience_fit     = min(1, your_years / years_required)           only if the job states years AND you stated yours
overall            = sum(applied_weight * component)               over the components that apply
```
Nominal weights are required 0.6, preferred 0.2, experience 0.2. A component that cannot be computed (no preferred
skills listed, no years requested, or your years unknown) is **left out and the remaining weights are renormalized**, so
missing data never turns into a free perfect score. If nothing at all can be scored, no score is produced.
Self-stated years count toward the expected score but never toward the conservative one.

**Evidence coverage** = share of the requirement weight backed by something beyond a bare claim (assessment, thin
assessment, or resume experience context). It is reported next to the score and labels confidence: Higher (>= 60%),
Moderate (>= 30%), Low (< 30%).

## 3. Worked example (this exact case is a unit test)

Required: Python (assessed, demonstrated, estimate 0.80, lower bound 0.60), SQL (only self-reported). Preferred: Docker
(nothing). No experience requirement.

* required_coverage = (1 x 0.80 + 1 x 0.20) / 2 = 0.50
* preferred_coverage = 0
* experience not applicable, so weights become required 0.75, preferred 0.25
* overall = 0.75 x 0.50 + 0.25 x 0 = **0.375**
* conservative = 0.75 x ((0.60 + 0) / 2) = **0.225**
* evidence coverage = 1 of 3 skills evidence-backed = 33% -> "Moderate evidence"

## 4. Readiness for a role
Same function, with the role's skills (required/preferred and importance weights from the database) as the requirements
and no experience component. Each assessment that changes your evidence stores a snapshot so the dashboard can show a real
trend (needs at least two).

## 5. Job requirement extraction
Rule-based (`apps/jobs/analyzer.py`): headings such as "Requirements" / "Nice to have", cue phrases ("preferred", "a plus"),
and the shared skill matcher. Skills mentioned in responsibilities count as required. Skills implied only by a prerequisite
(Django -> Python) are shown as *inferred* and are **not scored** unless you promote them. The posting's years and
education are read by pattern (highest years figure found). Only skills in the SkillVar taxonomy are recognized.

## 6. Known limitations
* The taxonomy has about 60 skills; anything outside it is invisible to matching.
* Keyword matching cannot understand negation ("no Java experience needed") or seniority nuances.
* The 0.2 / 0.5 credits and 0.6 / 0.2 / 0.2 weights are unvalidated starting points.
* Assessment banks are small; a handful of items cannot define professional ability.
* Experience is self-stated and unverified.
