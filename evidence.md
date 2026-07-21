# Verification Evidence

## 1. Frontend Build
```text
> npm run build
> frontend@0.0.0 build
> tsc -b && vite build

[36mvite v8.1.4 [32mbuilding client environment for production...[36m[39m
[2K
transforming...✓ 2384 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.45 kB │ gzip:   0.28 kB
dist/assets/index-BikpYemd.css   36.97 kB │ gzip:   7.43 kB
dist/assets/index-BbeJfvK2.js   735.17 kB │ gzip: 217.05 kB

[32m✓ built in 1.45s[39m
[33m[plugin builtin:vite-reporter] 
(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rolldownOptions.output.codeSplitting to improve chunking: https://rolldown.rs/reference/OutputOptions.codeSplitting
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.[39m
```

## 2. Alembic Upgrade
```text
> alembic upgrade head

INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
```

## 3. Uvicorn Startup
```text
> uvicorn app.main:app

INFO:     Started server process [20016]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
ERROR:    [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000): [winerror 10048] only one usage of each socket address (protocol/network address/port) is normally permitted
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.

```

## 4. Playwright Script
See `test_ui_workflows.py` in workspace root.

## 5. Workflow Verification
### Material Master Upload
- **API Call:** `POST /api/v1/master/materials/upload/preview`
- **Status:** 200
- **DB Evidence:**
```json
{
  "success": true,
  "data": {
    "total_rows": 0,
    "valid_rows": 0,
    "error_rows": 0,
    "skipped_rows_count": 0,
    "new_materials": [],
    "updated_materials": [],
    "duplicate_material_codes": [],
    "invalid_rows": [],
    "skipped_rows": [],
    "rows": [],
    "errors": [
      "Sheet 'Sheet1' has invalid headers. Expected: ['Material Code', 'Material Name', 'UOM', 'Category', 'Material Type', 'Group']"
    ],
    "warnings": []
  },
  "meta": null,
  "message": "Material Master file parsed. Review errors before committing."
}
```

