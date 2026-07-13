# Deployment Guide

This guide outlines the process for deploying the ITC Inventory Tracker to production using Neon (Database), Render (Backend), and Vercel (Frontend).

## Architecture Stack

*   **Database:** [Neon (Serverless Postgres)](https://neon.tech/)
*   **Backend:** [Render (Web Service)](https://render.com/)
*   **Frontend:** [Vercel](https://vercel.com/)

---

## 1. Database Deployment (Neon)

1.  **Create Project:** Create a new project in Neon.
2.  **Create Database:** Create a new database named `itc_inventory`.
3.  **Get Connection String:** Copy the pooled connection string (e.g., `postgresql://...`).
4.  **Initial Migration:** Run migrations locally against the Neon database to set up the schema.
    ```bash
    cd backend
    set DATABASE_URL="<neon_connection_string>"
    alembic upgrade head
    python seed.py
    ```

---

## 2. Backend Deployment (Render)

1.  **Create Web Service:** In Render, create a new Web Service connected to the GitHub repository.
2.  **Configuration:**
    *   **Root Directory:** `backend`
    *   **Environment:** Python 3
    *   **Build Command:** `pip install -r requirements.txt`
    *   **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3.  **Environment Variables:** Add the following environment variables:
    *   `DATABASE_URL`: Your Neon database connection string.
    *   `SECRET_KEY`: A strong, randomly generated string (e.g., output of `openssl rand -hex 32`).
    *   `ALGORITHM`: `HS256`
    *   `ACCESS_TOKEN_EXPIRE_MINUTES`: `600` (or as required).
    *   `CORS_ORIGINS`: `["https://your-vercel-app-url.vercel.app"]`
4.  **Deploy:** Trigger a manual deploy.

---

## 3. Frontend Deployment (Vercel)

1.  **Import Project:** In Vercel, import the GitHub repository.
2.  **Configuration:**
    *   **Framework Preset:** Vite
    *   **Root Directory:** `frontend`
    *   **Build Command:** `npm run build`
    *   **Output Directory:** `dist`
3.  **Environment Variables:** Add the following environment variables:
    *   `VITE_API_BASE_URL`: The URL of your Render backend (e.g., `https://your-backend-app.onrender.com`).
4.  **Deploy:** Click Deploy.

---

## 4. Deployment Verification

After all services are deployed, perform the following verification steps to ensure production readiness:

### A. Infrastructure Health
*   [ ] **Backend Health Endpoint:** Navigate to `https://<backend-url>/health`. Confirm it returns a success response.
*   [ ] **Swagger UI:** Navigate to `https://<backend-url>/docs`. Confirm the API documentation loads and endpoints are visible.
*   [ ] **Frontend Load:** Navigate to `https://<frontend-url>`. Confirm the React application loads without console errors.
*   [ ] **CORS Configuration:** Attempt a login request from the frontend. Verify there are no CORS errors in the browser console.

### B. End-to-End Business Workflow
Execute the core business flow exactly as defined in the system:

1.  [ ] **Login:** Log in as Admin.
2.  [ ] **Master Data:** Create a Warehouse, Material, and SKU/BOM.
3.  [ ] **Inventory Upload:** Upload the RMPM Opening Inventory Snapshot. Verify adjustments are created.
4.  [ ] **ODS Snapshot:** Upload the ODS Opening Inventory Snapshot.
5.  [ ] **Request Creation:** Log in as an ODS Operator. Create a material request for a specific SKU.
6.  [ ] **Requirement Calculation:** Verify the system calculates net RM/PM requirements accurately.
7.  [ ] **Reservation:** Log in as an RMPM Operator. Reserve the inventory for the request.
8.  [ ] **Approval:** Approve the request.
9.  [ ] **Dispatch:** Dispatch the materials to ODS.
10. [ ] **Receiving:** Log in as ODS Operator. Receive the materials.
11. [ ] **Closing:** Close the request.
12. [ ] **Ledger Verification:** Navigate to the inventory reports and confirm that the RMPM balances have decreased and ODS balances have increased appropriately.
13. [ ] **Transaction History:** Verify the audit log and transaction history reflect all steps above.
