"""Database seed script — creates all required reference data for a fresh install.

Creates:
  - 3 Roles: ADMIN, ODS_OPERATOR, RMPM_OPERATOR
  - Core Permissions for each domain action
  - 1 Admin user, 1 ODS operator, 1 RMPM operator
  - 2 Warehouses: RMPM-Main, ODS-Main
  - Material classifications (category, type, group)
  - 3 sample materials (2 RM, 1 PM)
  - 1 SKU with an active BOM version
  - Essential Settings (upload_max_mb, business_cutoff, etc.)

Usage:
    python seed.py

Requires DATABASE_URL environment variable to be set.
"""

import os
import sys
from decimal import Decimal

# Ensure the app package is importable when running from backend/.
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy.orm import Session

from app.domains.auth.models import Permission, Role, RolePermission, User
from app.domains.auth.security import hash_password
from app.domains.master.models import (
    SKU,
    BOMItem,
    BOMVersion,
    Material,
    MaterialCategory,
    MaterialGroup,
    MaterialType,
    Warehouse,
)
from app.domains.settings.models import Setting
from app.domains.audit.models import AuditLog, BusinessEventLog
from app.domains.inventory.models import InventoryTransaction, InventorySnapshot
from app.domains.requests.models import MaterialRequest, MaterialRequestSKU, MaterialRequestItem
from app.infrastructure.base_model import Base
from app.infrastructure.database import SessionLocal, engine

PERMISSIONS = [
    ("auth:login", "Authenticate and receive tokens"),
    ("users:create", "Create new system users"),
    ("users:read", "View user profiles"),
    ("master:read", "Read master data (SKUs, materials, BOMs)"),
    ("master:write", "Create and update master data"),
    ("inventory:read", "View inventory balances and transactions"),
    ("inventory:upload", "Upload RMPM opening balance Excel"),
    ("inventory:adjust", "Create inventory adjustments"),
    ("requests:create", "Submit morning material requests (ODS)"),
    ("requests:read", "View material requests"),
    ("requests:approve", "Approve or reject material requests (RMPM)"),
    ("reports:read", "View and export reports"),
    ("settings:read", "View application settings"),
    ("settings:write", "Modify application settings"),
]

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "ADMIN": [p[0] for p in PERMISSIONS],  # Admin gets everything.
    "ODS_OPERATOR": [
        "auth:login",
        "master:read",
        "inventory:read",
        "requests:create",
        "requests:read",
        "reports:read",
    ],
    "RMPM_OPERATOR": [
        "auth:login",
        "master:read",
        "inventory:read",
        "inventory:upload",
        "inventory:adjust",
        "requests:read",
        "requests:approve",
        "reports:read",
    ],
}

SETTINGS = [
    ("upload_max_mb", "5", "Maximum Excel upload size in megabytes.", "integer"),
    (
        "business_cutoff_time",
        "09:00",
        "Daily cutoff time for morning requests (HH:MM).",
        "string",
    ),
    (
        "reservation_timeout_hours",
        "24",
        "Hours before an unreleased reservation is auto-cancelled.",
        "integer",
    ),
    (
        "allowed_upload_extensions",
        '["xlsx", "xls"]',
        "Allowed Excel file extensions.",
        "json",
    ),
    ("plant_name", "ITC Plant", "Name of the manufacturing plant.", "string"),
    ("plant_code", "ITC-001", "Plant code used in reports.", "string"),
    (
        "notification_interval_minutes",
        "60",
        "Minimum interval between notification digests.",
        "integer",
    ),
    (
        "snapshot_eod_time",
        "21:00",
        "Time (HH:MM) to generate daily inventory snapshots.",
        "string",
    ),
]


