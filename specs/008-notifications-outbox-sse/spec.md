# Feature Specification: Notifications, Event Outbox & Live SSE

**Feature Branch**: `feature/008-notifications-outbox-sse`

**Created**: 2026-09-01

**Status**: Draft

**Input**: User description: "Notifications (Phase 8): EventOutbox + relay
worker; in-app notifications; SSE stream; criticality rule — domain events
per requirements §20 delivered to in-app recipients with live browser
updates"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every business action emits its domain event atomically (Priority: P1)

Whenever a listed business action happens — user creation, catalog item
creation, low-stock alert, item-request lifecycle, asset assignment/return,
loan request lifecycle — the corresponding domain event (per requirements
§20) is captured in the event outbox in the same database transaction as the
business change. If the business change rolls back, the event vanishes with
it; if it commits, the event is guaranteed to be delivered eventually.

**Why this priority**: Without trustworthy event capture there is nothing to
deliver — every other story depends on it.

**Independent Test**: Perform each mapped action → exactly one outbox row of
the right event type appears; roll a transaction back (e.g. a refused
fulfillment) → no outbox row for it.

**Acceptance Scenarios**:

1. **Given** a warehouse keeper receives stock that drops below threshold,
   **When** the alert episode is raised, **Then** an `InventoryLowStock`
   outbox row exists referencing that alert.
2. **Given** an approver approves an item request, **When** the decision
   commits, **Then** an `ItemRequestApproved` outbox row exists with the
   request's identity.
3. **Given** a fulfillment that fails atomically (insufficient stock),
   **When** the transaction rolls back, **Then** no
   `ItemRequestFulfilled` outbox row exists for it.
4. **Given** a loan request is activated, **When** the transition commits,
   **Then** a `LoanRequestActivated` outbox row exists.

---

### User Story 2 - The relay delivers in-app notifications to the right people (Priority: P1)

A background relay worker claims pending outbox events and creates in-app
notification rows for each resolved recipient — for example, item-request
lifecycle updates go to the requester, low-stock alerts go to the workplace's
warehouse actors, asset handovers go to the receiving employee's account,
loan lifecycle updates go to the requester. Delivery is idempotent (an event
is delivered once even if the relay restarts mid-flight), retries
automatically on transient failure, and any delivery failure never affects
the business system.

**Why this priority**: Delivery is the entire point of the outbox; without
it, captured events pile up unread.

**Independent Test**: Submit an item request → within seconds the requester
has a notification; simulate a delivery failure → the event is retried and
eventually delivered exactly once.

**Acceptance Scenarios**:

1. **Given** a pending event, **When** the relay processes it, **Then** one
   notification row per resolved recipient exists with the event's payload.
2. **Given** an event whose delivery failed, **When** the relay retries,
   **Then** no duplicate notifications are created (delivery is exactly
   once per recipient).
3. **Given** the relay crashes between claiming and delivering, **When** it
   restarts, **Then** the claimed event is redelivered (at-least-once
   claim, exactly-once effect via idempotent recipient marking).

---

### User Story 3 - Live notification updates in the browser via SSE (Priority: P1)

A signed-in user keeps a live Server-Sent-Events stream open; when one of
their notifications is created, the browser receives it within seconds
without polling. The stream requires authentication, delivers only the
signed-in user's notifications, and reconnects automatically after drops.

**Why this priority**: "Live notification received in browser" is the
phase's stated gate (requirements §20 SSE for live alerts).

**Independent Test**: Open the stream as a user, trigger a business action
addressed to them, and observe the event arriving on the stream within the
relay latency; an unauthenticated stream request is denied.

**Acceptance Scenarios**:

1. **Given** an open authenticated stream, **When** a notification for that
   user is delivered, **Then** the browser receives it promptly with the
   notification's type and payload.
2. **Given** an unauthenticated stream request, **When** it connects,
   **Then** it is denied with the standard authentication error.
3. **Given** a dropped connection, **When** the client reconnects, **Then**
   missed notifications are recovered (no gap) via the unread list.

---

### User Story 4 - Notification inbox in the console (Priority: P2)

Every user can open a notification panel from the header: the unread badge
shows the live count, the list shows recent notifications (newest first,
paginated), each entry explains what happened in plain bilingual language,
and entries can be marked read (individually or all at once).

**Why this priority**: The inbox is how users consume the stream day-to-day,
but capture/delivery/live update carry the core value.

**Independent Test**: Deliver two notifications → badge shows 2 → open the
panel → list shows both newest-first → mark one read → badge drops to 1 →
"mark all read" clears it.

**Acceptance Scenarios**:

1. **Given** 2 unread notifications, **When** the panel opens, **Then** the
   badge shows 2 and the list is newest-first with readable descriptions.
2. **Given** an unread notification, **When** the user marks it read,
   **Then** the unread count decrements immediately.
3. **Given** several unread notifications, **When** the user clicks
   "mark all read", **Then** the badge clears.

---

### User Story 5 - Criticality rule is observable (Priority: P2)

Events declared Critical are handled with the platform's strongest
guarantees: their in-app notification rows are written inside the business
transaction itself, so a failure to record them fails that transaction
(allowed by requirements §20 for explicitly-critical notifications);
everything else tolerates delivery failures silently with retries.

**Why this priority**: The rule is a requirements mandate, but it is a
guarantee property rather than a user-facing journey.

**Independent Test**: A Critical-mapped event's notification row exists in
the same commit as the business change; a non-critical event's delivery
failure leaves the business system untouched and the event retrying.

**Acceptance Scenarios**:

1. **Given** a Critical event, **When** the business action commits, **Then**
   the in-app notification rows already exist (same transaction).
2. **Given** a non-critical event, **When** delivery fails, **Then** the
   business action stays committed and the event remains pending/retrying.

