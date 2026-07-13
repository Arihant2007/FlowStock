# Architecture

## System Overview

The FMCG WMS is a single-tenant monolith built using Domain-Driven Design (DDD). All business logic is isolated within domain modules. Domains communicate via direct service calls wrapped inside a single database transaction — no event bus in V1.

## Domain Boundaries

| Domain | Responsibility |
|--------|---------------|
| `auth` | Users, Roles, Permissions, JWT authentication |
| `settings` | Runtime-configurable application parameters |
| `master` | Warehouses, Materials, SKUs, Bill of Materials |
| `inventory` | Ledger transactions, snapshots, EOD reconciliation |
| `requests` | Multi-SKU morning requests, approval workflow |
| `attachments` | Polymorphic file upload metadata |
| `reports` | Excel/PDF report generation (async) |
| `analytics` | Aggregation queries for dashboards |
| `dashboard` | UI-optimized read-only queries |
| `audit` | User action log + business event log |
| `notifications` | User alert delivery |

## Inventory Ledger Principle

The current balance for any (material, warehouse) pair is **always derived** by summing `inventory_transactions`. The `inventory_snapshots` table is a cache for reporting only. If a discrepancy exists, the ledger is correct.

## Request State Machine

```
DRAFT → SUBMITTED → RESERVED → APPROVED ──────────┐
                            └──→ PARTIALLY_APPROVED ┤
                            └──→ REJECTED (terminal) │
                                                      ↓
                                                DISPATCHED → RECEIVED → CLOSED
```

## Transaction Isolation Strategy

- **Default**: READ COMMITTED (Postgres default).
- **Inventory reservations**: READ COMMITTED + `pg_advisory_xact_lock()` per `(material_id, warehouse_id)` pair to prevent double-allocation without full SERIALIZABLE overhead.
- **Optimistic locking**: `version INT` on all editable tables; `409 Conflict` on version mismatch.

## Async Execution Abstraction

Long-running operations (Excel parsing, report generation, EOD snapshots) are dispatched asynchronously through an abstraction layer. V1 uses FastAPI `BackgroundTasks`. The abstraction allows migration to Celery/Redis without modifying business logic.
