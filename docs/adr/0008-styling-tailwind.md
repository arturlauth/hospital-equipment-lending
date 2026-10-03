# 0008 - Styling: Tailwind CSS (standalone CLI)

- Status: Accepted
- Date: 2026-10-03

## Decision
Style templates with Tailwind CSS utility classes. The standalone CLI runs through the
`pytailwindcss` dev dependency, so no Node toolchain. The built CSS is not versioned; it is
rebuilt locally and, later, in the deploy pipeline.

## Rationale
| Option | Rejected / chosen because |
|---|---|
| Bootstrap 5 | Ready components, but a generic look the product wants to avoid |
| Hand-written CSS | No design experience on the team; a consistent system would be built from zero |
| **Tailwind** | Mobile-first by default, consistent spacing and colour scale, and the classes carry over to React/Next (ADR 0003) |

## Revisit if
- Class lists repeat across templates faster than includes can absorb them.
- The frontend moves to React/Next: keep Tailwind, change only the build.
