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
    ("users:manage", "Create, edit, reset password, lock/unlock, activate/deactivate users"),
    ("admin:read", "Access the administration module"),
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
    "SYSTEM_ADMINISTRATOR": [p[0] for p in PERMISSIONS],  # Admin gets everything.
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
    for role_name in ["SYSTEM_ADMINISTRATOR", "ODS_OPERATOR", "RMPM_OPERATOR"]:
        r = db.query(Role).filter_by(name=role_name).first()
        if r is None:
            r = Role(name=role_name, is_system=True)
            db.add(r)
            db.flush()
        else:
            r.is_system = True
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
    admin_role = role_map["SYSTEM_ADMINISTRATOR"]
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
        ("RM-POT-01", "Raw Potato", "kg", cat_map["Raw Material"].id, type_map["RM"].id, group_map["Ingredients"].id),
        ("RM-OIL-01", "Edible Oil", "L", cat_map["Raw Material"].id, type_map["RM"].id, group_map["Ingredients"].id),
        ("RM-SLT-01", "Salt", "kg", cat_map["Raw Material"].id, type_map["RM"].id, group_map["Ingredients"].id),
        ("RM-SPC-01", "Masala Spices", "kg", cat_map["Raw Material"].id, type_map["RM"].id, group_map["Ingredients"].id),
        ("PM-FLM-01", "Laminate Film Roll", "m", cat_map["Packaging Material"].id, type_map["PM"].id, group_map["Films"].id),
        ("PM-BOX-01", "Corrugated Carton Box", "units", cat_map["Packaging Material"].id, type_map["PM"].id, group_map["Cartons"].id),
        ("PM-PCH-50", "Primary Pouch 50g", "units", cat_map["Packaging Material"].id, type_map["PM"].id, group_map["Pouches"].id),
        ("PM-PCH-100", "Primary Pouch 100g", "units", cat_map["Packaging Material"].id, type_map["PM"].id, group_map["Pouches"].id),
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
    sku_defs = [
        ("SKU-CHIPS-50", "Potato Chips 50g"),
        ("SKU-CHIPS-100", "Potato Chips 100g"),
    ]
    sku_map = {}
    for sku_code, sku_name in sku_defs:
        sku = db.query(SKU).filter_by(code=sku_code).first()
        if not sku:
            sku = SKU(code=sku_code, name=sku_name)
            db.add(sku)
            db.flush()
        sku_map[sku_code] = sku

    # BOM for 50g Chips
    bom_50 = db.query(BOMVersion).filter_by(sku_id=sku_map["SKU-CHIPS-50"].id, version_number=1).first()
    if not bom_50:
        bom_50 = BOMVersion(sku_id=sku_map["SKU-CHIPS-50"].id, version_number=1, is_active=True)
        db.add(bom_50)
        db.flush()
        bom_items_50 = [
            (mat_map["RM-POT-01"].id, Decimal("0.0500")),  # 50g potato
            (mat_map["RM-OIL-01"].id, Decimal("0.0100")),  # 10ml oil
            (mat_map["RM-SLT-01"].id, Decimal("0.0025")),  # 2.5g salt
            (mat_map["RM-SPC-01"].id, Decimal("0.0025")),  # 2.5g spices
            (mat_map["PM-PCH-50"].id, Decimal("1.0000")),  # 1 pouch
            (mat_map["PM-BOX-01"].id, Decimal("0.0500")),  # 1 box packs 20 units (1/20 = 0.05)
        ]
        for mat_id, qty in bom_items_50:
            db.add(BOMItem(bom_version_id=bom_50.id, material_id=mat_id, quantity_per_unit=qty))
        db.flush()

    # BOM for 100g Chips
    bom_100 = db.query(BOMVersion).filter_by(sku_id=sku_map["SKU-CHIPS-100"].id, version_number=1).first()
    if not bom_100:
        bom_100 = BOMVersion(sku_id=sku_map["SKU-CHIPS-100"].id, version_number=1, is_active=True)
        db.add(bom_100)
        db.flush()
        bom_items_100 = [
            (mat_map["RM-POT-01"].id, Decimal("0.1000")),  # 100g potato
            (mat_map["RM-OIL-01"].id, Decimal("0.0200")),  # 20ml oil
            (mat_map["RM-SLT-01"].id, Decimal("0.0050")),  # 5g salt
            (mat_map["RM-SPC-01"].id, Decimal("0.0050")),  # 5g spices
            (mat_map["PM-PCH-100"].id, Decimal("1.0000")), # 1 pouch
            (mat_map["PM-BOX-01"].id, Decimal("0.1000")),  # 1 box packs 10 units (1/10 = 0.10)
        ]
        for mat_id, qty in bom_items_100:
            db.add(BOMItem(bom_version_id=bom_100.id, material_id=mat_id, quantity_per_unit=qty))
        db.flush()

    print("Seeding settings...")
    for key, value, desc, vtype in SETTINGS:
        if not db.query(Setting).filter_by(key=key).first():
            db.add(Setting(key=key, value=value, description=desc, value_type=vtype))
    db.flush()

    print("Seeding opening inventory...")
    rmpm_wh = db.query(Warehouse).filter_by(name="RMPM-Main").first()
    ods_wh = db.query(Warehouse).filter_by(name="ODS-Main").first()
    
    # Check if inventory exists
    if not db.query(InventoryTransaction).first():
        # Add opening stock to RMPM
        for code, qty in [("RM-POT-01", 5000), ("RM-OIL-01", 1000), ("RM-SLT-01", 200), ("RM-SPC-01", 200), ("PM-FLM-01", 10000), ("PM-BOX-01", 5000), ("PM-PCH-50", 20000), ("PM-PCH-100", 20000)]:
            db.add(InventoryTransaction(
                destination_warehouse_id=rmpm_wh.id,
                material_id=mat_map[code].id,
                quantity=Decimal(str(qty)),
                transaction_type="RECEIPT",
                notes="Initial Opening Balance",
                reference_type="MANUAL_ADJUSTMENT",
                reference_id=1,
                created_by=1
            ))
        
        # Add a tiny bit to ODS to show net calculations
        for code, qty in [("RM-POT-01", 50), ("RM-OIL-01", 10), ("PM-BOX-01", 50)]:
            db.add(InventoryTransaction(
                destination_warehouse_id=ods_wh.id,
                material_id=mat_map[code].id,
                quantity=Decimal(str(qty)),
                transaction_type="RECEIPT",
                notes="Opening Floor Stock",
                reference_type="MANUAL_ADJUSTMENT",
                reference_id=1,
                created_by=1
            ))
        db.flush()

    print("Seeding sample requests...")
    if not db.query(MaterialRequest).first():
        import uuid
        from datetime import date
        req_number = f"REQ-ODS-{str(uuid.uuid4())[:8].upper()}"
        req = MaterialRequest(
            request_date=date.today(),
            request_number=req_number,
            status="SUBMITTED",
            ods_warehouse_id=ods_wh.id,
            rmpm_warehouse_id=rmpm_wh.id,
            notes="Morning Production Run - Line 1"
        )
        db.add(req)
        db.flush()
        
        sku_50 = MaterialRequestSKU(
            request_id=req.id,
            sku_id=sku_map["SKU-CHIPS-50"].id,
            bom_version_id=bom_50.id,
            planned_production_qty=Decimal("5000") # 5000 units of 50g chips
        )
        db.add(sku_50)
        
        sku_100 = MaterialRequestSKU(
            request_id=req.id,
            sku_id=sku_map["SKU-CHIPS-100"].id,
            bom_version_id=bom_100.id,
            planned_production_qty=Decimal("2000") # 2000 units of 100g chips
        )
        db.add(sku_100)
        db.flush()
        
        # We need to compute required items to render the request properly.
        req_items_map = {}
        # For 50g
        for item in bom_items_50:
            mat_id = item[0]
            req_qty = item[1] * Decimal("5000")
            req_items_map[mat_id] = req_items_map.get(mat_id, {"gross": Decimal("0"), "sku_id": sku_50.id})
            req_items_map[mat_id]["gross"] += req_qty
            
        # For 100g
        for item in bom_items_100:
            mat_id = item[0]
            req_qty = item[1] * Decimal("2000")
            if mat_id not in req_items_map:
                req_items_map[mat_id] = {"gross": Decimal("0"), "sku_id": sku_100.id}
            req_items_map[mat_id]["gross"] += req_qty
            
        # Deduct ODS floor stock
        floor_stock = {mat_map["RM-POT-01"].id: Decimal("50"), mat_map["RM-OIL-01"].id: Decimal("10"), mat_map["PM-BOX-01"].id: Decimal("50")}
        
        for mat_id, data in req_items_map.items():
            avail = floor_stock.get(mat_id, Decimal("0"))
            net = max(Decimal("0"), data["gross"] - avail)
            db.add(MaterialRequestItem(
                request_sku_id=data["sku_id"],
                material_id=mat_id,
                gross_required_qty=data["gross"],
                remaining_from_previous_day=avail,
                requested_qty=net,
                approved_qty=Decimal("0"),
                dispatched_qty=Decimal("0")
            ))
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
