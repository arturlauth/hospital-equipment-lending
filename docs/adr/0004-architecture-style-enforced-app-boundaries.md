# 0004 - Architecture style: Django apps with enforced code boundaries

- Status: Accepted
- Date: 2026-09-29

## Decision
One Django app per capability (equipment, lending, staff), with normal cross-app `ForeignKey`s.
Cross-app writes go through the owning app's `services.py`. Import Linter `protected` contracts
block importing another app's models, forms or views, as a failing CI check.

`services.py` is also the service layer required by ADR 0003.

## Rationale
| Option | Rejected / chosen because |
|---|---|
| Plain Django apps | Nothing stops cross-app imports, and there is no reviewer to catch them |
| Strict modular monolith (bare IDs) | Loses DB integrity, `on_delete`, joins and admin; schema independence is only worth that with multiple teams |
| **Apps + enforced boundaries** | Keeps DB integrity, ORM and admin; the linter is about ten lines of config |

Accepted gap: the linter sees imports, not ORM traversal (`loan.equipment.name`) or cross-app
queryset lookups (`Loan.objects.filter(equipment__status=...)`). Both count as reads and are
allowed.

## Revisit if
- A second developer or team owns an app.
- An app needs its own database or service.
- `services.py` files are only pass-through wrappers after the first milestone.
- Linter exemptions (`ignore_imports`, `allowed_importers`) outnumber the contracts: delete the
  config and amend this ADR to plain Django apps.

## References
[Makimo](https://makimo.com/blog/modular-monolith-in-django/) ·
[Milan Jovanović](https://milanjovanovic.tech/blog/modular-monolith-data-isolation) ·
[Import Linter contracts](https://import-linter.readthedocs.io/en/v2.7/contract_types.html)
