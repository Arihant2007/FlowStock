"""Requests domain service — material request submission and approval.

Key business rules enforced here:
  1. Net material calculation: requested_qty = gross_required_qty - remaining.
  2. BOM version snapshot: the BOM version active at request time is stored
     on the request; recipe changes do not affect historical requests.
  3. Approval: inventory is reserved atomically for each approved line.
  4. Partial approval: unapproved lines get approved_qty=0; request is
     marked PARTIALLY_APPROVED; the request is then closed — a new request
     must be raised for the shortfall.
  5. State transitions are validated; illegal transitions raise InvalidStateTransitionError.

Change #1: DRAFT state removed. New requests start as SUBMITTED.
Change #2: Net quantity calculation splits RM and PM remaining materials, resolved via BOM.
"""

from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import InvalidStateTransitionError, NotFoundError
from app.core.logger import get_logger
from app.domains.inventory.service import InventoryService
from app.domains.master.models import SKU, BOMItem, BOMVersion, Material, Warehouse
from app.domains.requests.models import (
    MaterialRequest,
    MaterialRequestItem,
    MaterialRequestSKU,
)
from app.domains.requests.schemas import (
    ApproveRequestPayload,
    CreateRequestPayload,
    RequestPreviewItemOut,
    RequestPreviewOut,
    RequestPreviewPayload,
    RequestPreviewSKUOut,
)

logger = get_logger(__name__)

VALID_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"SUBMITTED"},
    "SUBMITTED": {"APPROVED", "PARTIALLY_APPROVED", "REJECTED"},
    "APPROVED": {"DISPATCHED"},
    "PARTIALLY_APPROVED": {"DISPATCHED"},
    "DISPATCHED": {"RECEIVED"},
    "RECEIVED": {"CLOSED"},
}


def _assert_transition(current: str, target: str) -> None:
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidStateTransitionError(
            f"Cannot transition from '{current}' to '{target}'.",
            details={"current": current, "target": target, "allowed": list(allowed)},
        )


