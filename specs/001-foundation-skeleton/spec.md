# Feature Specification: Foundation Skeleton

**Feature Branch**: `feature/001-foundation-skeleton`

**Created**: 2026-08-29

**Status**: Draft

**Input**: Phase 1 of the implementation roadmap (`docs/reviews/en/01-implementation-roadmap.md`): backend platform skeleton (configuration, logging with trace correlation, standard error envelope, health endpoint); frontend application scaffold (framework, UI library, bilingual i18n, brand fonts, design tokens, root layout, login shell, page transitions); database migration base with shared entity mixins; environment templates for both sides; developer bring-up scripts; continuous integration pipeline. Gate: both applications boot and the health endpoint responds successfully.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Developer brings the system up from a clean checkout (Priority: P1)

A developer clones the repository, follows the bring-up guide, copies the two environment templates, fills in local values, runs the two startup commands (one for the backend platform, one for the frontend application), and both applications start successfully. The developer opens the health endpoint in a browser or calls it with a tool and receives a success response identifying the application and its version. The developer also opens the frontend in a browser and sees the application shell render without errors.

**Why this priority**: Nothing else in any later phase is possible until both applications reliably start from a clean machine with documented steps. This is the phase gate.

**Independent Test**: Follow the bring-up guide on a clean checkout; verify the backend health endpoint returns success and the frontend home page renders. No other feature is needed.

**Acceptance Scenarios**:

1. **Given** a clean checkout with prerequisites installed (language runtimes, database service), **When** the developer follows the bring-up guide (copy environment templates, install dependencies, run migrations, start both apps), **Then** both applications start without errors and the health endpoint returns a success response containing application name, environment, and version.
2. **Given** both applications are running, **When** the developer requests the frontend's server-side proxy path for the health endpoint, **Then** the response is forwarded from the backend platform (proving the browser-to-frontend-to-backend communication path exists).
3. **Given** the frontend is open in a browser, **When** the developer navigates to the login page, **Then** the login shell renders with form fields, buttons, and labels fully localized, and no console errors appear.

---

### User Story 2 - Every request is traceable and every error speaks the standard language (Priority: P2)

When any request hits the backend platform, it is assigned (or adopts) a correlation identifier that appears in the response headers and in every log line produced while serving that request. When any error occurs — invalid input, missing route, or an unexpected failure — the response body follows one fixed error structure: a machine-readable code from the standard error-code set, a human-readable message, optional details, and the correlation identifier. Developers can correlate a frontend failure to backend log lines using this identifier.

**Why this priority**: The error envelope and trace correlation are contractual for every later phase; retrofitting them after modules exist causes rework across the whole system.

**Independent Test**: Start the backend, send a request with a correlation header, observe the same identifier in the response and logs; trigger a validation failure and a not-found route, and verify both responses match the standard error structure with the standard codes.

**Acceptance Scenarios**:

1. **Given** the backend is running, **When** a client sends a request with an incoming correlation identifier, **Then** the response echoes the same identifier; **When** no identifier is supplied, **Then** the system generates one.
2. **Given** a request with invalid input, **When** the backend rejects it, **Then** the response body contains exactly the standard error fields with code `VALIDATION_ERROR` and the correlation identifier.
3. **Given** a request to an undefined path, **When** the backend responds, **Then** the body uses code `RESOURCE_NOT_FOUND` in the standard structure.
4. **Given** an unexpected internal failure, **When** the backend responds, **Then** the body uses code `INTERNAL_ERROR`, the correlation identifier is present, and the full exception details appear in server logs but never in the response body.

---

### User Story 3 - Bilingual, RTL-correct application shell (Priority: P3)

A user opens the frontend in English and sees the application shell and login page in English, left-to-right, with Latin digits. The user switches to Persian and sees the same pages in Persian, right-to-left, with the Persian brand font that renders Farsi digits natively. Layout uses direction-agnostic spacing so both locales look correct from one codebase. Pages animate their transitions smoothly and show loading skeletons; users who prefer reduced motion get none.

**Why this priority**: Bilingual RTL support is a constitution-level acceptance criterion for every future page; establishing it in the shell now prevents per-page rework later. It is P3 because the platform must boot and speak the error language first.

