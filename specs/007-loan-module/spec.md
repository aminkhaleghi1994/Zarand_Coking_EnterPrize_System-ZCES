# Feature Specification: Loan & Guarantee Management

**Feature Branch**: `feature/007-loan-module`

**Created**: 2026-09-01

**Status**: Draft

**Input**: User description: "Loan & guarantee module (Phase 7): LoanPolicy per
workplace/year; LoanRequest; validation cascade in the exact required order
(lifetime count → yearly count → active loan cap → active guarantee cap);
Jalali year math"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Define and manage workplace loan policies (Priority: P1)

A LoanOfficer (or admin) defines, for a specific workplace and Jalali year,
the loan rules that govern every request in that workplace for that year: the
maximum loan commitment, the maximum guarantee commitment, how many requests
an employee may submit that year, and how many over their whole career. The
officer can edit these numbers (stale-write protected), retire a policy, and
browse existing policies filtered by workplace and year.

**Why this priority**: Without a policy there is nothing to validate against —
every other story depends on it.

**Independent Test**: Create a policy for a workplace/year → it appears in the
policy list; edit a cap with a stale version → refused; retire it → it leaves
the active list while its audit trail remains.

**Acceptance Scenarios**:

1. **Given** a workplace with no policy for Jalali year 1405, **When** the
   officer creates one with all four limits, **Then** the policy is listed as
   active for that workplace and year.
2. **Given** an existing policy, **When** the officer creates another policy
   for the same workplace and year, **Then** the system refuses the duplicate.
3. **Given** a policy open in two screens, **When** one saves a change and the
   other saves with the old version, **Then** the second save is refused as a
   stale write.
4. **Given** an active policy, **When** the officer retires it, **Then** it
   disappears from the active list, the retirement is audited, and no data is
   physically deleted.

---

### User Story 2 - Submit a loan or guarantee request with policy validation (Priority: P1)