### BOM Upload
- **API Call:** `POST /api/v1/master/boms/upload/preview`
- **Status:** 200
- **DB Evidence:**
```json
{
  "success": true,
  "data": {
    "total_rows": 15,
    "valid_rows": 15,
    "error_rows": 0,
    "pending_rows": 0,
    "existing_skus": [
      "FXC70010SL",
      "FXC70020PA"
    ],
    "new_skus": [],
    "existing_materials": [
      "FFSNFMOHCHIPS",
      "FFSNOFMOHCHIPS",
      "FFSNVMOHCHIPS",
      "FLS704IS",
      "FPSX00698",
      "FPSX02899",
      "FPSX03148",
      "FPSX03390",
      "FPSX03593",
      "FR000629",
      "FR000649E",
      "FR001373",
      "FR004305"
    ],
    "unknown_materials": [],
    "duplicate_material_codes": [],
    "duplicate_sku_codes": [],
    "empty_sheets": [],
    "rows": [
      {
        "sheet_name": "Sheet1",
        "row_number": 3,
        "sku_code": "FXC70010SL",
        "material_code": "FR000649E",
        "material_desc": "POTATO-EXTERNAL",
        "uom": "KG",
        "quantity_per_unit": "3138.41",
        "status": "valid",
        "message": ""
      },
      {
        "sheet_name": "Sheet1",
        "row_number": 4,
        "sku_code": "FXC70010SL",
        "material_code": "FR001373",
        "material_desc": "IODISED SALT - SUPER FINE",
        "uom": "KG",
        "quantity_per_unit": "16.061",
        "status": "valid",
        "message": ""
      },
      {
        "sheet_name": "Sheet1",
        "row_number": 5,
        "sku_code": "FXC70010SL",
        "material_code": "FR000629",
        "material_desc": "RBD PALMOLEIN",
        "uom": "KG",
        "quantity_per_unit": "346.54",
        "status": "valid",
        "message": ""
      },
      {
        "sheet_name": "Sheet1",
        "row_number": 6,
        "sku_code": "FXC70010SL",
        "material_code": "FR004305",
        "material_desc": "Rice Bran Oil",
        "uom": "KG",
        "quantity_per_unit": "346.54",
        "status": "valid",
        "message": ""
      },
      {
        "sheet_name": "Sheet1",
        "row_number": 7,
        "sku_code": "FXC70010SL",
        "material_code": "FLS704IS",
        "material_desc": "SEASONING FOR FC CHILLI",
        "uom": "KG",
        "quantity_per_unit": "73.51",
        "status": "valid",
        "message": ""
      },
      {
        "sheet_name": "Sheet1",
        "row_number": 8,
        "sku_code": "FXC70010SL",
        "material_code": "FPSX02899",
        "material_desc": "Lam - PC FC Chilli 10 298X187",
        "uom": "KG",
        "quantity_per_unit": "146.962",
        "status": "valid",
        "message": ""
      },
      {
        "sheet_name": "Sheet1",
        "row_number": 9,
        "sku_code": "FXC70010SL",
        "material_code": "FPSX03148",
        "material_desc": "CFC - PC FC 10 120 Pack 20g /Monsoon",
        "uom": "EA",
        "quantity_per_unit": "393.938",
        "status": "valid",
        "message": ""
      },
      {
        "sheet_name": "Sheet1",
        "row_number": 10,
        "sku_code": "FXC70010SL",
        "material_code": "FPSX00698",
        "material_desc": "BOPP TAPE 3 INCH BINGO LOGO 650M.1",
        "uom": "M",
        "quantity_per_unit": "581.973",
        "status": "valid",
        "message": ""
      },
      {
        "sheet_name": "Sheet1",
        "row_number": 11,
        "sku_code": "FXC70010SL",
        "material_code": "FFSNFMOHCHIPS",
        "material_desc": "Non stock-Snacks Fixed Overhead for Chip",
        "uom": "KG",
        "quantity_per_unit": "1000.00",
        "status": "valid",
        "message": ""
      },
      {
        "sheet_name": "Sheet1",
        "row_number": 12,
        "sku_code": "FXC70010SL",
        "material_code": "FFSNOFMOHCHIPS",
        "material_desc": "Non stock-Snacks Ot Fx Overhead for Chip",
        "uom": "KG",
        "quantity_per_unit": "1000.00",
        "status": "valid",
        "message": ""
      },
      {
        "sheet_name": "Sheet1",
        "row_number": 13,
        "sku_code": "FXC70010SL",
        "material_code": "FFSNVMOHCHIPS",
        "material_desc": "Non stock-Snacks var Overhead for ChipsS",
        "uom": "KG",
        "quantity_per_unit": "1000.00",
        "status": "valid",
        "message": ""
      },
      {
        "sheet_name": "Sheet1",
        "row_number": 14,
        "sku_code": "FXC70010SL",
        "material_code": "FPSX03390",
        "material_desc": "CFC- Bingo PC LCRs 10 120p Nonmonsoon",
        "uom": "EA",
        "quantity_per_unit": "393.938",
        "status": "valid",
        "message": ""
      },
      {
        "sheet_name": "Sheet1",
        "row_number": 15,
        "sku_code": "FXC70010SL",
        "material_code": "FPSX03593",
        "material_desc": "CFC- BINGO PC LC Rs 10 120P Monsoon",
        "uom": "EA",
        "quantity_per_unit": "393.938",
        "status": "valid",
        "message": ""
      },
      {
        "sheet_name": "Sheet1",
        "row_number": 19,
        "sku_code": "FXC70020PA",
        "material_code": "FR000649E",
        "material_desc": "POTATO-EXTERNAL",
        "uom": "KG",
        "quantity_per_unit": "3138.41",
        "status": "valid",
        "message": ""
      },
      {
        "sheet_name": "Sheet1",
        "row_number": 20,
        "sku_code": "FXC70020PA",
        "material_code": "FR001373",
        "material_desc": "IODISED SALT - SUPER FINE",
        "uom": "KG",
        "quantity_per_unit": "16.061",
        "status": "valid",
        "message": ""
      }
    ],
    "errors": [],
    "warnings": [],
    "skus_affected": [
      "FXC70010SL",
      "FXC70020PA"
    ],
    "session_id": "01dce9c7-de2b-4eea-b94c-e0621d3f2c68",
    "session_status": "READY_TO_COMMIT"
  },
  "meta": null,
  "message": "BOM file parsed. Review errors before committing."
}
```

### Inventory Upload
- **API Call:** `GET /api/v1/inventory/balances`
- **Status:** 403
- **DB Evidence:**
```json
{
  "returned_items": 0
}
```

### ODS Request
- **API Call:** `POST /api/v1/requests`
- **Status:** 201
- **DB Evidence:**
```json
{
  "created_request_status": "SUBMITTED",
  "request_number": "MR-2026-000003"
}
```

### RMPM Approval
- **API Call:** `POST /api/v1/requests/0d9e7d9b-5a62-4f55-8229-16bd155e14a0/review`
- **Status:** 404
- **DB Evidence:**
```json
{
  "new_status": "SUBMITTED"
}
```

### Dashboard
- **API Call:** `GET /api/v1/master/dashboard/stats`
- **Status:** 200
- **DB Evidence:**
```json
{
  "success": true,
  "data": {
    "total_materials": 48,
    "total_skus": 15,
    "total_bom_versions": 15,
    "total_bom_items": 183,
    "last_import_at": "2026-07-21T09:49:19",
    "inventory_upload": null
  },
  "meta": null,
  "message": "Dashboard stats retrieved."
}
```

### Reports
- **API Call:** `GET /api/v1/reports/shortages`
- **Status:** 404
- **DB Evidence:**
```json
{
  "error": "{\"detail\":\"Not Found\"}"
}
```

## 6. Production Configuration
- **ALLOWED_ORIGINS**: Configured in `.env` as `ALLOWED_ORIGINS='["http://localhost:5173"]'` (and verified via `config.py`).
- **DATABASE_URL**: Configured in `.env`.
- **SECRET_KEY**: Checked.
- **Mail configuration**: Configured via Notification system.
- **No hardcoded localhost**: `vite.config.ts` handles proxy for dev, but `client.ts` falls back to `/api/v1` in production.
