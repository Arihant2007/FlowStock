"""Master domain repository — data access layer for all master tables.

Provides typed repository classes that extend BaseRepository for each
master entity. Domain-specific query methods are defined here; generic
CRUD (get_by_id, get_by_public_id, list_all, create, update, soft_delete)
is inherited from BaseRepository.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

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
from app.infrastructure.base_repository import BaseRepository

# ---------------------------------------------------------------------------
# Warehouse
# ---------------------------------------------------------------------------


class WarehouseRepository(BaseRepository[Warehouse]):
    """Data access methods for Warehouse entities."""

    model = Warehouse

    def get_by_name(self, name: str) -> Warehouse | None:
        """Return Warehouse by exact name or None."""
        return self.db.scalar(
            select(Warehouse)
            .where(Warehouse.name == name)
            .where(Warehouse.deleted_at.is_(None))
        )

    def list_by_type(self, warehouse_type: str) -> list[Warehouse]:
        """Return all active warehouses of a given type (ODS or RMPM)."""
        return list(
            self.db.scalars(
                select(Warehouse)
                .where(Warehouse.type == warehouse_type)
                .where(Warehouse.deleted_at.is_(None))
                .order_by(Warehouse.name)
            ).all()
        )


# ---------------------------------------------------------------------------
# Material Classifications
# ---------------------------------------------------------------------------


class MaterialCategoryRepository(BaseRepository[MaterialCategory]):
    model = MaterialCategory

    def get_by_name(self, name: str) -> MaterialCategory | None:
        return self.db.scalar(
            select(MaterialCategory)
            .where(MaterialCategory.name == name)
            .where(MaterialCategory.deleted_at.is_(None))
        )


class MaterialTypeRepository(BaseRepository[MaterialType]):
    model = MaterialType

    def get_by_name(self, name: str) -> MaterialType | None:
        return self.db.scalar(
            select(MaterialType)
            .where(MaterialType.name == name)
            .where(MaterialType.deleted_at.is_(None))
        )


class MaterialGroupRepository(BaseRepository[MaterialGroup]):
    model = MaterialGroup

    def get_by_name(self, name: str) -> MaterialGroup | None:
        return self.db.scalar(
            select(MaterialGroup)
            .where(MaterialGroup.name == name)
            .where(MaterialGroup.deleted_at.is_(None))
        )


# ---------------------------------------------------------------------------
# Material
# ---------------------------------------------------------------------------


def _material_with_relations() -> object:
    """Return a select statement for Material with all classification relations eagerly loaded."""
    return (
        select(Material)
        .where(Material.deleted_at.is_(None))
        .options(
            selectinload(Material.category),
            selectinload(Material.material_type),
            selectinload(Material.group),
        )
    )


class MaterialRepository(BaseRepository[Material]):
    """Data access methods for Material entities."""

    model = Material

    def get_by_id(self, record_id: int) -> Material:
        """Load material with classification relations eagerly."""
        obj = self.db.scalar(
            _material_with_relations().where(Material.id == record_id)  # type: ignore[attr-defined]
        )
        from app.core.errors import NotFoundError

        if obj is None:
            raise NotFoundError(f"Material with id={record_id} not found.")
        return obj

    def get_by_public_id(self, public_id: str | uuid.UUID) -> Material:
        obj = self.db.scalar(
            _material_with_relations().where(Material.public_id == public_id)  # type: ignore[attr-defined]
        )
        from app.core.errors import NotFoundError

        if obj is None:
            raise NotFoundError(f"Material with public_id={public_id} not found.")
        return obj

    def get_by_code(self, code: str) -> Material | None:
        """Return Material by unique code or None."""
        return self.db.scalar(
            _material_with_relations().where(Material.code == code)  # type: ignore[attr-defined]
        )

    def list_all(
        self, *, page: int = 1, page_size: int = 20
    ) -> tuple[list[Material], int]:
        """Return paginated materials with classification relations loaded."""
        from sqlalchemy import func

        total: int = (
            self.db.scalar(
                select(func.count(Material.id)).where(Material.deleted_at.is_(None))
            )
            or 0
        )
        rows = list(
            self.db.scalars(
                _material_with_relations()  # type: ignore[attr-defined]
                .order_by(Material.code)
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return rows, total


# ---------------------------------------------------------------------------
# SKU
# ---------------------------------------------------------------------------


class SKURepository(BaseRepository[SKU]):
    """Data access methods for SKU entities."""

    model = SKU

    def get_by_code(self, code: str) -> SKU | None:
        """Return SKU by unique code or None."""
        return self.db.scalar(
            select(SKU).where(SKU.code == code).where(SKU.deleted_at.is_(None))
        )


# ---------------------------------------------------------------------------
# BOM
# ---------------------------------------------------------------------------


def _bom_version_with_items() -> object:
    """BOMVersion select with nested items and material relations eagerly loaded."""
    return (
        select(BOMVersion)
        .where(BOMVersion.deleted_at.is_(None))
        .options(
            selectinload(BOMVersion.sku),
            selectinload(BOMVersion.items)
            .selectinload(BOMItem.material)
            .selectinload(Material.material_type),
            selectinload(BOMVersion.items)
            .selectinload(BOMItem.material)
            .selectinload(Material.category),
            selectinload(BOMVersion.items)
            .selectinload(BOMItem.material)
            .selectinload(Material.group),
        )
    )


class BOMVersionRepository(BaseRepository[BOMVersion]):
    """Data access methods for BOMVersion entities."""

    model = BOMVersion

    def get_active_for_sku(self, sku_id: int) -> BOMVersion | None:
        """Return the currently active BOM version for the given SKU or None."""
        return self.db.scalar(
            _bom_version_with_items()  # type: ignore[attr-defined]
            .where(BOMVersion.sku_id == sku_id)
            .where(BOMVersion.is_active.is_(True))
            .order_by(BOMVersion.version_number.desc())
            .limit(1)
        )

    def get_by_id_with_items(self, record_id: int) -> BOMVersion | None:
        return self.db.scalar(
            _bom_version_with_items().where(BOMVersion.id == record_id)  # type: ignore[attr-defined]
        )

    def get_next_version_number(self, sku_id: int) -> int:
        """Return the next sequential version number for a SKU's BOM."""
        from sqlalchemy import func

        max_ver: int = (
            self.db.scalar(
                select(func.max(BOMVersion.version_number)).where(
                    BOMVersion.sku_id == sku_id
                )
            )
            or 0
        )
        return max_ver + 1

    def deactivate_all_for_sku(self, sku_id: int) -> None:
        """Mark all BOM versions for a SKU as inactive before creating a new active version."""
        for bom in self.db.scalars(
            select(BOMVersion)
            .where(BOMVersion.sku_id == sku_id)
            .where(BOMVersion.is_active.is_(True))
        ).all():
            bom.is_active = False
        self.db.flush()


class BOMItemRepository(BaseRepository[BOMItem]):
    model = BOMItem

    def list_for_version(self, bom_version_id: int) -> list[BOMItem]:
        return list(
            self.db.scalars(
                select(BOMItem)
                .where(BOMItem.bom_version_id == bom_version_id)
                .where(BOMItem.deleted_at.is_(None))
                .options(
                    selectinload(BOMItem.material).selectinload(Material.material_type)
                )
            ).all()
        )
