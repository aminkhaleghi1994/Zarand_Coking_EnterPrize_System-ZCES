# Contract: Warehouse Module Interface (cross-module)

The warehouse module's published interface for other modules (constitution
VI — modules never touch another module's repositories or models directly).
Implemented as `backend/app/modules/warehouse/contracts.py` in Phase 4.

## Exported to other modules (Phase 5 — item requests)

```python
def get_item(session, item_id) -> ItemView | None
    """Catalog item snapshot (id, name/name_fa, code, unit, min_quantity,
    is_active) or None if unknown. No permission checks — caller is a module."""

def get_placement_for_stock(session, *, item_id, shelf_id) -> PlacementRef | None
    """Active placement reference (id, quantity) for a shelf×item pair."""

def get_shelf_context(session, shelf_id) -> ShelfContext | None
    """shelf_id -> {warehouse_id, workplace_id, complex_id, company_id};
    lets a calling module resolve the scope target before requesting stock."""

def apply_fulfillment_issue(session, *, placement_id, quantity,
                            actor_user_id, reason) -> MovementView
    """Phase 5 fulfillment path: atomically decrease the placement (FOR UPDATE),
    write a `fulfillment` movement, re-evaluate alerts, and audit — all in the
    CALLER's transaction (the caller owns commit/rollback).
    Raises AppError(INSUFFICIENT_STOCK) if the quantity would go negative.
    NOT exposed over HTTP; Phase 5 calls it from its own fulfillment service."""
```

**Transaction ownership**: `apply_fulfillment_issue` participates in the
caller's transaction (no commit inside) — consistent with the rule that the
request-fulfillment service owns the atomic "approve + fulfill + movement"
boundary. All Phase-4 HTTP services commit their own transactions.

## Inbound dependency (user module)

The warehouse module needs workplace anchoring:

```python
# backend/app/modules/user/contracts.py (added this phase)
def get_workplace_with_parents(session, workplace_id)
    -> WorkplaceView | None
"""Workplace snapshot including parent complex_id/company_id; used to fill
warehouses.org columns and to validate the scope target at creation."""
```

This is the only cross-module read the warehouse module makes; everything
else is self-contained. No warehouse tables are touched by other modules
except through the functions above.

## Permission codes registered by this module

Seeded idempotently by `seed_dev.run_seed` (see research R10):

```
warehouse:item:create  warehouse:item:read  warehouse:item:update  warehouse:item:retire
warehouse:warehouse:create  warehouse:warehouse:read  warehouse:warehouse:update  warehouse:warehouse:retire
warehouse:shelf:create  warehouse:shelf:read  warehouse:shelf:update  warehouse:shelf:retire
warehouse:stock:receive  warehouse:stock:issue  warehouse:stock:adjust  warehouse:stock:read
warehouse:alert:read
```

Role mapping: `WarehouseKeeper` (daily work + catalog management),
`WarehouseApprover` (read-only until Phase 5 approval flow),
`SuperAdmin` (ensure-all, existing seed behavior).

## Events (future)

Phase 4 writes audit entries directly (`STOCK_ALERT_RAISED` /
`STOCK_ALERT_RESOLVED`). No domain events are published to the outbox yet —
event emission and notification delivery arrive with Phase 8
(notifications-outbox-sse); the alert rows already carry everything that
phase will need to notify.
