# Feature Specification: Auth, RBAC & Scope Platform

**Feature Branch**: `feature/002-auth-rbac-scope-platform`

**Created**: 2026-08-29

**Status**: Draft

**Input**: Phase 2 of the implementation roadmap (`docs/reviews/en/01-implementation-roadmap.md`): login/logout/me; refresh rotation with reuse detection; cookies + CSRF; BFF auth routes; RBAC model; scope resolver (union, implicit deny); audit base (snapshots, masking, trace_id). Gate: login works end-to-end; scope resolver unit tests green.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A user signs in and out of the system (Priority: P1)

A person with an organizational account opens the login page, enters their email and password, and submits. On success they land in the application as a signed-in user and the system shows who they are (name/email, roles). They can end their session with a logout action, after which protected surfaces refuse access until they sign in again. Sign-in failures (wrong password, unknown email, deactivated account) show a single, non-revealing error message.

**Why this priority**: Authentication is the front door — no other platform feature or business module is meaningful without a verified session, and the phase gate requires end-to-end login.

**Independent Test**: Seed the initial admin, open the login page, sign in with correct credentials, observe the authenticated state, sign out, and observe that protected access is refused. Deliverable value: a working front door.

**Acceptance Scenarios**:

1. **Given** a seeded active user, **When** they submit valid credentials on the login page, **Then** the session is established without exposing any token to browser scripts, and the identity (email, roles) is visible in the app.
2. **Given** an authenticated user, **When** they log out, **Then** the session ends on both browser and server side; subsequent access to identity shows them as signed out.
3. **Given** any sign-in attempt with wrong password, unknown email, or a deactivated account, **When** they submit, **Then** one generic localized error is shown, response timing/shape does not reveal which factor failed, and the attempt is recorded server-side (failed attempts are security-relevant events).

---

### User Story 2 - Sessions survive page use but not token theft (Priority: P1)

While a user works, their session silently renews: when the short-lived credential expires, the system transparently obtains a fresh one using the long-lived refresh credential without interrupting the user. If a refresh credential that was already used (or revoked) is presented again — the signature of token theft — the system invalidates the entire credential family and forces re-authentication. All session credentials are stored in cookies that browser scripts cannot read, and mutating requests through the browser path carry an anti-forgery token that server-embedded pages did not forge.

**Why this priority**: Rotation with reuse detection is the core security guarantee of the approved architecture; retrofitting it after modules exist would touch every endpoint.

**Independent Test**: Authenticate, wait for (or force) access expiry, observe transparent renewal on the next call; replay an already-used refresh credential and verify the whole family is revoked and re-login is forced.

**Acceptance Scenarios**:

1. **Given** an authenticated user whose access credential has expired, **When** the browser calls a protected endpoint, **Then** renewal happens transparently (single retry, no user interaction) and the call succeeds.
2. **Given** a refresh credential that was already rotated or revoked, **When** it is presented for renewal, **Then** the entire credential family is invalidated, the response is a standard authentication error, and subsequent renewals with any family member fail.
3. **Given** any browser-originated mutating request, **When** it reaches the server without the valid anti-forgery token, **Then** it is rejected with a standard error and never processed.
4. **Given** the raw session cookies, **When** inspected in the browser, **Then** they are inaccessible to scripts and scoped to the app path.

---

### User Story 3 - Permissions and scope decide what a user may do (Priority: P2)

