---
name: ship
description: Artur approved the diff - run the quality gates, commit, push and open the PR. Only Artur triggers this.
disable-model-invocation: true
---

# Ship

Artur has reviewed the diff. Run straight through; stop only on a failure.

1. **Branch.** `git branch --show-current` must not be `main`. If it is, stop.
2. **Gates.** Run, in order, and stop with the full output on the first failure (do not fix, report):
   - `uv run ruff check`
   - `uv run ruff format --check`
   - `uv run pytest` (needs the DB: `docker compose up -d db`)
3. **Lessons (usually none).** Write a fact only if it is still true next month, not visible from
   code or git history, and changes what someone does. Repo/stack facts and project feedback go to
   this repo's `CLAUDE.md` (grep first; tighten a near-match line instead of adding one) and ship in
   this commit. Machine-level traps (shell, PATH, CLI quirks) go to
   `C:\Users\artur\Documents\ai-home-base\Claude\CLAUDE.md`, left uncommitted there with a note to
   run `/sync-global`. Never write to `memory/`.
4. **Stage.** `git status --porcelain -uall`, then `git add <path>` for each file this change
   touched, by explicit path. Never `git add .` or a directory. A path that looks unrelated or
   sensitive is not staged; list it in the report.
5. **Commit.** One commit, imperative English subject (<= 72 chars), short body if needed, ending with
   the Co-Authored-By line from the session's attribution reminder.
6. **Push.** `git push -u origin <branch>`. Never push `main`.
7. **PR.** `& "C:\Program Files\GitHub CLI\gh.exe" pr create --base main --title "<subject>" --body "<what and why, 2-5 lines>"`
   with the PR attribution line at the end of the body. Never merge - Artur merges.
8. **Report** in <= 8 lines: gate results (e.g. `pytest: 3 passed`), commit subject, PR URL,
   anything left unstaged, lessons written (absolute paths), then **Retro:** <= 3 one-line bullets on
   what went wrong in execution (claim past evidence, result misread, work redone) or "clean run".