**Independent Test**: Open the login shell in both locales, toggle language, verify layout direction, fonts, and digit rendering, and verify responsiveness and reduced-motion behavior.

**Acceptance Scenarios**:

1. **Given** the frontend is running, **When** the user opens the English locale, **Then** all visible strings come from the English dictionary, direction is left-to-right, and the Latin-digit brand font is used.
2. **Given** the user switches to Persian, **When** the page re-renders, **Then** all visible strings come from the Persian dictionary, direction flips to right-to-left, the Persian-digit brand font is used, and no hardcoded strings remain visible in either locale.
3. **Given** the login shell at 375px width and at 1440px width, **When** the user interacts with all controls, **Then** the layout reflows correctly at both sizes and every touch target is at least 44×44 pixels.
4. **Given** the operating system requests reduced motion, **When** the user navigates between pages, **Then** transitions are effectively instant and no non-essential animation runs.

---

### User Story 4 - Quality gates run automatically on every change (Priority: P3)

When developers push to the repository or open a pull request, an automated pipeline lints, type-checks, and tests the backend, and lints, type-checks, and builds the frontend. Failures block with clear messages. This keeps the main branch deployable from day one.

**Why this priority**: The constitution requires CI from this phase onward; automating quality now protects every subsequent phase cheaply.

**Independent Test**: Push a commit; observe the pipeline run all backend and frontend checks and report success or actionable failure.

**Acceptance Scenarios**:

1. **Given** a pull request with passing checks, **When** the pipeline completes, **Then** backend lint, type-check, and tests plus frontend lint, type-check, and build all report success.
2. **Given** a change that breaks a backend lint rule, **When** the pipeline runs, **Then** it fails and identifies the failing backend job.

---

### Edge Cases

- What happens when a required environment variable is missing or malformed? The application must fail fast at startup with a clear, specific message naming the problem; it must never print secret values.
- What happens when the database is unreachable? The health endpoint must still respond and must report the database component's status honestly (application liveness vs. component readiness are distinguished).
- What happens when a user visits an unsupported locale path? The user is redirected to the default locale rather than shown an error.
- What happens when a client spoofs or sends an empty correlation identifier? Empty identifiers are ignored and a fresh one is generated; malformed values are accepted verbatim without validation errors (identity passthrough, not security control).
- What happens when the backend is down while the frontend proxies a request? The browser receives a mapped, standard-structure error (not a raw network dump or HTML error page).

## Requirements *(mandatory)*

### Functional Requirements

**Platform & configuration**

- **FR-001**: The backend MUST expose a health endpoint that returns success with application name, environment, version, and per-component status (application and database), and MUST respond with liveness-success even when the database is unreachable.
- **FR-002**: The backend MUST load all configuration from environment variables with sensible non-secret development defaults documented in a committed template; startup MUST fail fast with a specific error when required configuration is missing or invalid, without ever printing secret values.
- **FR-003**: No host address, URL, or secret may appear in source code; all such values MUST come from environment templates only.

**Observability & error contract**

- **FR-004**: Every backend request MUST carry a correlation identifier: taken from the incoming correlation header when non-empty, otherwise generated; it MUST be returned in the response header and included in every log line for that request.
- **FR-005**: The backend MUST produce structured logs with configurable level (from environment) and MUST NOT log secrets or sensitive field values.
- **FR-006**: Every error response MUST use the fixed structure: machine-readable code (from the standard error-code set), message, optional details object, and correlation identifier — for validation failures, unknown routes, and unexpected exceptions alike.
- **FR-007**: The frontend proxy layer MUST map backend failures (including backend-unreachable) to the same standard error structure for browser consumption, and the browser MUST never communicate with the backend platform except through the frontend proxy layer.

**Data layer base**

- **FR-008**: The migration tooling MUST be initialized and connected to the application's database metadata, with an initial (possibly empty or minimal) migration that applies cleanly to a fresh database and is reversible.
- **FR-009**: Shared entity conventions MUST be available to all future entities as reusable building blocks: universally unique primary key, creation/update timestamps, soft-delete marker, change-version counter, and actor-attribution columns — so that later phases never re-implement them.
- **FR-010**: The database layer MUST be configurable entirely via environment (host, port, name, user, password as separate variables plus a composed connection string), with development defaults only in the committed template.

