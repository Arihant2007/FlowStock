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

import os
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from app.domains.master.models import BOMUploadSession, BOMUploadSessionStatus


import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

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
    MaterialUploadPreview,
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

    def archive_material(self, public_id: str, *, deleted_by: int) -> None:
        mat = self._material_repo.get_by_public_id(uuid.UUID(public_id) if isinstance(public_id, str) else public_id)
        
        # Check active BOMs
        active_boms = self._db.scalars(
            select(BOMItem)
            .join(BOMItem.bom_version)
            .where(BOMItem.material_id == mat.id)
            .where(BOMVersion.is_active.is_(True))
            .where(BOMVersion.deleted_at.is_(None))
        ).all()
        if active_boms:
            raise ValidationError("Cannot archive material. It is actively referenced in one or more active BOMs.")
            
        # Inventory check would go here (assuming Inventory models exist)
        # Request check would go here (assuming MaterialRequestItem models exist)
        # Note: If these models are available, they should be queried. For now, since they might not be fully wired up for inventory or open requests, we focus on BOMs which we know exist.
        
        self._material_repo.soft_delete(mat, deleted_by=deleted_by)
        self._audit.log_action(
            action="MATERIAL_ARCHIVED",
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
    def preview_bom_upload(
        self, file_bytes: bytes | None, filename: str | None, session_id: str | None, *, current_user_id: int
    ) -> BOMUploadPreview:
        """Parse and validate a BOM Excel file via session."""
        import time
        if file_bytes:
            # Create new session
            staging_dir = "uploads/bom_staging"
            os.makedirs(staging_dir, exist_ok=True)
            sess_id = str(uuid.uuid4())
            file_path = os.path.join(staging_dir, f"{sess_id}.xlsx")
            
            # Atomic file write
            tmp_path = file_path + ".tmp"
            with open(tmp_path, "wb") as f:
                f.write(file_bytes)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, file_path)
            
            logger.info("bom_upload_preview_started", session_id=sess_id, user_id=current_user_id, action="new_upload", filename=filename)
            
            file_size = len(file_bytes)
            sha256 = hashlib.sha256(file_bytes).hexdigest()
            
            session = BOMUploadSession(
                public_id=uuid.UUID(sess_id),
                created_by=current_user_id,
                filename=filename or "upload.xlsx",
                file_path=file_path,
                file_size=file_size,
                sha256_hash=sha256,
                status=BOMUploadSessionStatus.UPLOADED,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
            )
            self._db.add(session)
            self._db.flush()
        elif session_id:
            session = self._db.query(BOMUploadSession).filter_by(public_id=uuid.UUID(session_id)).first()
            if not session:
                raise NotFoundError("BOM Upload session not found.")
            if session.created_by != current_user_id:
                raise ValidationError("You do not have permission to access this session.")
            if (session.expires_at.replace(tzinfo=timezone.utc) if session.expires_at.tzinfo is None else session.expires_at) < datetime.now(timezone.utc):
                raise ValidationError("This upload session has expired.")
                
            logger.info("bom_upload_preview_started", session_id=session_id, user_id=current_user_id, action="resume_upload")
                
            with open(session.file_path, "rb") as f:
                file_bytes = f.read()
            filename = session.filename
        else:
            raise ValidationError("Either file_bytes or session_id must be provided.")

        try:
            parsed_rows, global_errors, empty_sheets, warnings = self._parse_bom_excel(file_bytes, filename)
        except Exception as e:
            session.status = BOMUploadSessionStatus.FAILED
            raise



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
        pending_count = 0
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

            status = "valid"
            message = ""

            if (sku_code, mat_code) in seen_sku_materials:
                duplicate_material_codes.add(f"{mat_code} in {sku_code}")
                status = "error"
                message = f"Duplicate material '{mat_code}' in SKU '{sku_code}'."
                error_count += 1
            else:
                seen_sku_materials.add((sku_code, mat_code))

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
                status = "pending_material"
                message = f"Material {mat_code} has not been created yet. Create it using the generated Material Master template, then resume the BOM import."
                pending_count += 1

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

        if unknown_materials:
            session.status = BOMUploadSessionStatus.WAITING_FOR_MATERIALS
        elif error_count == 0 and not global_errors:
            session.status = BOMUploadSessionStatus.READY_TO_COMMIT
        
        session.warnings = warnings
        self._db.flush()

        return BOMUploadPreview(
            total_rows=len(rows),
            valid_rows=len(rows) - error_count - pending_count,
            error_rows=error_count,
            pending_rows=pending_count,
            existing_skus=sorted(existing_skus),
            new_skus=sorted(new_skus),
            existing_materials=sorted(existing_materials),
            unknown_materials=sorted(unknown_materials),
            duplicate_material_codes=sorted(duplicate_material_codes),
            duplicate_sku_codes=sorted(duplicate_sku_codes),
            empty_sheets=empty_sheets,
            rows=rows,
            errors=global_errors,
            warnings=warnings,
            skus_affected=sorted(skus_affected),
            session_id=str(session.public_id),
            session_status=session.status.value,
        )

    def commit_bom_upload(
        self, session_id: str, *, current_user_id: int
    ) -> dict[str, int]:
        """Parse, validate, and commit a BOM Excel file from session."""
        session = self._db.query(BOMUploadSession).filter_by(public_id=uuid.UUID(session_id)).first()
        if not session:
            raise NotFoundError("BOM Upload session not found.")
        if session.created_by != current_user_id:
            raise ValidationError("You do not have permission to access this session.")
        if (session.expires_at.replace(tzinfo=timezone.utc) if session.expires_at.tzinfo is None else session.expires_at) < datetime.now(timezone.utc):
            raise ValidationError("This upload session has expired.")
        if session.status == BOMUploadSessionStatus.COMMITTED:
            raise ValidationError("This BOM import has already been completed.")
        if session.status != BOMUploadSessionStatus.READY_TO_COMMIT:
            raise ValidationError("Session is not ready to commit. Please resolve preview errors.")
            
        with open(session.file_path, "rb") as f:
            file_bytes = f.read()
        filename = session.filename
        created_by = current_user_id
        
        import time
        start_time = time.time()
        
        try:
            parsed_rows, global_errors, empty_sheets, _ = self._parse_bom_excel(file_bytes, filename)
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
            skus_created = 0
            items_created = 0
            bom_versions_created = 0

            # Create missing SKUs
            for sku_code in sku_codes:
                if sku_code not in sku_map:
                    # Find SKU Name
                    sku_name = next((r["sku_name"] for r in parsed_rows if r["sku_code"] == sku_code), sku_code)
                    new_sku = SKU(code=sku_code, name=sku_name, created_by=created_by)
                    self._db.add(new_sku)
                    self._db.flush()
                    sku_map[sku_code] = new_sku
                    skus_created += 1
                else:
                    skus_updated += 1

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
                bom_versions_created += 1

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

                self._audit.log_action(
                    action="BOM_VERSION_CREATED",
                    user_id=created_by,
                    resource_type="BOMVersion",
                    resource_id=bom.id,
                    details={"sku_code": sku_code, "version_number": next_ver},
                )

        except Exception as e:
            self._db.rollback()
            # Reload session to mark as FAILED
            failed_session = self._db.query(BOMUploadSession).filter_by(public_id=uuid.UUID(session_id)).first()
            if failed_session:
                failed_session.status = BOMUploadSessionStatus.FAILED
                self._db.flush()
                self._db.commit()
            logger.error("bom_upload_commit_failed", session_id=session_id, user_id=current_user_id, error=str(e))
            raise

        # If everything succeeded
        duration = time.time() - start_time
        materials_referenced = len(mat_codes)
        warnings = session.warnings or []
        
        logger.info(
            "bom_upload_committed",
            session_id=session_id,
            user_id=current_user_id,
            skus_created=skus_created,
            skus_updated=skus_updated,
            bom_versions_created=bom_versions_created,
            items_created=items_created,
            materials_referenced=materials_referenced,
            warnings_count=len(warnings),
            duration_seconds=round(duration, 2)
        )
        
        session.status = BOMUploadSessionStatus.COMMITTED
        
        result_payload = {
            "skus_created": skus_created,
            "skus_updated": skus_updated,
            "bom_versions_created": bom_versions_created,
            "items_created": items_created,
            "materials_referenced": materials_referenced,
            "warnings": warnings,
            "duration_seconds": round(duration, 2)
        }
        
        session.import_results = result_payload
        self._db.flush()
        # We allow the router's dependency to call the final db.commit()
        
        return result_payload

    def cancel_bom_upload(self, session_id: str, current_user_id: int) -> None:
        session = self._db.query(BOMUploadSession).filter_by(public_id=uuid.UUID(session_id)).first()
        if not session:
            return
        if session.created_by != current_user_id:
            raise ValidationError("Permission denied.")
        session.status = BOMUploadSessionStatus.CANCELLED
        logger.info("bom_upload_cancelled", session_id=session_id, user_id=current_user_id)
        # We optionally delete the file
        try:
            if os.path.exists(session.file_path):
                os.remove(session.file_path)
        except Exception:
            pass
        self._db.flush()

    def cleanup_expired_sessions(self) -> None:
        expired = self._db.query(BOMUploadSession).filter(
            BOMUploadSession.expires_at < datetime.now(timezone.utc),
            BOMUploadSession.status != BOMUploadSessionStatus.EXPIRED,
            BOMUploadSession.status != BOMUploadSessionStatus.COMMITTED
        ).all()
        for session in expired:
            session.status = BOMUploadSessionStatus.EXPIRED
            logger.info("bom_upload_session_expired", session_id=str(session.public_id))
            try:
                if os.path.exists(session.file_path):
                    os.remove(session.file_path)
            except Exception as e:
                logger.warning("failed_to_delete_expired_session_file", session_id=str(session.public_id), error=str(e))
        self._db.commit()

    def list_bom_sessions(self, limit: int = 50) -> list[BOMUploadSession]:
        return self._db.query(BOMUploadSession).order_by(BOMUploadSession.created_at.desc()).limit(limit).all()

    def get_dashboard_stats(self) -> dict:
        from sqlalchemy import func
        from .models import Material, SKU, BOMVersion, BOMItem
        
        total_materials = self._db.query(func.count(Material.id)).filter(Material.deleted_at.is_(None)).scalar() or 0
        total_skus = self._db.query(func.count(SKU.id)).filter(SKU.deleted_at.is_(None)).scalar() or 0
        total_bom_versions = self._db.query(func.count(BOMVersion.id)).filter(BOMVersion.deleted_at.is_(None)).scalar() or 0
        total_bom_items = self._db.query(func.count(BOMItem.id)).filter(BOMItem.deleted_at.is_(None)).scalar() or 0
        
        from app.domains.inventory.models import InventorySnapshot
        from app.domains.auth.models import User
        
        last_import = self._db.query(BOMUploadSession.created_at).filter(
            BOMUploadSession.status == BOMUploadSessionStatus.COMMITTED
        ).order_by(BOMUploadSession.created_at.desc()).first()
        
        # Get latest inventory snapshot
        latest_snapshot = self._db.query(InventorySnapshot).filter(
            InventorySnapshot.is_active == True
        ).order_by(InventorySnapshot.created_at.desc()).first()
        inventory_upload_stats = None
        if latest_snapshot:
            # We want to know the snapshot date, the upload time (created_at), the user, and the total materials uploaded for that date
            uploader = self._db.query(User).filter(User.id == latest_snapshot.created_by).first()
            
            from app.domains.master.models import Warehouse
            warehouse = self._db.query(Warehouse).filter(Warehouse.id == latest_snapshot.warehouse_id).first()
            
            total_mats_for_date = self._db.query(func.count(InventorySnapshot.id)).filter(
                InventorySnapshot.snapshot_date == latest_snapshot.snapshot_date,
                InventorySnapshot.is_active == True
            ).scalar() or 0
            
            # Calculate inventory health (variance counts)
            from app.domains.inventory.service import InventoryService
            inventory_svc = InventoryService(self._db)
            variances = inventory_svc.get_variance_report(target_date=latest_snapshot.snapshot_date)
            
            matched_count = 0
            variance_count = 0
            
            for v in variances:
                if v["variance"] == 0:
                    matched_count += 1
                else:
                    variance_count += 1
            
            inventory_upload_stats = {
                "snapshot_date": latest_snapshot.snapshot_date,
                "upload_time": latest_snapshot.created_at,
                "uploaded_by": uploader.full_name if uploader else "Unknown",
                "warehouse_name": warehouse.name if warehouse else "Unknown",
                "version": latest_snapshot.version,
                "total_materials": total_mats_for_date,
                "matched_count": matched_count,
                "variance_count": variance_count
            }
        
        return {
            "total_materials": total_materials,
            "total_skus": total_skus,
            "total_bom_versions": total_bom_versions,
            "total_bom_items": total_bom_items,
            "last_import_at": last_import[0] if last_import else None,
            "inventory_upload": inventory_upload_stats
        }

    def extract_materials_from_bom(
        self, file_bytes: bytes | None, filename: str | None, *, session_id: str | None = None, only_unknown: bool = True
    ) -> bytes:
        """Parse BOM Excel and generate a Material Master template for extracted materials."""
        if not file_bytes and session_id:
            session = self._db.query(BOMUploadSession).filter_by(public_id=uuid.UUID(session_id)).first()
            if not session:
                raise NotFoundError("BOM Upload session not found.")
            with open(session.file_path, "rb") as f:
                file_bytes = f.read()
            filename = session.filename

        if not file_bytes:
            raise ValidationError("Either file_bytes or session_id must be provided.")

        parsed_rows, global_errors, _, _ = self._parse_bom_excel(file_bytes, filename)
        if global_errors:
            raise ValidationError(global_errors[0])

        unique_materials = {}
        for r in parsed_rows:
            code = r["material_code"]
            desc = r["material_desc"]
            uom = r["uom"]

            if code not in unique_materials:
                unique_materials[code] = {
                    "Material Code": code,
                    "Material Name": desc,
                    "UOM": uom,
                    "Category": "",
                    "Material Type": "",
                    "Group": "",
                }
            else:
                # Consistency check
                existing = unique_materials[code]
                if existing["Material Name"] != desc or existing["UOM"] != uom:
                    logger.warning(
                        "inconsistent_material_in_bom",
                        code=code,
                        first_desc=existing["Material Name"],
                        first_uom=existing["UOM"],
                        new_desc=desc,
                        new_uom=uom,
                    )

        parsed_materials_count = len(unique_materials)

        # Retrieve existing materials from DB with relationships
        existing_materials = self._db.scalars(
            select(Material)
            .options(
                joinedload(Material.category),
                joinedload(Material.material_type),
                joinedload(Material.group)
            )
            .where(Material.code.in_(unique_materials.keys()))
            .where(Material.deleted_at.is_(None))
        ).all()
        
        existing_map = {m.code: m for m in existing_materials}
        existing_materials_count = len(existing_map)
        
        if only_unknown:
            unique_materials = {
                k: v for k, v in unique_materials.items() if k not in existing_map
            }

        missing_materials_count = len(unique_materials)

        logger.info(
            "bom_extraction_summary",
            parsed_materials=parsed_materials_count,
            existing_materials=existing_materials_count,
            missing_materials=missing_materials_count,
            written_to_excel=missing_materials_count
        )

        # Load configurable rules
        import json
        import os
        rules_path = os.path.join(os.path.dirname(__file__), "..", "..", "core", "classification_rules.json")
        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                rules = json.load(f)
        except Exception as e:
            logger.error("failed_to_load_classification_rules", error=str(e))
            rules = {"prefix_rules": [], "keyword_rules": [], "defaults": {"category": "Others", "type": "RM", "group": "Others"}}

        defaults = rules.get("defaults", {"category": "Others", "type": "RM", "group": "Others"})

        # Apply hierarchical classification
        for code, mat_dict in unique_materials.items():
            if code in existing_map:
                m = existing_map[code]
                mat_dict["Category"] = m.category.name if m.category else ""
                mat_dict["Material Type"] = m.material_type.name if m.material_type else ""
                mat_dict["Group"] = m.group.name if m.group else ""
            else:
                desc_lower = mat_dict["Material Name"].lower()
                code_lower = code.lower()
                
                # Apply Prefix Rules
                cat, mtype = None, None
                for pr in rules.get("prefix_rules", []):
                    if code_lower.startswith(pr.get("prefix", "").lower()):
                        cat = pr.get("category")
                        mtype = pr.get("type")
                        break
                
                if cat is None:
                    cat = defaults.get("category", "Others")
                    mtype = defaults.get("type", "RM")
                
                # Apply Keyword Rules
                grp = None
                for kr in rules.get("keyword_rules", []):
                    for kw in kr.get("keywords", []):
                        if kw.lower() in desc_lower:
                            grp = kr.get("group")
                            break
                    if grp:
                        break
                
                if grp is None:
                    grp = defaults.get("group", "Others")
                
                mat_dict["Category"] = cat
                mat_dict["Material Type"] = mtype
                mat_dict["Group"] = grp

        df = pd.DataFrame(
            list(unique_materials.values()),
            columns=[
                "Material Code",
                "Material Name",
                "UOM",
                "Category",
                "Material Type",
                "Group",
            ],
        )
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Material Master")
        
        return output.getvalue()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_bom_excel(
        self, file_bytes: bytes, filename: str
    ) -> tuple[list[dict[str, Any]], list[str], list[str], list[str]]:
        """Parse Excel bytes into a list of dictionaries.

        Returns:
            parsed_rows: list of dictionaries representing validly parsed data rows.
            global_errors: list of file-level validation errors.
            empty_sheets: list of sheet names that were skipped because they were empty.
        """
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if extension not in {"xlsx", "xls"}:
            return [], [f"Unsupported file type '.{extension}'. Use .xlsx or .xls."], [], []

        try:
            # Read all sheets, without headers
            sheets_dict = pd.read_excel(BytesIO(file_bytes), sheet_name=None, header=None, dtype=str)
        except Exception as exc:  # noqa: BLE001
            return [], [f"Could not read Excel file: {exc}"], [], []

        parsed_rows = []
        global_errors = []
        empty_sheets = []
        warnings = []

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
                    col1 = str(row[1]).strip() if df.shape[1] > 1 and pd.notna(row[1]) else ""
                    col2 = str(row[2]).strip() if df.shape[1] > 2 and pd.notna(row[2]) else ""
                    col3 = str(row[3]).strip() if df.shape[1] > 3 and pd.notna(row[3]) else ""

                    if not col0 or col0.lower() == "nan":
                        continue

                    # Detect Headers
                    if col0.lower() == expected_headers[0].lower():
                        actual_headers = [col0, col1, col2, col3]
                        if not all(a.lower() == e.lower() for a, e in zip(actual_headers, expected_headers, strict=False) if e):
                            global_errors.append(f"Sheet '{sheet_name}', Row {df.index[i] + 1} has invalid headers. Expected: {expected_headers}")
                            sku_block_valid = False
                        continue

                    # Detect SKU Block Definition
                    # A row is a SKU definition if it has no quantity (col2 is empty)
                    if not col2 or col2.lower() == "nan":
                        potential_sku_name = col0
                        potential_sku_code = col1

                        if not potential_sku_code or potential_sku_code.lower() == "nan":
                            msg = f"Sheet '{sheet_name}', Row {df.index[i] + 1}: Missing FG Code for SKU '{potential_sku_name}'. Using FG Name as SKU Code."
                            logger.warning(msg)
                            warnings.append(msg)
                            potential_sku_code = potential_sku_name

                        current_sku_name = potential_sku_name
                        current_sku_code = potential_sku_code
                        block_id += 1
                        sku_block_valid = True
                        continue

                    # Parse Material Row
                    if sku_block_valid:
                        parsed_rows.append({
                            "sheet_name": sheet_name,
                            "row_number": int(df.index[i]) + 1,
                            "sku_name": current_sku_name,
                            "sku_code": current_sku_code,
                            "material_code": col0,
                            "material_desc": col1,
                            "quantity_per_unit": col2,
                            "uom": col3,
                            "block_id": block_id
                        })

            except Exception as exc:
                global_errors.append(f"Error parsing sheet '{sheet_name}': {exc}")

        return parsed_rows, global_errors, empty_sheets, warnings

    # ------------------------------------------------------------------
    # Material Master Excel Upload
    # ------------------------------------------------------------------

    def preview_material_upload(self, file_bytes: bytes, filename: str) -> MaterialUploadPreview:
        from app.domains.master.schemas import MaterialUploadPreview, MaterialUploadRowResult

        parsed_rows, global_errors, empty_sheets, warnings = self._parse_material_excel(file_bytes, filename)

        if global_errors:
            return MaterialUploadPreview(
                total_rows=0, valid_rows=0, error_rows=0, skipped_rows_count=0,
                new_materials=[], updated_materials=[], duplicate_material_codes=[], invalid_rows=[], skipped_rows=[],
                rows=[], errors=global_errors, warnings=warnings
            )

        # Load existing references
        existing_mats = {m.code: m for m in self._db.scalars(select(Material).where(Material.deleted_at.is_(None))).all()}
        from app.domains.master.models import MaterialCategory, MaterialType, MaterialGroup
        existing_cats = {c.name.lower(): c for c in self._db.scalars(select(MaterialCategory)).all()}
        existing_types = {t.name.lower(): t for c in self._db.scalars(select(MaterialType)).all() for t in [c]}
        existing_groups = {g.name.lower(): g for c in self._db.scalars(select(MaterialGroup)).all() for g in [c]}

        rows: list[MaterialUploadRowResult] = []
        error_count = 0
        skipped_count = 0
        
        new_materials = set()
        updated_materials = set()
        duplicate_codes_in_file = set()
        invalid_rows = set()
        skipped_rows = set()
        
        seen_codes = set()

        for r in parsed_rows:
            code = r["material_code"]
            status = "valid"
            message = ""

            if code in seen_codes:
                status = "duplicate"
                message = f"Duplicate material code '{code}' in upload file."
                duplicate_codes_in_file.add(code)
                error_count += 1
            else:
                seen_codes.add(code)

            if status != "duplicate":
                # Validate foreign keys
                if not r["category"]:
                    status = "error"
                    message = "Category is required."
                elif r["category"].lower() not in existing_cats:
                    status = "error"
                    message = f"Category '{r['category']}' does not exist."
                elif not r["material_type"]:
                    status = "error"
                    message = "Material Type is required."
                elif r["material_type"].lower() not in existing_types:
                    status = "error"
                    message = f"Material Type '{r['material_type']}' does not exist."
                elif not r["group"]:
                    status = "error"
                    message = "Group is required."
                elif r["group"].lower() not in existing_groups:
                    status = "error"
                    message = f"Material Group '{r['group']}' does not exist."

                if status == "error":
                    invalid_rows.add(code)
                    error_count += 1
                else:
                    if code in existing_mats:
                        mat = existing_mats[code]
                        # Check if anything changed
                        cat_id = existing_cats[r["category"].lower()].id
                        type_id = existing_types[r["material_type"].lower()].id
                        group_id = existing_groups[r["group"].lower()].id if r["group"] else None

                        if mat.name == r["material_name"] and mat.uom == r["uom"] and mat.category_id == cat_id and mat.type_id == type_id and mat.group_id == group_id:
                            status = "skipped"
                            message = "No changes detected."
                            skipped_rows.add(code)
                            skipped_count += 1
                        else:
                            updated_materials.add(code)
                    else:
                        new_materials.add(code)

            rows.append(
                MaterialUploadRowResult(
                    row_number=r["row_number"],
                    material_code=code,
                    material_name=r["material_name"],
                    uom=r["uom"],
                    category=r["category"],
                    material_type=r["material_type"],
                    group=r["group"],
                    status=status,
                    message=message,
                )
            )

        return MaterialUploadPreview(
            total_rows=len(rows),
            valid_rows=len(rows) - error_count - skipped_count,
            error_rows=error_count,
            skipped_rows_count=skipped_count,
            new_materials=sorted(new_materials),
            updated_materials=sorted(updated_materials),
            duplicate_material_codes=sorted(duplicate_codes_in_file),
            invalid_rows=sorted(invalid_rows),
            skipped_rows=sorted(skipped_rows),
            rows=rows,
            errors=global_errors,
            warnings=warnings,
        )

    def commit_material_upload(self, file_bytes: bytes, filename: str, *, created_by: int) -> dict[str, int]:
        """Parse, validate, and commit a Material Master Excel file."""
        parsed_rows, global_errors, _, _ = self._parse_material_excel(file_bytes, filename)
        if global_errors:
            raise ValidationError(global_errors[0])

        existing_mats = {m.code: m for m in self._db.scalars(select(Material).where(Material.deleted_at.is_(None))).all()}
        from app.domains.master.models import MaterialCategory, MaterialType, MaterialGroup
        existing_cats = {c.name.lower(): c for c in self._db.scalars(select(MaterialCategory)).all()}
        existing_types = {t.name.lower(): t for c in self._db.scalars(select(MaterialType)).all() for t in [c]}
        existing_groups = {g.name.lower(): g for c in self._db.scalars(select(MaterialGroup)).all() for g in [c]}

        created = 0
        updated = 0
        skipped = 0

        # Run within nested transaction implicitly done by caller or here
        # Validation
        seen_codes = set()
        for r in parsed_rows:
            code = r["material_code"]
            if code in seen_codes:
                raise ValidationError(f"Duplicate material code '{code}' in upload file.")
            seen_codes.add(code)

            if not r["category"]:
                raise ValidationError(f"Category is required (Row {r['row_number']}).")
            if r["category"].lower() not in existing_cats:
                raise ValidationError(f"Category '{r['category']}' does not exist (Row {r['row_number']}).")
            
            if not r["material_type"]:
                raise ValidationError(f"Material Type is required (Row {r['row_number']}).")
            if r["material_type"].lower() not in existing_types:
                raise ValidationError(f"Material Type '{r['material_type']}' does not exist (Row {r['row_number']}).")
            
            if not r["group"]:
                raise ValidationError(f"Group is required (Row {r['row_number']}).")
            if r["group"].lower() not in existing_groups:
                raise ValidationError(f"Material Group '{r['group']}' does not exist (Row {r['row_number']}).")

        # Upsert
        for r in parsed_rows:
            code = r["material_code"]
            cat_id = existing_cats[r["category"].lower()].id
            type_id = existing_types[r["material_type"].lower()].id
            group_id = existing_groups[r["group"].lower()].id if r["group"] else None

            if code in existing_mats:
                mat = existing_mats[code]
                if mat.name != r["material_name"] or mat.uom != r["uom"] or mat.category_id != cat_id or mat.type_id != type_id or mat.group_id != group_id:
                    mat.name = r["material_name"]
                    mat.uom = r["uom"]
                    mat.category_id = cat_id
                    mat.type_id = type_id
                    mat.group_id = group_id
                    
                    self._audit.log_action(
                        action="MATERIAL_UPDATED",
                        user_id=created_by,
                        resource_type="Material",
                        resource_id=mat.id,
                        details={"source": "excel_upload", "updates": r},
                    )
                    updated += 1
                else:
                    skipped += 1
            else:
                mat = Material(
                    code=code,
                    name=r["material_name"],
                    uom=r["uom"],
                    category_id=cat_id,
                    type_id=type_id,
                    group_id=group_id,
                    created_by=created_by,
                )
                self._db.add(mat)
                self._db.flush()
                self._audit.log_action(
                    action="MATERIAL_CREATED",
                    user_id=created_by,
                    resource_type="Material",
                    resource_id=mat.id,
                    details={"source": "excel_upload", "code": code},
                )
                created += 1

        logger.info("material_upload_committed", created=created, updated=updated, skipped=skipped, created_by=created_by)
        return {"created": created, "updated": updated, "skipped": skipped}

    def _parse_material_excel(self, file_bytes: bytes, filename: str) -> tuple[list[dict[str, Any]], list[str], list[str], list[str]]:
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if extension not in {"xlsx", "xls"}:
            return [], [f"Unsupported file type '.{extension}'. Use .xlsx or .xls."], [], []

        try:
            sheets_dict = pd.read_excel(BytesIO(file_bytes), sheet_name=None, dtype=str)
        except Exception as exc:
            return [], [f"Could not read Excel file: {exc}"], [], []

        parsed_rows = []
        global_errors = []
        empty_sheets = []
        warnings = []

        expected_headers = ["Material Code", "Material Name", "UOM", "Category", "Material Type", "Group"]

        for sheet_name, df in sheets_dict.items():
            df = df.dropna(how="all")
            if df.empty:
                empty_sheets.append(sheet_name)
                continue

            actual_headers = list(df.columns)
            if not all(h in actual_headers for h in expected_headers[:5]): # Group is optional if missing column
                global_errors.append(f"Sheet '{sheet_name}' has invalid headers. Expected: {expected_headers}")
                continue

            for i in range(len(df)):
                row = df.iloc[i]
                col_code = str(row.get("Material Code", "")).strip()
                if not col_code or col_code.lower() == "nan":
                    continue
                
                def normalize(val: Any) -> str | None:
                    if pd.isna(val) or val is None:
                        return None
                    v = str(val).strip()
                    if not v or v.lower() == "nan":
                        return None
                    return v

                parsed_rows.append({
                    "row_number": int(df.index[i]) + 2, # +2 for header and 0-index
                    "material_code": col_code,
                    "material_name": normalize(row.get("Material Name", "")),
                    "uom": normalize(row.get("UOM", "")),
                    "category": normalize(row.get("Category", "")),
                    "material_type": normalize(row.get("Material Type", "")),
                    "group": normalize(row.get("Group", "")) if "Group" in row else None
                })

        return parsed_rows, global_errors, empty_sheets, warnings
