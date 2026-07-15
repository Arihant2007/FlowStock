"""Master domain service — CRUD and BOM Excel upload business logic.

Key responsibilities:
  1. CRUD for Warehouses, Materials, SKUs with optimistic locking via BaseRepository.update.
  2. Soft-deletion; lists always exclude deleted items by default.
  3. Validates that category/type/group references exist before creating/updating materials.
  4. BOM Upload: parses an Excel file, validates each row (SKU and Material must exist),
     deactivates the current BOM version for that SKU, and creates a new immutable
     BOMVersion with all its BOMItems. Each item is tagged with the material's RM/PM type.
  5. Audit log entries for all mutations.
"""

from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import DuplicateError, NotFoundError, ValidationError
from app.core.logger import get_logger
from app.core.responses import PaginationMeta
from app.domains.audit.service import AuditService
from app.domains.master.models import (
    SKU,
    BOMItem,
    BOMVersion,
    Material,
    Warehouse,
)
from app.domains.master.repository import (
    BOMVersionRepository,
    MaterialCategoryRepository,
    MaterialGroupRepository,
    MaterialRepository,
    MaterialTypeRepository,
    SKURepository,
    WarehouseRepository,
)
from app.domains.master.schemas import (
    BOMUploadPreview,
    BOMUploadRowResult,
    MaterialCreate,
    MaterialUpdate,
    SKUCreate,
    SKUUpdate,
    WarehouseCreate,
    WarehouseUpdate,
)

logger = get_logger(__name__)

BOM_REQUIRED_COLUMNS = {"SKU Code", "Material Code", "Quantity Per Unit"}


