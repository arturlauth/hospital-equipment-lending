# 0007 - Lint and format: Ruff

- Status: Accepted
- Date: 2026-10-03

## Decision
Ruff lints and formats all code; migrations are excluded. Rules: Ruff defaults (E4, E7, E9, F),
import sorting (I), bugbear (B) and Django checks (DJ). Line length 100.
A rule set is added only if it catches bugs or settles a recurring style debate.

## Rationale
| Option | Rejected / chosen because |
|---|---|
| **Ruff** | One tool and one config for lint, import order and format; fast enough to run on every save |
| flake8 + isort + Black | Same checks, three tools and three configs to keep in sync |

## Revisit if
- A check the project needs exists only outside Ruff.

## References
[Ruff](https://docs.astral.sh/ruff/) · [Ruff rules](https://docs.astral.sh/ruff/rules/)