def seed(db: Session) -> None:  # noqa: C901
    print("Seeding permissions...")
    perm_map: dict[str, Permission] = {}
    for code, desc in PERMISSIONS:
        p = db.query(Permission).filter_by(code=code).first()
        if p is None:
            p = Permission(code=code, description=desc)
            db.add(p)
            db.flush()
        perm_map[code] = p

    print("Seeding roles...")
    role_map: dict[str, Role] = {}
    for role_name in ["ADMIN", "ODS_OPERATOR", "RMPM_OPERATOR"]:
        r = db.query(Role).filter_by(name=role_name).first()
        if r is None:
            r = Role(name=role_name)
            db.add(r)
            db.flush()
        role_map[role_name] = r

    print("Assigning permissions to roles...")
    for role_name, codes in ROLE_PERMISSIONS.items():
        role = role_map[role_name]
        for code in codes:
            perm = perm_map[code]
            exists = (
                db.query(RolePermission)
                .filter_by(role_id=role.id, permission_id=perm.id)
                .first()
            )
            if not exists:
                db.add(RolePermission(role_id=role.id, permission_id=perm.id))
    db.flush()

    print("Seeding users...")
    admin_role = role_map["ADMIN"]
    ods_role = role_map["ODS_OPERATOR"]
    rmpm_role = role_map["RMPM_OPERATOR"]

    users_to_seed = [
        (
            "admin",
            "admin@plant.local",
            "System Administrator",
            "Admin@12345",
            admin_role.id,
        ),
        ("ods_op", "ods@plant.local", "ODS Operator 1", "OdsOp@12345", ods_role.id),
        ("rmpm_op", "rmpm@plant.local", "RMPM Operator 1", "Rmpm@12345", rmpm_role.id),
    ]
    for username, email, full_name, pw, role_id in users_to_seed:
        if not db.query(User).filter_by(username=username).first():
            db.add(
                User(
                    username=username,
                    email=email,
                    full_name=full_name,
                    password_hash=hash_password(pw),
                    role_id=role_id,
                )
            )
    db.flush()

    print("Seeding warehouses...")
    for wh_name, wh_type in [("RMPM-Main", "RMPM"), ("ODS-Main", "ODS")]:
        if not db.query(Warehouse).filter_by(name=wh_name).first():
            db.add(Warehouse(name=wh_name, type=wh_type))
    db.flush()

    print("Seeding material classifications...")
    import json
    rules_path = os.path.join(os.path.dirname(__file__), "app", "core", "classification_rules.json")
    with open(rules_path, "r") as f:
        rules = json.load(f)

    categories = set(["Raw Material", "Packaging Material", "Others", "General"])
    types = set(["RM", "PM"])
    groups = set(["Ingredients", "Laminates", "Films", "Cartons", "Pouches", "Labels", "Others", "Default"])

    for rule in rules.get("prefix_rules", []):
        if "category" in rule:
            categories.add(rule["category"])
        if "type" in rule:
            types.add(rule["type"])
    for rule in rules.get("keyword_rules", []):
        if "group" in rule:
            groups.add(rule["group"])
    if "defaults" in rules:
        if "category" in rules["defaults"]:
            categories.add(rules["defaults"]["category"])
        if "type" in rules["defaults"]:
            types.add(rules["defaults"]["type"])
        if "group" in rules["defaults"]:
            groups.add(rules["defaults"]["group"])

    cat_map = {}
    for c_name in categories:
        cat = db.query(MaterialCategory).filter_by(name=c_name).first()
        if not cat:
            cat = MaterialCategory(name=c_name)
            db.add(cat)
            db.flush()
        cat_map[c_name] = cat

    type_map = {}
    for t_name in types:
        mtype = db.query(MaterialType).filter_by(name=t_name).first()
        if not mtype:
            mtype = MaterialType(name=t_name)
            db.add(mtype)
            db.flush()
        type_map[t_name] = mtype

    group_map = {}
    for g_name in groups:
        grp = db.query(MaterialGroup).filter_by(name=g_name).first()
        if not grp:
            grp = MaterialGroup(name=g_name)
            db.add(grp)
            db.flush()
        group_map[g_name] = grp

    print("Seeding sample materials...")
    mat_defs = [
        ("RM-001", "Wheat Flour", "kg", cat_map["Raw Material"].id, type_map["RM"].id, group_map["Ingredients"].id),
        ("RM-002", "Edible Oil", "L", cat_map["Raw Material"].id, type_map["RM"].id, group_map["Ingredients"].id),
        ("PM-001", "Cardboard Box 500g", "units", cat_map["Packaging Material"].id, type_map["PM"].id, group_map["Cartons"].id),
    ]
    mat_map: dict[str, Material] = {}
    for code, name, uom, cat_id, type_id, group_id in mat_defs:
        m = db.query(Material).filter_by(code=code).first()
        if not m:
            m = Material(
                code=code,
                name=name,
                uom=uom,
                category_id=cat_id,
                type_id=type_id,
                group_id=group_id,
            )
            db.add(m)
            db.flush()
        mat_map[code] = m

    print("Seeding sample SKU and BOM...")
    sku = db.query(SKU).filter_by(code="SKU-BISCUIT-500").first()
    if not sku:
        sku = SKU(code="SKU-BISCUIT-500", name="Biscuit 500g Pack")
        db.add(sku)
        db.flush()

    bom = db.query(BOMVersion).filter_by(sku_id=sku.id, version_number=1).first()
    if not bom:
        bom = BOMVersion(sku_id=sku.id, version_number=1, is_active=True)
        db.add(bom)
        db.flush()
        bom_items = [
            (mat_map["RM-001"].id, Decimal("0.2500")),  # 250g flour per unit
            (mat_map["RM-002"].id, Decimal("0.0500")),  # 50ml oil per unit
            (mat_map["PM-001"].id, Decimal("1.0000")),  # 1 box per unit
        ]
        for mat_id, qty in bom_items:
            db.add(
                BOMItem(
                    bom_version_id=bom.id, material_id=mat_id, quantity_per_unit=qty
                )
            )
        db.flush()

    print("Seeding settings...")
    for key, value, desc, vtype in SETTINGS:
        if not db.query(Setting).filter_by(key=key).first():
            db.add(Setting(key=key, value=value, description=desc, value_type=vtype))
    db.flush()

    db.commit()
    print("Seed complete.")
    print("\nDefault credentials:")
    print("  Admin:        admin / Admin@12345")
    print("  ODS Operator: ods_op / OdsOp@12345")
    print("  RMPM Operator:rmpm_op / Rmpm@12345")


if __name__ == "__main__":
    print("Creating all tables (if not exist)...")
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)
