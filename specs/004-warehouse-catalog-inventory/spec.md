# Feature Specification: Warehouse, Item Catalog & Inventory

**Feature Branch**: `feature/004-warehouse-catalog-inventory`

**Created**: 2026-08-31

**Status**: Draft

**Input**: Phase 4 of the implementation roadmap — item catalog with duplicate
prevention and debounced live search, warehouse and shelf definition, stock
placement at shelf level, audited stock movements as the only way stock ever
changes (atomic, row-locked, never negative), and low-stock alerting.

## Clarifications

### Session 2026-08-31

- Q: Should receiving stock, issuing stock, and correcting (adjusting) stock be three separately-gated permissions, or one shared permission for any stock change? → A: Three separate permissions — receive, issue, and adjust are each independently gated, so daily stock work and quantity corrections are separate authorities.
- Q: Should catalog items carry an item code (SKU/part number) in addition to their name, or is the name the only identity? → A: Items carry an optional unique code alongside the name; uniqueness applies among active items and only when a code is provided; search matches name or code.
- Q: Should stock always be recorded in the item's single unit of measure with no unit conversion, or can keepers enter quantities in different units? → A: One unit per item — every placement, movement, and threshold for an item is expressed in that item's unit; no conversion exists in this phase.
- Q: Roughly how many distinct catalog items should the first version stay fast and usable for? → A: Up to about 500 items — a focused industrial catalog; search and pagination stay simple and comfortably fast at that scale.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Item catalog with duplicate prevention and live search (Priority: P1)

As a warehouse keeper, I define each item once in the company catalog: a
bilingual display name, an optional item code (SKU/part number), a unit of
measure, a minimum-stock threshold, and an optional description. When I start
typing a name or code while defining or picking an item, matching catalog
entries appear live as I type, so I can select the existing item instead of
creating a duplicate. The system refuses to create a second active item with
the same name or the same code; when an item is retired (soft-deleted), its
name and code become reusable. Every create and edit is recorded in the audit
trail.

**Why this priority**: The catalog is the vocabulary of the whole warehouse
domain — placements, movements, and the future item-request flow all reference
it. Without it nothing else in this phase can exist.

**Independent Test**: Create an item, see it appear in live search while
typing, attempt to create the same active name again and be rejected, retire
it and successfully reuse the name — all without involving shelves or stock.

**Acceptance Scenarios**:

1. **Given** a warehouse keeper with the item-create permission and scope,
   **When** they submit a valid new item, **Then** the item exists as an
   active catalog entry and the operation appears in the audit trail with
   before/after snapshots.
2. **Given** an active item named "X" exists, **When** any user attempts to
   create another active item named "X", **Then** the creation is rejected
   with a duplicate-resource error naming the conflicting field, and the live
   search surfaces the existing item to select instead.
3. **Given** the user types at least a few characters of an item name or
   code, **When** the live search responds, **Then** matching active items
   are returned as a bounded, paginated result set that updates as the user
   continues typing, without flooding the system with a request per
   keystroke.
4. **Given** an active item named "X", **When** it is retired (soft-deleted),
   **Then** a new active item named "X" can be created, and the retired item
   remains visible in historical records.
5. **Given** two keepers edit the same item concurrently, **When** the second
   save arrives based on a stale view, **Then** it is rejected with a conflict
   error instead of silently overwriting.

---

### User Story 2 - Warehouses and shelves defined per site (Priority: P1)

As an administrator, I define warehouses (each anchored to one workplace of
the organization) and, inside each warehouse, its shelves. A shelf belongs to
exactly one warehouse. Both levels can be retired; retirement is blocked while
stock remains on the shelves, so inventory can never be orphaned. Lists are
scope-filtered: a workplace-level actor manages only their workplace's
warehouses, a complex-level actor every warehouse of their complex's
workplaces, a global actor all.

**Why this priority**: Placements (stock) are the combination of shelf and
item; the physical-location half of that combination must exist first, and its
scope anchoring determines who may ever see or move the stock.

**Independent Test**: Create a warehouse, add shelves, attempt to retire a
shelf holding stock and be blocked, move the stock away and retire
successfully — with a lower-scope actor seeing none of it.