Access to any operation requires BOTH a granted permission (via the user's roles) AND a valid scope assignment for that operation's module/resource/operation. Scope assignments live at Global, Complex, or Workplace level; a higher level covers its sub-organizations, a lower level never reaches upward; multiple assignments combine by union; absence means deny. The resolution logic is a single central decision point that every future endpoint reuses.

**Why this priority**: This is the system's primary risk control (requirements Risk 1); it must exist before business modules create their first scoped query.

**Independent Test**: Assign roles/permissions and scope assignments to test users, then ask the central resolver "may this user perform this operation on this organization unit?" and verify each combination (permission-only, scope-only, both, hierarchy coverage, union, deny-by-default).

**Acceptance Scenarios**:

1. **Given** a user with a permission but no covering scope, **When** access is evaluated, **Then** it is denied.
2. **Given** a user with a covering scope but without the permission, **When** access is evaluated, **Then** it is denied.
3. **Given** a user holding a Global-level assignment for an operation, **When** evaluation targets any Complex or Workplace, **Then** it is allowed; a Complex-level assignment covers only its workplaces; a Workplace-level assignment covers only that workplace.
4. **Given** a user with multiple non-overlapping assignments, **When** evaluation targets organizations covered by either, **Then** access is allowed (union).
5. **Given** a user with no matching assignment or an unknown operation, **When** evaluation runs, **Then** the result is deny (implicit deny) — never an error, never allow.

---

### User Story 4 - Security-relevant actions leave an audit trail (Priority: P2)

The platform records who did what, when, and with which trace id for security-relevant actions — at minimum: successful and failed sign-ins, sign-outs, credential renewals (including reuse detections and family revocations), role assignments/revocations, and scope assignment changes. Each record captures the actor, the affected entity, an action code, before/after snapshots where applicable, and the request's trace id. Sensitive field values are masked in records (credentials/tokens fully; national/personnel identifiers partially), and only privileged roles may view full snapshots.

**Why this priority**: The constitution mandates 100% audit of sensitive operations with masking and trace correlation; the audit base must exist before business modules write their first sensitive change.

**Independent Test**: Perform a sign-in, a failed sign-in, and a role assignment; inspect the audit store for each and verify actor, action, snapshot, masking, and trace id presence.

**Acceptance Scenarios**:

1. **Given** a successful sign-in, **When** the audit trail is inspected, **Then** a record exists with the user as actor, action `LOGIN_SUCCEEDED`-class, and the request trace id.
2. **Given** a failed sign-in attempt, **When** the audit trail is inspected, **Then** a record exists with action `LOGIN_FAILED`-class and no password material anywhere.
3. **Given** a role or scope change, **When** the audit trail is inspected, **Then** before/after snapshots are present and any sensitive fields inside them are masked.
4. **Given** a token revocation due to reuse detection, **When** the audit trail is inspected, **Then** the event is recorded with the family identifier and trace id, and no token material is stored in clear text.

---

### User Story 5 - The system boots with a secure administrative identity (Priority: P3)

On first bring-up, an idempotent seeding process creates the initial administrator from environment-provided credentials (never defaults in code), plus the base role set and their permissions. Running it repeatedly changes nothing; a deactivated or renamed admin is not duplicated; the production seed refuses to run with an unsafe (unchanged/default) admin password.

**Why this priority**: US1–US4 all need at least one real user and role set to exist; seeding is the bridge between an empty database and a testable system. It is P3 because it is a precondition, not user-facing capability.

**Independent Test**: Run the seed twice against a fresh database; verify one admin user, the base roles/permissions exist, and a second run is a no-op.

**Acceptance Scenarios**:

1. **Given** a fresh database and environment-provided admin credentials, **When** the seed runs, **Then** the admin user exists with the SuperAdmin role, full scope grant, and base roles/permissions exist exactly once.
2. **Given** the seed has already run, **When** it runs again, **Then** no duplicates are created and existing changes are preserved.
3. **Given** the production seed with an unchanged/default admin password from the template, **When** it runs, **Then** it refuses with a clear error and creates nothing.

---

### Edge Cases

- What happens when the access credential expires mid-session? The browser path renews transparently once; if renewal fails, the user is redirected to sign-in with a localized "session expired" message.
- What happens when a refresh credential is presented that belongs to no known family? It is rejected as an authentication error and the attempt is audited; no error discrimination between "expired" and "unknown" is exposed to the client.
- What happens when a deactivated user's still-valid credentials are used? Active status is checked at the authentication boundary; a deactivated user is denied with the standard error, and their refresh families are revoked upon deactivation.
- What happens when two logins happen for the same user (two browsers)? Each gets an independent credential family; one session's logout does not disturb the other.
- What happens when a scope assignment references a non-existent organization unit? The system prevents creating it (validation), and the resolver treats unknown references as deny, not error.
- What happens when a request lacks the anti-forgery token on a mutation? It is rejected before any business processing with a standard validation-class error.
- What happens when audit writing fails while a sensitive operation succeeds? For non-critical audit events the operation is not broken (constitution VII); for auth-critical events (login, revocations) the audit write is part of the same transaction.

## Requirements *(mandatory)*

### Functional Requirements

**Authentication & session**

- **FR-001**: The system MUST authenticate users by email + password with hash-based verification, and MUST respond identically (single generic error, standard envelope code `AUTHENTICATION_REQUIRED`) to unknown email, wrong password, and deactivated account — with no user enumeration.
- **FR-002**: The system MUST establish sessions using a short-lived signed access credential (default 15 minutes, env-configurable) and a long-lived rotating refresh credential (default 7 days, env-configurable), both delivered ONLY as HttpOnly cookies over the app path; raw credentials MUST never be exposed to browser scripts or request bodies from the browser.
- **FR-003**: Refresh rotation MUST issue a new refresh credential on every renewal, mark the used one rotated, and detect reuse: presenting an already-rotated/revoked refresh credential MUST revoke the entire credential family (all devices) and force re-authentication; families MUST be tracked server-side (one per login session) and revocable per user.
- **FR-004**: The system MUST expose session identity (`who am I`: user id, email, roles, scopes summary) and logout (revoke current family) endpoints; logout MUST end the server-side family, not just clear cookies.
- **FR-005**: All browser-facing mutating requests MUST carry an anti-forgery (CSRF) token validated server-side; the token MUST be obtainable from a server-provided non-HttpOnly source and rejected when missing/invalid with a standard validation-class error.
- **FR-006**: Deactivating a user MUST revoke all their refresh families and deny subsequent authentication.

**Authorization model**

- **FR-007**: The system MUST model roles, permissions (stable machine codes), role→permission grants, user→role assignments, and user→scope assignments as first-class entities with UUID keys and audit coverage on assignment changes.
- **FR-008**: The scope model MUST follow `Level:Module:Resource:Operation` with levels Global > Complex > Workplace; each assignment binds a level with its organization-unit reference (complex id / workplace id as applicable).
- **FR-009**: A single central resolver MUST decide "may user U perform operation `Module:Resource:Operation` on organization unit X?": allow only when the user holds a matching permission AND at least one covering scope; higher levels cover lower units; multiple scopes union; deny is implicit; unknown/missing references deny.
- **FR-010**: Every authorization failure MUST produce the standard envelope code `AUTHORIZATION_DENIED` with HTTP 403; every authentication failure `AUTHENTICATION_REQUIRED` with HTTP 401.
- **FR-011**: Role and scope administration endpoints (assign/revoke) MUST exist for administrative use, guarded by the same permission+scope mechanism they manage (bootstrap via the seeded SuperAdmin), and MUST be audited.

**Audit base**

- **FR-012**: The audit store MUST record: actor user id, entity type + id, action code, before/after snapshots (JSON), request trace id, and timestamp; sign-ins (success/failure), sign-outs, renewals, reuse detections, family revocations, and role/scope changes MUST be audited.
- **FR-013**: Sensitive values MUST be masked in audit records and logs: credentials, tokens, and secrets fully (never stored/echoed); national-id style identifiers partially (suffix-only per requirements §21); masking MUST be a shared central helper reused by all future modules.
- **FR-014**: Audit records for authentication-critical events (sign-in success/failure, revocations) MUST be written in the same transaction as the event; other audit events MUST follow the notification-tolerance rule (failure does not break the operation).
- **FR-015**: Audit reading (list/get) MUST be a permission-guarded administrative capability with full snapshots restricted to privileged roles.

**Session UX & BFF**

- **FR-016**: The login page MUST submit to the BFF layer (server-side route handlers) which owns all credential exchange; on success the BFF sets the session cookies and the UI transitions to the authenticated state without exposing tokens.
- **FR-017**: The application shell MUST reflect the authenticated identity (email, roles) with a logout control; unauthenticated visitors to protected pages MUST be redirected to the login page preserving the attempted destination; localized "session expired" messaging MUST exist.
- **FR-018**: The BFF MUST transparently retry once through the renewal path when the backend answers authentication-required, then either succeed or surface the standard error; the renewal route itself MUST use the refresh cookie only.
- **FR-019**: All new user-facing strings (sign-in states, session expired, logout, identity labels, authorization errors) MUST come from the EN/FA dictionaries; API error codes map to localized messages through the existing dictionary mechanism.

**Seed & configuration**

- **FR-020**: An idempotent dev seed MUST create: the initial admin (credentials from environment: email, username, password — no code defaults), the base roles from the requirements role table (SuperAdmin, HRAdmin, WarehouseKeeper, WarehouseApprover, LoanOfficer, Auditor, Manager), base permissions, SuperAdmin grants, and a Global scope assignment for the admin; re-running MUST be a no-op; a production variant MUST refuse unsafe/default admin passwords.

### Key Entities *(include if feature involves data)*

- **User**: organizational login identity — email (unique among active), username, hashed password, active flag, standard conventions (UUID, timestamps, soft delete, version, actors). Employee linkage arrives in Phase 3 (1:1, one transaction).
- **Role**: named collection of permissions (e.g. SuperAdmin, Auditor); unique among active.
- **Permission**: stable machine code (e.g. `user:employee:create`) with localized display name.
- **RolePermission / UserRole**: grant tables binding roles↔permissions and users↔roles.
- **ScopeAssignment**: user + level (Global/Complex/Workplace) + module/resource/operation target + the organization-unit reference implied by the level.
- **RefreshToken (family member)**: server-side record of one issued refresh credential — family id, credential hash (never the token itself), expiry, status (active/rotated/revoked), device/agent hint.
- **AuditLog**: append-only record per FR-012 (no soft delete, no updates).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can sign in from the login page and reach the authenticated shell in under 10 seconds on the dev machine, entirely through the BFF path.
- **SC-002**: Scope resolver unit tests cover every combination of permission×scope×level×union×implicit-deny (≥ 15 cases) and pass green.
- **SC-003**: Reuse-detection tests prove: replay of a rotated credential revokes the family; every family member fails after revocation; re-login restores access.
- **SC-004**: 100% of Phase 2 security events (login success/failure, logout, renewal, reuse detection, role/scope changes) appear in the audit trail with actor, trace id, and masked payloads — verified by tests.
- **SC-005**: No test, log, audit record, or response body contains a clear-text password or refresh token.
- **SC-006**: All previously green gates stay green: backend ruff/mypy/pytest, frontend lint/tsc/build, smoke test extended with auth checks, CI green on the final commit.
- **SC-007**: Seed idempotency: running it twice yields identical state (one admin, one role set) — verified by test.

## Assumptions

- Fixed stack per constitution: JWT-based credentials (library choice researched in plan), password hashing with a modern salted adaptive scheme, sync SQLAlchemy sessions; auth logic lives in the backend (validation always server-side), the BFF only proxies and manages cookies.
- Role/permission/seed data model matches requirements §4 (7 base roles) and §9.1 (user module ownership). Employee↔User 1:1 and organization entities are Phase 3; in this phase users exist standalone and Global scope covers everything for the admin.
- Access/refresh lifetimes and cookie flags come from the env template already reserved in Phase 1 (`ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `COOKIE_*`, `JWT_*`, `INITIAL_ADMIN_*`).
- CSRF strategy: double-submit token pair (server-issued readable token + cookie) validated on cookie-authed mutations — researched in plan.
- No rate limiting yet (Phase 10); failed-login auditing now gives the raw material for it later.
- The frontend keeps existing pages; login page becomes real (form → BFF), shell shows identity + logout; protected-route guard applies to the shell (all current pages are Phase 2-visible to any authenticated user; fine-grained per-page guards arrive with business modules).
- Redis/Celery remain unused; JWT revocation is DB-backed via refresh families (no blacklist cache needed at this scale).
