# Database design (PostgreSQL)

Ownership rule: every row that describes a person has a `user` foreign key with `ON DELETE CASCADE`, and every view
filters by `request.user` (other users' ids return 404). Shared reference data (skills, roles, questions, shared job
postings) uses `PROTECT` so it cannot be deleted while in use.

| Model (app) | Purpose | Key relationships / constraints | Indexes | Retention |
|---|---|---|---|---|
| `User` (accounts) | Custom user; email required | unique `lower(email)` | username unique | until account deletion |
| `Profile` (accounts) | Goal, education, experience, onboarding timestamp | 1:1 user; goal -> Role (SET_NULL); M2M preferred roles | PK | with user |
| `SkillCategory`, `Skill` (skills) | Canonical skills | unique slug and name; category PROTECT | slug | permanent reference |
| `SkillAlias` | Synonyms ("Postgres") | unique `normalized` globally (an alias maps to one skill) | unique | reference |
| `SkillPrerequisite` | DAG edges | unique pair; check `skill != prerequisite` | pair | reference |
| `Role`, `RoleRequirement` | Target roles and weighted requirements | unique (role, skill); check 0 < importance <= 1 | pair | reference |
| `Evidence` (evidence) | **Append-only** log: self-report, assessment, practice | user CASCADE; skill PROTECT; checks on score range, weight >= 0, assessment rows must have an answer and difficulty, self-report must have a level | (user, created_at), (user, skill) | with user |
| `Resume` (resumes) | Upload metadata, extracted text, analysis | user CASCADE; unique (user, sha256) | user + date | until the user deletes it (file + text + skills removed) |
| `ResumeSkill` | Detected/confirmed/rejected/manual skills with snippet | resume CASCADE; unique (resume, skill) | pair | with resume |
| `JobDescription` (jobs) | Pasted jobs (owned) or dataset jobs (user NULL) | check: ownerless rows must be `dataset`; unique content hash among shared rows | (user, -created), (source, -created), hash | owned: until user deletes |
| `JobRequirement` | Required/preferred, explicit/inferred, with snippet | job CASCADE; unique (job, skill) | (skill, kind) | with job |
| `JobMatch` (matching) | Stored result with full breakdown and formula version | user, job CASCADE; check 0 <= score <= 1 | (user, -created) | with user/job |
| `ReadinessSnapshot` | Readiness history after counted assessments | user CASCADE; check score range | (user, role, created) | with user |
| `Assessment`, `Question` (assessments) | Question bank; SQL grading data never shown | MCQ must have `correct_index`; difficulty 0..1; `version` | - | reference |
| `Attempt`, `AnswerRecord` | One submission and per-question result | user CASCADE; unique (attempt, question); stores `question_version` and `weight_applied` | (user, -created) | with user |
| `LearningResource`, `Roadmap`, `RoadmapItem` (roadmaps) | Curated activities, user roadmaps and progress | unique (roadmap, skill); item status todo/doing/done | (user, is_active) | with user |
| `Dataset`, `IngestionRun`, `DataQualityResult`, `RejectedRecord` (dataops) | Pipeline metadata, quality checks, failed rows | run CASCADE to results/rejects | - | operational history |

Transactions: resume processing, assessment submission, roadmap generation and each ingestion batch each run in one
transaction, so related rows succeed or fail together. Migrations are in `apps/*/migrations` and are checked in CI with
`makemigrations --check`.

Not done: no `pg_trgm`/GIN index for text search (the sample-job title search is a sequential scan, about 90 ms at 10,000
rows), no table partitioning, no archival job for old `Evidence`/`Attempt` rows.