**Acceptance Scenarios**:

1. **Given** a permitted administrator, **When** they create a warehouse bound
   to a workplace, **Then** it exists, appears in scope-filtered lists, and
   the operation is audited.
2. **Given** a warehouse, **When** shelves are added under it, **Then** each
   shelf belongs to exactly that warehouse, and shelf identifiers are unique
   within the warehouse among active shelves.
3. **Given** a shelf (or warehouse) whose shelves still hold a non-zero stock
   quantity, **When** retirement is attempted, **Then** it is rejected with a
   business-rule error; after the stock is moved or drawn to zero, retirement
   succeeds and the record is soft-deleted.
4. **Given** a workplace-scoped actor, **When** they list warehouses, **Then**
   only warehouses of their workplace appear; out-of-scope access is denied
   without revealing existence.

---

### User Story 3 - Stock lives at shelf level and only moves through movements (Priority: P1)

As a warehouse keeper, I record stock for an item on a specific shelf of my
warehouse: receiving stock increases the quantity, issuing stock decreases it,
and corrections adjust it. Every single change of a quantity is stored together
with a stock-movement record in one atomic step — who did it, when, what kind
of movement, how much, and why (a free-text reason or reference). Two keepers
working at the same moment cannot drive a quantity below zero: decrements are
serialized, and an issue that would overdraw the available quantity is
rejected with a clear insufficient-stock error while the other operation
succeeds untouched. The full movement history of any placement is viewable.

**Why this priority**: This is the integrity core of the phase and a binding
principle of the whole system: stock never changes without a movement, atomic
transactions, row-locked decrements, and no negative quantities ever.

**Independent Test**: Receive stock onto a shelf, issue part of it, view the
movement history, then attempt to issue more than remains — the overdraw is
rejected with the quantity unchanged — and run two concurrent overdrawing
issues to prove exactly one wins.

**Acceptance Scenarios**:

1. **Given** an item and a shelf, **When** the keeper records an entry of a
   positive quantity, **Then** the placement quantity increases by exactly
   that amount and one matching movement record exists.
2. **Given** a placement holding quantity "Q", **When** the keeper issues
   "Q" or less, **Then** the quantity decreases accordingly with a movement
   record in the same operation.
3. **Given** a placement holding quantity "Q", **When** an issue of more than
   "Q" is attempted, **Then** the operation is rejected with an
   insufficient-stock error and neither the quantity nor any movement record
   changes.
4. **Given** two simultaneous issues that together exceed the available
   quantity, **When** both complete, **Then** exactly one succeeded, the
   other was rejected with the insufficient-stock error, the final quantity
   is zero or positive, and the movement records match the successful
   operations exactly (no lost or phantom movements).
5. **Given** any quantity change, **When** the audit trail is inspected,
   **Then** the change is recorded with actor, timestamp, trace correlation,
   and before/after snapshots.
6. **Given** a placement, **When** its history is opened, **Then** all
   movements are listed newest-first with type, quantity, reason, actor, and
   timestamp, paginated.
7. **Given** a keeper holding the receive and issue permissions but not the
   adjustment permission, **When** they attempt a stock correction,
   **Then** the operation is denied with the standard authorization error.

---

### User Story 4 - Low-stock alerts when a placement drops below its threshold (Priority: P2)

As a warehouse keeper or supervisor, I rely on the system to notice shortages:
each catalog item carries a minimum-quantity threshold, and whenever a
placement's quantity drops below that threshold, the system raises a
low-stock alert for that placement, records it in the audit trail, and makes
active alerts visible so keepers can react before shelves run empty. Alerts
do not duplicate while the condition persists; a new alert is raised only
after the quantity recovered to the threshold or above and dropped below
again.

**Why this priority**: The alert turns raw stock data into an actionable
signal — the requirement's explicit "low stock alert" outcome — but it builds
on top of placements and movements, so it follows them.

**Independent Test**: Set an item's threshold, bring a placement to or below
it, observe one alert (with audit entry); issue more while below threshold and
observe no duplicate alert; receive stock back to the threshold or above and
drop below again to observe a second alert.

