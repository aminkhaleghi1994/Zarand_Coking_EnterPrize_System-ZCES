# ZCES Improvements Review — Add / Remove / Watch

**Date:** 2026-08-29 · **Language:** English (Persian version: `docs/reviews/fa/`)
**Question reviewed:** What else should be done to improve the
implementation? Should anything be added or removed?

## 1. Add (beyond the requirements text)

### Security hardening (cheap now, expensive later)
- **Account lockout + password policy** — failed-login throttling per
  account/IP before rate limiting exists; bcrypt cost target agreed in Phase 2.
- **Refresh-token reuse detection** — rotation already required; detecting
  reuse of a rotated token must invalidate the family (stolen-token signal).
- **Security headers** — CSP, X-Frame-Options DENY, HSTS (prod), referrer
  policy; verified in Phase 10.
- **Session/logout everywhere** — invalidate all refresh tokens on password
  change (audited).

### Developer experience & quality
- **Pre-commit hooks** — ruff + mypy (backend), eslint + prettier
  (frontend), detect-secrets; installed Phase 1, enforced in CI Phase 1+.
- **One-command bring-up** — `scripts/dev.ps1` starts backend, frontend,
  celery, and checks Postgres/Redis health; `scripts/seed-dev.ps1` for
  idempotent dev seeds. This directly serves the owner's goal of personally
  running the app.
- **Faker-based dev seeds** — realistic bilingual sample data (employees,
  catalog, stock, loans) so every UI page is demonstrable without manual
  data entry.

### Observability & correctness
- **/healthz and /readyz** — liveness vs readiness (DB + Redis checks);
  used by systemd and Nginx.
- **Prometheus /metrics** — request latency, error rates, outbox depth,
  SSE connections; Grafana dashboards remain optional post-v1.
- **Playwright E2E pack** — browser-level smoke of the §27.3 critical
  flows (login, employee creation, item request→fulfillment, loan
  validation, live notification), both locales incl. RTL screenshots.

### Product polish
- **Empty/error/loading states as first-class UI** — every list page ships
  with skeleton, empty state, and error state (bilingual) from day one.
- **Optimistic-locking UX** — STALE_VERSION errors surface a friendly
  "data changed, reload" dialog instead of a raw error.
- **Jalali/Gregorian date picker component** — shared across all forms;
  never hand-rolled per page.

## 2. Remove / defer (keep v1 lean)

| Item | Decision | Reason |
|---|---|---|
| Cloud layer (06) | Out | On-prem VM; env-driven config preserves portability |
| Load balancer / multi-node (11) | Out | Single VM suffices; stateless design keeps option open |
| CDN | Out | Intranet app — no public edge |
| PostgreSQL native RLS | Defer | App-level scope filter is mandated anyway; revisit if threat model changes |
| Full OpenTelemetry tracing | Defer | trace_id correlation (FE↔BE↔worker) meets the observability requirement at a fraction of the ops cost |
| Grafana dashboards | Defer | Prometheus metrics now, dashboards post-v1 |
| Docker | Defer (per requirements §33) | Explicitly planned after local/VM stabilization |
| Email channel | Defer | In-app + SSE only in v1 (email hooks stubbed behind the outbox) |

## 3. Watch items / risks

1. **Font license** — FontLicense.txt must ship beside the fonts; insert the
   6-digit FontIran license code when available (placeholder currently empty).
2. **Redis dependency** — absent on this machine; WSL2 decided. Phase 1
   bring-up includes install + `redis-cli ping` verification. SSE fan-out
   and Celery both depend on it — do not let Phase 8 arrive without it.
3. **PostgreSQL 18 vs "16+"** — satisfies the requirement, but Alembic
   autogenerate quirks must be reviewed per migration (partial indexes,
   UUID columns) — already codified in backend/AGENTS.md.
4. **Scope resolver is the #1 project risk** (requirements §36.1) —
   mitigated by: central resolver, unit + integration tests in Phase 2
   before any business module exists, and the no-query-without-scope rule.
5. **Jalali year boundary math** — loan validation depends on correct
   Jalali year derivation; dedicated unit tests around Nowruz boundaries.
6. **create-next-app vs pre-populated frontend/** — frontend/ already
   contains DESIGN.md, AGENTS.md, and src/fonts; Phase 1 scaffolds Next.js
   in a temp dir and merges (documented in the Phase 1 spec).

## 4. Definition of done (project-level)

The implementation is done when: all 11 phase gates have passed; the §35
success criteria are demonstrably met; the owner can follow
`docs/runbooks/bring-up.md` (created Phase 11) to bring the whole web
application up personally on the VM and observe every module working in
both English and Persian.
