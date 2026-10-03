# 0006 - Testing: pytest + pytest-django

- Status: Accepted
- Date: 2026-10-03

## Decision
Tests run with pytest and pytest-django, written as plain functions with pytest fixtures.
Each test creates the rows it needs; the demo JSON fixtures are for local data, never for tests.
A test is kept only if a plausible mistake in our code would make it fail.

## Rationale
| Option | Rejected / chosen because |
|---|---|
| **pytest + pytest-django** | The standard Python test runner, so the skill carries beyond Django; plain `assert` and fixtures keep tests short |
| Django's built-in test runner | Works (built on `unittest`), but is Django-only and needs class-based tests |

Tests own their data so that editing the demo data never breaks a test for an unrelated reason.

## Revisit if
- A Django testing feature the project needs is unavailable through pytest-django.

## References
[pytest](https://docs.pytest.org/) · [pytest-django](https://pytest-django.readthedocs.io/) ·
[Kent Beck — Desirable unit tests](https://newsletter.kentbeck.com/p/desirable-unit-tests)