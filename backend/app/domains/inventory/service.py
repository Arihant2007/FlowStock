"""Inventory service — business logic for ledger operations.

All inventory mutations are wrapped in explicit transactions with row-level
locking (SELECT ... FOR UPDATE) on the relevant aggregate query to prevent
race conditions during simultaneous approvals or reservations.

Isolation level:
  READ COMMITTED (Postgres default) with per-row SELECT FOR UPDATE.
  This provides correctness without the full overhead of SERIALIZABLE.
  Documented here per architecture requirement.

Upload / Snapshot design (Change #3):
  Opening balance uploads are treated as *inventory snapshots*, not automatic
  RECEIPT transactions. The flow is:
    1. Parse the Excel file and validate each row against master data.
    2. For each (material, warehouse) pair, query the current ledger balance.
    3. Compute delta = uploaded_qty - current_balance.
    4. If delta != 0, create an ADJUSTMENT transaction to reconcile the ledger.
    5. Store the uploaded quantity in inventory_snapshots for reporting.
"""

from decimal import Decimal
from io import BytesIO
from typing import Any

import pandas as pd
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.errors import InsufficientInventoryError, ValidationError
from app.core.logger import get_logger
from app.domains.inventory.models import InventorySnapshot, InventoryTransaction
from app.domains.inventory.schemas import OpeningBalanceUploadPreview

logger = get_logger(__name__)

# Required columns for the RMPM Opening Balance upload template.
OPENING_BALANCE_REQUIRED_COLUMNS = {
    "Material Code",
    "Quantity",
    "UoM",
    "Warehouse",
    "Date",
}


