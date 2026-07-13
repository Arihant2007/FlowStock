# FMCG WMS — Inventory Transfer System

Production-grade Warehouse Management System digitizing the inventory transfer process between the **RMPM Warehouse** (Raw Material & Packaging Material) and **ODS** (One Day Stock) in an FMCG manufacturing plant.

## Overview

| Area | Technology |
|------|-----------|
| Backend | FastAPI 0.115, SQLAlchemy 2, Alembic, Pydantic v2 |
| Frontend | React 18 + Vite, TypeScript, Tailwind CSS, Shadcn UI |
| Database | PostgreSQL 16 (Neon) |
| Deployment | Backend → Render, Frontend → Vercel |
| Auth | JWT (access + refresh tokens), RBAC |

## Quick Links

| Document | Description |
|----------|-------------|
| [Architecture](docs/Architecture.md) | System design, DDD structure, domain boundaries |
| [Database](docs/Database.md) | Schema, ER diagram, migrations |
| [API Reference](docs/API.md) | All endpoints, request/response schemas |
| [Deployment](docs/Deployment.md) | Render, Vercel, Neon setup |
| [Developer Guide](docs/DeveloperGuide.md) | Local setup, code standards, testing |
| [Excel Templates](docs/ExcelTemplates.md) | Upload format specifications |
| [Troubleshooting](docs/Troubleshooting.md) | Common issues and solutions |

## Local Setup

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL 16 (local or Neon)
- `uv` (recommended): `pip install uv`

### Backend

```bash
cd backend
cp .env.example .env          # Edit DATABASE_URL, SECRET_KEY
uv pip install -e ".[dev]"
alembic upgrade head           # Run all migrations
python seed.py                 # Seed reference data
uvicorn app.main:app --reload  # Start dev server → http://localhost:8000
```

### Frontend

```bash
cd frontend
cp .env.example .env           # Edit VITE_API_URL
npm ci
npm run dev                    # Start dev server → http://localhost:5173
```

### Default Seed Credentials

| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | `Admin@12345` |
| ODS Operator | `ods_op` | `OdsOp@12345` |
| RMPM Operator | `rmpm_op` | `Rmpm@12345` |

> ⚠️ Change all passwords immediately after first deployment.

## Key Business Rules

1. **All inventory quantities are `DECIMAL(18,4)`** — no floating-point arithmetic.
2. **Inventory is ledger-based** — balances are always calculated from `inventory_transactions`. Never overwritten.
3. **Requests are multi-SKU** — one morning request can contain multiple SKUs.
4. **BOM versioning** — historical transactions always reference the BOM version active on the request date.
5. **Soft deletes** — master data is never physically deleted.
6. **EOD reconciliation** — any gap between expected and actual inventory creates an explicit `ADJUSTMENT` transaction.

## Project Structure

```
fmcg-wms/
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── core/             # Config, Logger, Errors, Middleware, Responses
│   │   ├── infrastructure/   # DB engine, base models, base repository
│   │   ├── domains/          # All business domains (DDD)
│   │   │   ├── auth/
│   │   │   ├── settings/
│   │   │   ├── master/
│   │   │   ├── inventory/
│   │   │   ├── requests/
│   │   │   ├── attachments/
│   │   │   ├── reports/
│   │   │   ├── analytics/
│   │   │   ├── dashboard/
│   │   │   ├── audit/
│   │   │   └── notifications/
│   │   └── api/              # Router assembly + health endpoints
│   ├── alembic/              # Database migrations
│   ├── tests/                # Domain-organized unit + integration tests
│   └── seed.py               # Reference data seeder
├── frontend/                 # React + Vite application
├── docs/                     # Developer documentation
└── .github/workflows/        # GitHub Actions CI/CD
```

## Running Tests

```bash
cd backend
pytest                          # All tests with coverage
pytest tests/domains/auth/      # Specific domain
pytest -k "test_login"          # Specific test name
```

## License

Private — FMCG Manufacturing Plant Internal System.