class MasterService:
    """All master data business logic: CRUD and BOM Excel upload."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._audit = AuditService(db)
        self._warehouse_repo = WarehouseRepository(db)
        self._material_repo = MaterialRepository(db)
        self._sku_repo = SKURepository(db)
        self._bom_repo = BOMVersionRepository(db)
        self._cat_repo = MaterialCategoryRepository(db)
        self._type_repo = MaterialTypeRepository(db)
        self._group_repo = MaterialGroupRepository(db)

    # ------------------------------------------------------------------
    # Warehouse CRUD
    # ------------------------------------------------------------------

    def list_warehouses(
        self, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[Warehouse], PaginationMeta]:
        rows, total = self._warehouse_repo.list_all(page=page, page_size=page_size)
        import math

        meta = PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if page_size else 1,
        )
        return rows, meta

    def get_warehouse(self, public_id: str) -> Warehouse:
        return self._warehouse_repo.get_by_public_id(public_id)

    def create_warehouse(
        self, payload: WarehouseCreate, *, created_by: int
    ) -> Warehouse:
        existing = self._warehouse_repo.get_by_name(payload.name)
        if existing is not None:
            raise DuplicateError(
                f"Warehouse with name '{payload.name}' already exists."
            )

        wh = Warehouse(
            name=payload.name,
            type=payload.type,
            description=payload.description,
            created_by=created_by,
        )
        result = self._warehouse_repo.create(wh)
        self._audit.log_action(
            action="WAREHOUSE_CREATED",
            user_id=created_by,
            resource_type="Warehouse",
            resource_id=result.id,
            details={"name": payload.name, "type": payload.type},
        )
        logger.info("warehouse_created", name=payload.name, created_by=created_by)
        return result

    def update_warehouse(
        self, public_id: str, payload: WarehouseUpdate, *, updated_by: int
    ) -> Warehouse:
        wh = self._warehouse_repo.get_by_public_id(public_id)
        updates: dict[str, Any] = {}
        if payload.name is not None:
            existing = self._warehouse_repo.get_by_name(payload.name)
            if existing is not None and existing.id != wh.id:
                raise DuplicateError(
                    f"Warehouse name '{payload.name}' is already taken."
                )
            updates["name"] = payload.name
        if payload.description is not None:
            updates["description"] = payload.description

        # Temporarily set the version on the in-memory object to the client's
        # version so BaseRepository.update can do the optimistic locking check.
        wh.version = payload.version
        result = self._warehouse_repo.update(wh, updates, updated_by=updated_by)
        self._audit.log_action(
            action="WAREHOUSE_UPDATED",
            user_id=updated_by,
            resource_type="Warehouse",
            resource_id=wh.id,
            details=updates,
        )
        return result

    def delete_warehouse(self, public_id: str, *, deleted_by: int) -> None:
        wh = self._warehouse_repo.get_by_public_id(public_id)
        self._warehouse_repo.soft_delete(wh, deleted_by=deleted_by)
        self._audit.log_action(
            action="WAREHOUSE_DELETED",
            user_id=deleted_by,
            resource_type="Warehouse",
            resource_id=wh.id,
        )

    # ------------------------------------------------------------------
    # Material CRUD
    # ------------------------------------------------------------------

    def list_materials(
        self, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[Material], PaginationMeta]:
        rows, total = self._material_repo.list_all(page=page, page_size=page_size)
        import math

        meta = PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if page_size else 1,
        )
        return rows, meta

    def get_material(self, public_id: str) -> Material:
        return self._material_repo.get_by_public_id(public_id)

    def create_material(self, payload: MaterialCreate, *, created_by: int) -> Material:
        existing = self._material_repo.get_by_code(payload.code)
        if existing is not None:
            raise DuplicateError(f"Material with code '{payload.code}' already exists.")

        cat = self._cat_repo.get_by_public_id(payload.category_public_id)
        mat_type = self._type_repo.get_by_public_id(payload.type_public_id)
        group_id: int | None = None
        if payload.group_public_id is not None:
            group = self._group_repo.get_by_public_id(payload.group_public_id)
            group_id = group.id

        mat = Material(
            code=payload.code,
            name=payload.name,
            uom=payload.uom,
            category_id=cat.id,
            type_id=mat_type.id,
            group_id=group_id,
            created_by=created_by,
        )
        result = self._material_repo.create(mat)
        self._audit.log_action(
            action="MATERIAL_CREATED",
            user_id=created_by,
            resource_type="Material",
            resource_id=result.id,
            details={"code": payload.code},
        )
        logger.info("material_created", code=payload.code, created_by=created_by)
        return self._material_repo.get_by_id(result.id)

    def update_material(
        self, public_id: str, payload: MaterialUpdate, *, updated_by: int
    ) -> Material:
        mat = self._material_repo.get_by_public_id(public_id)
        updates: dict[str, Any] = {}
        if payload.name is not None:
            updates["name"] = payload.name
        if payload.uom is not None:
            updates["uom"] = payload.uom
        if payload.category_public_id is not None:
            cat = self._cat_repo.get_by_public_id(payload.category_public_id)
            updates["category_id"] = cat.id
        if payload.type_public_id is not None:
            mat_type = self._type_repo.get_by_public_id(payload.type_public_id)
            updates["type_id"] = mat_type.id
        if payload.group_public_id is not None:
            group = self._group_repo.get_by_public_id(payload.group_public_id)
            updates["group_id"] = group.id

        mat.version = payload.version
        result = self._material_repo.update(mat, updates, updated_by=updated_by)
        self._audit.log_action(
            action="MATERIAL_UPDATED",
            user_id=updated_by,
            resource_type="Material",
            resource_id=mat.id,
            details=updates,
        )
        return self._material_repo.get_by_id(result.id)

    def delete_material(self, public_id: str, *, deleted_by: int) -> None:
        mat = self._material_repo.get_by_public_id(public_id)
        self._material_repo.soft_delete(mat, deleted_by=deleted_by)
        self._audit.log_action(
            action="MATERIAL_DELETED",
            user_id=deleted_by,
            resource_type="Material",
            resource_id=mat.id,
        )

    # ------------------------------------------------------------------
    # SKU CRUD
    # ------------------------------------------------------------------

    def list_skus(
        self, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[SKU], PaginationMeta]:
        rows, total = self._sku_repo.list_all(page=page, page_size=page_size)
        import math

        meta = PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=math.ceil(total / page_size) if page_size else 1,
        )
        return rows, meta

    def get_sku(self, public_id: str) -> SKU:
        return self._sku_repo.get_by_public_id(public_id)

    def create_sku(self, payload: SKUCreate, *, created_by: int) -> SKU:
        existing = self._sku_repo.get_by_code(payload.code)
        if existing is not None:
            raise DuplicateError(f"SKU with code '{payload.code}' already exists.")

        sku = SKU(
            code=payload.code,
            name=payload.name,
            description=payload.description,
            created_by=created_by,
        )
        result = self._sku_repo.create(sku)
        self._audit.log_action(
            action="SKU_CREATED",
            user_id=created_by,
            resource_type="SKU",
            resource_id=result.id,
            details={"code": payload.code},
        )
        logger.info("sku_created", code=payload.code, created_by=created_by)
        return result

    def update_sku(self, public_id: str, payload: SKUUpdate, *, updated_by: int) -> SKU:
        sku = self._sku_repo.get_by_public_id(public_id)
        updates: dict[str, Any] = {}
        if payload.name is not None:
            updates["name"] = payload.name
        if payload.description is not None:
            updates["description"] = payload.description
        sku.version = payload.version
        result = self._sku_repo.update(sku, updates, updated_by=updated_by)
        self._audit.log_action(
            action="SKU_UPDATED",
            user_id=updated_by,
            resource_type="SKU",
            resource_id=sku.id,
            details=updates,
        )
        return result

    def delete_sku(self, public_id: str, *, deleted_by: int) -> None:
        sku = self._sku_repo.get_by_public_id(public_id)
        self._sku_repo.soft_delete(sku, deleted_by=deleted_by)
        self._audit.log_action(
            action="SKU_DELETED",
            user_id=deleted_by,
            resource_type="SKU",
            resource_id=sku.id,
        )

    def get_active_bom(self, sku_public_id: str) -> BOMVersion:
        """Return the active BOM version for a SKU, with items and material types loaded."""
        sku = self._sku_repo.get_by_public_id(sku_public_id)
        bom = self._bom_repo.get_active_for_sku(sku.id)
        if bom is None:
            raise NotFoundError(f"No active BOM found for SKU '{sku.code}'.")
        return bom

    # ------------------------------------------------------------------
    # BOM Excel Upload
    # ------------------------------------------------------------------
    def preview_bom_upload(self, file_bytes: bytes, filename: str) -> BOMUploadPreview:
        """Parse and validate a BOM Excel file without committing any changes."""
        parsed_rows, global_errors, empty_sheets = self._parse_bom_excel(file_bytes, filename)


        sku_codes = list({r["sku_code"] for r in parsed_rows})
        mat_codes = list({r["material_code"] for r in parsed_rows})

        skus_db = self._db.scalars(
            select(SKU).where(SKU.code.in_(sku_codes)).where(SKU.deleted_at.is_(None))
        ).all()
        sku_map = {s.code: s for s in skus_db}

        materials_db = self._db.scalars(
            select(Material).where(Material.code.in_(mat_codes)).where(Material.deleted_at.is_(None))
        ).all()
        material_map = {m.code: m for m in materials_db}

        rows: list[BOMUploadRowResult] = []
        error_count = 0
        skus_affected: set[str] = set()

        existing_skus = set()
        new_skus = set()
        existing_materials = set()
        unknown_materials = set()

        seen_blocks = set()
        seen_sku_codes = set()
        duplicate_sku_codes = set()

        seen_sku_materials = set()
        duplicate_material_codes = set()

        for r in parsed_rows:
            sku_code = r["sku_code"]
            mat_code = r["material_code"]
            qty_raw = r["quantity_per_unit"]
            block_key = (r["sheet_name"], r["block_id"])

            if block_key not in seen_blocks:
                seen_blocks.add(block_key)
                if sku_code in seen_sku_codes:
                    duplicate_sku_codes.add(sku_code)
                seen_sku_codes.add(sku_code)

            if (sku_code, mat_code) in seen_sku_materials:
                duplicate_material_codes.add(f"{mat_code} in {sku_code}")
                status = "error"
                message = f"Duplicate material '{mat_code}' in SKU '{sku_code}'."
                error_count += 1
            else:
                seen_sku_materials.add((sku_code, mat_code))

            status = status if 'status' in locals() and status == "error" else "valid"
            message = message if 'message' in locals() and message != "" else ""

            # SKU check
            if sku_code in sku_map:
                existing_skus.add(sku_code)
            else:
                new_skus.add(sku_code)

            # Material check
            if mat_code in material_map:
                existing_materials.add(mat_code)
            else:
                unknown_materials.add(mat_code)
                status = "unknown_material"
                message = f"Unknown material '{mat_code}'. Must be created first."

            # Validate quantity
            try:
                qty = Decimal(qty_raw)
                if qty <= 0:
                    raise ValueError("Must be positive.")
            except (InvalidOperation, ValueError):
                status = "error"
                message = f"Invalid quantity '{qty_raw}': must be a positive number."
                error_count += 1

            skus_affected.add(sku_code)
            rows.append(
                BOMUploadRowResult(
                    sheet_name=r["sheet_name"],
                    row_number=r["row_number"],
                    sku_code=sku_code,
                    material_code=mat_code,
                    material_desc=r["material_desc"],
                    uom=r["uom"],
                    quantity_per_unit=qty_raw,
                    status=status,
                    message=message,
                )
            )

        return BOMUploadPreview(
            total_rows=len(rows),
            valid_rows=len(rows) - error_count - len([r for r in rows if r.status == 'unknown_material']),
            error_rows=error_count,
            existing_skus=sorted(existing_skus),
            new_skus=sorted(new_skus),
            existing_materials=sorted(existing_materials),
            unknown_materials=sorted(unknown_materials),
            duplicate_material_codes=sorted(duplicate_material_codes),
            duplicate_sku_codes=sorted(duplicate_sku_codes),
            empty_sheets=empty_sheets,
            rows=rows,
            errors=global_errors,
            skus_affected=sorted(skus_affected),
        )

    def commit_bom_upload(
        self, file_bytes: bytes, filename: str, *, created_by: int
    ) -> dict[str, int]:
        """Parse, validate, and commit a BOM Excel file."""
        parsed_rows, global_errors, empty_sheets = self._parse_bom_excel(file_bytes, filename)
        if global_errors:
            raise ValidationError(global_errors[0])

        sku_codes = list({r["sku_code"] for r in parsed_rows})
        mat_codes = list({r["material_code"] for r in parsed_rows})

        skus_db = self._db.scalars(
            select(SKU).where(SKU.code.in_(sku_codes)).where(SKU.deleted_at.is_(None))
        ).all()
        sku_map = {s.code: s for s in skus_db}

        materials_db = self._db.scalars(
            select(Material).where(Material.code.in_(mat_codes)).where(Material.deleted_at.is_(None))
        ).all()
        material_map = {m.code: m for m in materials_db}

        # Check for unknown materials (rollback)
        unknown_mats = [code for code in mat_codes if code not in material_map]
        if unknown_mats:
            raise ValidationError(f"Cannot commit. Unknown materials found: {', '.join(unknown_mats)}")

        # Check quantities
        for r in parsed_rows:
            try:
                qty = Decimal(r["quantity_per_unit"])
                if qty <= 0:
                    raise ValueError
            except ValueError as e:
                raise ValidationError(f"Invalid quantity {r['quantity_per_unit']} for material {r['material_code']}.") from e

        skus_updated = 0
        items_created = 0

        # Create missing SKUs
        for sku_code in sku_codes:
            if sku_code not in sku_map:
                # Find SKU Name
                sku_name = next((r["sku_name"] for r in parsed_rows if r["sku_code"] == sku_code), sku_code)
                new_sku = SKU(code=sku_code, name=sku_name, created_by=created_by)
                self._db.add(new_sku)
                self._db.flush()
                sku_map[sku_code] = new_sku

        # Group by SKU
        sku_groups: dict[str, list[dict[str, Any]]] = {}
        for r in parsed_rows:
            sku_groups.setdefault(r["sku_code"], []).append(r)

        for sku_code, mat_rows in sku_groups.items():
            sku = sku_map[sku_code]

            self._bom_repo.deactivate_all_for_sku(sku.id)
            next_ver = self._bom_repo.get_next_version_number(sku.id)

            bom = BOMVersion(
                sku_id=sku.id,
                version_number=next_ver,
                is_active=True,
                notes=f"Uploaded via Excel — version {next_ver}",
                created_by=created_by,
            )
            self._db.add(bom)
            self._db.flush()

            for r in mat_rows:
                mat = material_map.get(r["material_code"])
                assert mat is not None
                self._db.add(
                    BOMItem(
                        bom_version_id=bom.id,
                        material_id=mat.id,
                        quantity_per_unit=Decimal(r["quantity_per_unit"]),
                        created_by=created_by,
                    )
                )
                items_created += 1

            self._db.flush()
            skus_updated += 1

            self._audit.log_action(
                action="BOM_VERSION_CREATED",
                user_id=created_by,
                resource_type="BOMVersion",
                resource_id=bom.id,
                details={"sku_code": sku_code, "version_number": next_ver},
            )

        logger.info(
            "bom_upload_committed",
            skus_updated=skus_updated,
            items_created=items_created,
            created_by=created_by,
        )
        return {"skus_updated": skus_updated, "items_created": items_created}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_bom_excel(
        self, file_bytes: bytes, filename: str
    ) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        """Parse Excel bytes into a list of dictionaries.

        Returns:
            parsed_rows: list of dictionaries representing validly parsed data rows.
            global_errors: list of file-level validation errors.
            empty_sheets: list of sheet names that were skipped because they were empty.
        """
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if extension not in {"xlsx", "xls"}:
            return [], [f"Unsupported file type '.{extension}'. Use .xlsx or .xls."], []

        try:
            # Read all sheets, without headers
            sheets_dict = pd.read_excel(BytesIO(file_bytes), sheet_name=None, header=None, dtype=str)
        except Exception as exc:  # noqa: BLE001
            return [], [f"Could not read Excel file: {exc}"], []

        parsed_rows = []
        global_errors = []
        empty_sheets = []

        expected_headers = ["Material Code", "Material Description", "Quantity for 1 ton", "UOM"]

        for sheet_name, df in sheets_dict.items():
            df = df.dropna(how="all")  # Drop completely empty rows
            if df.empty or len(df) < 3:
                empty_sheets.append(sheet_name)
                continue

            try:
                current_sku_name = ""
                current_sku_code = ""
                sku_block_valid = False
                block_id = 0

                for i in range(len(df)):
                    row = df.iloc[i]
                    col0 = str(row[0]).strip() if pd.notna(row[0]) else ""

                    # Skip completely blank lines or NaNs
                    if not col0 or col0.lower() == "nan":
                        continue

                    # Detect Headers (indicates the start of the material list for a SKU block)
                    if col0.lower() == expected_headers[0].lower():
                        h1 = col0
                        h2 = str(row[1]).strip() if df.shape[1] > 1 and pd.notna(row[1]) else ""
                        h3 = str(row[2]).strip() if df.shape[1] > 2 and pd.notna(row[2]) else ""
                        h4 = str(row[3]).strip() if df.shape[1] > 3 and pd.notna(row[3]) else ""
                        actual_headers = [h1, h2, h3, h4]

                        if not all(a.lower() == e.lower() for a, e in zip(actual_headers, expected_headers, strict=False)):
                            global_errors.append(f"Sheet '{sheet_name}', Row {df.index[i] + 1} has invalid headers. Expected: {expected_headers}")
                            sku_block_valid = False
                            continue

                        block_id += 1

                        # Look at the previous row for SKU Name and SKU Code
                        if i == 0:
                            global_errors.append(f"Sheet '{sheet_name}': Headers found on first row, missing SKU block definition.")
                            sku_block_valid = False
                            continue

                        prev_row = df.iloc[i-1]
                        current_sku_name = str(prev_row[0]).strip() if pd.notna(prev_row[0]) else ""
                        current_sku_code = str(prev_row[1]).strip() if df.shape[1] > 1 and pd.notna(prev_row[1]) else ""

                        if not current_sku_name or current_sku_name.lower() == "nan":
                            global_errors.append(f"Sheet '{sheet_name}', Row {df.index[i] + 1}: Missing SKU Name.")
                            sku_block_valid = False
                            continue

                        if not current_sku_code or current_sku_code.lower() == "nan":
                            global_errors.append(f"Sheet '{sheet_name}', Row {df.index[i] + 1}: Missing SKU Code for SKU '{current_sku_name}'.")
                            sku_block_valid = False
                            continue

                        # It's valid!
                        sku_block_valid = True
                        continue

                    # If it's a material row
                    if sku_block_valid:
                        # We are inside a valid block, so this row is a material.
                        mat_code = col0

                        # Check if this row is actually a SKU definition without headers immediately following?
                        # No, the next row would have headers, so it would just be skipped because sku_block_valid remains True until headers are found again... Wait.
                        # What if there are blank rows separating the blocks, and then a SKU definition row?
                        # df.dropna() removes blank rows.
                        # So a SKU definition row will appear immediately after the last material of the previous block.
                        # If we parse it as a material, it will be added as a material to the PREVIOUS block!
                        # BUT wait! We detect headers at `i`. The row `i-1` is the SKU definition.
                        # So when we process row `i-1` in the loop, we will currently treat it as a material for the previous block!
                        # Let's fix this! We should not add it as a material if it's going to be a SKU definition.
                        # How do we know it's a SKU definition? We don't, until we see the headers on the NEXT row.

                        # Lookahead is better:
                        next_row_col0 = ""
                        if i + 1 < len(df):
                            next_row = df.iloc[i+1]
                            next_row_col0 = str(next_row[0]).strip() if pd.notna(next_row[0]) else ""

                        if next_row_col0.lower() == expected_headers[0].lower():
                            # This row is actually the SKU definition for the next block!
                            # Do NOT process it as a material.
                            sku_block_valid = False # Temporary suspend until headers process it.
                            continue

                        mat_desc = str(row[1]).strip() if df.shape[1] > 1 and pd.notna(row[1]) else ""
                        qty_raw = str(row[2]).strip() if df.shape[1] > 2 and pd.notna(row[2]) else ""
                        uom = str(row[3]).strip() if df.shape[1] > 3 and pd.notna(row[3]) else ""

                        parsed_rows.append({
                            "sheet_name": sheet_name,
                            "row_number": int(df.index[i]) + 1,
                            "sku_name": current_sku_name,
                            "sku_code": current_sku_code,
                            "material_code": mat_code,
                            "material_desc": mat_desc,
                            "quantity_per_unit": qty_raw,
                            "uom": uom,
                            "block_id": block_id
                        })

            except Exception as exc:
                global_errors.append(f"Error parsing sheet '{sheet_name}': {exc}")

        return parsed_rows, global_errors, empty_sheets