**Frontend scaffold**

- **FR-011**: The frontend MUST be a typed, lintable, buildable application using the project's fixed frontend stack, with strict type checking enabled and zero build errors at phase gate.
- **FR-012**: Every user-visible string MUST come from locale dictionaries for English and Persian; routes MUST be locale-prefixed; the document language and text direction MUST switch with the locale (right-to-left for Persian).
- **FR-013**: The Persian locale MUST render with the Persian brand font variant that renders Farsi digits natively; the English locale MUST use the standard variant; the font license file MUST remain adjacent to the font files.
- **FR-014**: The global stylesheet MUST implement the design tokens defined in the design system document (surface colors, single accent color, ink text colors, two-tier corner radii, typography scale, spacing) and MUST style the root layout, buttons, and inputs accordingly.
- **FR-015**: A login shell page MUST exist as the visual/interaction shell (fields, primary button, validation-ready form structure, error message slot) with no real authentication logic; authentication arrives in Phase 2.
- **FR-016**: Page transitions and interactive feedback MUST use smooth 150–300ms animations and skeleton loaders for data fetching, and MUST respect the user's reduced-motion preference.
- **FR-017**: The application shell MUST include the basic app chrome (brand mark area, navigation placeholder, footer) responsive across 480/768/1024/1280 breakpoints with ≥44×44px touch targets on mobile.

**Developer experience & CI**

- **FR-018**: A bring-up guide and helper scripts MUST allow starting both applications (and applying migrations) with a small number of documented commands on the development platform.
- **FR-019**: A CI pipeline MUST run on push and pull request: backend lint, type-check, and test suite; frontend lint, type-check, and production build; any failure MUST fail the pipeline.
- **FR-020**: The version file and changelog MUST be updated to reflect the first buildable system state (0.1.0 baseline).

### Key Entities *(include if feature involves data)*

This phase introduces **no business entities**. It establishes the shared conventions every later entity inherits:

- **Entity convention (base building blocks)**: universally unique identifier primary key; `created_at`/`updated_at` timestamps; nullable soft-delete marker; integer change-version for optimistic locking; nullable actor attribution (created-by/updated-by). Delivered as reusable building blocks plus a verified migration baseline; first real entities arrive in Phase 3.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer following the bring-up guide on a clean checkout reaches both applications running — including health check passing — in under 15 minutes with no undocumented steps.
- **SC-002**: The health endpoint responds in under 2 seconds and reports application name, environment, version, and database component status.
- **SC-003**: During phase smoke testing, 100% of observed error responses conform to the standard error structure and include a correlation identifier.
- **SC-004**: Every Phase 1 page renders correctly in both English and Persian, including full right-to-left layout in Persian with Farsi digits; zero hardcoded user-facing strings remain.
- **SC-005**: The login shell renders without horizontal overflow at 375px and 1440px widths, with all interactive elements meeting the 44×44px touch-target minimum.
- **SC-006**: The CI pipeline completes green on the phase's final commit.
- **SC-007**: The full backend test suite and frontend checks pass locally with a single command per side.

## Assumptions

- The technology stack is fixed by the constitution and requirements document (FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2 backend; Next.js App Router + TypeScript strict + Tailwind + shadcn/ui + next-intl frontend; PostgreSQL; the design system document governs all visual work) — these are binding constraints, not implementation choices, so they appear here rather than as requirements details.
- No authentication, business data, roles, or permissions exist in this phase; the login page is a visual shell only. Redis/Celery are NOT required in this phase (they arrive with the first phase that needs them, per the simplicity principle).
- Development environment: Windows with Python 3.12 venv for the backend and Node LTS for the frontend; PostgreSQL runs as a local service; the database name/user come from environment templates.
- Default locale is English; visiting the root redirects to a locale-prefixed route. Locale switching is a UI control, not an authenticated feature.
- The frontend proxies health (and later API) calls server-side to the backend using the backend base URL from its environment template.
- CI runs on GitHub-hosted runners; backend tests that require a database use a service container in CI. If database-dependent tests prove flaky in CI, they may be marked for local execution — but at least the endpoint/health tests must run in CI.
