# Database Architecture

The FMCG WMS utilizes a relational database (PostgreSQL 16) built on the principles of Domain-Driven Design and a strict ledger-based inventory system.

## Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    users ||--o{ roles : has
    roles ||--o{ permissions : grants
    users {
        int id PK
        string username
        string full_name
        string password_hash
        boolean is_active
        int role_id FK
        int warehouse_id FK
    }
    
    warehouses ||--o{ inventory_transactions : tracks
    warehouses ||--o{ material_requests : receives
    warehouses {
        int id PK
        string code
        string name
        string type "RMPM or ODS"
    }

    materials ||--o{ inventory_transactions : "qty transfer"
    materials ||--o{ bom_items : "forms SKU"
    materials {
        int id PK
        string code
        string name
        string uom
    }

    skus ||--o{ bom_items : "contains"
    skus ||--o{ material_requests : "requested"
    skus {
        int id PK
        string code
        string name
    }

    material_requests ||--o{ material_requests_items : "has items"
    material_requests {
        int id PK
        string request_id
        string status
        int source_warehouse_id FK
        int destination_warehouse_id FK
    }
    
    inventory_transactions {
        int id PK
        int warehouse_id FK
        int material_id FK
        decimal quantity
        string type "IN, OUT, ADJUSTMENT"
    }
```

## Base Model Principles
All domain models inherit from an `AuditedModel` which includes:
- `id`: Integer Primary Key
- `public_id`: UUID for external API references (prevents enumeration).
- `version`: Integer for optimistic locking.
- `created_at` / `updated_at` / `deleted_at`: Soft delete timestamps.
- `created_by` / `updated_by` / `deleted_by`: User ID tracking.

## Ledger-Based Inventory
Inventory balances are not overwritten. Instead, every movement is recorded in `inventory_transactions`. The current available stock is `SUM(quantity)` where `type = IN` minus `type = OUT`. This guarantees complete traceability.