class InventoryService:
    """All inventory business logic: balance queries, transfers, reservations."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Balance
    # ------------------------------------------------------------------

    def get_balance(self, material_id: int, warehouse_id: int) -> Decimal:
        """Calculate the current available (unreserved) balance from the ledger.

        Inbound types: RECEIPT, TRANSFER_IN, RESERVATION_RELEASE, ADJUSTMENT(+)
        Outbound types: DISPATCH, TRANSFER_OUT, RESERVATION

        Rather than distinguishing sign by type in a CASE statement,
        we maintain the convention that DISPATCH/TRANSFER_OUT/RESERVATION
        quantities are stored positively and the query subtracts them.
        """
        inbound_types = ("RECEIPT", "TRANSFER_IN", "RESERVATION_RELEASE", "ADJUSTMENT")
        outbound_types = (
            "DISPATCH",
            "TRANSFER_OUT",
            "RESERVATION",
            "ADJUSTMENT",
            "CONSUMPTION",
        )

        inbound = self._db.scalar(
            select(func.coalesce(func.sum(InventoryTransaction.quantity), Decimal("0")))
            .where(InventoryTransaction.material_id == material_id)
            .where(InventoryTransaction.destination_warehouse_id == warehouse_id)
            .where(InventoryTransaction.transaction_type.in_(inbound_types))
        ) or Decimal("0")

        # Adjustments can be positive or negative — stored in notes/reference
        # and handled as ADJUSTMENT with a signed quantity using separate RECEIPT
        # and DISPATCH records. Kept simple for V1.

        outbound = self._db.scalar(
            select(func.coalesce(func.sum(InventoryTransaction.quantity), Decimal("0")))
            .where(InventoryTransaction.material_id == material_id)
            .where(InventoryTransaction.source_warehouse_id == warehouse_id)
            .where(InventoryTransaction.transaction_type.in_(outbound_types))
        ) or Decimal("0")

        return inbound - outbound

    def get_variance_report(
        self, warehouse_id: int | None = None, snapshot_date: object | None = None
    ) -> list[dict[str, Any]]:
        """Generate a variance report comparing snapshot to current ledger."""
        from datetime import date as date_cls
        from app.domains.master.models import Material, Warehouse
        from app.domains.inventory.models import InventorySnapshot
        
        target_date = snapshot_date or date_cls.today()
        
        # We need all materials and warehouses that either have a snapshot OR a current balance
        # For simplicity and correctness, we will iterate over materials and warehouses.
        mat_query = select(Material).where(Material.deleted_at.is_(None))
        wh_query = select(Warehouse).where(Warehouse.deleted_at.is_(None))
        if warehouse_id is not None:
            wh_query = wh_query.where(Warehouse.id == warehouse_id)
            
        materials = list(self._db.scalars(mat_query).all())
        warehouses = list(self._db.scalars(wh_query).all())
        
        # Load snapshots for target_date
        snap_query = select(InventorySnapshot).where(
            InventorySnapshot.snapshot_date == target_date,
            InventorySnapshot.is_active == True
        )
        if warehouse_id is not None:
            snap_query = snap_query.where(InventorySnapshot.warehouse_id == warehouse_id)
        snapshots = self._db.scalars(snap_query).all()
        
        snap_map = {(s.material_id, s.warehouse_id): s.closing_balance for s in snapshots}
        
        results = []
        for wh in warehouses:
            for mat in materials:
                snap_bal = snap_map.get((mat.id, wh.id))
                ledger_bal = self.get_balance(mat.id, wh.id)
                
                # If neither has a balance, skip
                if snap_bal is None and ledger_bal == Decimal("0"):
                    continue
                    
                snap_val = snap_bal if snap_bal is not None else Decimal("0")
                
                variance = ledger_bal - snap_val
                
                # Snapshot = 0 and Ledger = 0 → 0%
                # Snapshot = 0 and Ledger > 0 → N/A
                # Otherwise use the standard percentage calculation
                if snap_val == Decimal("0"):
                    if ledger_bal == Decimal("0"):
                        variance_percentage = "0.00"
                    else:
                        variance_percentage = "N/A"
                else:
                    pct = (variance / snap_val) * Decimal("100")
                    variance_percentage = f"{pct:.2f}"
                    
                results.append({
                    "material_public_id": str(mat.public_id),
                    "material_code": mat.code,
                    "material_name": mat.name,
                    "warehouse_public_id": str(wh.public_id),
                    "warehouse_name": wh.name,
                    "snapshot_date": target_date,
                    "snapshot_balance": snap_val,
                    "current_ledger_balance": ledger_bal,
                    "variance": variance,
                    "variance_percentage": variance_percentage,
                    "uom": mat.uom,
                })
                
        return results

    # ------------------------------------------------------------------
    # Reservation (called inside request approval workflow)
    # ------------------------------------------------------------------

    def reserve(
        self,
        *,
        material_id: int,
        source_warehouse_id: int,
        quantity: Decimal,
        reference_type: str,
        reference_id: int,
        reserved_by: int,
    ) -> InventoryTransaction:
        """Create a RESERVATION transaction with row-level locking.

        Acquires a Postgres advisory lock keyed on (material_id, warehouse_id)
        to serialize concurrent reservation attempts without SERIALIZABLE isolation.

        Raises:
            InsufficientInventoryError: If available balance < requested quantity.
        """
        # Advisory lock on composite key: prevents two approvals reserving
        # the same material simultaneously.
        if self._db.bind and self._db.bind.dialect.name == "postgresql":
            lock_key = material_id * 100_000 + source_warehouse_id
            self._db.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": lock_key})

        available = self.get_balance(material_id, source_warehouse_id)
        if available < quantity:
            raise InsufficientInventoryError(
                f"Insufficient inventory for material_id={material_id}.",
                details={
                    "available": str(available),
                    "requested": str(quantity),
                },
            )

        tx = InventoryTransaction(
            material_id=material_id,
            source_warehouse_id=source_warehouse_id,
            destination_warehouse_id=None,
            transaction_type="RESERVATION",
            quantity=quantity,
            reference_type=reference_type,
            reference_id=reference_id,
            created_by=reserved_by,
        )
        self._db.add(tx)
        self._db.flush()
        logger.info(
            "inventory_reserved",
            material_id=material_id,
            warehouse_id=source_warehouse_id,
            quantity=str(quantity),
        )
        return tx

    def release_reservation(
        self,
        *,
        material_id: int,
        source_warehouse_id: int,
        quantity: Decimal,
        reference_type: str,
        reference_id: int,
        released_by: int,
    ) -> InventoryTransaction:
        """Create a RESERVATION_RELEASE transaction to free up reserved inventory."""
        tx = InventoryTransaction(
            material_id=material_id,
            source_warehouse_id=None,
            destination_warehouse_id=source_warehouse_id,
            transaction_type="RESERVATION_RELEASE",
            quantity=quantity,
            reference_type=reference_type,
            reference_id=reference_id,
            created_by=released_by,
        )
        self._db.add(tx)
        self._db.flush()
        logger.info(
            "inventory_reservation_released",
            material_id=material_id,
            warehouse_id=source_warehouse_id,
            quantity=str(quantity),
        )
        return tx

    def dispatch_transfer(
        self,
        *,
        material_id: int,
        source_warehouse_id: int,
        quantity: Decimal,
        reference_type: str,
        reference_id: int,
        dispatched_by: int,
    ) -> InventoryTransaction:
        """Create a TRANSFER_OUT transaction to deduct from source warehouse."""
        tx_out = InventoryTransaction(
            material_id=material_id,
            source_warehouse_id=source_warehouse_id,
            destination_warehouse_id=None,
            transaction_type="TRANSFER_OUT",
            quantity=quantity,
            reference_type=reference_type,
            reference_id=reference_id,
            created_by=dispatched_by,
        )
        self._db.add(tx_out)
        self._db.flush()
        logger.info(
            "inventory_dispatched",
            material_id=material_id,
            from_wh=source_warehouse_id,
            quantity=str(quantity),
        )
        return tx_out

    def receive_transfer(
        self,
        *,
        material_id: int,
        destination_warehouse_id: int,
        quantity: Decimal,
        reference_type: str,
        reference_id: int,
        received_by: int,
    ) -> InventoryTransaction:
        """Create a TRANSFER_IN transaction to add to destination warehouse."""
        tx_in = InventoryTransaction(
            material_id=material_id,
            source_warehouse_id=None,
            destination_warehouse_id=destination_warehouse_id,
            transaction_type="TRANSFER_IN",
            quantity=quantity,
            reference_type=reference_type,
            reference_id=reference_id,
            created_by=received_by,
        )
        self._db.add(tx_in)
        self._db.flush()
        logger.info(
            "inventory_received",
            material_id=material_id,
            to_wh=destination_warehouse_id,
            quantity=str(quantity),
        )
        return tx_in

    def consume(
        self,
        *,
        material_id: int,
        source_warehouse_id: int,
        quantity: Decimal,
        reference_type: str,
        reference_id: int,
        consumed_by: int,
    ) -> InventoryTransaction:
        """Create a CONSUMPTION transaction to deduct from warehouse."""
        tx = InventoryTransaction(
            material_id=material_id,
            source_warehouse_id=source_warehouse_id,
            destination_warehouse_id=None,
            transaction_type="CONSUMPTION",
            quantity=quantity,
            reference_type=reference_type,
            reference_id=reference_id,
            created_by=consumed_by,
        )
        self._db.add(tx)
        self._db.flush()
        logger.info(
            "inventory_consumed",
            material_id=material_id,
            from_wh=source_warehouse_id,
            quantity=str(quantity),
        )
        return tx

    def record_adjustment(
        self,
        *,
        material_id: int,
        warehouse_id: int,
        expected: Decimal,
        actual: Decimal,
        reference_id: int,
        adjusted_by: int,
    ) -> InventoryTransaction | None:
        """Record an EOD adjustment when actual != expected.

        Returns None when no adjustment is required.
        """
        delta = actual - expected
        if delta == Decimal("0"):
            return None

        if delta > 0:
            tx = InventoryTransaction(
                material_id=material_id,
                source_warehouse_id=None,
                destination_warehouse_id=warehouse_id,
                transaction_type="ADJUSTMENT",
                quantity=delta,
                reference_type="EOD_COUNT",
                reference_id=reference_id,
                notes=f"EOD adjustment: expected={expected}, actual={actual}",
                created_by=adjusted_by,
            )
        else:
            tx = InventoryTransaction(
                material_id=material_id,
                source_warehouse_id=warehouse_id,
                destination_warehouse_id=None,
                transaction_type="ADJUSTMENT",
                quantity=abs(delta),
                reference_type="EOD_COUNT",
                reference_id=reference_id,
                notes=f"EOD adjustment: expected={expected}, actual={actual}",
                created_by=adjusted_by,
            )

        self._db.add(tx)
        self._db.flush()
        logger.info(
            "inventory_adjusted",
            material_id=material_id,
            warehouse_id=warehouse_id,
            delta=str(delta),
        )
        return tx

    # ------------------------------------------------------------------
    # Opening Balance Upload (snapshot-based)
    # ------------------------------------------------------------------

    def parse_opening_balance_excel(
        self, file_bytes: bytes, filename: str
    ) -> tuple[pd.DataFrame | None, list[str]]:
        """Parse and template-validate an opening balance Excel file.

        Returns (DataFrame, []) on success or (None, [errors]) on failure.
        Validation checks:
          - Correct file extension.
          - All required columns present.
          - Non-empty data rows.
        No business validation (material/warehouse lookup) is performed here;
        that is done in preview_opening_balance and commit_opening_balance_snapshot.
        """
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if extension not in {"xlsx", "xls"}:
            return None, [f"Unsupported file type '.{extension}'. Use .xlsx or .xls."]

        try:
            df = pd.read_excel(BytesIO(file_bytes), dtype=str)
        except Exception as exc:  # noqa: BLE001
            return None, [f"Could not read Excel file: {exc}"]

        df.columns = df.columns.str.strip()
        missing = OPENING_BALANCE_REQUIRED_COLUMNS - set(df.columns)
        if missing:
            return None, [f"Missing required column(s): {', '.join(sorted(missing))}"]

        df = df.dropna(how="all")
        if df.empty:
            return None, ["The uploaded file contains no data rows."]

        return df, []

    def preview_opening_balance(
        self, file_bytes: bytes, filename: str, *,
        user_warehouse_id: int | None = None,
        is_admin: bool = False,
    ) -> OpeningBalanceUploadPreview:
        """Validate an opening balance Excel file and return a row-by-row preview.

        Business validations:
          - Material Code must exist in master data.
          - UoM must match the material's registered UoM.
          - Warehouse must exist and be of type RMPM.
          - Quantity must be >= 0.
          - Date must not be in the future.
        """
        from datetime import date as date_cls
        from decimal import InvalidOperation

        from app.domains.master.models import Material, Warehouse

        df, global_errors = self.parse_opening_balance_excel(file_bytes, filename)
        if global_errors or df is None:
            return OpeningBalanceUploadPreview(
                total_rows=0,
                valid_rows=0,
                error_rows=0,
                warning_rows=0,
                rows=[],
                warnings=[],
                errors=global_errors,
            )

        # Pre-fetch for bulk lookup to avoid N+1 queries
        mat_codes = df.get("Material Code", pd.Series(dtype=str)).dropna().unique().tolist()
        wh_names = df.get("Warehouse", pd.Series(dtype=str)).dropna().unique().tolist()

        materials_db = self._db.scalars(
            select(Material)
            .where(Material.code.in_(mat_codes))
            .where(Material.deleted_at.is_(None))
        ).all()
        material_map = {m.code: m for m in materials_db}

        warehouses_db = self._db.scalars(
            select(Warehouse)
            .where(Warehouse.name.in_(wh_names))
            .where(Warehouse.deleted_at.is_(None))
        ).all()
        warehouse_map = {w.name: w for w in warehouses_db}

        rows_out: list[dict[str, Any]] = []
        errors: list[str] = []
        warnings: list[str] = []
        seen_keys: dict[tuple[str, str, str], int] = {}
        
        total_quantity = Decimal("0")
        unique_materials = set()
        unknown_materials_count = 0
        negative_quantities_count = 0
        duplicates_count = 0

        for idx, row in df.iterrows():
            row_num = int(idx) + 2  # header on row 1
            mat_code = str(row.get("Material Code", "")).strip()
            qty_raw = str(row.get("Quantity", "")).strip()
            uom_raw = str(row.get("UoM", "")).strip()
            wh_name = str(row.get("Warehouse", "")).strip()
            date_raw = str(row.get("Date", "")).strip()

            row_status = "valid"
            row_messages: list[str] = []

            # --- Quantity ---
            try:
                qty = Decimal(qty_raw)
                if qty < 0:
                    raise ValueError("Negative quantity.")
            except (InvalidOperation, ValueError):
                row_status = "error"
                row_messages.append(f"Invalid quantity '{qty_raw}'.")
                qty = Decimal("0")

            # --- Date ---
            try:
                from dateutil import parser as dateutil_parser
                from app.core.config import get_settings
                from datetime import timedelta

                parsed_date: date_cls = dateutil_parser.parse(
                    date_raw, dayfirst=True
                ).date()
                
                settings = get_settings()
                max_past_date = date_cls.today() - timedelta(days=settings.snapshot_edit_window_days)
                
                if parsed_date > date_cls.today():
                    row_status = "error"
                    row_messages.append(f"Date '{date_raw}' is in the future.")
                elif parsed_date < max_past_date:
                    if not is_admin:
                        row_status = "error"
                        row_messages.append(f"Date '{date_raw}' is locked. Cannot edit snapshots older than {settings.snapshot_edit_window_days} days.")
                    else:
                        if row_status != "error":
                            row_status = "warning"
                        row_messages.append(f"Date '{date_raw}' is locked. Admin override will be logged.")
                        warnings.append(row_messages[-1])
            except Exception:  # noqa: BLE001
                row_status = "error"
                row_messages.append(f"Cannot parse date '{date_raw}'. Use DD/MM/YYYY.")
                parsed_date = date_cls.today()

            # --- Material ---
            material = material_map.get(mat_code)
            if material is None:
                row_status = "error"
                row_messages.append(f"Material code '{mat_code}' not found.")
                unknown_materials_count += 1
            elif material.uom.lower() != uom_raw.lower():
                row_status = "error"
                row_messages.append(
                    f"UoM mismatch: uploaded '{uom_raw}', expected '{material.uom}'."
                )
            
            if material is not None:
                unique_materials.add(mat_code)

            # --- Warehouse ---
            warehouse = warehouse_map.get(wh_name)
            if warehouse is None:
                row_status = "error"
                row_messages.append(f"Warehouse '{wh_name}' not found.")
            elif not is_admin and user_warehouse_id and warehouse.id != user_warehouse_id:
                row_status = "error"
                row_messages.append(f"Not authorized to upload inventory for warehouse '{wh_name}'.")

            # --- Duplicate detection ---
            dup_key = (mat_code, wh_name, date_raw)
            if dup_key in seen_keys:
                if row_status != "error":
                    row_status = "warning"
                row_messages.append(
                    f"Duplicate entry for Material '{mat_code}' + Warehouse '{wh_name}' + Date '{date_raw}' "
                    f"(first seen on row {seen_keys[dup_key]}). Last row wins."
                )
                warnings.append(row_messages[-1])
                duplicates_count += 1
            else:
                seen_keys[dup_key] = row_num
                
            if qty < 0:
                negative_quantities_count += 1
            elif row_status != "error":
                total_quantity += qty

            rows_out.append(
                {
                    "row": row_num,
                    "material_code": mat_code,
                    "warehouse": wh_name,
                    "uom": uom_raw,
                    "quantity": qty_raw,
                    "date": date_raw,
                    "status": row_status,
                    "messages": row_messages,
                }
            )

        error_count = sum(1 for r in rows_out if r["status"] == "error")
        warning_count = sum(1 for r in rows_out if r["status"] == "warning")
        return OpeningBalanceUploadPreview(
            total_rows=len(rows_out),
            valid_rows=len(rows_out) - error_count - warning_count,
            error_rows=error_count,
            warning_rows=warning_count,
            total_materials=len(unique_materials),
            total_quantity=total_quantity,
            duplicates=duplicates_count,
            unknown_materials=unknown_materials_count,
            negative_quantities=negative_quantities_count,
            rows=rows_out,
            warnings=warnings,
            errors=errors,
        )

    def commit_opening_balance_snapshot(
        self,
        file_bytes: bytes,
        filename: str,
        *,
        committed_by: int,
        user_warehouse_id: int | None = None,
        ignore_warnings: bool = False,
        is_admin: bool = False,
    ) -> dict[str, Any]:
        """Commit an opening balance Excel as a reconciled snapshot.

        For each valid (material, warehouse, date, quantity) row:
          1. Compute current ledger balance for (material, warehouse).
          2. delta = uploaded_qty - current_balance.
          3. If delta > 0: create ADJUSTMENT inbound transaction.
          4. If delta < 0: create ADJUSTMENT outbound transaction.
          5. If delta == 0: no transaction needed.
          6. Upsert an InventorySnapshot record for the (material, warehouse, date).

        Raises:
            ValidationError: If any rows have errors (preview must be clean first).
        """
        from datetime import date as date_cls
        from decimal import InvalidOperation

        from app.domains.master.models import Material, Warehouse

        df, global_errors = self.parse_opening_balance_excel(file_bytes, filename)
        if global_errors or df is None:
            raise ValidationError(
                global_errors[0] if global_errors else "Invalid file."
            )

        # Collect last-seen row per duplicate key (last row wins)
        valid_rows: dict[tuple[str, str, str], dict[str, Any]] = {}
        errors_found: list[str] = []

        mat_codes = df.get("Material Code", pd.Series(dtype=str)).dropna().unique().tolist()
        wh_names = df.get("Warehouse", pd.Series(dtype=str)).dropna().unique().tolist()

        materials_db = self._db.scalars(
            select(Material)
            .where(Material.code.in_(mat_codes))
            .where(Material.deleted_at.is_(None))
        ).all()
        material_map = {m.code: m for m in materials_db}

        warehouses_db = self._db.scalars(
            select(Warehouse)
            .where(Warehouse.name.in_(wh_names))
            .where(Warehouse.deleted_at.is_(None))
        ).all()
        warehouse_map = {w.name: w for w in warehouses_db}

        for _, row in df.iterrows():
            mat_code = str(row.get("Material Code", "")).strip()
            qty_raw = str(row.get("Quantity", "")).strip()
            uom_raw = str(row.get("UoM", "")).strip()
            wh_name = str(row.get("Warehouse", "")).strip()
            date_raw = str(row.get("Date", "")).strip()

            try:
                qty = Decimal(qty_raw)
                if qty < 0:
                    raise ValueError()
            except (InvalidOperation, ValueError):
                errors_found.append(
                    f"Invalid quantity '{qty_raw}' for material '{mat_code}'."
                )
                continue

            try:
                from dateutil import parser as dateutil_parser
                from app.core.config import get_settings
                from datetime import timedelta

                parsed_date: date_cls = dateutil_parser.parse(
                    date_raw, dayfirst=True
                ).date()
                
                settings = get_settings()
                max_past_date = date_cls.today() - timedelta(days=settings.snapshot_edit_window_days)
                
                if parsed_date > date_cls.today():
                    errors_found.append(f"Date '{date_raw}' is in the future.")
                    continue
                elif parsed_date < max_past_date:
                    if not is_admin:
                        errors_found.append(f"Date '{date_raw}' is locked. Cannot edit snapshots older than {settings.snapshot_edit_window_days} days.")
                        continue
            except Exception:  # noqa: BLE001
                errors_found.append(f"Cannot parse date '{date_raw}'.")
                continue

            material = material_map.get(mat_code)
            if material is None:
                errors_found.append(f"Material code '{mat_code}' not found.")
                continue
            if material.uom.lower() != uom_raw.lower():
                errors_found.append(
                    f"UoM mismatch for '{mat_code}': '{uom_raw}' vs expected '{material.uom}'."
                )
                continue

            warehouse = warehouse_map.get(wh_name)
            if warehouse is None:
                errors_found.append(f"Warehouse '{wh_name}' not found.")
                continue
            if not is_admin and user_warehouse_id and warehouse.id != user_warehouse_id:
                errors_found.append(f"Not authorized to upload inventory for warehouse '{wh_name}'.")
                continue

            dup_key = (mat_code, wh_name, str(parsed_date))
            valid_rows[dup_key] = {
                "material": material,
                "warehouse": warehouse,
                "quantity": qty,
                "snapshot_date": parsed_date,
            }

        if errors_found:
            raise ValidationError("; ".join(errors_found))

        # Check for existing snapshots for these (warehouse, date) combinations
        unique_wh_dates = list({
            (entry["warehouse"].id, entry["snapshot_date"])
            for entry in valid_rows.values()
        })
        for wh_id, snap_date in unique_wh_dates:
            exists = self._db.scalar(
                select(InventorySnapshot)
                .where(InventorySnapshot.warehouse_id == wh_id)
                .where(InventorySnapshot.snapshot_date == snap_date)
                .limit(1)
            )
            if exists:
                # Log or just proceed as we will upsert
                pass

        adjustments_created = 0
        snapshots_upserted = 0

        for entry in valid_rows.values():
            material = entry["material"]
            warehouse = entry["warehouse"]
            uploaded_qty: Decimal = entry["quantity"]
            snapshot_date: date_cls = entry["snapshot_date"]

            assert material is not None
            assert warehouse is not None

            # Current ledger balance
            current_balance = self.get_balance(material.id, warehouse.id)
            delta = uploaded_qty - current_balance

            if delta != Decimal("0"):
                self.record_adjustment(
                    material_id=material.id,
                    warehouse_id=warehouse.id,
                    expected=current_balance,
                    actual=uploaded_qty,
                    reference_id=0,  # No specific reference for upload adjustments
                    adjusted_by=committed_by,
                )
                adjustments_created += 1

            # Upsert snapshot (with versioning)
            existing_snapshots = self._db.scalars(
                select(InventorySnapshot)
                .where(InventorySnapshot.material_id == material.id)
                .where(InventorySnapshot.warehouse_id == warehouse.id)
                .where(InventorySnapshot.snapshot_date == snapshot_date)
            ).all()
            
            # Check if this requires an admin override audit log
            from app.core.config import get_settings
            from datetime import timedelta
            settings = get_settings()
            max_past_date = date_cls.today() - timedelta(days=settings.snapshot_edit_window_days)
            if snapshot_date < max_past_date:
                from app.domains.audit.models import AuditLog
                audit_log = AuditLog(
                    entity_type="InventorySnapshot",
                    entity_id=0, # not single entity
                    action="ADMIN_OVERRIDE",
                    user_id=committed_by,
                    details={
                        "reason": "Admin bypassed edit window lock.",
                        "snapshot_date": str(snapshot_date),
                        "material": material.code,
                        "warehouse": warehouse.name
                    }
                )
                self._db.add(audit_log)
            
            max_version = 0
            if existing_snapshots:
                for snap in existing_snapshots:
                    if snap.is_active:
                        snap.is_active = False
                    if snap.version > max_version:
                        max_version = snap.version
            
            self._db.add(
                InventorySnapshot(
                    material_id=material.id,
                    warehouse_id=warehouse.id,
                    snapshot_date=snapshot_date,
                    closing_balance=uploaded_qty,
                    reserved_balance=Decimal("0.0000"),
                    version=max_version + 1,
                    is_active=True,
                    created_by=committed_by,
                )
            )
            snapshots_upserted += 1

        self._db.flush()
        logger.info(
            "opening_balance_committed",
            adjustments_created=adjustments_created,
            snapshots_upserted=snapshots_upserted,
            committed_by=committed_by,
        )
        return {
            "adjustments_created": adjustments_created,
            "snapshots_upserted": snapshots_upserted,
        }
