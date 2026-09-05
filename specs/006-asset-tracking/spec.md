# Feature Specification: Asset Tracking

**Feature Branch**: `feature/006-asset-tracking`

**Created**: 2026-08-31

**Status**: Draft

**Input**: Phase 6 of the implementation roadmap — asset instances with unique
serial numbers, assignment to employees or locations, returns, a complete
per-asset history timeline, and audited sensitive operations (requirements
§18, events `AssetAssigned` / `AssetReturned`).

## Clarifications

### Session 2026-08-31

- Q: What can an asset be assigned to — employees only, or also physical locations? → A: Both, per requirements §18 ("به کارمند یا محل تخصیص دهد"): the assignment target is either an in-scope employee or a free-text location (e.g. "warehouse shelf B-2"), recorded as an explicit target type.
- Q: Must every asset carry a serial number? → A: Yes — a serial number is required and unique among active assets (traceability is the phase's stated success criterion); it becomes reusable when the asset is retired.
- Q: Is asset retirement part of this phase? → A: Yes, as soft delete consistent with every master-data entity: retirement is blocked while the asset is assigned, and retired assets disappear from pickers while their history remains queryable.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Register an asset instance (Priority: P1)

As a warehouse keeper, I register a physical asset: bilingual name, required
serial number, optional description, anchored to my workplace. The serial must
be unique among active assets (case- and whitespace-normalized, like the item
catalog); duplicates are refused naming the field, and a retired asset's
serial becomes reusable. Retirement is blocked while the asset is assigned.
Every registration is audited.

**Why this priority**: Without registered instances there is nothing to
assign, return, or trace — the anchor of the phase.

**Independent Test**: Register an asset, attempt a duplicate serial
(case/whitespace variant) and be rejected, retire it and register the same
serial again — no assignment involved.

**Acceptance Scenarios**:

1. **Given** a keeper with the create permission and scope, **When** they
   submit a valid asset, **Then** the instance exists, anchored to their
   workplace, and `ASSET_CREATED` is audited.
2. **Given** an active asset with serial "X", **When** another active asset
   is registered with serial "x " (case/whitespace variant), **Then** the
   registration is refused with a duplicate error naming the serial.
3. **Given** a retired asset with serial "X", **When** a new asset is
   registered with serial "X", **Then** creation succeeds.
4. **Given** two keepers editing the same asset concurrently, **When** the
   second save arrives, **Then** it is rejected with a stale-version
   conflict.
5. **Given** an assigned asset, **When** retirement is attempted, **Then**
   it is refused with a business-rule error; after return, retirement
   succeeds.

---

### User Story 2 - Assign an asset to an employee or a location (Priority: P1)

As a warehouse keeper, I assign an available asset to an employee of my
workplace (chosen from the directory) or to a physical location (free-text
description). The asset's current holder is set, an immutable history entry
is written, and `ASSET_ASSIGNED` is audited with before/after holder
snapshots. Assigning an already-assigned asset is refused; two concurrent
assignments of the same asset resolve to exactly one winner via the
version guard.

**Why this priority**: Assignment is the core lifecycle action and a §25
concurrency-sensitive operation.

**Independent Test**: Register an asset, assign it to an employee (holder
set + history + audit), then attempt a second assignment (refused as
already-assigned), and race two assignments from two sessions — exactly one
wins.

**Acceptance Scenarios**:

1. **Given** an available asset and an active in-scope employee, **When**
   the keeper assigns it with an optional note, **Then** the asset's holder
   becomes that employee, a history entry records the assignment, and
   `ASSET_ASSIGNED` is audited.
2. **Given** an available asset, **When** the keeper assigns it to a
   location description, **Then** the holder records the location target
   type with the note as the location.
3. **Given** an already-assigned asset, **When** another assignment is
   attempted, **Then** it is refused with a business-rule error.
4. **Given** two concurrent assignments of the same available asset,
   **When** both complete, **Then** exactly one succeeded and the other
   received a stale-version conflict.
5. **Given** an assignment attempt targeting a deactivated employee or an
   employee outside the caller's scope, **When** it completes, **Then** it
   is refused (field error for the deactivated target; standard
   authorization denial for out-of-scope — no existence leak).

---

### User Story 3 - Return an assigned asset (Priority: P1)

As a warehouse keeper, I return an assigned asset: the holder is cleared, an
immutable history entry records the return, and `ASSET_RETURNED` is audited.
Returning an available (never-assigned or already-returned) asset is refused.
The return is version-guarded like assignment.

**Why this priority**: Returns complete the lifecycle loop and free the
asset for reassignment — half the traceability story.

**Independent Test**: Assign then return — holder cleared, two history
entries (assigned + returned), audit entries for both; a second return is
refused; a return of a never-assigned asset is refused.

**Acceptance Scenarios**:

1. **Given** an assigned asset, **When** the keeper returns it with an
   optional note, **Then** the holder is cleared, a history entry records
   the return, and `ASSET_RETURNED` is audited.
2. **Given** an available asset (never assigned or already returned),
   **When** a return is attempted, **Then** it is refused with a
   business-rule error and no history entry is written.
3. **Given** two concurrent returns of the same assigned asset, **When**
   both complete, **Then** exactly one succeeded and the other received a
   stale-version conflict.

---

### User Story 4 - Scoped asset list and per-asset history timeline (Priority: P2)

As warehouse staff, I see the assets of my organizational scope (workplace →
complex → global) in a paginated list with search by name/serial and a status
filter (available / assigned / retired / all); opening an asset shows its
full history timeline — every registration, assignment, return, and
retirement — newest first. Out-of-scope assets are invisible; denials never
reveal existence.

**Why this priority**: Traceability (§35) requires the timeline; visibility
rules reuse the established scope machinery.

**Independent Test**: Register assets in two different workplaces; a
CP1-scoped keeper sees only CP1 assets; each asset's timeline shows all its
actions in order.

**Acceptance Scenarios**:

1. **Given** a workplace-scoped keeper, **When** they list assets, **Then**
   only their workplace's assets appear, paginated, searchable, with the
   status filter honored.
2. **Given** any asset in scope, **When** its history is opened, **Then**
   all lifecycle entries appear newest-first with action, holder
   (from/to), note, actor, and timestamp.
3. **Given** an out-of-scope asset id fetched directly, **When** the request
   completes, **Then** the caller receives the standard authorization denial
   indistinguishable from a missing asset.

---

### User Story 5 - Bilingual assets console (Priority: P2)

As a user of either language, I manage assets through the web UI: a page
with register/edit/retire actions, assign and return actions surfaced per
status, employee picker for assignment targets, and the history timeline
drawer. Complete in English and Persian with RTL correctness, Farsi digits,
Jalali timestamps, responsive card layouts below 768px, skeletons, and
reduced-motion respect.

**Why this priority**: The constitution's bilingual/RTL/responsive gate
applies to every phase.

**Independent Test**: Walk register → assign → history → return in both
locales at mobile and desktop widths.

**Acceptance Scenarios**:

1. **Given** the Persian locale, **When** the assets surfaces open, **Then**
   all strings, dates, and digits render natively with correct RTL layout.
2. **Given** a mobile viewport, **When** the console is used, **Then**
   tables collapse to cards and touch targets remain at least 44px.

---

### Edge Cases

- What happens when a serial differs only by case/whitespace from an active
  asset? Treated as a duplicate and refused (normalization, like the item
  catalog).
- What happens when an asset is assigned to an employee who is later
  deactivated? The assignment stands (historical fact); the asset remains
  assigned until someone returns it — return does not depend on the holder's
  account state.
- What happens when a return and an assignment race on the same asset?
  Exactly one wins via the version guard; the other receives a stale-version
  error.
- What happens when an asset is retired while assigned? Blocked (business
  rule) until returned.
- What happens when history is queried for a retired asset? Fully
  queryable — retirement never removes history.
- What happens when an assignment note exceeds the length limit? Field-level
  validation error before any state change.
- What happens when an out-of-scope asset id is fetched, assigned, or
  returned directly? Standard authorization denial, never revealing
  existence.

## Requirements *(mandatory)*

### Functional Requirements

**Registration & lifecycle**

- **FR-001**: The system MUST allow authorized users to register assets with
  a bilingual display name, a required serial number, and an optional
  description, anchored to the creator's workplace.
- **FR-002**: The system MUST enforce serial uniqueness among active assets
  (case- and whitespace-normalized), refusing duplicates with the standard
  duplicate error and allowing the serial again once the previous holder is
  retired.
- **FR-003**: The system MUST support editing assets (name, description,
  serial) with stale-write detection (stale saves refused with the standard
  conflict error).
- **FR-004**: The system MUST support retiring (soft-deleting) assets;
  retirement MUST be blocked while the asset is assigned; retired assets
  disappear from lists and pickers but their history remains queryable;
  physical deletion never occurs.

**Assignment & return**

- **FR-005**: The system MUST support assigning an available asset to either
  an active in-scope employee or a location described in free text, recording
  the target type, the target, and an optional note; the asset's current
  holder becomes the assignment target.
- **FR-006**: The system MUST refuse assignment of an already-assigned asset
  and MUST refuse assignments targeting deactivated employees; concurrent
  assignments of the same asset MUST resolve to exactly one winner (version
  guard).
- **FR-007**: The system MUST support returning an assigned asset, clearing
  the holder; returns of available assets MUST be refused; concurrent returns
  resolve exactly like assignments.
- **FR-008**: Every assignment and return MUST write an immutable history
  entry recording the action, target (from/to), note, actor, and timestamp.

**History & visibility**

- **FR-009**: The system MUST record every lifecycle action (registration,
  edit, assignment, return, retirement) in the audit trail with actor, trace
  correlation, and before/after snapshots, using the `ASSET_ASSIGNED` /
  `ASSET_RETURNED` actions for the §18 events.
- **FR-010**: The system MUST expose a per-asset history timeline, newest
  first, combining the asset's own history entries, scope-filtered to the
  viewer.
- **FR-011**: Asset listing MUST be paginated with a bounded page size,
  searchable by name/serial, filterable by status (available / assigned /
  retired / all), and scope-filtered (workplace → complex → global union);
  out-of-scope access MUST be denied without revealing existence.

**Bilingual UI**

- **FR-012**: All asset surfaces MUST be fully bilingual (English / Persian)
  with RTL Persian rendering, native Farsi digits, Jalali timestamps,
  responsive layouts with tables collapsing to cards below 768px, loading
  skeletons, and reduced-motion respect.

### Key Entities *(include if feature involves data)*

- **AssetInstance**: a physical asset — bilingual name, required serial
  (unique among active assets), optional description, workplace anchor
  (scope), current holder (employee or location, null when available),
  version-guarded; soft-deletable; never physically deleted.
- **AssetHistory**: an immutable per-asset lifecycle entry — action
  (created / assigned / returned / retired), target from/to (employee or
  location), note, actor, timestamp; append-only.
- **Employee / Workplace**: assignment targets and the scope anchor; reused
  from Phase 3 unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of duplicate active-serial registrations are refused;
  100% of serials become reusable after retirement.
- **SC-002**: 100% of assignments target active in-scope employees or valid
  location descriptions; 100% of assignments of already-assigned assets are
  refused; concurrent assignment races produce exactly one winner.
- **SC-003**: Every assignment/return writes exactly one history entry plus
  the matching audit action; 100% of returns of available assets are refused
  with no history written.
- **SC-004**: A workplace-scoped viewer sees zero assets from outside their
  workplace; history timelines are complete for every asset, newest first.
- **SC-005**: 100% of lifecycle actions appear in the audit trail with
  actor, trace correlation, and before/after snapshots.
- **SC-006**: Both locales present every surface completely with correct RTL
  rendering, Farsi digits, and Jalali dates at mobile and desktop widths.

## Assumptions

- Assignment targets are employees (from the Phase-3 directory, active and
  in-scope) or free-text locations — the requirements' "کارمند یا محل" is
  taken literally; a structured location registry is out of scope.
- "Current holder" is a single target at a time (an asset is either with one
  employee, at one location, or available) — multi-holder scenarios are not
  in the requirements.
- Serial numbers are required and immutable after creation (traceability
  anchor, like employee identity fields).
- No condition/condition-reporting fields (damage reports, maintenance
  schedule) are required in v1; the note fields cover free-form tracking.
- Assets are warehouse-module data (§9.2) and reuse the established
  authorization machinery: `warehouse:asset:create/read/update/retire/assign/return`
  permission codes, workplace-anchored scope filters, version-guarded
  mutations.
