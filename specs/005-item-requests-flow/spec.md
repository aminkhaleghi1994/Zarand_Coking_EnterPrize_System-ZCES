# Feature Specification: Item Request Flow

**Feature Branch**: `feature/005-item-requests-flow`

**Created**: 2026-08-31

**Status**: Draft

**Input**: Phase 5 of the implementation roadmap — item requests with lines and
a purpose description, approve/reject decisions by the authorized role,
fulfillment that atomically draws stock through the Phase-4 movement ledger,
and full status-change audit.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Requester submits an item request with lines and purpose (Priority: P1)

As an employee, I submit a request for the items I need: I add one or more
lines (each an item picked from the live catalog search plus a quantity in
that item's unit), write why I need them (purpose description), and submit.
The request starts in the pending state, the submission is recorded in the
audit trail, and the request appears in my requests list. Requests with no
lines, blank purpose, or invalid quantities are refused with field-level
errors.

**Why this priority**: The request is the anchor of the whole flow — nothing
can be decided or fulfilled until requests exist.

**Independent Test**: Submit a valid request (2 lines), see it pending in the
list, then attempt an empty-lines submission and a zero-quantity line and be
rejected with field errors — without involving approvers or stock.

**Acceptance Scenarios**:

1. **Given** an authenticated employee, **When** they submit a request with
   two valid lines and a purpose description, **Then** the request exists in
   the pending state with exactly those lines, attributed to them, and the
   audit trail records the creation.
2. **Given** a submission with zero lines, **When** it is sent, **Then** it
   is rejected with a validation error before any record exists.
3. **Given** a line with quantity zero or negative, **When** the request is
   submitted, **Then** it is rejected with a field-level error on that line.
4. **Given** a line referencing a retired (or unknown) catalog item,
   **When** the request is submitted, **Then** it is rejected naming the
   line.
5. **Given** a submission with a blank purpose description, **When** it is
   sent, **Then** it is rejected with a field-level error.

---

### User Story 2 - Authorized approver approves or rejects a pending request (Priority: P1)

As a warehouse approver, I review pending requests within my scope and either
approve or reject each one, optionally with a decision note. Only pending
requests can be decided — an already-approved, rejected, or fulfilled request
refuses further decisions. Two approvers deciding the same request at the same
moment produce exactly one winner: the loser receives a version-conflict
error instead of a silent double decision. Every decision records who decided,
when, the transition, and (when present) the note — in the audit trail.

**Why this priority**: The approve/reject gate is the control point the
requirements explicitly assign to the WarehouseApprover role; without it the
flow cannot proceed safely to fulfillment.

**Independent Test**: Create a pending request, approve it (status changes,
audit entry written), then attempt to reject the approved request and be
refused; run two concurrent decisions on a second pending request and verify
exactly one succeeds.

**Acceptance Scenarios**:

1. **Given** a pending request in the approver's scope, **When** they approve
   it, **Then** the status becomes approved and the audit trail records the
   transition with actor and timestamp.
2. **Given** a pending request, **When** the approver rejects it with a note,
   **Then** the status becomes rejected, the note is stored, and the audit
   trail records it.
3. **Given** a request that is already approved, rejected, or fulfilled,
   **When** any further decision is attempted, **Then** it is refused with a
   business-rule error and no state change occurs.
4. **Given** two approvers deciding the same pending request simultaneously,
   **When** both complete, **Then** exactly one decision succeeded and the
   other received a stale-version conflict error.
5. **Given** an approver acting on a request outside their organizational
   scope, **When** they attempt a decision, **Then** they are denied with the
   standard authorization error that never reveals the request's existence.
6. **Given** a user without the decision permission, **When** they attempt a
   decision, **Then** they are denied.

---

### User Story 3 - Fulfillment draws stock atomically through the movement ledger (Priority: P1)

As a warehouse keeper, I fulfill an approved request: the system decrements
the requested quantity of every line from the stock placements I select, each
decrement written as a fulfillment movement in the same all-or-nothing
transaction, and the request becomes fulfilled. If any line cannot be covered
by the available stock, the whole fulfillment is refused with a clear
insufficient-stock error naming the offending line — no partial deductions,
no negative stock, no orphan movements. Fulfillment of the same request twice
is impossible, and two concurrent fulfillments competing for the same stock
serialize exactly like Phase-4 issues. Every fulfillment is audited with
before/after quantities.

**Why this priority**: This is the transactional heart of the phase and the
requirement's explicit "control stock on fulfillment" rule; it reuses the
Phase-4 ledger so stock can never drift.

**Independent Test**: Receive stock for two items, approve a request whose
lines reference them, fulfill it with placements selected per line — verify
quantities dropped exactly, fulfillment movements exist, the request is
fulfilled; then attempt to fulfill again (refused) and fulfill a second
request whose line exceeds remaining stock (refused atomically).

**Acceptance Scenarios**:

1. **Given** an approved request whose lines are coverable by in-scope stock,
   **When** the keeper fulfills it with placements selected per line,
   **Then** every line's placement quantity drops by exactly the requested
   amount, one fulfillment movement exists per line, and the request status
   becomes fulfilled.
2. **Given** a line whose requested quantity exceeds the selected
   placement's available stock, **When** fulfillment is attempted, **Then**
   it is refused with an insufficient-stock error naming the line, and no
   placement quantity changes and no movements exist.
3. **Given** an approved request, **When** fulfillment is attempted twice,
   **Then** the second attempt is refused as a business-rule violation.
4. **Given** two concurrent fulfillments of different requests drawing from
   the same placement, **When** their combined need exceeds the stock,
   **Then** exactly one succeeds and the other receives the
   insufficient-stock error with the stock unchanged.
5. **Given** a pending (not approved) request, **When** fulfillment is
   attempted, **Then** it is refused — only approved requests can be
   fulfilled.
6. **Given** any fulfillment attempt, **When** the audit trail is inspected,
   **Then** the attempt's outcome is recorded with actor, trace correlation,
   and before/after quantities.

---

### User Story 4 - Requesters and warehouse staff see the requests they should (Priority: P2)

As a requester, I see my own requests with their status and history; as
warehouse staff (keeper or approver), I see the requests belonging to my
organizational scope so I can review and decide them. Lists are paginated and
filterable by status. Requests outside a viewer's scope are invisible —
denials never reveal existence.

**Why this priority**: Visibility rules make the flow operable for both sides
without leaking data across workplaces; they build directly on the
established scope machinery.

**Independent Test**: Create requests from two different workplace-scoped
users; a keeper scoped to one workplace sees only that workplace's requests
plus their own; the other workplace's requests never appear in any list or
detail fetch.

**Acceptance Scenarios**:

1. **Given** a requester, **When** they open the requests list, **Then** they
   see their own requests (any status), paginated, with a status filter.
2. **Given** a keeper or approver scoped to a workplace, **When** they open
   the requests list, **Then** they see all requests of that workplace (and
   their own, wherever raised), paginated, with a status filter.
3. **Given** a request outside the caller's scope, **When** its detail is
   requested directly, **Then** the caller receives the standard
   authorization denial indistinguishable from a missing request.
4. **Given** a global-scope warehouse actor, **When** they list requests,
   **Then** all requests appear.

---

### User Story 5 - Bilingual request UI (Priority: P2)

As a user of either language, I manage the whole flow through the web UI: a
requests page where employees compose requests with the live item-search
picker and a line editor (add/remove lines), a purpose text area, a list with
status chips and filters, and decision/fulfillment actions surfaced only to
the authorized roles. Everything is complete in English and Persian with
correct RTL layout, Farsi digits, and Jalali timestamps, responsive down to
mobile widths with skeletons and smooth transitions.

**Why this priority**: The constitution makes bilingual, RTL, responsive,
animated UX an acceptance criterion of every phase.

**Independent Test**: Walk compose → list → decide → fulfill in both locales
at mobile and desktop widths; verify RTL correctness, Farsi digits, Jalali
timestamps, and reduced-motion behavior.

**Acceptance Scenarios**:

1. **Given** the Persian locale, **When** the requests surfaces are opened,
   **Then** all strings, dates, and digits render natively with correct
   right-to-left layout matching the design system.
2. **Given** a mobile-width viewport, **When** the line editor and lists are
   used, **Then** tables collapse to cards, touch targets stay at least
   44px, and nothing breaks.
3. **Given** either locale, **When** a decision or fulfillment fails
   (e.g. insufficient stock), **Then** the error is surfaced inline in the
   user's language using the standard error-code dictionary.

---

### Edge Cases

- What happens when a line references an item that is retired between adding
  it and submitting? Submission is rejected naming the line; the picker only
  ever offers active items.
- What happens when two approvers decide different requests that both draw
  from the same placement at fulfillment time? Fulfillment is the locking
  point: one succeeds, the other is refused with insufficient stock.
- What happens when a fulfillment selects a placement on a shelf that gets
  retired mid-flow? The placement of a retired shelf is not fulfllable —
  selection is validated at fulfillment time and the attempt is refused.
- What happens when a line quantity has more than 3 decimal places? It is
  rejected with a field error (same quantity discipline as the ledger).
- What happens when a rejected request's lines are needed again? A new
  request is submitted; rejected/fulfilled requests are immutable history.
- What happens when the requester of a pending request is later deactivated?
  The request remains visible and decidable for the approvers; fulfillment
  proceeds — the stock flow does not depend on the requester's account state.
- What happens when a decision arrives with a stale version? It is rejected
  with the standard stale-version error and the UI offers refresh-and-retry.

## Requirements *(mandatory)*

### Functional Requirements

**Request composition**

- **FR-001**: The system MUST allow authorized users to create item requests
  carrying a non-empty purpose description and one or more lines, each line
  referencing an active catalog item with a quantity greater than zero (up to
  3 decimal places, in that item's unit of measure).
- **FR-002**: Every request MUST start in the pending state and record its
  requester and timestamp.
- **FR-003**: The system MUST reject submissions with zero lines, blank
  purpose, non-positive or over-precision quantities, or lines referencing
  unknown/retired items — with field-level errors identifying the offending
  line.

**Decisions (approve / reject)**

- **FR-004**: The system MUST allow authorized approvers to approve or reject
  pending requests, optionally recording a decision note.
- **FR-005**: Decisions MUST be permitted only on pending requests; any other
  state MUST refuse the decision with a business-rule error and no state
  change.
- **FR-006**: Decisions MUST be guarded by optimistic locking: a decision
  based on a stale view MUST be rejected with the standard stale-version
  error.
- **FR-007**: Every decision MUST be audited with actor, timestamp, trace
  correlation, transition, and the note when present.

**Fulfillment**

- **FR-008**: Fulfillment MUST be permitted only on approved requests.
- **FR-009**: Fulfillment MUST decrement every line's quantity from
  caller-selected stock placements, writing exactly one fulfillment movement
  per line through the same ledger and integrity machinery as Phase 4 (row
  locking, atomic transaction), and MUST mark the request fulfilled in the
  same transaction.
- **FR-010**: Fulfillment MUST be refused atomically — with the standard
  insufficient-stock error naming the offending line and the available
  quantity — when any line cannot be covered; no partial deduction and no
  movements may remain.
- **FR-011**: Fulfillment MUST be refused on already-fulfilled or re-decided
  requests (a request is fulfilled exactly once).
- **FR-012**: Fulfillment MUST record the acting user, per-line movement
  references, and before/after quantities in the audit trail.

**Visibility & access control**

- **FR-013**: Request creation MUST be available to any active authenticated
  user for their own account; the requester is recorded and immutable.
- **FR-014**: Request listing MUST be paginated with a bounded page size and
  filterable by status; requesters see their own requests, while holders of
  warehouse read permissions additionally see all requests within their
  organizational scope (workplace → complex → global union), and denials MUST
  NOT reveal existence.
- **FR-015**: Every decision and fulfillment operation MUST require BOTH the
  corresponding permission AND a valid organizational scope; scope checks use
  the requester's workplace anchoring for list visibility.
- **FR-016**: Every creation, decision, and fulfillment MUST be recorded in
  the audit trail with actor, timestamp, trace correlation, and
  before/after snapshots; the four audit actions correspond to the
  requirements' domain events (created / approved / rejected / fulfilled).

**Bilingual UI**

- **FR-017**: All request surfaces MUST be fully bilingual (English /
  Persian) with right-to-left Persian rendering, native Farsi digits and
  Jalali timestamps, responsive layouts with tables collapsing to cards below
  768px, loading skeletons, and reduced-motion respect.

### Key Entities *(include if feature involves data)*

- **ItemRequest**: a request by one user — purpose description, status
  (pending → approved → fulfilled, or pending → rejected), requester, optional
  decision note with decider/decided-at, fulfillment timestamp; version-guarded
  for concurrent decisions; never deleted.
- **ItemRequestLine**: one line of a request — active catalog item reference,
  quantity (> 0, ≤ 3 decimals, in the item's unit), optional line note;
  immutable after creation; belongs to exactly one request.
- **StockMovement / InventoryPlacement**: Phase-4 entities consumed here —
  fulfillment writes `fulfillment` movements against caller-selected
  placements through the published module contract.
- **User / Workplace**: requester identity and the workplace anchoring used
  for scope-filtered visibility.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of invalid submissions (no lines, blank purpose,
  non-positive/over-precision quantities, retired items) are rejected with
  field-level errors; 100% of valid submissions create pending requests.
- **SC-002**: Only pending requests can be decided — 100% of decisions on
  non-pending requests are refused with no state change; concurrent decisions
  on the same request produce exactly one winner.
- **SC-003**: Fulfillment decrements exactly the requested quantities with
  one movement per line; 100% of fulfillment attempts that would overdraw are
  refused atomically with zero quantity changes and zero orphan movements;
  under concurrent fulfillment contention exactly the feasible fulfillments
  succeed.
- **SC-004**: 100% of creations, decisions, and fulfillments appear in the
  audit trail with actor, trace correlation, and snapshots.
- **SC-005**: A workplace-scoped viewer sees zero requests from outside their
  workplace (beyond their own); requesters always see their own requests.
- **SC-006**: Both locales present every new surface completely with correct
  RTL rendering, Farsi digits, and Jalali dates at mobile and desktop widths.

## Assumptions

- Fulfillment is whole-request in v1: all lines are fulfilled together in one
  transaction; per-line or partial fulfillment is deferred (the requirements
  define a single fulfill action per request).
- The fulfillment actor selects the stock placement per line at fulfillment
  time (placements are the unit of stock; auto-selection heuristics are not
  required by the requirements and would hide stock decisions from
  warehouse staff).
- Any active authenticated user may raise requests for themselves
  (self-service); requests are not raised on behalf of others in v1.
- There is no cancel/withdraw action in v1 — the requirements define
  created → approved/rejected → fulfilled only; a rejected or fulfilled
  request is terminal and immutable.
- The decision note is optional for approval and rejection alike (the
  requirements do not mandate notes).
- Requests are never deleted (no cancel path, no soft delete) — they are
  immutable flow history.
- Notification of decisions/fulfillment to the requester arrives with the
  Phase-8 notifications module; this phase records the audited status
  transitions the notifications will read.
- The Phase-4 published contract (`apply_fulfillment_issue`) is reused as-is
  for the per-line stock decrements; no new stock machinery is introduced.
- Permissions follow the established code convention: e.g.
  `warehouse:request:create/read/decide/fulfill`, seeded idempotently with
  `WarehouseApprover` gaining decide and `WarehouseKeeper` gaining
  create/fulfill/read mappings.

## Clarifications

### Session 2026-08-31

- Q: Should fulfillment cover the whole request at once, or can individual lines be fulfilled separately? → A: Whole-request fulfillment in v1 — every line is fulfilled together in one atomic transaction; partial/per-line fulfillment is deferred.
- Q: When fulfilling, how is the stock placement chosen for each line? → A: The fulfilling keeper selects the placement per line from in-scope placements of that item (stock decisions stay visible to warehouse staff; no auto-deduction).
- Q: Who may create item requests? → A: Any active authenticated user may raise requests for themselves (self-service); the requester is recorded and immutable.
