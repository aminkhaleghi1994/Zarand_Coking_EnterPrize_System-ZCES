# Feature Specification: Organizational Structure & Employee/User Management

**Feature Branch**: `feature/003-org-user-module`

**Created**: 2026-08-31

**Status**: Draft

**Input**: Phase 3 of the implementation roadmap — organizational structure (Company → Complex → Workplace) with seed data, employee records with a mandatory one-to-one user account, duplicate identity prevention, scope-filtered employee visibility, deactivation cascade, and the first administrative UI for employees, roles, permissions, and scope assignment.

## Clarifications

### Session 2026-08-31

- Q: After an employee's account exists, what should happen when their password is lost or compromised? → A: Administrators can set a new password for any in-scope user as an audited operation (sensitive material masked in the audit trail).
- Q: Should the employee directory show deactivated employees by default, or hide them? → A: Active employees only by default, with a status filter (active / deactivated / all).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Organization tree exists and is seeded (Priority: P1)

As an administrator, I open the system for the first time and the organizational
hierarchy already exists: one company ("Zarand Coking & Steel"), two complexes
("Coking and Tar Refining Complex", "Steelmaking Complex"), and four workplaces
("Khamroud Coal Mine", "Coke Plant 1", "Coke Plant 2", "Steel Plant") distributed
between the complexes. Every workplace belongs to exactly one complex, and the
company is the single root. This hierarchy is the backbone that every scoped
operation in later phases hangs off, so it must exist before employees can be
enrolled.

**Why this priority**: Employees cannot be created without a workplace to belong
to; every later module (warehouse, loans, assets) filters data through this
tree. It is the first blocker for everything else in this phase.

**Independent Test**: Seeding the organization on a fresh deployment produces
exactly the hierarchy above; re-running the seed changes nothing (idempotent);
the tree is visible to an administrator in the employee forms.

**Acceptance Scenarios**:

1. **Given** a fresh deployment with no organization data, **When** the
   organization seed runs, **Then** the company, both complexes, and all four
   workplaces exist with their correct parent relationships.
2. **Given** the seed has already run, **When** it runs again, **Then** no
   duplicate companies, complexes, or workplaces are created and existing
   records keep their identity.
3. **Given** any authenticated viewer, **When** they request the list of
   complexes or workplaces, **Then** only records within their authorized
   portion of the tree are returned (a viewer with no scope sees none).

---

### User Story 2 - Employee enrolled with linked user account in one atomic act (Priority: P1)

As an administrator, I create a new employee by filling in personal identity
(national ID number, personnel code, first/last name, optional Persian names,
birth date, phone) and choosing their workplace; at the same time I provide the
work email and an initial password for their sign-in account. The system creates
the employee record and the linked user account together: either both exist
afterwards, or neither does. A second attempt to enroll an employee whose
national ID or personnel code already belongs to another active employee is
rejected with a clear duplicate error, while a formerly soft-deleted employee's
identities can be reused.

**Why this priority**: This is the core data-creation flow of the phase and the
transactional employee+user rule is a binding principle of the whole system.

**Independent Test**: Creating an employee via the admin UI results in a
employee and a user that can immediately sign in; interrupting the process (or
forcing a failure) leaves no half-created employee or user; duplicate national
ID/personnel code attempts are rejected.

**Acceptance Scenarios**:

1. **Given** a valid form submission, **When** the administrator saves, **Then**
   an active employee and its linked user account both exist, the user belongs
   to no role by default, and the operation is recorded in the audit trail with
   masked sensitive fields.
2. **Given** an employee with national ID "X" is active, **When** another
   employee is submitted with the same national ID, **Then** the submission is
   rejected with a duplicate-resource error naming the offending field.
3. **Given** an employee with national ID "X" was soft-deleted, **When** a new
   employee is submitted with national ID "X" and personnel code "Y" (unused),
   **Then** the creation succeeds.
4. **Given** the user-account side of the creation fails (for example the work
   email already belongs to an active user), **When** the process completes,
   **Then** no employee record was created — the transaction rolled back
   entirely.
5. **Given** a concurrent edit of the same employee by two administrators,
   **When** the second save arrives, **Then** it is rejected with a conflict
   error instead of silently overwriting the first save.

---

### User Story 3 - Scope-filtered employee directory with edit (Priority: P2)

