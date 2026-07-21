# FMCG WMS - User Guide

Welcome to the FMCG Warehouse Management System. This guide details how to perform the core workflows of the application.

## 1. Initial Setup and Access
The system recognizes three roles:
- **System Administrator**: Can create users, reset passwords, and oversee master data.
- **RMPM Operator**: Manages Raw Material & Packaging Material warehouse operations, fulfills material requests.
- **ODS Operator**: Manages One Day Stock warehouse, initiates material requests based on production schedules.

### First Login
If an administrator creates your account or resets your password, you will be given a **Temporary Password**.
Upon your first login using this temporary password, the system will redirect you to a mandatory onboarding page. You must choose a new, secure password before accessing the dashboard.

## 2. Managing Master Data
*Available to: Administrators & Planners (depending on permissions).*

### Material Master Upload
Instead of entering materials one-by-one, use the bulk upload feature:
1. Navigate to **Master Data > Materials**.
2. Click **Upload Material Master**.
3. Upload your `.xlsx` file (download the template if needed).
4. **Preview**: The system will parse your file and display a preview. Any errors (e.g., missing fields, duplicate codes) will be flagged in red.
5. **Commit**: Once errors are resolved (or if the file is valid), click **Commit Master Records** to save them to the database.

### Bill of Materials (BOM) Upload
BOMs define the recipe (Raw Materials + Packaging Materials) required for a Finished Good (SKU).
1. Navigate to **Master Data > SKUs**.
2. Click **Upload BOM Master**.
3. The upload process mimics Material Upload (Preview -> Commit).
4. The WMS supports **BOM Versioning**. Existing historical requests will retain the BOM logic active at the time they were created.

## 3. The Daily Workflow (ODS to RMPM)

### Step 1: Submitting a Material Request (ODS Operator)
When the ODS warehouse needs materials for the day's production:
1. Navigate to **Requests > New Request**.
2. Add the Target SKUs and the quantity to be manufactured.
3. The system automatically explodes the BOM and calculates the required materials.
4. If ODS has opening stock (e.g., from a snapshot upload), the system calculates the **Net Requirement** (Required - Opening Stock).
5. Submit the request. It enters the `SUBMITTED` state.

### Step 2: Reserving and Approving (RMPM Operator)
The RMPM operator receives the request.
1. Navigate to **Requests** and open the `SUBMITTED` request.
2. Click **Reserve**. The system locks the requested inventory in the RMPM warehouse. The status becomes `RESERVED`.
3. Click **Approve**. The system finalizes the transfer quantities. The status becomes `APPROVED`.

### Step 3: Dispatching (RMPM Operator)
Once the physical pallets are loaded and leave the RMPM warehouse:
1. Open the `APPROVED` request.
2. Click **Dispatch**. The inventory is officially deducted from the RMPM ledger.

### Step 4: Receiving (ODS Operator)
When the physical goods arrive at the ODS warehouse floor:
1. Open the `DISPATCHED` request.
2. Click **Receive**. The inventory is officially added to the ODS ledger.
3. Click **Close** to finalize the lifecycle of the request.

## 4. Reports and Traceability
- **Dashboard**: Provides real-time metrics on pending requests, low stock alerts, and daily transfer volumes.
- **Audit Logs**: Administrators can track every action (who created a request, who approved it, who uploaded a BOM).
- **Ledger Balances**: View real-time, mathematically accurate inventory balances across all warehouses.