**Acceptance Scenarios**:

1. **Given** a placement whose quantity falls below the item's threshold,
   **When** the stock change completes, **Then** an active low-stock alert
   exists for that placement and an audit entry records the alert.
2. **Given** an active low-stock alert for a placement, **When** further
   issues keep the quantity below the threshold, **Then** no additional alert
   is created for the same condition.
3. **Given** a placement that recovered to the threshold or above, **When**
   it drops below again, **Then** a new alert is raised.
4. **Given** a permitted viewer, **When** they open the low-stock view,
   **Then** active alerts are listed scope-filtered with item, shelf,
   warehouse, current quantity, and threshold.

---

### User Story 5 - Bilingual warehouse UI (Priority: P2)

As a user of the system in either language, I manage all of the above through
the web UI: catalog page with live search and create/edit/retire, warehouses
and shelves page, stock placement page with receive/issue/adjust actions and
movement history, and a low-stock view. Every page is complete in both
English and Persian — with correct right-to-left layout, native Farsi digits,
and Jalali dates in the Persian locale — fully responsive down to mobile
widths, with loading skeletons and smooth transitions.

**Why this priority**: The constitution makes bilingual, RTL, responsive,
animated UX an acceptance criterion of every phase; the phase is not done
until the capability is usable by Persian-speaking keepers.

**Independent Test**: Walk the four surfaces in both locales at mobile and
desktop widths; verify RTL layout, Farsi digits, Jalali timestamps, and
reduced-motion behavior.

**Acceptance Scenarios**:

1. **Given** the Persian locale, **When** any warehouse page is opened,
   **Then** all strings, dates (Jalali), and digits render natively and the
   layout is direction-correct, matching the design system.
2. **Given** the English locale, **When** the same pages are opened, **Then**
   all strings render in English with Gregorian dates.
3. **Given** a mobile-width viewport, **When** the surfaces are used, **Then**
   tables collapse gracefully, touch targets remain at least 44px, and no
   layout breaks.
4. **Given** a slow search response, **When** results are pending, **Then** a
   skeleton or busy indicator shows and the page remains usable.

---

### Edge Cases

- What happens when an item name or code is submitted that differs only by
  surrounding whitespace or letter case from an active item? The system
  normalizes and treats it as a duplicate, rejecting with the standard
  duplicate error.
- What happens when a receive/issue/adjust quantity is zero or negative? The
  operation is rejected with field-level validation before any stock logic
  runs.
- What happens when the shelf (or item) referenced by a stock operation was
  retired between opening the form and saving? The operation is rejected and
  the user re-picks a valid target.
- What happens when two keepers issue stock simultaneously and the combined
  amount exceeds the available quantity? Exactly one succeeds; the loser gets
  the insufficient-stock error; no negative quantity and no orphan movement
  ever exist.
- What happens when a keeper retires a shelf whose stock is zero but which
  still has historical movements? Retirement succeeds; history remains fully
  queryable.
- What happens when the minimum threshold of an item is edited while a
  placement is below the new threshold? The change is saved; the alert view
  reflects the condition on the next stock change (no retroactive sweep in
  this phase).
- What happens when a search term matches hundreds of items? Results stay
  paginated with a bounded page size; search never returns an unbounded list.
- What happens when a shelf or item with an active low-stock alert is
  retired? The alert is resolved (the condition can no longer be acted on)
  and the resolution is audited; history remains queryable.
- What happens when a user without any warehouse scope queries warehouse
  endpoints? They receive the standard authorization denial that never
  reveals whether matching records exist.

## Requirements *(mandatory)*

### Functional Requirements

**Item catalog**

- **FR-001**: The system MUST allow authorized users to create catalog items
  carrying a bilingual display name, an optional item code (SKU/part number),
  a unit of measure, a minimum-stock threshold, and an optional description.
- **FR-002**: The system MUST enforce that an item's name is unique among
  *active* items (case- and whitespace-normalized), rejecting duplicates with
  a standard duplicate-resource error; where an item code is provided it MUST
  likewise be unique among active items; names (and codes) MUST become
  reusable once the previous holder is retired.
