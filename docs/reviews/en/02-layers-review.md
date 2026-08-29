# ZCES Software Engineering Layers Review

**Date:** 2026-08-29 · **Language:** English (Persian version: `docs/reviews/fa/`)
**Question reviewed:** Do all 13 software engineering layers need to be
implemented for this project?

**Short answer: No.** This is an on-premises, single-VM, intranet-scale
enterprise system. Six layers get full implementation, six get a scoped
(lighter) implementation matched to actual requirements, and two are
explicitly out of scope for v1. Building all 13 at full depth would add cost
and risk without benefit — the requirements document itself defers Docker,
cloud, and scale-out.

## Verdict table

| # | Layer | Verdict | Scope in ZCES | Phase |
|---|---|---|---|---|
| 01 | Front-End Foundation | **Full** | Next.js + TS strict + Tailwind + shadcn/ui + TanStack Query + RHF/Zod + next-intl (en/fa) + RTL + Kalameh + fully responsive + smooth motion | P1+ |
| 02 | Apps & Back-End | **Full** | FastAPI modular monolith (6 modules), Celery workers, SSE stream | P1–9 |
| 03 | DB & Storage | **Full** | PostgreSQL (UUID, soft delete, partial unique indexes, constraints) + Alembic + Redis. No object storage in v1 | P1+ |
| 04 | Authentications & Permissions | **Full** | JWT + rotating refresh in HttpOnly cookies, BFF pattern, RBAC + scope resolver, CSRF, masking | P2–3 |
| 05 | Hosting & Deployment | **Scoped** | Windows local dev + one Ubuntu VM (systemd, Nginx, Certbot HTTPS). No cloud hosting | P11 |
| 06 | Cloud & Computing | **Out of scope (v1)** | On-prem VM. Environment-driven config preserves future portability; nothing else needed now | — |
| 07 | CI/CD & Version Control | **Scoped** | Git + branching model + Conventional Commits + SemVer from day 1; GitHub Actions lint/test on every push; VM deploys scripted but manually triggered | P1+ (CI), P11 (deploy) |
| 08 | Rate Limiting | **Light** | Redis-backed limits on auth endpoints and sensitive mutations only. No API gateway tier | P10 |
| 09 | Security & Row Level Security | **Core, app-level** | The mandatory scope filter on every query IS the row-level security of v1 (enforced in the repository layer + tests). Plus CSRF/XSS/SQLi protection, masking, secrets discipline. PostgreSQL native RLS = optional defense-in-depth later | P2, P10 |
| 10 | Caching & CDN | **Light** | Redis cache for permission lookups and catalog live-search. No CDN — intranet app, no public edge | P10 |
| 11 | Load Balancing & Scaling | **Out of scope (v1)** | Single VM, Nginx in front, multiple uvicorn workers. Statelessness (JWT + Redis) keeps horizontal scale-out possible later | — |
| 12 | Error Tracking & Logs | **Full (lean tooling)** | Structured JSON logs, trace_id correlation across frontend↔backend↔workers, Sentry optional via env flag, Prometheus `/metrics` | P1 (trace), P10 (metrics) |
| 13 | Availability & Recovery | **Light but essential** | pg_dump backup + restore scripts + a practiced drill, health checks, systemd restart policies, runbook. No multi-node HA | P11 |

## Rationale for the exclusions

- **Layer 06 (Cloud):** the requirements mandate local Windows dev and a VM
  deploy with explicit "no Docker early" guidance. Cloud adds zero value to
  an intranet system while violating the simplicity risk mitigation (§36.5).
- **Layer 11 (Load balancing/scaling):** the user base is one company's
  employees (thousands at most, likely hundreds). A single VM with Nginx +
  multiple uvicorn workers comfortably exceeds the P95 < 200ms API target.
  The architecture stays stateless so layer 11 can be added later without
  rework.
- **PostgreSQL native RLS:** application-level scope filtering is required by
  the requirements regardless (permission AND scope on every query), so DB
  RLS would duplicate a mechanism we must build and test anyway. Revisit as
  defense-in-depth if the threat model changes.

## Where each included layer lands in the roadmap

See `01-implementation-roadmap.md` §3. Layer coverage is woven into phase
contents (rightmost column above) — no layer is left without an owning phase,
and no phase introduces infrastructure the requirements do not justify.
