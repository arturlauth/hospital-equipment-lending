# 0003 - Frontend: Django templates + HTMX

- Status: Accepted
- Date: 2026-09-20

## Decision
Start with server-rendered Django templates enhanced with HTMX.

## Constraint
Must allow a later move to React/Next. Keep business logic in the service/domain layer, not in
views or templates, so a JSON API can be added beside the HTML views without a rewrite.
