"""Master domain models: Warehouse, MaterialCategory, MaterialType,
MaterialGroup, Material, SKU, BOMVersion, BOMItem.

Design notes:
  - Quantities in BOMItem use NUMERIC(18,4) via SQLAlchemy's Numeric type.
  - All master tables include full soft-delete and audit columns via AuditedModel.
  - BOMVersion is immutable once published; historical transactions always
    resolve to the version that was active on the transaction date.
"""

from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.base_model import AuditedModel


class Warehouse(AuditedModel):
    """A named physical storage location (e.g., RMPM-Main, ODS-Line-1)."""

    __tablename__ = "warehouses"
    __table_args__ = (
        UniqueConstraint("name", name="uq_warehouses_name"),
        UniqueConstraint("public_id", name="uq_warehouses_public_id"),
        CheckConstraint("type IN ('ODS', 'RMPM')", name="ck_warehouses_type"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")


class MaterialCategory(AuditedModel):
    """Broad classification of materials (e.g., Chemicals, Packaging)."""

    __tablename__ = "material_categories"
    __table_args__ = (
        UniqueConstraint("name", name="uq_material_categories_name"),
        UniqueConstraint("public_id", name="uq_material_categories_public_id"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    materials: Mapped[list["Material"]] = relationship(
        "Material", back_populates="category"
    )


class MaterialType(AuditedModel):
    """RM (Raw Material) or PM (Packaging Material)."""

    __tablename__ = "material_types"
    __table_args__ = (
        UniqueConstraint("name", name="uq_material_types_name"),
        UniqueConstraint("public_id", name="uq_material_types_public_id"),
    )

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    materials: Mapped[list["Material"]] = relationship(
        "Material", back_populates="material_type"
    )


class MaterialGroup(AuditedModel):
    """Sub-classification within a category for reporting purposes."""

    __tablename__ = "material_groups"
    __table_args__ = (
        UniqueConstraint("name", name="uq_material_groups_name"),
        UniqueConstraint("public_id", name="uq_material_groups_public_id"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    materials: Mapped[list["Material"]] = relationship(
        "Material", back_populates="group"
    )


class Material(AuditedModel):
    """A single raw or packaging material used in production."""

    __tablename__ = "materials"
    __table_args__ = (
        UniqueConstraint("code", name="uq_materials_code"),
        UniqueConstraint("public_id", name="uq_materials_public_id"),
        Index("ix_materials_category_id", "category_id"),
        Index("ix_materials_type_id", "type_id"),
    )

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    uom: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="Unit of measure: kg, L, units, etc."
    )
    category_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("material_categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    type_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("material_types.id", ondelete="RESTRICT"), nullable=False
    )
    group_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("material_groups.id", ondelete="SET NULL"), nullable=True
    )

    category: Mapped["MaterialCategory"] = relationship(
        "MaterialCategory", back_populates="materials"
    )
    material_type: Mapped["MaterialType"] = relationship(
        "MaterialType", back_populates="materials"
    )
    group: Mapped["MaterialGroup | None"] = relationship(
        "MaterialGroup", back_populates="materials"
    )
    bom_items: Mapped[list["BOMItem"]] = relationship(
        "BOMItem", back_populates="material"
    )


class SKU(AuditedModel):
    """A finished-goods Stock Keeping Unit produced on the line."""

    __tablename__ = "skus"
    __table_args__ = (
        UniqueConstraint("code", name="uq_skus_code"),
        UniqueConstraint("public_id", name="uq_skus_public_id"),
    )

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    bom_versions: Mapped[list["BOMVersion"]] = relationship(
        "BOMVersion", back_populates="sku", order_by="BOMVersion.version_number"
    )


class BOMVersion(AuditedModel):
    """A versioned Bill of Materials for a single SKU.

    When the recipe changes, a new BOMVersion is created rather than
    updating the existing one. Historical transactions always reference
    the version that was effective on the transaction date.
    """

    __tablename__ = "bom_versions"
    __table_args__ = (
        UniqueConstraint("sku_id", "version_number", name="uq_bom_versions_sku_ver"),
        Index("ix_bom_versions_sku_id", "sku_id"),
    )

    sku_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("skus.id", ondelete="RESTRICT"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    sku: Mapped["SKU"] = relationship("SKU", back_populates="bom_versions")
    items: Mapped[list["BOMItem"]] = relationship(
        "BOMItem", back_populates="bom_version", cascade="all, delete-orphan"
    )


class BOMItem(AuditedModel):
    """A single material line within a BOMVersion with quantity per production unit."""

    __tablename__ = "bom_items"
    __table_args__ = (
        UniqueConstraint("bom_version_id", "material_id", name="uq_bom_items_ver_mat"),
        CheckConstraint("quantity_per_unit > 0", name="ck_bom_items_qty_positive"),
        Index("ix_bom_items_bom_version_id", "bom_version_id"),
        Index("ix_bom_items_material_id", "material_id"),
    )

    bom_version_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("bom_versions.id", ondelete="CASCADE"), nullable=False
    )
    material_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False
    )
    quantity_per_unit: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        comment="Material qty required to produce 1 unit of the parent SKU.",
    )

    bom_version: Mapped["BOMVersion"] = relationship(
        "BOMVersion", back_populates="items"
    )
    material: Mapped["Material"] = relationship("Material", back_populates="bom_items")
