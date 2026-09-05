# Tasks: Notifications, Event Outbox & Live SSE

**Input**: Design documents from `/specs/008-notifications-outbox-sse/`

**Prerequisites**: plan.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: REQUIRED per task (constitution: tests are part of each task).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable · **[Story]**: US1–US5; FND = foundational
- FR/SC references map to spec.md; R# to research.md

---

## Phase 1: Setup

- [x] T001 [FND] `backend/app/common/bus.py`: in-process event bus — thread→asyncio bridge (subscribe per user_id, publish from threads, async wait with timeout); `backend/tests/test_bus.py`: publish/subscribe, per-user filtering, timeout path (research R5)

## Phase 2: Foundational — models & migration (blocking)

- [x] T002 [FND] `backend/app/modules/notification/models.py`: `OutboxStatus`/`NotificationEventType` constants + `EventOutbox` (status CHECK, 13-type CHECK, claim index, actor/trace) + `Notification` (owner FK, outbox FK, exactly-once partial unique, unread + list indexes, read_at) per data-model.md; alembic `backend/alembic/versions/0008_notifications_outbox_sse.py`; verify reversible on local PG (data-model notes)
- [x] T003 [P] [FND] `backend/app/modules/notification/schemas.py`: `NotificationOut` (payload passthrough), `UnreadCountOut`, `MarkedOut`, payload builder helpers; `backend/tests/test_notification_schemas.py` fixtures (contracts)

**Checkpoint**: migration reversible; bus proven.

## Phase 3: US1 — Atomic event capture (P1) 🎯 MVP

**Goal**: every mapped action emits its §20 event in the same transaction.

**Independent Test**: perform each mapped action → one outbox row; a rolled-back action → no row.

- [x] T004 [US1] `backend/app/modules/notification/contracts.py`: `record_event(session, event_type, payload, actor_user_id, critical=False)` + `deliver_critical(...)` + `CRITICAL_EVENTS` mapping (v1: InventoryLowStock); unit test: capture writes pending row in-session (research R1/R4)
- [x] T005 [US1] Wire capture into emitting services: employee+user creation (`UserCreated`, seed-exempt), catalog create, low-stock raise (+ critical in-transaction delivery), request create/approve/reject/fulfill, asset assign/return, loan create/activate/settle — each in the same transaction; test additions: event capture matrix + rollback case (refused fulfillment leaves no row) (FR-001, FR-003, SC-001, research R9)
  - **Deferred (decided 2026-09-01)**: `ItemReturned` has no emitting business
    action in the current product surface (no return-to-stock flow exists; the
    only return flow is asset returns, which emit `AssetReturned`). The type
    stays valid — CHECK + relay deliver it — but no emitter is wired until a
    return flow ships. The capture matrix covers the 12 emittable events.

**Checkpoint**: all 13 events captured atomically; rollback-proof.

## Phase 4: US2 — Relay delivery (P1)

**Goal**: pending events become per-recipient notifications, exactly-once, retries bounded.

**Independent Test**: submit a request → requester notification within relay latency; forced failure → retry; restart replay → no duplicates.

- [x] T006 [US2] `backend/app/modules/user/contracts.py`: `get_recipient_user_ids(session, permission_code, workplace_id)` (active users whose scopes cover the unit, implicit deny); contract tests (research R3)
- [x] T007 [US2] `backend/app/modules/notification/service.py`: `deliver_event` — claim-aware delivery, per-event recipient mapping (R3 table), idempotent inserts (partial unique), deactivated-recipient skip, bounded retries (≤5) + terminal `failed`/`skipped`, unknown event type → immediate `failed`; test additions: delivery matrix, duplicate-replay safety, deactivated skip, unknown-type terminal failure (FR-004, FR-005, FR-006, SC-002)
- [x] T008 [US2] `backend/app/modules/notification/relay.py`: lifespan-managed daemon thread — poll 2s, claim ≤ 50 via SKIP LOCKED, deliver, publish to bus, re-claim orphaned `processing` on startup; test additions: end-to-end outbox→notification within latency, restart redelivery without duplicates (FR-004, SC-002, SC-003, research R2)

**Checkpoint**: the relay delivers live; failures never break anything.

## Phase 5: US3 — Live SSE stream (P1)

**Goal**: authenticated per-user stream pushes new notifications within seconds.

**Independent Test**: open stream → deliver an event → SSE frame arrives; unauthenticated → denied.

- [x] T009 [US3] `router.py`: `GET /notifications/stream` (async generator over the bus + keep-alive comments, Bearer-auth, owner filter only) + endpoint tests: 401 unauthenticated, frame on delivery, foreign-user filtering (FR-007, SC-003)
- [x] T010 [P] [US3] `backend/app/modules/notification/router.py` REST endpoints: `GET /notifications` (page, unread_only), `GET /unread-count`, `POST /{id}/read`, `POST /read-all` — owner-scoped; endpoint tests: pagination, unread filtering, idempotent read, read-all, foreign 404 (FR-008)

**Checkpoint**: live stream + inbox API proven; Phase gate (browser) pending UI.

## Phase 6: US4 — Notification inbox UI (P2)

- [ ] T011 [US4] BFF: `frontend/src/app/api/notifications/**` (list/unread-count/[id]/read/read-all) + streaming SSE passthrough route forwarding the session cookie; `lib/client-api.ts` `notificationApi` + types; `messages/{en,fa}.json` `notifications.*` namespace incl. per-event bilingual descriptions (FR-009, contracts)
- [ ] T012 [US4] UI: header bell with live unread badge (EventSource on app mount → invalidate queries), `features/notifications/NotificationPanel.tsx` (newest-first list, per-event descriptions, mark one/all read, skeletons) ; `features/notifications/useNotificationStream.ts` hook; responsive + reduced motion (FR-009, SC-005, research R11)

## Phase 7: US5 — Criticality observability (P2)

- [ ] T013 [US5] Critical-mapping test additions: `InventoryLowStock` in-app rows exist in the SAME commit as the alert; a non-critical event's delivery failure leaves business state untouched and the event retrying (FR-010, SC-004)

## Phase 8: Polish & Convergence

- [ ] T014 [P] [POL] `scripts/smoke-test.ps1`: notifications section — low-stock alert → outbox row + critical notifications in same commit → requester notification delivered → unread-count increments → mark-read works (SC-001..SC-005)
- [ ] T015 [POL] CHANGELOG 0.8.0 entry + VERSION bump + README notifications section (outbox model, relay, SSE, criticality)
- [ ] T016 [POL] Full gate: backend ruff/mypy/pytest (scratch DB), frontend lint/tsc/build, seed twice idempotent, manual browser checklist per quickstart.md, `scripts/smoke-ui.ps1` green, commit + push; CI green

---

## Dependencies & Execution Order

- T001 → T002–T003 (parallel) → T004–T005 (US1) → T006–T008 (US2;
  T006 before T007) → T009–T010 (US3; [P]) → T011–T012 (US4) → T013 (US5)
  → T014–T016.
- US1 is the MVP substrate; US2 delivers; US3 makes it live; US4/US5
  complete the phase.

## Notes

- No physical deletes; terminal failures are statuses (research R2).
- The exactly-once partial unique `(outbox_event_id, user_id)` is the
  idempotency backbone (research R2/R3).
- Delivery failures must never raise into business transactions except the
  Critical in-transaction rows (research R4).
- The relay is lifespan-managed; tests that need deterministic delivery
  call `deliver_event` directly (relay latency tests use the running
  relay with generous waits).
- Commit after each phase checkpoint (Conventional Commits).