An employee submits a request — loan or guarantee — for an amount. The system
validates it against their workplace's active policy for the current Jalali
year, in the exact required order: (1) lifetime request count, (2) current
year request count, (3) active loan commitment cap, (4) active guarantee
commitment cap. The first failing rule is refused with a clear message that
names the rule and shows the numbers involved (e.g. "3 of 3 yearly requests
used"). Settled and soft-deleted requests never free the count limits; only
active requests count toward the amount caps, and a settled or cancelled
request frees its amount commitment.

**Why this priority**: This is the phase's core business rule — the validation
cascade in exact order is an explicit requirements mandate (§19).

**Independent Test**: Seed a policy with known limits, then submit requests
that trip each rule in turn and verify each is refused with the correct
rule named — and that a request passing all four is accepted as pending.

**Acceptance Scenarios**:

1. **Given** a policy allowing 3 requests/year and 5 lifetime, **When** an
   employee who already used 3 this year submits, **Then** the request is
   refused naming the yearly-count rule (not the lifetime rule).
2. **Given** an employee at 5 lifetime requests but 0 this year, **When** they
   submit, **Then** the request is refused naming the lifetime rule.
3. **Given** active loan commitments of 90,000,000 against a 100,000,000 cap,
   **When** the employee requests a 20,000,000 loan, **Then** the request is
   refused naming the active-loan-cap rule with current/limit amounts.
4. **Given** the same setup for guarantees, **When** a guarantee request
   exceeds the guarantee cap, **Then** it is refused naming the
   guarantee-cap rule.
5. **Given** a request that passes all four rules, **When** submitted, **Then**
   it is created as pending and audited.
6. **Given** a settled request counted toward the yearly count, **When** the
   employee submits a new request, **Then** the settled one still counts
   against the count limits.
7. **Given** no active policy for the workplace and current year, **When** any
   request is submitted, **Then** it is refused with a clear "no policy"
   message.

---

### User Story 3 - Progress a request through its lifecycle (Priority: P1)

A LoanOfficer reviews pending requests in their scope and moves them through
pending → active (the loan/guarantee is granted) → settled (repaid/released,
recording when it was settled) or cancelled. Every transition is
version-guarded so concurrent decisions resolve to exactly one winner, and
activating consumes the amount commitment while settling or cancelling frees
it. Deactivated employees' requests can no longer be activated.

**Why this priority**: The lifecycle is what makes the caps and counts
meaningful; without transitions the validation cascade never changes state.

**Independent Test**: Submit a passing request → activate it → the active
commitment grows and a second same-size request is now refused; settle the
first → the commitment frees and the same request now passes the cap rule.

**Acceptance Scenarios**:

1. **Given** a pending request, **When** the officer activates it, **Then**
   status becomes active, the activation is audited, and the amount counts
   against the cap from that moment.
2. **Given** an active request, **When** the officer settles it, **Then**
   status becomes settled with a recorded settlement timestamp and the amount
   stops counting toward the active cap.
3. **Given** an active request, **When** the officer cancels it, **Then**
   status becomes cancelled and the amount stops counting toward the active
   cap.
4. **Given** two officers activating the same pending request concurrently,
   **When** both submit, **Then** exactly one succeeds and the other receives
   the standard stale-write error.
5. **Given** a pending request of a deactivated employee, **When** the officer
   tries to activate it, **Then** it is refused with a business-rule error.

---

### User Story 4 - Scoped browsing of policies and requests (Priority: P2)

Users browse loan policies and requests with pagination and filters (type,
status, year, search by employee name). Visibility follows the platform's
scope hierarchy: an employee sees their own requests; a scoped LoanOfficer
sees requests and policies only for their covered workplaces; global coverage
sees everything. Out-of-scope lookups are denied without revealing existence.

**Why this priority**: Browsing is needed to operate the module day-to-day,
but the writes above carry the business value first.

**Independent Test**: Create policies and requests across two workplaces;
a workplace-scoped officer sees only their workplace's rows; a requester sees
only their own requests; a cross-workplace direct URL is denied without leak.

**Acceptance Scenarios**:

1. **Given** requests in two workplaces, **When** a workplace-scoped officer
   lists requests, **Then** only their workplace's requests appear.
2. **Given** an employee with 2 of their own requests, **When** they list
   requests, **Then** they see exactly their own two.
3. **Given** a filtered list, **When** the officer filters by type or status
   or year, **Then** only matching rows are returned with standard pagination.

---

### User Story 5 - Bilingual loans console (Priority: P2)

All policy and request surfaces are fully bilingual: an English/Persian
policies screen and a loans screen — create/edit forms with validation
messages, filter chips, responsive tables that collapse to cards on small
screens, loading skeletons, Jalali year display and Farsi digits in Persian,
RTL layout, and reduced-motion respect.

**Why this priority**: Required for daily use by both language groups, but it
depends on the endpoints above.

**Independent Test**: Open both locales, exercise create/edit/filter flows on
mobile and desktop widths, and verify Persian renders RTL with Jalali year
labels and native Farsi digits.

**Acceptance Scenarios**:

1. **Given** the Persian locale, **When** the officer opens the policies
   screen, **Then** every label, placeholder, error, and date renders in
   Persian with RTL layout and Jalali year.
2. **Given** a 375px-wide viewport, **When** the loans list is open, **Then**
   the table collapses to cards and all actions remain reachable.

### Edge Cases

- What happens when the workplace has no active policy for the current Jalali
  year? → the request is refused with an explicit "no active policy" error
  naming the workplace and year.
- What happens at the Jalali new-year boundary (e.g. a request submitted days
  before and after Nowruz)? → the year is derived from the submission
  timestamp; requests on either side belong to different policy years.
- What happens when two requests are submitted simultaneously for the last
  remaining count slot? → exactly one wins; the other is refused naming the
  count rule.
- What happens with zero or negative amounts? → refused as a validation
  error before any policy rules run.
- What happens when the assigned employee is deactivated between submission
  and activation? → activation is refused.
- What happens when a policy is retired while requests are pending? → pending
  requests keep validating against the policy snapshot of their creation;
  the retired policy no longer accepts new requests (explicit "no active
  policy" refusal).

## Requirements *(mandatory)*

### Functional Requirements

**Policies**

- **FR-001**: The system MUST allow authorized users to create a loan policy
  for a specific workplace and Jalali year with: maximum loan amount,
  maximum guarantee amount, maximum requests per year, maximum requests per
  lifetime, and an active flag; a workplace may have only one active policy
  per year.
- **FR-002**: The system MUST support editing every policy field with
  stale-write detection (stale saves refused with the standard conflict
  error), and MUST support retiring (soft-deleting) policies with the
  retirement audited; physical deletion never occurs.
- **FR-003**: Policy listing MUST be paginated with a bounded page size,
  filterable by workplace and year, and scope-filtered.

**Requests & validation**

- **FR-004**: The system MUST allow an employee to submit a loan or guarantee
  request with a positive amount; the request records the employee, their
  workplace, the type, the amount, and the Jalali year of submission as an
  immutable year snapshot.
- **FR-005**: The system MUST validate every new request against the
  submitting employee's workplace active policy for the request's year, in
  exactly this order: (1) lifetime request count, (2) current-year request
  count, (3) active loan amount cap, (4) active guarantee amount cap — and
  MUST refuse on the first failing rule with a standard business-rule error
  that names the rule and shows the current and limit values.
- **FR-006**: Count limits MUST count every request ever made that is not
  physically deleted — including settled, cancelled, and soft-deleted ones;
  settled and cancelled requests MUST NOT free the count limits.
- **FR-007**: Amount caps MUST count only requests whose status is active;
  settling or cancelling a request MUST free its amount commitment;
  soft-deleted requests MUST behave like their pre-deletion state for caps
  (an active request that is soft-deleted still counts until settled).
- **FR-008**: The system MUST derive the calculation year from the Jalali
  calendar (submission date → Jalali year), not the Gregorian year.
- **FR-009**: The system MUST refuse requests when the workplace has no
  active policy for the request's year, with an explicit error naming the
  workplace and year.

**Lifecycle**

- **FR-010**: The system MUST support the transitions pending → active,
  active → settled, active → cancelled, and pending → cancelled, each
  version-guarded so concurrent transitions resolve to exactly one winner;
  settling MUST record the settlement timestamp.
- **FR-011**: The system MUST refuse activating requests whose employee is
  deactivated, and MUST restrict transitions to authorized roles.
- **FR-012**: Every lifecycle action (policy create/edit/retire; request
  create/activate/settle/cancel) MUST be audited with actor, trace
  correlation, and before/after snapshots, with loan amounts masked in
  audit snapshots per the platform masking rules.

**Visibility & UI**

- **FR-013**: Request listing MUST be paginated with a bounded page size and
  filterable by type, status, and year; an employee sees only their own
  requests; scoped officers see only their covered workplaces' requests;
  out-of-scope access MUST be denied without revealing existence.
- **FR-014**: All policy and request surfaces MUST be fully bilingual
  (English / Persian) with RTL Persian rendering, native Farsi digits,
  Jalali year display, responsive layouts with tables collapsing to cards
  below 768px, loading skeletons, and reduced-motion respect.

### Key Entities *(include if feature involves data)*

- **LoanPolicy**: per-workplace per-Jalali-year rule set — max loan amount,
  max guarantee amount, max requests per year, max requests per lifetime,
  active flag; unique per workplace+year among active policies; soft-deletable.
- **LoanRequest**: an employee's loan or guarantee demand — employee,
  workplace (scope anchor), type (loan | guarantee), positive amount, Jalali
  year snapshot, status (pending | active | settled | cancelled), settlement
  timestamp, version-guarded; soft-deletable; never physically deleted.
- **Employee / Workplace**: request owner and validation anchor; reused from
  Phase 3 unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of out-of-policy requests are refused naming the first
  failing rule in the exact required order (1→4), with current/limit values
  in the error details.
- **SC-002**: 100% of settled, cancelled, and soft-deleted requests keep
  counting toward the count limits; 100% of active commitments count toward
  the amount caps and are freed by settlement or cancellation.
- **SC-003**: Concurrent submissions at a count or amount boundary resolve to
  exactly one winner in 100% of race cases.
- **SC-004**: Jalali year derivation is correct at the new-year boundary
  (a submission in Esfand maps to the previous Jalali year; one after
  Nowruz to the next).
- **SC-005**: 100% of policy and request lifecycle actions appear in the
  audit trail with actor, trace correlation, and masked before/after
  snapshots.
- **SC-006**: Both locales present every surface completely with correct RTL
  rendering, Farsi digits, and Jalali year display at mobile and desktop
  widths; scope purity holds in 100% of cross-workplace checks.

## Assumptions

- Loan/guarantee requests are submitted self-service by the employee (the
  platform's 1:1 employee↔user identity resolves the requester); LoanOfficer
  and admins manage policies and lifecycle transitions. Registration on
  behalf of another employee is out of scope for this phase.
- A cancelled request behaves like a settled one for count semantics (never
  frees counts); only active status counts toward amount caps — matching
  §19's explicit settled/soft-deleted rules conservatively.
- Policy retirement is soft-delete with no blocking rule: pending requests
  validate against the policy snapshot of their creation year; a retired
  policy simply stops accepting new requests.
- Amounts are positive decimal money values with at most two decimal places.
- Domain events (`LoanRequestCreated`, `LoanRequestActivated`) are emitted in
  Phase 8 with the outbox/SSE infrastructure; this phase ships audit records
  only.
- Loan-specific permission codes follow the platform pattern
  (`loan:policy:*`, `loan:request:*`) and are seeded idempotently; the
  seeded `LoanOfficer` role maps to them.