As an administrator whose authority covers only one workplace (or one complex),
I open the Employees page and see only the employees that belong to my portion
of the organization — a workplace administrator sees their own workplace's
employees, a complex administrator sees every employee of every workplace in
their complex, and a global administrator sees everyone. I can search by name,
national ID, or personnel code, and I can edit an employee's profile fields and
move them between the workplaces I control. Any attempt to reach an employee
outside my scope (even by typing the address directly) is denied.

**Why this priority**: Read/edit with scope enforcement is what makes the
directory usable for delegated administration and is the first live exercise of
the scope rules on real data.

**Independent Test**: Logged in as a workplace-scoped admin, the list shows only
that workplace's employees; edit works within scope and is denied outside it;
list responses are paginated; deactivated employees reappear via the status
filter for reactivation.

**Acceptance Scenarios**:

1. **Given** a workplace-scoped administrator, **When** they open the employee
   list, **Then** only employees of that workplace appear, paginated, with
   search by name, national ID, and personnel code.
2. **Given** a complex-scoped administrator, **When** they open the employee
   list, **Then** employees from all workplaces of their complex appear.
3. **Given** any administrator, **When** they request an employee outside their
   scope directly, **Then** the system denies access with the standard
   authorization error (never leaks existence).
4. **Given** an administrator edits an in-scope employee's phone number,
   **When** they save, **Then** the change is visible and the audit trail
   records before/after values with sensitive fields masked.
5. **Given** an administrator attempts to move an employee to a workplace
   outside their own scope, **When** they save, **Then** the move is denied.

---

### User Story 4 - Deactivating an employee locks out the linked user (Priority: P2)

As an administrator, I deactivate an employee who has left the company. The
employee record is marked inactive (never physically deleted), and the linked
user account is deactivated at the same time: that person can no longer sign in,
and any active sessions they hold die immediately. Re-activating restores the
employee and the account. The national ID and personnel code of a deactivated
employee become reusable by a future employee.

**Why this priority**: This is the required offboarding story and proves the
deactivation-cascade rule end to end.

**Independent Test**: Deactivate an employee with an active browser session →
their next request fails and sign-in is refused; reactivate → both return;
identities become reusable.

**Acceptance Scenarios**:

1. **Given** an active employee with a signed-in user, **When** an
   administrator deactivates the employee, **Then** the linked user is
   deactivated in the same operation, all the user's refresh sessions are
   revoked, and the next sign-in attempt is refused with a generic
   authentication error.
2. **Given** a deactivated employee, **When** an administrator reactivates
   them, **Then** both the employee and the linked user become active again and
   the user can sign in.
3. **Given** a deactivated employee with national ID "X", **When** a new
   employee is created with national ID "X", **Then** creation succeeds.
4. **Given** the deactivation of an employee, **When** the audit trail is
   inspected, **Then** a deactivation entry exists with actor, timestamp, and
   masked before/after snapshots.

---

### User Story 5 - Administrative management of roles, permissions, and scopes (Priority: P3)

As a global administrator, I manage the authorization surface of the system
through the UI: I can list roles and permissions, create a new role, and assign
or revoke roles for a user; I can view every permission definition; and I can
assign or remove organizational scopes for a user (global, complex, or workplace
level, each tied to specific operations). Every one of these changes is audited
with snapshots. Administrators without the corresponding permissions see these
management surfaces denied or hidden.

**Why this priority**: Role/scope administration already has working backend
endpoints from Phase 2; this story surfaces them in the UI, completing the
"management of roles/permissions/scopes" requirement. It is independent of the
employee stories above.

**Independent Test**: With the global admin, create a role, assign it to a
user, and grant that user a complex-level scope — then verify the user's
identity screen reflects all three changes; verify a permission-less admin
cannot reach the surfaces.

**Acceptance Scenarios**:

1. **Given** a global administrator, **When** they open the role management
   surface, **Then** all existing roles and the full permission catalog are
   listed, paginated where applicable.
2. **Given** a new role name, **When** the administrator creates it, **Then**
   it appears in the list, duplicates are rejected, and the creation is
   audited.
3. **Given** a user, **When** the administrator assigns then revokes a role,
   **Then** both operations succeed, are audited with snapshots, and are
   reflected in the user's identity.
