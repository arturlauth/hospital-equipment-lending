# 0002 - Backend: Python / Django

- Status: Accepted
- Date: 2026-09-20

## Decision
Build the backend with Django.

## Rationale
The domain is CRUD, auth, permissions and audit. Django ships ORM, migrations, admin and a
permission model out of the box; FastAPI would require assembling those.
