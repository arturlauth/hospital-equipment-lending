# hospital-equipment-lending

Lending system for hospital equipment. Monorepo, one product.

## Rules

- **English only** — code, comments, docs, commit messages.
- **Docs explain decisions and business, never code.** `docs/adr/` holds architecture decisions
  (what was chosen, why, when to revisit). Business rules live in `docs/`. Code is documented by
  docstrings, not by docs. Reason: docs that describe code drift silently as the code changes;
  decisions and business rules change only by an explicit decision, which produces a new ADR.
- **Lean docs.** Short files. No filler sections, no restating the code. An ADR follows the shape
  of `docs/adr/0004-*`: Decision in a few lines, options as a table, Revisit if, no persuasion.
  A detailed prompt is context, not a request for length; a seven-section draft was rejected.
- **README states only purpose, kept open-ended ("ongoing project").** No status, progress or
  stack details — they go stale every session. Bilingual (English + pt-BR) in one file for now.
- **Test business rules, not plumbing.** A test earns its place only if a realistic code change
  would turn it red. Write each rule as a sentence ("one open loan per equipment"); it gets a
  happy-path test plus one per edge: boundaries (same day, empty), state transitions (lend after
  return, return twice), concurrency (double submit), bad references (written-off equipment).
  Never test Django/PostgreSQL themselves — test our constraints, models and logic. See a new
  test fail once before trusting it.
- **Learning stays out of this repo.** Experiments, study notes and trial-and-error go to
  `C:\Users\artur\Documents\Learning`.

## Git flow

- One branch per change off `main`: `feat/<slug>`, `fix/<slug>` or `setup/<slug>`. Never edit on `main`.
- Claude creates the branch, makes the changes and stops for Artur to review the diff. Only after he
  runs `/ship` does Claude run the gates (ruff + pytest), commit, push and open the PR
  (`.claude/skills/ship/`). Artur merges (merge commit); Claude never merges or pushes `main`.
  Enforced in `.claude/settings.json`.

## Commands

Managed with `uv`. Settings read `.env` (python-dotenv); `DJANGO_SECRET_KEY` and `POSTGRES_DB/USER/PASSWORD/HOST/PORT`
are required — `.env.example` lists only the first two.

- DB: `docker compose up -d db` (Postgres 18 on 5432)
- Migrate / run: `uv run python manage.py migrate`, `uv run python manage.py runserver`
- Demo data: `uv run python manage.py loaddata demo_inventory demo_lending` (inventory first)
- Tests: `uv run pytest`; one test: `uv run pytest hospitalequip/lending/tests.py::test_name`
  (needs the DB running — pytest-django creates a test database)
- Lint / format: `uv run ruff check --fix`, `uv run ruff format` (ADR 0007; migrations excluded)

## Architecture

Django project in `config/`, apps under `hospitalequip/`: `inventory` (Warehouse, Equipment) and
`lending` (Person, Loan). Dependency runs one way: `lending` → `inventory` (Loan FKs Equipment), never
back, enforced by Import Linter (`uv run lint-imports`; contracts in `pyproject.toml`). Lending rules
(e.g. one open loan per equipment, date ordering) are DB constraints in `Loan.Meta.constraints`.

## Decisions

See `docs/adr/README.md`. Accepted so far: responsive web app, Django backend, Django templates +
HTMX frontend (must stay portable to React/Next), Django apps with enforced code boundaries
(Import Linter), PostgreSQL (managed).