### Edge Cases

- What happens when the relay is down for minutes? → events accumulate in
  the outbox; on restart, all pending events are delivered in order; users
  recover missed notifications from the unread list (US3 scenario 3).
- What happens when a recipient's employee is deactivated between event
  capture and delivery? → notification delivery to a deactivated user's
  account is skipped and marked as such (no leak, no error loop).
- What happens when an event references data the user cannot see
  (out-of-scope)? → the notification payload renders what the recipient is
  allowed to see; the recipient only ever receives events addressed to them
  or their unit.
- What happens when a user has the stream open in two tabs? → both tabs
  receive the same live events (fan-out is per-connection).
- What happens with an unknown/future event type in the outbox? → the relay
  marks it permanently failed with a clear reason instead of retrying
  forever.

## Requirements *(mandatory)*

### Functional Requirements

**Capture (outbox)**

- **FR-001**: The system MUST capture the following domain events in the
  event outbox within the same transaction as the triggering business
  action: `UserCreated`, `ItemCatalogCreated`, `InventoryLowStock`,
  `ItemRequestCreated`, `ItemRequestApproved`, `ItemRequestRejected`,
  `ItemRequestFulfilled`, `ItemReturned`, `LoanRequestCreated`,
  `LoanRequestActivated`, `LoanRequestSettled`, `AssetAssigned`,
  `AssetReturned` — with the triggering action's identity in the payload.
- **FR-002**: The outbox row MUST record the event type, a JSON payload
  (entity id, actor, human-readable summary keys), the actor user, trace
  correlation, a pending/processing/delivered/failed status, and a retry
  counter; physically deleted events never occur — terminal failures are a
  status, not a deletion.
- **FR-003**: An event MUST be captured even when its notification delivery
  later fails; delivery failure MUST NOT affect the triggering business
  transaction (requirements §20 rule).

**Delivery (relay)**

- **FR-004**: The system MUST deliver pending outbox events to in-app
  notification rows via a background relay that claims events without
  double-delivery (at-least-once claim, idempotent effect), retries failed
  deliveries with backoff up to a bounded attempt count, and marks events
  delivered/failed terminally.
- **FR-005**: Recipient resolution MUST be deterministic per event type:
  item-request lifecycle → the requester; low-stock alerts → users with
  warehouse-stock visibility scoped to the alert's workplace; asset
  assignment/return → the holder employee's linked user; loan lifecycle →
  the requester; user/catalog creation → the acting context's users with
  user/warehouse read scope on the unit (documented per event in the
  plan).
- **FR-006**: Delivery to a deactivated user's account MUST be skipped and
  recorded as skipped, never retried forever.

**Live stream**

- **FR-007**: The system MUST expose an authenticated SSE stream that
  pushes each of the signed-in user's new notifications within seconds of
  delivery, carrying the notification type, payload summary, and id; the
  stream MUST NOT reveal other users' notifications.
- **FR-008**: The notification store MUST support: list (paginated,
  newest-first), unread count, mark-one-read, and mark-all-read — all
  scoped strictly to the signed-in user.

**Inbox & criticality**

- **FR-009**: The console header MUST offer a notification entry point with
  a live unread badge, a bilingual (EN/FA, RTL-correct) notification panel
  with human-readable descriptions, skeletons, and reduced-motion respect;
  Farsi digits and Jalali timestamps in the `fa` locale.
- **FR-010**: Events explicitly mapped as Critical MUST have their in-app
  notification rows written inside the business transaction (a recording
  failure fails that transaction, per §20); non-critical events MUST tolerate
  any delivery failure without user-visible breakage.

### Key Entities *(include if feature involves data)*

- **EventOutbox**: an append-only, in-transaction event record — event
  type (one of the §20 events), JSON payload, actor, trace id, delivery
  status with retry counter and terminal-failure reason.
- **Notification**: a per-recipient in-app message — owner user, event
  type, payload summary, read timestamp; strictly owner-scoped visibility.
- **User / Employee / Workplace**: recipient resolution sources, reused
  from earlier phases unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the 13 mapped §20 events are captured atomically with
  their business action; rolled-back actions leave zero outbox rows.
- **SC-002**: 100% of delivered events produce exactly one notification per
  resolved recipient (no duplicates across relay restarts or retries).
- **SC-003**: A signed-in browser receives a new notification on the open
  stream within the relay latency (seconds, not minutes); the relay
  recovers all backlog after downtime with no lost events.
- **SC-004**: 100% of delivery failures leave the business system
  untouched; a Critical event's in-app rows are present in the business
  commit.
- **SC-005**: The unread badge, list, and mark-read flows work in both
  locales with correct RTL rendering, Farsi digits, and Jalali timestamps
  at mobile and desktop widths; scope purity holds — users see only their
  own notifications in 100% of cross-account checks.

## Assumptions

- Channels for v1: in-app notifications + SSE live stream (§20 "channels of
  the first version"); the Email channel is deferred until a transport is
  chosen and stays out of this phase's scope.
- The relay runs in-process with the backend (single-VM deployment, MVP
  simplicity per constitution VIII): a bounded poll interval, no Celery
  broker introduction this phase — Redis-backed fan-out can replace the
  in-process bus later without changing the outbox contract.
- Recipient resolution follows the platform's scope model (a user is a
  recipient only if their existing scopes cover the event's unit for the
  mapped permission) — no new subscription/preferences system in this
  phase; notification preferences arrive with the Settings phase (9).
- Critical mapping for v1: `InventoryLowStock` (alerting is the reason the
  channel exists) — everything else ships non-critical; the mapping is a
  data-driven table so future phases can reclassify without code changes.
- Unread/live counts derive from the notification store; no separate
  counters table.
