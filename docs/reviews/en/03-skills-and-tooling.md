# ZCES Skills & Tooling Review

**Date:** 2026-08-29 · **Language:** English (Persian version: `docs/reviews/fa/`)

## 1. Toolchain audit (this machine)

| Tool | Version | Status |
|---|---|---|
| git | 2.45.1 (Windows) | OK |
| Node.js | 24.11.0 | OK |
| npm | 11.5.1 | OK |
| Python | 3.12.0 | OK (backend target) |
| uv | 0.11.23 | OK (spec-kit installer) |
| PostgreSQL | 18 (service `postgresql-x64-18`) | Running on :5432 |
| Redis | — | **Missing** → provided via WSL2 (see §5) |
| specify CLI | 1.0.1 | Installed via `uv tool install specify-cli` |

## 2. Agent skills installed

### Project-level (`.opencode/skills/`)

| Skill | Source | Purpose |
|---|---|---|
| ui-ux-pro-max (+ design, design-system, ui-styling, brand, banner-design, slides) | nextlevelbuilder/ui-ux-pro-max-skill (user-requested) | Design-system generation, UI style intelligence, 192 industry rules |
| frontend-design | anthropics/skills (user-requested) | Distinctive, intentional visual design guidance |
| react-best-practices | vercel-labs/agent-skills | React/Next.js best practices |
| web-design-guidelines | vercel-labs/agent-skills | Web design quality guidelines |
| shadcn | shadcn/ui official | Component registry usage, CLI, customization |
| tdd | mattpocock/skills | Test-driven development discipline |
| code-review | mattpocock/skills | Structured code review |
| domain-modeling | mattpocock/skills | Domain-driven design, ADRs |

### Global (`~/.agents/skills/`)

| Skill | Source | Purpose |
|---|---|---|
| find-skills | vercel-labs/skills (from skills.sh, user-requested) | Skill discovery/installation across projects |

Notes: the `npx skillsadd` CLI currently points at a different registry
(skills.ws) and its list endpoint failed, so skills were installed directly
from their official GitHub sources — content is identical, provenance
verified against skills.sh listings.

## 3. Spec Kit setup

- `specify init --here --force --non-interactive --integration opencode`
- Commands available as `.opencode/commands/speckit.*.md`:
  specify, clarify, plan, analyze, tasks, implement, converge, checklist,
  constitution, taskstoissues.
- Constitution ratified at `.specify/memory/constitution.md` (v1.0.0) —
  8 principles + architecture constraints + workflow gates + governance.
- Workflow per phase (binding): specify → clarify → plan → analyze → tasks →
  implement → converge; repeat implement/converge until Converged; phase
  gate (app boots, tests green, manual smoke test) before the next phase.

## 4. Kalameh font setup (done in Phase 0)

- Staged at `frontend/src/fonts/kalameh/`:
  - `standard/` — 8 files (woff2 + woff × Thin/Regular/Bold/Black) for `en`
  - `fa-num/` — 8 files (woff2 + woff × 4 weights) for `fa` (Farsi digits)
  - `FontLicense.txt` — FontIran license; **must ship beside the fonts**.
    ⚠ The 6-digit FontIran license code placeholder is empty — insert your
    license code if you hold one.
- Source folder `kalameh(Eco) @RealPentesting/` deleted after verified copy
  (17 files). EOT variants dropped (IE-only, unnecessary for Next.js).
- Design mapping (permanent, see `frontend/AGENTS.md`): Kalameh replaces
  Forma DJR Micro; weight mapping 400→Regular, 500/600→Bold 700,
  900→Black; no synthesized weights.

## 5. Redis on Windows — WSL2 (decided)

Redis is required for cache, Celery broker, and SSE fan-out. Decision:
run Redis inside WSL2 (closest to the production Ubuntu VM).

Setup (to be performed in Phase 1 bring-up):

```powershell
wsl --install -d Ubuntu            # if no distro yet
wsl sudo apt-get update && sudo apt-get install -y redis-server
wsl sudo service redis-server start
wsl redis-cli ping                 # expect PONG
```

`REDIS_HOST`/`REDIS_URL` in `.env` will point at the WSL2 host (config via
env only — never hardcoded).

## 6. CI (decided: basic, from Phase 1)

GitHub Actions on push/PR:

- Backend job: ruff (lint), mypy (types), pytest (unit + integration)
- Frontend job: eslint, tsc --noEmit, next build

VM deployment remains manual-triggered until Phase 11 defines the runbook.