4. **Given** a user, **When** the administrator assigns a complex-level scope
   without naming the complex, **Then** the assignment is rejected; with a
   named complex it succeeds and is audited.
5. **Given** a user, **When** the administrator sets a new password for them,
   **Then** the user can subsequently sign in with the new credential and the
   old one stops working; the audit entry shows the operation without any
   credential material.
6. **Given** an administrator lacking the management permissions, **When** they
   attempt any of the above, **Then** the system denies with the standard
   authorization error and the UI surfaces are not offered.

---

### Edge Cases

- What happens when an employee form is submitted with an invalid national ID
  format (wrong length or non-numeric)? The system rejects it with a field-level
  validation message before any uniqueness check matters.
- What happens when the chosen workplace is deactivated/soft-deleted between
  opening the form and saving? The save is rejected; the user re-picks a valid
  workplace.
- What happens when two administrators create employees with the same national
  ID at the same moment? Exactly one succeeds; the other receives the duplicate
  error — no partially-created pair remains.
- What happens when the administrator editing an employee is outpaced by
  another save (stale version)? The late save is rejected with a conflict error
  and the page offers a refresh-and-retry.
- What happens when deactivating an employee whose user is already deactivated?
  The operation succeeds idempotently (no error, audit entry written).
- What happens when a search term matches hundreds of employees? Results stay
  paginated with a bounded page size; search never loads an unbounded list.

## Requirements *(mandatory)*

### Functional Requirements

**Organization structure**

- **FR-001**: The system MUST represent a two-level organization under a single
  fixed company: complexes, each containing workplaces, forming a strict
  Company → Complex → Workplace → Employee hierarchy.
- **FR-002**: The system MUST seed the initial organization (one company, the
  two named complexes, the four named workplaces with their complex parents) on
  first run, and re-running the seed MUST change nothing (idempotent).
- **FR-003**: The system MUST prevent a workplace from belonging to more than
  one complex and an employee from belonging to more than one workplace at any
  time.
- **FR-004**: Every organization record MUST support deactivation (soft delete)
  such that deactivated records disappear from pickers and lists but remain
  historically referenceable.

**Employee & user lifecycle**

- **FR-005**: The system MUST create an employee and their mandatory linked
  user account as a single all-or-nothing operation; a failure on either side
  MUST leave neither record.
- **FR-006**: The employee record MUST capture: national ID number, personnel
  code, first and last name, optional Persian (native) name fields, optional
  birth date, optional phone number, and exactly one workplace.
- **FR-007**: The linked user account MUST carry the work email (its sign-in
  identity) and an initial password set by the administrator at creation.
- **FR-008**: The system MUST reject creation of an employee whose national ID
  or personnel code duplicates another *active* employee, and MUST allow those
  identities once the previous holder is deactivated.
- **FR-009**: The system MUST reject a user email that duplicates another
  *active* user, and MUST reject an employee whose work email duplicates an
  active user (rolling the whole creation back).
- **FR-010**: The system MUST validate the national ID as a numeric identifier
  of the country's standard length (10 digits) and the personnel code as
  non-empty, before uniqueness is evaluated; field-level errors MUST be
  reported per field.
- **FR-011**: The system MUST treat national ID and personnel code as immutable
  after creation; edits may change names, contact fields, and workplace, never
  the identity anchors.
- **FR-012**: The system MUST support editing in-scope employees and moving an
  employee between workplaces within the editor's scope, with stale-write
  detection: a save based on an outdated view MUST be rejected with a conflict
  error rather than overwrite.
- **FR-013**: The system MUST support deactivating and reactivating an employee
  such that deactivation also deactivates the linked user and revokes all the
  user's active sessions immediately; reactivation restores both.
- **FR-014**: Deactivation of an already-deactivated employee MUST succeed
  without error (idempotent) and still be audited.
- **FR-021**: Administrators MUST be able to set a new password for an
  in-scope user as an audited operation; the credential material itself MUST
  never appear in the audit trail, responses, or logs, and the operation MUST
  follow the same credential rules as account creation.

**Access control (applies to every operation above)**

- **FR-015**: Every employee and organization operation MUST require BOTH the
  corresponding permission AND a valid scope; a workplace-level actor reaches
  only their workplace's employees, a complex-level actor every workplace of
  their complex, a global actor all; anything else is implicitly denied.
