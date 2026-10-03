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

## Decisions

See `docs/adr/README.md`. Accepted so far: responsive web app, Django backend, Django templates +
HTMX frontend (must stay portable to React/Next), Django apps with enforced code boundaries
(Import Linter), PostgreSQL (managed).
