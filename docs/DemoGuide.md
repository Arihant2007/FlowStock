# ITC Inventory Demo Guide

This guide provides a step-by-step walkthrough to demonstrate the capabilities of the ITC Inventory application.

## 1. Environment Setup
1. **Start the Database**: Ensure PostgreSQL (or the local SQLite test DB) is running.
2. **Start the Backend**:
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # (or .venv\Scripts\activate on Windows)
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```
   *The backend runs on `http://localhost:8000`*
   *Access Swagger documentation at `http://localhost:8000/docs`*

3. **Start the Frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   *The frontend runs on `http://localhost:5173`*

4. **Seed the Database**:
   Run the seed script to populate master data and users:
   ```bash
   cd backend
   python seed.py
   ```

## 2. Demonstration Flow

### Role 1: Administrator (Master Data Setup)
1. Navigate to the frontend UI (`http://localhost:5173`).
2. Log in using `admin` / `Admin@12345`.
3. Navigate to **Master Data -> Warehouses** and observe the `RMPM-Main` and `ODS-Main` warehouses.
4. Navigate to **Master Data -> Materials** to view `RM-001` (Wheat Flour) and `RM-002` (Edible Oil).
5. Navigate to **Master Data -> SKUs** to view the BOM definition for `SKU-BISCUIT-500`.

### Role 2: RMPM Operator (Inventory Loading)
1. Log out, then log in as `rmpm_op` / `Rmpm@12345`.
2. Navigate to **Inventory -> Upload Snapshot**.
3. Upload a sample snapshot indicating RMPM holds 1000kg of Wheat Flour and 500L of Edible Oil.
4. Check **Inventory -> Balances** to confirm the ledger reflects the uploaded adjustment.

### Role 3: ODS Operator (Request Generation)
1. Log out, then log in as `ods_op` / `OdsOp@12345`.
2. Navigate to **Inventory -> Upload Snapshot** and upload ODS's current stock (e.g., 10kg Flour).
3. Navigate to **Material Requests** and create a new request to manufacture 100 units of `SKU-BISCUIT-500`.
4. Observe the system automatically calculates the net RM/PM requirement by applying the BOM and subtracting the ODS Opening stock.

### Role 4: RMPM Operator (Approval & Dispatch)
1. Log out, then log in as `rmpm_op` / `Rmpm@12345`.
2. Navigate to **Material Requests** and view the newly created `SUBMITTED` request.
3. Click **Reserve** to lock the required inventory.
4. Click **Approve** to authorize the quantities and trigger the automated transfer (`TRANSFER_OUT` / `TRANSFER_IN`).
5. Click **Dispatch** when the physical goods leave the RMPM warehouse.

### Role 5: ODS Operator (Receiving & Closure)
1. Log out, then log in as `ods_op` / `OdsOp@12345`.
2. Navigate to **Material Requests**.
3. View the `DISPATCHED` request and click **Receive** once the materials arrive.
4. Click **Close** to complete the lifecycle.

### Final Verification
1. Navigate to **Reports -> Inventory Ledger**.
2. Observe the complete transaction history, demonstrating an exact balance calculation devoid of any overlaps or double deductions.
