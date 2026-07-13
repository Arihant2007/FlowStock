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
        """Parse and validate a BOM Excel file without committing any changes.

        Validates:
          - All required columns are present.
          - Each SKU Code references an existing, non-deleted SKU.
          - Each Material Code references an existing, non-deleted Material.
          - Quantity Per Unit is a positive decimal.

        Returns a row-by-row preview with status markers.
        """
        df, global_errors = self._parse_bom_excel(file_bytes, filename)
        if global_errors:
            return BOMUploadPreview(
                total_rows=0,
                valid_rows=0,
                error_rows=0,
                rows=[],
                errors=global_errors,
                skus_affected=[],
            )

        rows: list[BOMUploadRowResult] = []
        error_count = 0
        skus_affected: set[str] = set()

        for idx, row in df.iterrows():
            row_num = int(idx) + 2  # 1-indexed with header on row 1
            sku_code = str(row["SKU Code"]).strip()
            mat_code = str(row["Material Code"]).strip()
            qty_raw = str(row["Quantity Per Unit"]).strip()

            status = "valid"
            message = ""

            # Validate quantity
            try:
                qty = Decimal(qty_raw)
                if qty <= 0:
                    raise ValueError("Must be positive.")
            except (InvalidOperation, ValueError):
                status = "error"
                message = f"Invalid quantity '{qty_raw}': must be a positive number."
                error_count += 1
                rows.append(
                    BOMUploadRowResult(
                        row_number=row_num,
                        sku_code=sku_code,
                        material_code=mat_code,
                        quantity_per_unit=qty_raw,
                        status=status,
                        message=message,
                    )
                )
                continue

            # Validate SKU
            sku = self._sku_repo.get_by_code(sku_code)
            if sku is None:
                status = "error"
                message = f"SKU Code '{sku_code}' not found in master data."
                error_count += 1
                rows.append(
                    BOMUploadRowResult(
                        row_number=row_num,
                        sku_code=sku_code,
                        material_code=mat_code,
                        quantity_per_unit=qty_raw,
                        status=status,
                        message=message,
                    )
                )
                continue

            # Validate Material
            mat = self._material_repo.get_by_code(mat_code)
            if mat is None:
                status = "error"
                message = f"Material Code '{mat_code}' not found in master data."
                error_count += 1
                rows.append(
                    BOMUploadRowResult(
                        row_number=row_num,
                        sku_code=sku_code,
                        material_code=mat_code,
                        quantity_per_unit=qty_raw,
                        status=status,
                        message=message,
                    )
                )
                continue

            skus_affected.add(sku_code)
            rows.append(
                BOMUploadRowResult(
                    row_number=row_num,
                    sku_code=sku_code,
                    material_code=mat_code,
                    quantity_per_unit=qty_raw,
                    status=status,
                    message=message,
                )
            )

        return BOMUploadPreview(
            total_rows=len(rows),
            valid_rows=len(rows) - error_count,
            error_rows=error_count,
            rows=rows,
            errors=[],
            skus_affected=sorted(skus_affected),
        )

    def commit_bom_upload(
        self, file_bytes: bytes, filename: str, *, created_by: int
    ) -> dict[str, int]:
        """Parse, validate, and commit a BOM Excel file.

        For each unique SKU in the file:
          1. Deactivate all existing BOM versions for that SKU.
          2. Create a new active BOMVersion (version_number incremented).
          3. Create one BOMItem per row for this SKU.

        Returns a dict with counts: {"skus_updated": N, "items_created": M}.

        Raises:
            ValidationError: If any rows contain errors (caller must preview first).
        """
        df, global_errors = self._parse_bom_excel(file_bytes, filename)
        if global_errors:
            raise ValidationError(global_errors[0])

        # Group rows by SKU code
        sku_rows: dict[str, list[tuple[str, Decimal]]] = {}
        for _, row in df.iterrows():
            sku_code = str(row["SKU Code"]).strip()
            mat_code = str(row["Material Code"]).strip()
            try:
                qty = Decimal(str(row["Quantity Per Unit"]).strip())
                if qty <= 0:
                    raise ValueError()
            except (InvalidOperation, ValueError) as exc:
                raise ValidationError(
                    f"Invalid quantity for material '{mat_code}' in SKU '{sku_code}'."
                ) from exc

            sku = self._sku_repo.get_by_code(sku_code)
            if sku is None:
                raise ValidationError(f"SKU Code '{sku_code}' not found.")
            mat = self._material_repo.get_by_code(mat_code)
            if mat is None:
                raise ValidationError(f"Material Code '{mat_code}' not found.")

            sku_rows.setdefault(sku_code, []).append((mat_code, qty))

        items_created = 0
        skus_updated = 0
        for sku_code, mat_qty_pairs in sku_rows.items():
            sku = self._sku_repo.get_by_code(sku_code)
            assert sku is not None

            # Deactivate existing BOM versions
            self._bom_repo.deactivate_all_for_sku(sku.id)

            # Create new version
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

            for mat_code, qty in mat_qty_pairs:
                mat = self._material_repo.get_by_code(mat_code)
                assert mat is not None
                self._db.add(
                    BOMItem(
                        bom_version_id=bom.id,
                        material_id=mat.id,
                        quantity_per_unit=qty,
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
    ) -> tuple[pd.DataFrame, list[str]]:
        """Parse Excel bytes into a DataFrame and return (df, global_errors).

        Global errors (returned as second element) indicate file-level problems
        that prevent row-level validation entirely.
        """
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if extension not in {"xlsx", "xls"}:
            return pd.DataFrame(), [
                f"Unsupported file type '.{extension}'. Use .xlsx or .xls."
            ]

        try:
            df = pd.read_excel(BytesIO(file_bytes), dtype=str)
        except Exception as exc:  # noqa: BLE001
            return pd.DataFrame(), [f"Could not read Excel file: {exc}"]

        missing_cols = BOM_REQUIRED_COLUMNS - set(df.columns.str.strip())
        if missing_cols:
            cols = ", ".join(sorted(missing_cols))
            return pd.DataFrame(), [f"Missing required column(s): {cols}"]

        # Normalise column names
        df.columns = df.columns.str.strip()
        df = df.dropna(how="all")

        if df.empty:
            return pd.DataFrame(), ["The uploaded file contains no data rows."]

        return df, []
