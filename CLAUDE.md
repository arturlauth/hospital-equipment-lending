# hospital-equipment-lending

Lending system for hospital equipment. Monorepo, one product.

## Rules

- **English only** — code, comments, docs, commit messages.
- **Docs explain decisions and business, never code.** `docs/adr/` holds architecture decisions
  (what was chosen, why, when to revisit). Business rules live in `docs/`. Code is documented by
  docstrings, not by docs. Reason: docs that describe code drift silently as the code changes;
  decisions and business rules change only by an explicit decision, which produces a new ADR.
  Business lives in one file, `docs/business-model.md` (entities, situações, processes, rules) in
  business words: no field/model names, form validation or admin mechanics.
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
  Enforced in `.claude/settings.json`. GitHub ruleset `protect-main` also requires a PR and the
  `checks` CI job.
- **CLAUDE.md-only edits never get their own branch or PR.** Leave them uncommitted and carry them
  onto the next feature branch, where they ship with that PR.
- **Visual changes get browser QA before review.** After changing what a page shows or how it reacts
  (buttons, chips, layout, HTMX swaps), Claude spawns the `qa` agent (`.claude/agents/qa.md`,
  Sonnet) and loops fix → QA until it passes, then stops for Artur. QA logs in with the local
  `QA_USERNAME`/`QA_PASSWORD` test account from `.env`. Give QA numbered expectations with exact
  steps (URL, what to click, what must be true); re-runs list only the failed items.
  QA writes screenshots/snapshots to `.playwright-mcp/` (gitignored); once QA has reported, Claude
  deletes that folder (`rm -rf .playwright-mcp`), since the QA agent has no delete tool.
- **"Merged" alone means clean up, without asking:** `git switch main`, `git pull`, then delete the
  merged branch locally (`git branch -d`) and on the remote (`git push origin --delete`).

## Commands

Managed with `uv`. Settings read `.env` (python-dotenv); `DJANGO_SECRET_KEY` and `POSTGRES_DB/USER/PASSWORD/HOST/PORT`
are required; `.env.example` lists every variable (`config/test_env_example.py` fails if one is missing).

- DB: `docker compose up -d db` (Postgres 18 on 5432)
- Migrate / run: `uv run python manage.py migrate`, `uv run python manage.py runserver`
- Demo data: `uv run python manage.py loaddata demo_inventory demo_lending` (inventory first)
- Tests: `uv run pytest`; one test: `uv run pytest hospitalequip/lending/tests.py::test_name`
  (needs the DB running — pytest-django creates a test database)
- Lint / format: `uv run ruff check --fix`, `uv run ruff format` (ADR 0007; migrations excluded)
- CSS: `uv run tailwindcss -i assets/tailwind.css -o static/css/app.css --watch` (ADR 0008;
  output not versioned, pages render unstyled until built)

## Architecture

Django project in `config/`, apps under `hospitalequip/`: `inventory` (Warehouse, Category, Equipment with images and spec rows) and
`lending` (Person, Loan), `staff` (login, roles as auth Groups created by migration; staff pages use
`staff.access.staff_required`). Shared
layout in `templates/base.html`. An app's models are imported only by that app, enforced by Import Linter
(`uv run lint-imports`; contracts in `pyproject.toml`); other apps go through its `services.py`.
`lending` FKs `inventory`; `inventory` reads loan state through that reverse relation (ORM read,
allowed by ADR 0004). Debts: `docs/known-debts.md`. Lending rules
(e.g. one open loan per equipment, date ordering) are DB constraints in `Loan.Meta.constraints`.

## Decisions

See `docs/adr/README.md`. Accepted so far: responsive web app, Django backend, Django templates +
HTMX frontend (must stay portable to React/Next), Django apps with enforced code boundaries
(Import Linter), PostgreSQL (managed).

## Lessons Learned — Do Not Retry

Running log of mistakes, dead-ends, and environment quirks discovered while working on this
repo. **Purpose:** a future session should read this and avoid burning time/tokens
re-discovering the same thing. Append a row whenever a real mistake or non-obvious constraint
is hit — newest at the top.

**Scope:** repo- and stack-specific traps only. Machine-level traps (PATH, shells, git
credentials, a missing CLI) belong in the global `CLAUDE.md`, not here. Anything already
stated elsewhere in this file, in the code, or in git history does not get a row.

| Date | Trap / mistake | Correct approach |
|---|---|---|
| 2026-10-04 | `Meta.ordering = ["name"]` vanished once `person_list` added `Count` annotations (Django drops Meta.ordering on aggregated queries); QA caught unsorted Pessoas | Add an explicit `.order_by(...)` to any annotated queryset; test the order with a row created last that sorts first |
| 2026-10-04 | A `sed` mutation "proved" a test because the pattern no longer matched: `ruff format` had moved the trailing comment, so the fix was never removed | After mutating, `grep -c` the removed text (must be 0) before trusting a red/green result |
| 2026-10-04 | QA reported a missing element that the code renders: two `runserver` processes were listening on :8000 and one was stale | Before QA, check `netstat -ano` for a single listener on :8000 |
| 2026-10-04 | `subagent_type: "qa"` failed ("Agent type 'qa' not found") after `/clear`: agents load only at process start, not on clear | Restart Claude Code, or spawn `general-purpose` with `model: sonnet` told to read and follow `.claude/agents/qa.md` |
| 2026-10-04 | New Tailwind classes did nothing in the browser (chip highlight missing) because `static/css/app.css` was stale; tests and the template were fine | After adding classes, rebuild once (`uv run tailwindcss -i assets/tailwind.css -o static/css/app.css --minify`) or keep `--watch` running before any visual check |
| 2026-10-04 | `select_for_update()` with `select_related` on a nullable FK (e.g. `Loan.guarantor`) crashes on PostgreSQL: "FOR UPDATE cannot be applied to the nullable side of an outer join" | Lock only the row you change: `select_for_update(of=("self",))` |
| 2026-10-03 | The on-`main` hook in `.claude/settings.json` blocks every Write, even to the scratchpad; a large mockup write was rejected and had to be resent | Create the feature branch before writing any file, including throwaway mockups |
| 2026-10-03 | Weakening a `Meta.constraints` entry to watch its test fail changed nothing: the test DB is built from migrations, so the test stayed green | Mutate the constraint in the migration file and run with `--create-db`; then restore |
| 2026-10-03 | `.env.example` drifted from `settings.py` (listed 2 of 7 variables) and the gap was logged as a debt instead of fixed; a fresh clone fails at startup with `KeyError` | Add the variable to `.env.example` in the same change that reads it; `config/test_env_example.py` now enforces this |
