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

### Role 1: Administrator (User & Master Data Setup)
1. Navigate to the frontend UI (`http://localhost:5173`).
2. Log in using `admin` / `Admin@12345`.
3. **Show User Management**:
   - Go to **Administration -> Users**.
   - Create a new User: "ODS Operator 2" (Username: `ods2`).
   - Notice that no password is asked for. Click Save.
   - **Show the Temporary Password modal** and explain how this simplifies the enterprise flow.
4. **Show Master Data**:
   - Navigate to **Master Data -> Warehouses** and observe the `RMPM-Main` and `ODS-Main` warehouses.
   - Navigate to **Master Data -> Materials** to view the realistic dataset (`RM-POT-01` Raw Potato, `PM-FLM-01` Laminate Film Roll).
   - Navigate to **Master Data -> SKUs** to view the BOM definition for `SKU-CHIPS-50` (Potato Chips 50g).

### Role 2: New ODS Operator (First Login & Password Change)
1. Log out, then log in using `ods2` and the **temporary password** you just copied.
2. Observe the system immediately blocking access to the dashboard, forcing a **Mandatory Password Change**.
3. Change the password and proceed to the dashboard.
4. (Optional) Log out and log back in as the main `ods_op` / `OdsOp@12345` to continue with existing seeded data.

### Role 3: RMPM Operator (Inventory Loading)
1. Log out, then log in as `rmpm_op` / `Rmpm@12345`.
2. Check **Inventory -> Balances** to confirm the ledger reflects the uploaded opening balance (e.g., 5000kg of Raw Potato).
3. The dashboard clearly shows low stock alerts and recent activity.

### Role 4: ODS Operator (Request Generation)
1. Log out, then log in as `ods_op` / `OdsOp@12345`.
2. Notice the Dashboard shows the previously seeded request (`SUBMITTED`).
3. Navigate to **Material Requests** and create a new request to manufacture 10000 units of `SKU-CHIPS-50`.
4. Observe how the system explodes the BOM: 10000 units * 0.05kg = 500kg of Potatoes.
5. Notice how the system subtracts the ODS Opening Floor stock (if any) to calculate the **Net Requirement**.
6. Submit the request.

### Role 5: RMPM Operator (Approval & Dispatch)
1. Log out, then log in as `rmpm_op` / `Rmpm@12345`.
2. Navigate to **Material Requests** and view the newly created `SUBMITTED` request.
3. Click **Reserve** to lock the required inventory in RMPM.
4. Click **Approve** to authorize the quantities.
5. Click **Dispatch** when the physical goods leave the RMPM warehouse.

### Role 6: ODS Operator (Receiving & Closure)
1. Log out, then log in as `ods_op` / `OdsOp@12345`.
2. Navigate to **Material Requests**.
3. View the `DISPATCHED` request and click **Receive** once the materials physically arrive on the production floor.
4. Click **Close** to complete the lifecycle.

### Final Verification & Reporting
1. Log back in as `admin` / `Admin@12345`.
2. Navigate to **Reports -> Inventory Ledger**.
3. Observe the complete transaction history, demonstrating an exact ledger balance calculation (Transfer OUT of RMPM, Transfer IN to ODS).
4. Navigate to **Administration -> Audit Logs** to show the strict tracking of every status change (who approved it, when it happened).
