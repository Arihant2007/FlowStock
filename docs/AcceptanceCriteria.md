# Acceptance Criteria (Definition of Done)

This document formalizes the Acceptance Criteria for the Core Domain Logic phases (Phases 2 through 5) of the FMCG WMS. No phase is considered complete until all criteria are satisfied.

---

## Phase 2: Authentication & Authorization

**Goal:** Establish secure access control based on user roles (Admin, ODS Operator, RMPM Operator).

### Definition of Done
- [x] Login API endpoint returns a valid JWT access token and refresh token.
- [x] Invalid credentials return a `401 Unauthorized` standard error.
- [x] Token refresh API successfully issues a new access token.
- [x] Access tokens have a short lifespan (e.g., 15 minutes) and refresh tokens have a long lifespan (e.g., 7 days).
- [x] RBAC middleware successfully blocks access to endpoints requiring permissions the user lacks (`403 Forbidden`).
- [x] Full test coverage for successful login, failed login, token refresh, and RBAC rejection.
- [x] OpenAPI (Swagger) documentation generated with Security Definitions configured so users can authenticate via the Swagger UI.

**Known Limitations for V1:** No SSO/Active Directory integration. Passwords are managed internally via bcrypt.

---

## Phase 3: Master Data CRUD

**Goal:** Provide endpoints to manage Warehouses, Materials, SKUs, and BOMs.

### Definition of Done
- [ ] RESTful CRUD endpoints exist for Warehouses, Materials, and SKUs.
- [ ] BOM endpoints allow uploading/creating a *new version* of a BOM (BOM versions are immutable).
- [ ] Soft deletion (`deleted_at`) is implemented; GET lists exclude deleted items by default.
- [ ] Optimistic locking (`version` column) prevents lost updates. Concurrent modifications return a `409 Conflict`.
- [ ] Validations ensure UoM, category, and type IDs reference valid master records.
- [ ] Audit logs capture every CRUD modification (recorded in `audit_logs`).

**Rollback Plan (if schema changes):** Alembic down-revision tested and verified.

---

## Phase 4: Inventory Ledger

**Goal:** Ingest opening balances and handle physical End-of-Day (EOD) adjustments.

### Definition of Done
- [ ] Endpoint `/api/v1/inventory/upload` correctly parses an Excel file using the expected template.
- [ ] Validation detects missing materials, invalid warehouses, or bad quantities, returning a preview with warnings/errors.
- [ ] Committing an upload appends correct `RECEIPT` transactions to `inventory_transactions`.
- [ ] Endpoint `/api/v1/inventory/eod-count` calculates the delta between system balance and actual physical count, creating an `ADJUSTMENT` transaction.
- [ ] All quantities are strictly handled as `DECIMAL(18,4)`.
- [ ] Transaction isolation prevents dirty reads during balance calculations.

**Demo Scenario:** Upload a 10-line Excel file with 2 deliberate errors. Verify the preview rejects the errors. Fix the errors and commit. Check the ledger balance updates accordingly.

---

## Phase 5: Material Requests (ODS & RMPM workflows)

**Goal:** The core operational workflow — ODS requests materials; RMPM approves and dispatches.

### Definition of Done
- [ ] ODS can create a multi-SKU `DRAFT` request. The system accurately calculates net materials required (`BOM qty * planned_qty - remaining_qty`).
- [ ] Request captures the *active* BOM version snapshot at the time of creation.
- [ ] ODS can submit the request (`DRAFT -> SUBMITTED`).
- [ ] RMPM can view submitted requests and approve them line-by-line.
- [ ] Approval atomically triggers:
    1. A `RESERVATION` hold on the inventory.
    2. A paired `TRANSFER_OUT` and `TRANSFER_IN` moving inventory from RMPM to ODS.
- [ ] Strict state machine enforcement (e.g., cannot approve a `DRAFT`).
- [ ] Concurrent approval of the same request or requests needing the same limited material is handled gracefully (via `SELECT ... FOR UPDATE` or optimistic locking) without deadlocks or double-spending.

**Rollback Plan:** `inventory_transactions` is append-only. Reversals must be implemented via corrective transactions (`RESERVATION_RELEASE`, reverse `TRANSFER`), not `DELETE`.
