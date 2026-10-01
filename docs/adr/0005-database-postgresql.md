# 0005 - Database: PostgreSQL

- Status: Accepted
- Date: 2026-09-29

## Decision
PostgreSQL, as a managed cloud instance. Models use standard Django fields; a
`django.contrib.postgres` feature is used only when it replaces application code.

## Rationale
| Option | Rejected / chosen because |
|---|---|
| **PostgreSQL** | Officially supported by Django; a failed migration rolls back cleanly; no license fee |
| MySQL | Officially supported and no license fee, but a failed migration must be undone by hand; its scale advantages (lighter connections) do not apply at this size |
| SQL Server | Third-party Django backend only; managed hosting charges a per-vCPU license with a 4-core minimum |

Accepted gap: no engine is imposed by a client or hospital IT today, so the choice rests on
Django fit and cost, not on an organisational constraint.

## Revisit if
- A hosting organisation (e.g. a hospital IT department) imposes a different engine.
- Connection limits are reached despite Django's PostgreSQL connection pool.

## References
[Django databases](https://docs.djangoproject.com/en/stable/ref/databases/) ·
[Django migrations: backend support](https://docs.djangoproject.com/en/stable/topics/migrations/) ·
[Cloud SQL pricing](https://cloud.google.com/sql/pricing)
