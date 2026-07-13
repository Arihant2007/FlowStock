# ITC Inventory API Documentation

## Base URL
`/api/v1`

## Authentication (`/auth`)
*   `POST /auth/login`: Authenticate user and receive a JWT token.
*   `POST /auth/refresh`: Refresh JWT token.
*   `GET /auth/me`: Get current authenticated user profile.

## Master Data (`/master`)
*   `GET /master/warehouses`: List all active warehouses.
*   `POST /master/warehouses`: Create a new warehouse.
*   `GET /master/materials`: List all raw materials/packaging materials.
*   `POST /master/materials`: Create a new material.
*   `GET /master/skus`: List all SKUs (finished goods) along with their BOMs.
*   `POST /master/skus`: Create a new SKU and define its BOM requirements.

## Inventory (`/inventory`)
*   `POST /inventory/opening-balance`: Upload Excel snapshot to initialize RMPM or ODS inventory (creates `ADJUSTMENT` transactions).
*   `POST /inventory/eod-count`: Submit End-of-Day counts to adjust inventory balances.
*   `GET /inventory/balances`: Retrieve the active ledger balances (available vs. reserved) for a specific warehouse.
*   `GET /inventory/transactions`: Retrieve the complete audit trail of inventory movements (`TRANSFER_IN`, `TRANSFER_OUT`, `RESERVATION`, `DISPATCH`, etc).

## Material Requests (`/requests`)
*   `GET /requests`: List all material requests with filters (status, date, warehouse).
*   `POST /requests`: Create a new material request (typically by ODS Operator).
*   `GET /requests/{request_id}`: Retrieve detailed line-item view of a specific request.
*   `POST /requests/{request_id}/reserve`: Reserve inventory for a request (typically by RMPM).
*   `POST /requests/{request_id}/approve`: Approve the requested quantities and trigger the inventory transfer.
*   `POST /requests/{request_id}/dispatch`: Mark the request as physically dispatched from RMPM.
*   `POST /requests/{request_id}/receive`: Mark the request as physically received at ODS.
*   `POST /requests/{request_id}/close`: Close the request workflow.
*   `POST /requests/{request_id}/reject`: Reject the request (if insufficient stock or invalid).

## Health (`/health`)
*   `GET /health`: Returns `{ "status": "ok" }` to verify backend availability.