- **FR-003**: The system MUST provide a live search over active items by name
  or item code that is executed server-side against an indexed, paginated
  query with a bounded page size, and the UI MUST debounce user typing so
  that pauses — not keystrokes — trigger searches.
- **FR-004**: The system MUST support editing catalog items (name, unit,
  threshold, description) with stale-write detection: a save based on an
  outdated view MUST be rejected with a conflict error.
- **FR-005**: The system MUST support retiring (soft-deleting) items; retired
  items disappear from search and pickers but remain referenceable by
  historical records; physical deletion MUST never occur.

**Warehouses & shelves**

- **FR-006**: The system MUST allow authorized users to define warehouses,
  each bound to exactly one workplace of the organization, and shelves, each
  bound to exactly one warehouse.
- **FR-007**: The system MUST enforce shelf uniqueness within their warehouse
  among active shelves (identifier/name), rejecting duplicates with the
  standard duplicate error.
- **FR-008**: The system MUST block retirement of a warehouse or shelf while
  any placement under it holds a non-zero quantity, with a business-rule
  error naming the blocking placement(s).
- **FR-009**: Warehouses and shelves MUST support soft delete and versioned
  concurrent editing, consistent with catalog items.

**Placement & stock movements**

- **FR-010**: The system MUST record stock as a quantity of one item on one
  shelf (placement), created implicitly on first receive; stock MUST never be
  recorded anywhere else; all quantities for an item (placements, movements,
  threshold) are expressed in that item's single unit of measure, with no
  unit conversion.
- **FR-011**: The system MUST guarantee that every quantity change is stored
  together with exactly one stock-movement record in the same all-or-nothing
  operation; a quantity change without its movement MUST be impossible.
- **FR-012**: Each movement MUST record: movement type (receive, issue,
  adjustment; extensible for future flows), quantity, the resulting quantity,
  the acting user, a timestamp, and an optional reason/reference text.
- **FR-022**: Receiving stock, issuing stock, and adjusting stock MUST be
  gated by three separate permissions; a holder of the receive and issue
  permissions who lacks the adjustment permission MUST be denied adjustments.
- **FR-013**: The system MUST serialize concurrent decreases of the same
  placement (row-level locking) and MUST refuse any operation whose
  application would make a placement quantity negative, with a dedicated
  insufficient-stock error.
- **FR-014**: The system MUST expose per-placement movement history,
  paginated, newest first, scope-filtered to the viewer.
- **FR-015**: The system MUST record every stock change and every catalog /
  warehouse / shelf create-edit-retire in the audit trail with actor,
  timestamp, trace correlation, and before/after snapshots.

**Low-stock alerts**

- **FR-016**: The system MUST evaluate the low-stock condition against each
  placement's quantity and its item's threshold after every stock change on
  that placement, using a strict "quantity below threshold" comparison (a
  configurable comparison arrives with the settings phase).
- **FR-017**: The system MUST create at most one active low-stock alert per
  placement per below-threshold episode, clearing (resolving) the alert when
  the quantity recovers to the threshold or above — or when the placement's
  shelf or item is retired — and raising a new alert on a subsequent drop
  while the placement remains active.
- **FR-018**: Each alert MUST be recorded in the audit trail, and active
  alerts MUST be listed scope-filtered with item, warehouse, shelf, current
  quantity, and threshold. Delivery of alerts as user notifications arrives
  with the notifications phase.

**Access control (applies to every operation above)**

- **FR-019**: Every warehouse operation MUST require BOTH the corresponding
  permission AND a valid organizational scope; a workplace-level actor reaches
  only their workplace's warehouses, a complex-level actor every warehouse of
  their complex's workplaces, a global actor all; anything else is implicitly
  denied. The one documented exception is catalog **reading** (FR-003): the
  item catalog is company-wide reference data, so reads require only the
  permission, while catalog writes additionally require at least one active
  warehouse scope (clarify-session decision; see research R5).
- **FR-020**: All list endpoints MUST paginate with the standard envelope and
  a bounded page size; authorization denials MUST NOT reveal whether the
  requested resource exists.

**Bilingual UI**