- **FR-016**: Employee listings MUST be paginated with a bounded page size and
  MUST support search by name, national ID, and personnel code within the
  caller's scope. The default listing MUST show active employees only, with a
  status filter (active / deactivated / all) available to the caller.
- **FR-017**: Authorization denials MUST NOT reveal whether the requested
  resource exists (single standard authorization error).

**Management surfaces & audit**

- **FR-018**: The system MUST provide administrative surfaces (UI) to list
  roles, list the permission catalog, create roles, assign/revoke a user's
  roles, and assign/remove a user's organizational scopes (global, complex,
  workplace levels), each operation permission-gated.
- **FR-019**: A complex- or workplace-level scope assignment MUST require the
  corresponding organizational unit to be named; a global-level scope MUST NOT
  carry one. Invalid combinations MUST be rejected.
- **FR-020**: Every create, edit, move, deactivation, reactivation, role
  change, and scope change MUST be recorded in the audit trail with actor,
  timestamp, trace correlation, and before/after snapshots in which sensitive
  values (national ID, password material) are masked.

### Key Entities *(include if feature involves data)*

- **Company**: the single root organization; fixed in the first version,
  created by seed; identity, display name (bilingual), active flag.
- **Complex**: a major production division of the company (e.g., coking and tar
  refining, steelmaking); belongs to the company; parent of workplaces.
- **Workplace**: a specific site/plant within a complex (e.g., a mine, a coke
  plant, the steel plant); belongs to exactly one complex; parent of employees;
  the finest scoping unit.
- **Employee**: a person employed in exactly one workplace; carries national ID
  and personnel code (unique among active employees, immutable), bilingual
  names, optional birth date and phone; linked one-to-one to a User; supports
  soft delete and versioned concurrent editing.
- **User**: the sign-in identity of an employee; work email unique among active
  users, credential material, activation state; roles and scope assignments
  attach here. Existence is mandatory for every employee and created with it.
- **Role / Permission / ScopeAssignment**: existing Phase-2 concepts reused
  here; this phase adds the management UI and the new permission definitions
  for employee and organization operations.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a fresh deployment, the seeded organization tree (company,
  2 complexes, 4 workplaces) is present and visible to a global administrator,
  and re-running the seed produces zero duplicates.
- **SC-002**: An administrator completes employee enrollment including the
  linked account in under 2 minutes, and the new user can sign in immediately
  with the administrator-issued credentials.
- **SC-003**: 100% of duplicate national-ID and duplicate personnel-code
  enrollment attempts against active employees are rejected with a
  field-specific duplicate error; 100% of such attempts against deactivated
  employees succeed.
- **SC-004**: A workplace-scoped administrator's employee list contains zero
  employees from outside their workplace; a complex-scoped administrator sees
  every employee of their complex and nothing beyond it.
- **SC-005**: After deactivation, the deactivated user cannot sign in and all
  their previously active sessions stop working within the same interaction;
  reactivation restores access.
- **SC-006**: Every create/edit/move/deactivate/reactivate/password-reset/
  role/scope change performed in this phase appears in the audit trail with
  masked snapshots — 100% coverage verified by tests.
- **SC-007**: Both locales (English and Persian) present every new surface
  completely, with correct right-to-left rendering in Persian, at mobile and
  desktop widths.

## Assumptions

- The company is a single fixed root in the first version (per requirements
  §5); multi-company support is out of scope.
- National ID and personnel code are immutable after creation (identity
  anchors; renaming them would corrupt audit traceability).
- The initial password is chosen by the administrator at creation time; there
  is no email infrastructure, so no invitation flow or forced first-login
  reset in this phase (a forced reset may arrive with a later hardening phase).
- Employee self-service (employees viewing/editing their own profile) is NOT in
  this phase; all surfaces here are administrative.
- Organization structure is read-mostly in this phase: complexes/workplaces
  arrive by seed; an administrative editor for creating/moving workplaces is
  deferred (scope assignment UI can already reference the seeded tree).
- Deletion of employees is only soft; physical removal never happens anywhere
  in the system.
- The existing Phase-2 authentication, RBAC model, scope resolver, and audit
  base are reused as-is; this phase consumes them through module contracts.
