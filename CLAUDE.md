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
- **Learning stays out of this repo.** Experiments, study notes and trial-and-error go to
  `C:\Users\artur\Documents\Learning`.

## Decisions

See `docs/adr/README.md`. Accepted so far: responsive web app, Django backend, Django templates +
HTMX frontend (must stay portable to React/Next), Django apps with enforced code boundaries
(Import Linter), PostgreSQL (managed).