- **FR-021**: All new user-facing surfaces MUST be fully bilingual (English /
  Persian) with Persian rendering right-to-left using the project font with
  native Farsi digits and Jalali dates, fully responsive across the standard
  breakpoints, with loading skeletons and reduced-motion respect.

### Key Entities *(include if feature involves data)*

- **ItemCatalog**: the definition of an item — bilingual name (unique among
  active items), optional item code (unique among active items when
  provided), unit of measure, minimum-stock threshold, optional description;
  soft-deletable; versioned for concurrent edits. Distinct from any physical
  location: an item exists whether or not stock exists.
- **Warehouse**: a physical warehouse bound to exactly one workplace (the
  scope anchor); bilingual name and code (unique among active); soft-deletable.
- **Shelf**: a physical shelf inside exactly one warehouse; identifier/name
  unique within its warehouse among active shelves; soft-deletable.
- **InventoryPlacement**: the pairing of one shelf and one item holding the
  current quantity; the single place stock exists; created implicitly by the
  first receive; never negative.
- **StockMovement**: the immutable ledger entry proving every quantity change
  — type, quantity, resulting quantity, actor, timestamp, reason/reference;
  written in the same transaction as the change it causes.
- **StockAlert**: a low-stock episode for a placement — raised when the
  quantity drops below the item's threshold, resolved on recovery; feeds the
  audit trail and, later, the notification system.
- **Workplace**: existing Phase-3 concept reused as the scope anchor for
  warehouses; this phase adds no changes to it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of duplicate active item-name (and item-code) creation
  attempts are rejected; 100% of such names/codes become creatable after the
  previous holder is retired.
- **SC-002**: Live item search returns matching results fast enough that a
  user typing perceives results as immediate (no perceptible stall between
  keystroke pauses and results), with every result set bounded and paginated.
- **SC-003**: 100% of quantity changes in the system are paired with exactly
  one stock-movement record (verified by tests comparing placement quantities
  to their movement ledgers); zero quantity changes exist without movements.
- **SC-004**: Under concurrent issuing, the number of placement quantities
  that ever go negative is exactly zero, and every overdraw attempt is
  rejected with the insufficient-stock error while successful concurrent
  operations remain intact.
- **SC-005**: Every placement that drops below its item's threshold has an
  active alert plus audit entry; no placement has more than one active alert
  for the same episode; recovery resolves the alert.
- **SC-006**: A workplace-scoped actor sees zero warehouses, items in stock
  views, or alerts from outside their workplace; a global actor sees all —
  verified by tests.
- **SC-007**: 100% of create/edit/retire and stock operations of this phase
  appear in the audit trail with actor, trace correlation, and snapshots.
- **SC-008**: Both locales present every new surface completely with correct
  RTL rendering, Farsi digits, and Jalali dates at mobile and desktop widths.

## Assumptions

- Each warehouse is bound to one workplace (the finest scoping unit) so
  warehouse visibility follows the existing organizational scope; a warehouse
  shared across workplaces is not needed in v1.
- Catalog scale: the first version targets up to roughly 500 active items;
  search and list pagination are designed to stay simple and fast at that
  scale (no heavy search machinery is justified for v1).
- The minimum-stock threshold lives on the catalog item and is evaluated per
  placement; an aggregate per-item view across shelves can arrive with the
  reports phase.
- The strict "quantity below threshold" comparison is used now; making the
  comparison configurable is a settings-phase concern (per requirements §16).
- Alert delivery as in-app notifications (including outbox and streaming)
  arrives with the notifications phase; this phase stores and exposes alerts
  and audits them.
- Movement types in v1 are receive, issue, and adjustment; the item-request
  fulfillment movement (Phase 5) will reuse the same ledger.
- Expiry dates, serial/lot tracking, multi-location transfers between
  warehouses, and unit-of-measure conversion are not required by the source
  requirements and are out of scope; a transfer can be composed later from an
  issue plus a receive.
- The existing Phase-2/3 authentication, RBAC, scope resolver, audit base,
  and seeded permission model are reused as-is; new warehouse permissions are
  added to the seed. Cross-module needs (workplace lookup for scope anchors)
  go through module contracts only.
