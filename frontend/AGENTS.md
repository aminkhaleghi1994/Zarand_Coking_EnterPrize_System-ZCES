# Frontend Agent Instructions — Next.js App

Read the root `AGENTS.md` first. `DESIGN.md` in this folder is the design
system source of truth — read it before any UI work and follow it exactly.
Use the `frontend-design` and `ui-ux-pro-max` skills when designing/building
UI, and the `shadcn` + `react-best-practices` skills for component work.

## Stack

Next.js (App Router) · TypeScript (strict) · Tailwind CSS · shadcn/ui ·
React Hook Form + Zod · TanStack Query · next-intl.

## Design system (DESIGN.md — key rules)

- Pure white canvas, HP Electric Blue `#024ad8` as the ONLY accent (at most
  ~two uses per viewport), ink `#1a1a1a` text, cloud `#f7f7f7` /
  fog `#e8e8e8` alternating bands, dark-navy ink slabs close the page rhythm.
- Two-tier radius: buttons/inputs 4px, cards/photo frames 16px.
- Soft Lift shadow `0 2px 8px rgba(26,26,26,.08)` for cards and pricing
  tiles only; section bands stay flat.
- Chevron motif: hero/login/banner surfaces ONLY — never inline noise.
- Buttons: uppercase labels, 0.7px tracking, 44px height.

### Font substitution (permanent decision)

Kalameh replaces Forma DJR Micro everywhere. Fonts are staged at
`src/fonts/kalameh/` — load with `next/font/local`:

- `en` locale -> `standard/` variant (Latin digits)
- `fa` locale -> `fa-num/` variant (Farsi digits ۰-۹ rendered natively)
- Available weights: Thin 100, Regular 400, Bold 700, Black 900. Map the
  design's 500/600 emphasis steps to Bold 700 — never rely on synthesized
  (faux-bold) weights.
- `FontLicense.txt` must stay next to the font files at all times
  (FontIran license requirement).

## Bilingual & RTL (mandatory)

- Every user-facing string goes through next-intl messages (`en.json`,
  `fa.json`). No hardcoded strings in components.
- Routes are locale-prefixed (`/en/...`, `/fa/...`); `<html lang>` and `dir`
  switch per locale (`fa` -> `dir="rtl"`).
- Use CSS logical properties (`margin-inline`, `padding-inline`,
  `inset-inline-start/end`) — never physical left/right — so one layout
  serves both directions.
- Dates: Jalali calendar for `fa`, Gregorian for `en`. Farsi digits come
  from the FaNum font — do not convert digits in code.
- API error `code` strings map to localized messages via a shared
  error-code dictionary (mirrors the backend error-code set).

## Responsiveness (mandatory)

- Breakpoints: 480 / 768 / 1024 / 1280. Test every page at 375px and 1440px
  minimum. Touch targets >= 44x44px on mobile. Data tables collapse to
  card lists on small screens.

## Motion (mandatory, tasteful)

- Page/section transitions, skeleton loaders on data fetch, hover
  micro-interactions: 150-300ms ease-out.
- Always respect `prefers-reduced-motion`.
- Do not add animation libraries beyond CSS transitions or framer-motion
  without a phase decision.

## Conventions

- Server Components by default; `"use client"` only where interactivity
  requires it.
- Feature code lives in `features/<module>/`; shared UI in `components/`;
  shadcn primitives in `components/ui/` (never hand-edit generated shadcn
  files except via tokens/config).
- The browser talks ONLY to the Next.js BFF route handlers (`app/api/**`);
  it never calls FastAPI directly and never sees raw tokens.
- Forms: React Hook Form + Zod schemas mirroring backend validation; render
  backend field errors inline.
- Tables: server-side pagination/filter/sort only (backend contract
  `{items, page, page_size, total}`).
- Item search combo boxes: debounced live search against the backend search
  endpoint (indexed + paginated), reuse-before-create per warehouse rules.
