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
    ) -> tuple[Warehouse, list[dict[str, Any]]]:
        """Core calculation logic for Gross, Remaining, Net."""
        ods_warehouse = self._db.scalar(
            select(Warehouse).where(
                Warehouse.public_id == payload.ods_warehouse_public_id
            )
        )
        if not ods_warehouse:
            raise NotFoundError(
                f"Warehouse {payload.ods_warehouse_public_id} not found."
            )

        # Mandatory daily inventory upload check
        from app.domains.inventory.models import InventorySnapshot

        snapshot_exists = self._db.scalar(
            select(InventorySnapshot)
            .where(InventorySnapshot.warehouse_id == ods_warehouse.id)
            .where(InventorySnapshot.snapshot_date == payload.request_date)
            .limit(1)
        )
        if not snapshot_exists:
            from app.core.errors import ValidationError

            raise ValidationError(
                f"ODS Inventory snapshot for {payload.request_date} is missing. "
                "You must upload today's ODS inventory before creating requests."
            )

        result_skus: list[dict[str, Any]] = []
        for sku_payload in payload.skus:
            sku = self._db.scalar(
                select(SKU).where(SKU.public_id == sku_payload.sku_public_id)
            )
            if not sku:
                raise NotFoundError(f"SKU {sku_payload.sku_public_id} not found.")

            bom_version = self._resolve_bom_version(sku.id, payload.request_date)

            sku_data: dict[str, Any] = {
                "sku": sku,
                "bom_version": bom_version,
                "planned_qty": sku_payload.planned_production_qty,
                "items": [],
            }

            for bom_item in bom_version.items:
                mat = bom_item.material
                gross = bom_item.quantity_per_unit * sku_payload.planned_production_qty

                # Dynamic remaining calculation from ODS balance
                remaining = self._inventory.get_balance(mat.id, ods_warehouse.id)
                net = max(gross - remaining, Decimal("0.0000"))

                sku_data["items"].append(
                    {
                        "material": mat,
                        "gross_required_qty": gross,
                        "remaining_from_previous_day": remaining,
                        "requested_qty": net,
                    }
                )
            result_skus.append(sku_data)

        return ods_warehouse, result_skus

    def preview_request(self, payload: RequestPreviewPayload) -> RequestPreviewOut:
        """Preview material requirements based on active BOM and current ODS stock."""
        ods_warehouse, result_skus = self._calculate_request_skus(payload)

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

        return RequestPreviewOut(skus=out_skus)

    def create_request(
        self, payload: CreateRequestPayload, *, created_by: int
    ) -> MaterialRequest:
        """Create a SUBMITTED material request with calculated net quantities."""
        ods_warehouse, result_skus = self._calculate_request_skus(payload)

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
        logger.info("request_created", request_id=request.id, created_by=created_by)
        return request

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def dispatch_request(
        self, request_id: int, *, dispatched_by: int
    ) -> MaterialRequest:
        """Transition request from APPROVED/PARTIALLY_APPROVED -> DISPATCHED."""
        request = self._get_request(request_id)
        _assert_transition(request.status, "DISPATCHED")
        request.status = "DISPATCHED"
        request.version += 1
        request.updated_by = dispatched_by

        for sku_line in request.skus:
            for item in sku_line.items:
                if item.approved_qty and item.approved_qty > 0:
                    item.dispatched_qty = item.approved_qty
                    item.version += 1
                    item.updated_by = dispatched_by

                    assert request.rmpm_warehouse_id is not None, "RMPM warehouse must be set for dispatch"

                    self._inventory.dispatch_transfer(
                        material_id=item.material_id,
                        source_warehouse_id=request.rmpm_warehouse_id,
                        quantity=item.dispatched_qty,
                        reference_type="MATERIAL_REQUEST",
                        reference_id=request.id,
                        dispatched_by=dispatched_by,
                    )

        self._db.flush()
        logger.info("request_dispatched", request_id=request_id)
        return request

    def receive_request(self, request_id: int, *, received_by: int) -> MaterialRequest:
        """Transition request from DISPATCHED -> RECEIVED."""
        request = self._get_request(request_id)
        _assert_transition(request.status, "RECEIVED")
        request.status = "RECEIVED"
        request.version += 1
        request.updated_by = received_by

        for sku_line in request.skus:
            for item in sku_line.items:
                if item.dispatched_qty and item.dispatched_qty > 0:
                    item.received_qty = item.dispatched_qty
                    item.version += 1
                    item.updated_by = received_by

                    self._inventory.receive_transfer(
                        material_id=item.material_id,
                        destination_warehouse_id=request.ods_warehouse_id,
                        quantity=item.received_qty,
                        reference_type="MATERIAL_REQUEST",
                        reference_id=request.id,
                        received_by=received_by,
                    )

        self._db.flush()
        logger.info("request_received", request_id=request_id)
        return request

    def close_request(self, request_id: int, *, closed_by: int) -> MaterialRequest:
        """Transition request from RECEIVED -> CLOSED.

        This signifies production is complete. All received materials are
        consumed from the ODS warehouse.
        """
        request = self._get_request(request_id)
        _assert_transition(request.status, "CLOSED")
        request.status = "CLOSED"
        request.version += 1
        request.updated_by = closed_by

        # Trigger consumption from ODS ledger
        for sku_line in request.skus:
            for item in sku_line.items:
                if item.received_qty and item.received_qty > 0:
                    self._inventory.consume(
                        material_id=item.material_id,
                        source_warehouse_id=request.ods_warehouse_id,
                        quantity=item.received_qty,
                        reference_type="MATERIAL_REQUEST",
                        reference_id=request.id,
                        consumed_by=closed_by,
                    )

        self._db.flush()
        logger.info("request_closed", request_id=request_id)
        return request

    def reject_request(self, request_id: int, *, rejected_by: int) -> MaterialRequest:
        """Transition request to REJECTED."""
        request = self._get_request(request_id)
        _assert_transition(request.status, "REJECTED")
        request.status = "REJECTED"
        request.version += 1
        request.updated_by = rejected_by
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

        For each item in the approval payload:
          - Set approved_qty on the MaterialRequestItem.
          - Reserve the approved quantity from RMPM.

        If any approved_qty < requested_qty, status = PARTIALLY_APPROVED.
        All-approved -> APPROVED.
        """
        request = self._get_request(request_id)
        _assert_transition(request.status, "APPROVED")

        request.rmpm_warehouse_id = rmpm_warehouse_id

        approval_map = {
            str(item.material_request_item_public_id): item.approved_qty
            for item in payload.items
        }

        is_partial = False
        reservations = []
        for sku_line in request.skus:
            for item in sku_line.items:
                approved_qty = approval_map.get(str(item.public_id), Decimal("0"))
                item.approved_qty = approved_qty
                item.version += 1
                item.updated_by = approved_by

                if approved_qty < item.requested_qty:
                    is_partial = True

                if approved_qty > Decimal("0"):
                    reservations.append((item.material_id, approved_qty))

        # Sort reservations by material_id to acquire advisory locks consistently and prevent deadlocks
        reservations.sort(key=lambda x: x[0])

        for mat_id, qty in reservations:
            self._inventory.reserve(
                material_id=mat_id,
                source_warehouse_id=rmpm_warehouse_id,
                quantity=qty,
                reference_type="MATERIAL_REQUEST",
                reference_id=request.id,
                reserved_by=approved_by,
            )

        request.status = "PARTIALLY_APPROVED" if is_partial else "APPROVED"
        request.approved_by = approved_by
        request.version += 1
        request.updated_by = approved_by
        self._db.flush()

        logger.info(
            "request_approved",
            request_id=request_id,
            status=request.status,
            approved_by=approved_by,
        )
        return request

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_request(self, request_id: int) -> MaterialRequest:
        obj = self._db.scalar(
            select(MaterialRequest)
            .where(MaterialRequest.id == request_id)
            .options(
                selectinload(MaterialRequest.skus).selectinload(
                    MaterialRequestSKU.items
                )
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
