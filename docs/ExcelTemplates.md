# Excel Upload Templates

All Excel uploads processed by the system must follow the exact column specifications below. Use the templates provided to avoid validation errors.

---

## 1. RMPM Opening Balance Upload

**Endpoint**: `POST /api/v1/inventory/upload/preview` (then `/commit`)
**File format**: `.xlsx` or `.xls`
**Max size**: Configurable via `upload_max_mb` setting (default: 5 MB)

### Required Columns

| Column Header | Type | Description | Example |
|---------------|------|-------------|---------|
| `Material Code` | Text | Must match an existing `materials.code` | `RM-001` |
| `Quantity` | Number | Physical count quantity (4 decimal places max) | `1250.5000` |
| `UoM` | Text | Must match the material's registered UoM | `kg` |
| `Warehouse` | Text | Must match an existing `warehouses.name` | `RMPM-Main` |
| `Date` | Date | Opening balance date (DD/MM/YYYY) | `10/07/2026` |

### Validation Rules
- `Material Code` must exist in the materials master.
- `Quantity` must be ≥ 0.
- `UoM` must match the registered UoM for the material (no conversion performed).
- `Warehouse` must exist and be of type `RMPM`.
- `Date` must not be in the future.
- Duplicate `(Material Code, Warehouse, Date)` combinations within the same file trigger a warning (last row wins after confirmation).

### Upload Lifecycle
1. **Upload** → File size and extension check.
2. **Template Validation** → Verify all required columns are present.
3. **Column Validation** → Verify data types per column.
4. **Business Validation** → Cross-reference material codes, warehouses, UoMs.
5. **Preview** → User reviews a table of parsed rows (green = valid, red = error, amber = warning).
6. **Warnings** → Shown to user; user can choose to proceed or cancel.
7. **Commit** → Inventory transactions created; audit log entry written.

---

## 2. BOM Master Upload

**Endpoint**: `POST /api/v1/master/boms/upload`

### Required Columns

| Column Header | Type | Description | Example |
|---------------|------|-------------|---------|
| `SKU Code` | Text | Must match an existing `skus.code` | `SKU-BISCUIT-500` |
| `Material Code` | Text | Must match an existing `materials.code` | `RM-001` |
| `Quantity Per Unit` | Number | Material required to produce 1 unit of SKU | `0.2500` |

### Validation Rules
- `SKU Code` must exist.
- `Material Code` must exist.
- `Quantity Per Unit` must be > 0.
- Upload creates a **new BOM version** for each SKU — it does not overwrite the existing version.

---

## Common Upload Errors

| Error Code | Message | Resolution |
|------------|---------|------------|
| `XLS_001` | Missing required column: `Material Code` | Add the column with the exact header name. |
| `XLS_002` | Unknown material code: `RM-999` | Register the material in master data first. |
| `XLS_003` | Invalid quantity value: `abc` | Quantity must be a numeric value. |
| `XLS_004` | Warehouse not found: `ODS-Line-2` | Add the warehouse in master data first. |
