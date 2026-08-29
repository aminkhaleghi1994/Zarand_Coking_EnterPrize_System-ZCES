# ZCES Implementation Roadmap Review

**Date:** 2026-08-29 · **Language:** English (Persian version: `docs/reviews/fa/`)
**Inputs:** `docs/requirements-prompt.txt` (full requirements), `frontend/DESIGN.md`, environment audit, user decisions.

---

## 1. What we are building

A bilingual (EN/FA) enterprise web system for Zarand Coking & Steel covering
employees, warehouse & inventory, item requests, asset tracking, loans &
guarantees, notifications, reports, settings, and full audit logging — built
as a **Modular Monolith**:

- **Backend:** FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2, Celery + Redis
- **Frontend:** Next.js (App Router) + TypeScript + Tailwind + shadcn/ui +
  TanStack Query, acting as BFF
- **Data:** PostgreSQL (UUID keys, soft delete, partial unique indexes)
- **Auth:** JWT + refresh rotation in HttpOnly cookies; RBAC + hierarchical
  scopes (Global > Complex > Workplace)
- **Deploy:** local Windows dev → single Ubuntu VM (systemd + Nginx) → Docker later

## 2. Delivery approach — module by module (answered)

**Question:** Is it better to implement each module/service, bring it up,
test it, and only then move to the next?

**Answer: Yes — with one refinement.** Pure module-by-module works, but the
optimal shape is:

1. **Horizontal platform first** (Phase 1–2): skeleton, config, error
   envelope, auth, RBAC + scope resolver, audit base. Every business module
   depends on these; building them inside a business module causes rework.
2. **Then vertical slices** (Phase 3–9): each business module is delivered
   end-to-end — models → migration → repository (scope-filtered) → service →
   router → tests → **frontend pages** → bring the app up → manual smoke
   test → converge → next module.

Why this beats alternatives:

| Approach | Verdict | Reason |
|---|---|---|
| Vertical slices per module (chosen) | Best | Continuous executable feedback; early discovery of scope-filter and integration gaps; the app is always runnable |
| Big-bang (all modules, one test pass) | Worst | Integration risk compounds; nothing demonstrable until the end |
| Backend-first, then all frontend | Weak | Late UI/RTL/i18n feedback; one huge risky frontend phase |
| Microservices per module | Rejected | Contradicts the approved Modular Monolith architecture |

**Phase gate (every phase, no exceptions):** the application boots, all
tests are green, and the new capability is manually smoke-tested. Only then
may the next phase's `/speckit.specify` begin.

## 3. Phase plan

Each phase = one full Spec Kit cycle:
`/speckit.specify → /speckit.clarify → /speckit.plan → /speckit.analyze → /speckit.tasks → /speckit.implement → /speckit.converge` (repeat implement/converge until **Converged**).

| # | Spec slug | Contents | Gate |
|---|---|---|---|
| 0 | *(tooling, done)* | Repo, skills, fonts, spec-kit, constitution, AGENTS.md, this review | Workspace ready |
| 1 | `foundation-skeleton` | Backend skeleton (config, logging + trace_id, error envelope, healthz); frontend scaffold (Next.js, shadcn, next-intl, Kalameh fonts, DESIGN.md tokens, root layout, login shell, page transitions); Alembic base + mixins; `.env.example` both sides; dev bring-up scripts; GitHub Actions CI | Both apps boot; healthz 200 |
| 2 | `auth-rbac-scope-platform` | Login/logout/refresh/me; refresh rotation + reuse detection; cookies + CSRF; BFF proxy routes; RBAC model; scope resolver (union, implicit deny); audit base (snapshots, masking, trace_id) | Login works end-to-end; scope resolver unit tests green |
| 3 | `org-user-module` | Company/Complex/Workplace + seed; Employee↔User 1:1 in one transaction; partial unique indexes (national_id, personnel_code); roles/permissions/scope assignment UI; employees pages | Employee CRUD verified; duplicates blocked; deactivate cascades to user |
| 4 | `warehouse-catalog-inventory` | ItemCatalog + debounced live search (indexed, paginated); Warehouse/Shelf; InventoryPlacement; StockMovement (atomic + FOR UPDATE); low-stock alert | Stock flow verified; no negative inventory |
| 5 | `item-requests-flow` | ItemRequest + lines; purpose description; approve/reject/fulfill; stock control on fulfillment; full status audit | E2E request→fulfillment passes |
| 6 | `asset-tracking` | AssetInstance; assign/return; AssetHistory; AssetAssigned/AssetReturned events | Asset lifecycle verified |
| 7 | `loan-module` | LoanPolicy per workplace/year; LoanRequest; validation cascade in exact order (lifetime count → yearly count → active loan cap → active guarantee cap); Jalali year math | All 4 validation rules tested (incl. settled/soft-deleted semantics) |
| 8 | `notifications-outbox-sse` | EventOutbox + relay worker; in-app notifications; SSE stream; criticality rule | Live notification received in browser |
| 9 | `settings-reports-dashboard` | Settings + feature flags (audited); management dashboard; inventory/request/loan/audit reports; Excel export with permission-aware masking | Reports + export verified for both locales |
| 10 | `hardening-observability` | Rate limiting (auth + sensitive mutations); security headers; Redis caching for permissions/catalog search; Prometheus `/metrics`; structured log review; pre-commit hooks | Security checklist green |
| 11 | `vm-deployment-recovery` | systemd units, Nginx, Certbot HTTPS, seed_prod, pg_dump backup/restore + drill, health checks, runbook, **one-command bring-up guide** | User deploys and runs the app personally |
| later | `dockerization` | Per requirements §33, after local/VM is stable | — |

**Task granularity:** fine on purpose. The user explicitly opted for more
tasks over lost detail — expect 20–60 tasks per phase.

## 4. Confirmed decisions (2026-08-29)

1. Monorepo at the ZCES folder (this repo root).
2. Redis via **WSL2** on this Windows machine.
3. Kalameh **FaNum** variant for the FA locale (native Farsi digits);
   Standard variant for EN.
4. **Interleaved vertical slices** — every phase ships backend + UI + tests.
5. Skills installed **project-level** (`.opencode/skills/`) + `find-skills`
   global (`~/.agents/skills/`).
6. **Basic GitHub Actions CI from Phase 1** (ruff/mypy/pytest + eslint/tsc/next build).

## 5. Environment audit results (Phase 0)

- git 2.45.1, Node 24.11, npm 11.5.1, Python 3.12.0, uv 0.11.23 — all OK
- PostgreSQL 18 service running on :5432 — OK (requirements said 16+; 18 satisfies)
- Redis — **absent** (port 6379 closed) → resolved via WSL2 decision
- Ports 3000/8000 free

## 6. Success criteria mapping

Requirements §35 criteria are distributed across phase gates: RBAC/scope
correctness (P2–3), transactional Employee+User + duplicate blocking (P3),
stock integrity + movements (P4), request flow (P5), asset traceability (P6),
loan policy validation (P7), 100% audit + masking (P2, continuous), standard
errors + trace_id (P1–2), VM deployability (P11). A criterion is met only
when its owning phase's gate passes.