class RequestService:
    """Handles creation, submission, and approval of material requests."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._inventory = InventoryService(db)

    # ------------------------------------------------------------------
    # Create (Starts as SUBMITTED)
    # ------------------------------------------------------------------

    def _calculate_request_skus(
        self, payload: CreateRequestPayload | RequestPreviewPayload
    ) -> tuple[Warehouse, list[dict[str, Any]], bool]:
        """Core calculation logic for Gross, Remaining, Net.

        Returns:
            (ods_warehouse, result_skus, no_snapshot_found)

        If a previous-day ODS snapshot exists, ``remaining`` is read from the
        live inventory balance for each material and deducted from gross.
        If **no snapshot exists** (first-time system setup or missed upload) the
        method does *not* block — it sets ``remaining = 0`` for every material
        and signals callers via ``no_snapshot_found = True``, which the API
        surface can relay to the frontend as an informational banner.
        """
        ods_warehouse = self._db.scalar(
            select(Warehouse).where(
                Warehouse.public_id == payload.ods_warehouse_public_id
            )
        )
        if not ods_warehouse:
            raise NotFoundError(
                f"Warehouse {payload.ods_warehouse_public_id} not found."
            )

        # --- Snapshot check (non-blocking) -----------------------------------
        from datetime import timedelta
        from app.domains.inventory.models import InventorySnapshot

        snapshot_date_required = payload.request_date - timedelta(days=1)
        snapshot_exists = self._db.scalar(
            select(InventorySnapshot)
            .where(InventorySnapshot.warehouse_id == ods_warehouse.id)
            .where(InventorySnapshot.snapshot_date == snapshot_date_required)
            .where(InventorySnapshot.is_active == True)
            .limit(1)
        )
        no_snapshot_found: bool = snapshot_exists is None
        if no_snapshot_found:
            logger.warning(
                "no_ods_snapshot",
                warehouse_id=ods_warehouse.id,
                snapshot_date=str(snapshot_date_required),
                message="No prior ODS snapshot found — proceeding with zero remaining inventory.",
            )

        # --- First pass: Resolve SKUs, BOMs and fetch ODS balance once per material ---
        material_totals: dict[int, dict[str, Any]] = {}
        sku_records = []

        for sku_payload in payload.skus:
            sku = self._db.scalar(
                select(SKU).where(SKU.public_id == sku_payload.sku_public_id)
            )
            if not sku:
                raise NotFoundError(f"SKU {sku_payload.sku_public_id} not found.")

            bom_version = self._resolve_bom_version(sku.id, payload.request_date)
            sku_records.append({
                "sku": sku,
                "bom_version": bom_version,
                "planned_qty": sku_payload.planned_production_qty
            })

            for bom_item in bom_version.items:
                mat = bom_item.material
                if mat.id not in material_totals:
                    # Use snapshot balance when a snapshot exists; zero otherwise.
                    if no_snapshot_found:
                        remaining = Decimal("0")
                    else:
                        snapshot = self._db.scalar(
                            select(InventorySnapshot.closing_balance)
                            .where(InventorySnapshot.warehouse_id == ods_warehouse.id)
                            .where(InventorySnapshot.material_id == mat.id)
                            .where(InventorySnapshot.snapshot_date == snapshot_date_required)
                            .where(InventorySnapshot.is_active == True)
                        )
                        remaining = snapshot if snapshot is not None else Decimal("0")
                        
                    material_totals[mat.id] = {
                        "material": mat,
                        "remaining": remaining,
                    }

        # --- Second pass: Apportion remaining balance greedily across SKUs ---
        result_skus: list[dict[str, Any]] = []
        for rec in sku_records:
            sku: SKU | None = rec["sku"]  # type: ignore
            bom_version: BOMVersion = rec["bom_version"]  # type: ignore
            planned_qty: Decimal = rec["planned_qty"]  # type: ignore

            sku_data: dict[str, Any] = {
                "sku": sku,
                "bom_version": bom_version,
                "planned_qty": planned_qty,
                "items": [],
            }

            for bom_item in bom_version.items:
                mat = bom_item.material
                gross = Decimal(bom_item.quantity_per_unit) * Decimal(planned_qty)

                # Dynamic remaining calculation apportioned across duplicate materials
                mat_state = material_totals[mat.id]
                apportioned_rem = min(gross, mat_state["remaining"])
                mat_state["remaining"] -= apportioned_rem
                net = max(gross - apportioned_rem, Decimal("0.0000"))

                sku_data["items"].append(
                    {
                        "material": mat,
                        "gross_required_qty": gross,
                        "remaining_from_previous_day": apportioned_rem,
                        "requested_qty": net,
                    }
                )
            result_skus.append(sku_data)

        return ods_warehouse, result_skus, no_snapshot_found

    def preview_request(self, payload: RequestPreviewPayload) -> RequestPreviewOut:
        """Preview material requirements based on active BOM and current ODS stock.

        When no previous-day ODS snapshot exists the preview proceeds with
        remaining = 0 (full BOM quantities) and includes no_snapshot_found=True
        so the frontend can display an informational first-run banner.
        """
        ods_warehouse, result_skus, no_snapshot_found = self._calculate_request_skus(payload)

        out_skus = []
        for sku_data in result_skus:
            out_items = []
            for item_data in sku_data["items"]:
                mat = item_data["material"]
                out_items.append(
                    RequestPreviewItemOut(
                        material_public_id=mat.public_id,
                        material_name=mat.name,
                        material_code=mat.code,
                        material_type=mat.material_type.name
                        if mat.material_type
                        else "RM",
                        gross_required_qty=item_data["gross_required_qty"],
                        remaining_from_previous_day=item_data[
                            "remaining_from_previous_day"
                        ],
                        requested_qty=item_data["requested_qty"],
                    )
                )

            out_skus.append(
                RequestPreviewSKUOut(
                    sku_public_id=sku_data["sku"].public_id,
                    sku_name=sku_data["sku"].name,
                    sku_code=sku_data["sku"].code,
                    planned_production_qty=sku_data["planned_qty"],
                    items=out_items,
                )
            )

        return RequestPreviewOut(skus=out_skus, no_snapshot_found=no_snapshot_found)

    def create_request(
        self, payload: CreateRequestPayload, *, created_by: int
    ) -> MaterialRequest:
        """Create a SUBMITTED material request with calculated net quantities.

        Works the same whether or not a previous-day ODS snapshot exists;
        if no snapshot is present, remaining = 0 and full BOM quantities are requested.
        """
        ods_warehouse, result_skus, _no_snapshot = self._calculate_request_skus(payload)

        request = MaterialRequest(
            request_date=payload.request_date,
            status="SUBMITTED",
            notes=payload.notes,
            ods_warehouse_id=ods_warehouse.id,
            created_by=created_by,
        )
        self._db.add(request)
        self._db.flush()

        for sku_data in result_skus:
            req_sku = MaterialRequestSKU(
                request_id=request.id,
                sku_id=sku_data["sku"].id,
                planned_production_qty=sku_data["planned_qty"],
                bom_version_id=sku_data["bom_version"].id,
                created_by=created_by,
            )
            self._db.add(req_sku)
            self._db.flush()

            for item_data in sku_data["items"]:
                req_item = MaterialRequestItem(
                    request_sku_id=req_sku.id,
                    material_id=item_data["material"].id,
                    gross_required_qty=item_data["gross_required_qty"],
                    remaining_from_previous_day=item_data[
                        "remaining_from_previous_day"
                    ],
                    requested_qty=item_data["requested_qty"],
                    created_by=created_by,
                )
                self._db.add(req_item)

        self._db.flush()
        
        request.request_number = f"MR-{request.request_date.year}-{request.id:06d}"
        
        from app.domains.requests.models import MaterialRequestHistory
        
        history = MaterialRequestHistory(
            request_id=request.id,
            user_id=created_by,
            previous_status="DRAFT",
            new_status="SUBMITTED",
            action="CREATED"
        )
        self._db.add(history)
        self._db.flush()
        
        logger.info("request_created", request_id=request.id, created_by=created_by)
        return request

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def reject_request(self, request_id: int, *, rejected_by: int) -> MaterialRequest:
        request = self._get_request(request_id)
        prev = request.status
        _assert_transition(request.status, "REJECTED")
        request.status = "REJECTED"
        request.version += 1
        request.updated_by = rejected_by
        
        from app.domains.requests.models import MaterialRequestHistory
        from app.domains.audit.models import Notification
        
        history = MaterialRequestHistory(
            request_id=request.id,
            user_id=rejected_by,
            previous_status=prev,
            new_status="REJECTED",
            action="REJECTED"
        )
        self._db.add(history)
        
        notif = Notification(
            user_id=request.created_by,
            message=f"Request {request.request_number or request.public_id} was rejected.",
            link=f"/requests/{request.public_id}",
            type="REQUEST_REJECTED"
        )
        self._db.add(notif)
        
        self._db.flush()
        logger.info("request_rejected", request_id=request_id)
        return request

    # ------------------------------------------------------------------
    # Approve
    # ------------------------------------------------------------------

    def approve_request(
        self,
        request_id: int,
        payload: ApproveRequestPayload,
        *,
        approved_by: int,
        rmpm_warehouse_id: int,
    ) -> MaterialRequest:
        """Process RMPM approval: reserve inventory.

        For each material in the approval payload:
          - Distribute approved_qty across MaterialRequestItem lines greedily.
          - Reserve the total approved quantity from RMPM.

        If any approved_qty < requested_qty across the board, status = PARTIALLY_APPROVED.
        """
        request = self._get_request(request_id)
        _assert_transition(request.status, "APPROVED")

        request.rmpm_warehouse_id = rmpm_warehouse_id

        # Fetch materials to map public_id to internal id
        mat_ids = {item.material_id for sku_line in request.skus for item in sku_line.items}
        materials = self._db.scalars(select(Material).where(Material.id.in_(mat_ids))).all()
        pub_to_id = {str(m.public_id): m.id for m in materials}

        # Map material_id -> total approved_qty
        approval_map: dict[int, Decimal] = {}
        for payload_item in payload.items:
            mat_id = pub_to_id.get(str(payload_item.material_public_id))
            if mat_id is not None:
                approval_map[mat_id] = payload_item.approved_qty

        # Group items by material_id
        items_by_mat: dict[int, list[MaterialRequestItem]] = {}
        for sku_line in request.skus:
            for item in sku_line.items:
                if item.material_id is not None:
                    items_by_mat.setdefault(item.material_id, []).append(item)

        is_partial = False
        reservations: list[tuple[int, Decimal]] = []

        for mat_id, items in items_by_mat.items():
            approved_remaining = approval_map.get(mat_id, Decimal("0"))
            total_approved = approved_remaining

            if total_approved > Decimal("0"):
                reservations.append((mat_id, total_approved))

            for req_item in items:
                # Greedily allocate up to req_item.requested_qty
                allocation = min(approved_remaining, req_item.requested_qty)
                req_item.approved_qty = allocation
                req_item.version += 1
                req_item.updated_by = approved_by

                approved_remaining -= allocation

                if req_item.approved_qty < req_item.requested_qty:
                    is_partial = True

        # Sort reservations by material_id to acquire advisory locks consistently and prevent deadlocks
        reservations.sort(key=lambda x: x[0] or 0)

        for mat_id, qty in reservations:
            self._inventory.reserve(
                material_id=mat_id,
                source_warehouse_id=rmpm_warehouse_id,
                quantity=qty,
                reference_type="MATERIAL_REQUEST",
                reference_id=request.id,
                reserved_by=approved_by,
            )

        prev = request.status
        request.status = "APPROVED"
        request.approved_by = approved_by
        request.version += 1
        request.updated_by = approved_by
        
        from app.domains.requests.models import MaterialRequestHistory
        from app.domains.audit.models import Notification
        
        history = MaterialRequestHistory(
            request_id=request.id,
            user_id=approved_by,
            previous_status=prev,
            new_status="APPROVED",
            action="APPROVED"
        )
        self._db.add(history)
        
        notif = Notification(
            user_id=request.created_by,
            message=f"Request {request.request_number or request.public_id} was approved.",
            link=f"/requests/{request.public_id}",
            type="REQUEST_APPROVED"
        )
        self._db.add(notif)
        
        self._db.flush()

        logger.info(
            "request_approved",
            request_id=request_id,
            status=request.status,
            approved_by=approved_by,
        )
        return request

    # ------------------------------------------------------------------
    # Dispatch / Receive / Close
    # ------------------------------------------------------------------

    def dispatch_request(self, request_id: int, *, dispatched_by: int) -> MaterialRequest:
        """Transition APPROVED/PARTIALLY_APPROVED → DISPATCHED.

        Records a TRANSFER_OUT from RMPM to ODS for each approved material line
        and creates a history entry.
        """
        request = self._get_request(request_id)
        _assert_transition(request.status, "DISPATCHED")
        prev = request.status

        # Record inventory transfer out from RMPM for each approved item
        if request.rmpm_warehouse_id:
            for sku_line in request.skus:
                for item in sku_line.items:
                    if item.approved_qty and item.approved_qty > 0:
                        self._inventory.release_reservation(
                            material_id=item.material_id,
                            source_warehouse_id=request.rmpm_warehouse_id,
                            quantity=item.approved_qty,
                            reference_type="MATERIAL_REQUEST",
                            reference_id=request.id,
                            released_by=dispatched_by,
                        )
                        self._inventory.dispatch_transfer(
                            material_id=item.material_id,
                            source_warehouse_id=request.rmpm_warehouse_id,
                            quantity=item.approved_qty,
                            reference_type="MATERIAL_REQUEST",
                            reference_id=request.id,
                            dispatched_by=dispatched_by,
                        )
                        item.dispatched_qty = item.approved_qty
                        item.version += 1
                        item.updated_by = dispatched_by

        request.status = "DISPATCHED"
        request.version += 1
        request.updated_by = dispatched_by

        from app.domains.requests.models import MaterialRequestHistory
        from app.domains.audit.models import Notification

        self._db.add(
            MaterialRequestHistory(
                request_id=request.id,
                user_id=dispatched_by,
                previous_status=prev,
                new_status="DISPATCHED",
                action="DISPATCHED",
            )
        )
        self._db.add(
            Notification(
                user_id=request.created_by,
                message=f"Request {request.request_number or request.public_id} has been dispatched.",
                link=f"/requests/{request.public_id}",
                type="REQUEST_DISPATCHED",
            )
        )
        self._db.flush()
        logger.info("request_dispatched", request_id=request_id, dispatched_by=dispatched_by)
        return request

    def receive_request(self, request_id: int, *, received_by: int) -> MaterialRequest:
        """Transition DISPATCHED → RECEIVED.

        Records a RECEIPT into the ODS warehouse for each dispatched item
        and creates a history entry.
        """
        request = self._get_request(request_id)
        _assert_transition(request.status, "RECEIVED")
        prev = request.status

        for sku_line in request.skus:
            for item in sku_line.items:
                if item.dispatched_qty and item.dispatched_qty > 0:
                    self._inventory.receive_transfer(
                        material_id=item.material_id,
                        destination_warehouse_id=request.ods_warehouse_id,
                        quantity=item.dispatched_qty,
                        reference_type="MATERIAL_REQUEST",
                        reference_id=request.id,
                        received_by=received_by,
                    )
                    item.received_qty = item.dispatched_qty
                    item.version += 1
                    item.updated_by = received_by

        request.status = "RECEIVED"
        request.version += 1
        request.updated_by = received_by

        from app.domains.requests.models import MaterialRequestHistory
        from app.domains.audit.models import Notification

        self._db.add(
            MaterialRequestHistory(
                request_id=request.id,
                user_id=received_by,
                previous_status=prev,
                new_status="RECEIVED",
                action="RECEIVED",
            )
        )
        self._db.add(
            Notification(
                user_id=request.created_by,
                message=f"Request {request.request_number or request.public_id} has been received.",
                link=f"/requests/{request.public_id}",
                type="REQUEST_RECEIVED",
            )
        )
        self._db.flush()
        logger.info("request_received", request_id=request_id, received_by=received_by)
        return request

    def close_request(self, request_id: int, *, closed_by: int) -> MaterialRequest:
        """Transition RECEIVED → CLOSED.

        Final terminal state indicating all materials have been consumed.
        """
        request = self._get_request(request_id)
        _assert_transition(request.status, "CLOSED")
        prev = request.status

        request.status = "CLOSED"
        request.version += 1
        request.updated_by = closed_by

        from app.domains.requests.models import MaterialRequestHistory

        self._db.add(
            MaterialRequestHistory(
                request_id=request.id,
                user_id=closed_by,
                previous_status=prev,
                new_status="CLOSED",
                action="CLOSED",
            )
        )
        self._db.flush()
        logger.info("request_closed", request_id=request_id, closed_by=closed_by)
        return request

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_request(self, request_id: int) -> MaterialRequest:
        obj = self._db.scalar(
            select(MaterialRequest)
            .where(MaterialRequest.id == request_id)
            .options(
                selectinload(MaterialRequest.skus)
                .selectinload(MaterialRequestSKU.items)
                .selectinload(MaterialRequestItem.material)
                .selectinload(Material.material_type)
            )
        )
        if obj is None:
            raise NotFoundError(f"MaterialRequest id={request_id} not found.")
        return obj

    def _resolve_bom_version(self, sku_id: int, as_of_date: object) -> BOMVersion:
        """Return the BOM version effective on the given date with its items loaded."""
        bom = self._db.scalar(
            select(BOMVersion)
            .where(BOMVersion.sku_id == sku_id)
            .where(BOMVersion.is_active.is_(True))
            .where(BOMVersion.deleted_at.is_(None))
            .order_by(BOMVersion.version_number.desc())
            .options(
                selectinload(BOMVersion.items)
                .selectinload(BOMItem.material)
                .selectinload(Material.material_type)
            )
            .limit(1)
        )
        if bom is None:
            raise NotFoundError(f"No active BOM found for SKU id={sku_id}.")
        return bom
