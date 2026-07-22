import io
from datetime import datetime, date
from decimal import Decimal
from typing import List, Dict, Any

import pandas as pd
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.domains.master.models import SKU, Material, BOMVersion, BOMItem
from app.domains.requests.models import MaterialRequest, MaterialRequestSKU, MaterialRequestItem
from app.domains.master.models import Warehouse

class ODSUploadService:
    def __init__(self, db: Session):
        self.db = db

    def generate_template(self) -> io.BytesIO:
        """Generate an empty Excel template for ODS Daily Upload."""
        df = pd.DataFrame(columns=[
            "Business Date",
            "SKU",
            "FG Quantity",
            "Material",
            "Material Type (RM / PM)",
            "Remaining Quantity"
        ])
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="ODS_Upload")
        output.seek(0)
        return output

    def preview_upload(self, file_bytes: bytes, current_user_id: int) -> dict:
        """Parse ODS Excel file, calculate requirements, and return preview."""
        try:
            df = pd.read_excel(io.BytesIO(file_bytes))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid Excel file: {str(e)}")

        required_columns = ["Business Date", "SKU", "FG Quantity", "Material", "Remaining Quantity"]
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing columns: {', '.join(missing)}")

        # Clean data
        df = df.dropna(how='all')
        df['Business Date'] = pd.to_datetime(df['Business Date']).dt.date
        df['SKU'] = df['SKU'].astype(str).str.strip()
        df['Material'] = df['Material'].astype(str).str.strip()
        df['FG Quantity'] = pd.to_numeric(df['FG Quantity'], errors='coerce')
        df['Remaining Quantity'] = pd.to_numeric(df['Remaining Quantity'], errors='coerce')

        if df['FG Quantity'].isnull().any() or df['Remaining Quantity'].isnull().any():
            raise HTTPException(status_code=400, detail="Invalid numeric values in quantities.")

        errors = []
        parsed_data = []

        # Group by Business Date and SKU
        grouped = df.groupby(['Business Date', 'SKU'])

        for (business_date, sku_code), group in grouped:
            sku = self.db.query(SKU).filter(SKU.code == sku_code, SKU.deleted_at.is_(None)).first()
            if not sku:
                errors.append(f"Row {group.index[0] + 2}: SKU not found: {sku_code}")
                continue

            active_bom = next((b for b in sku.bom_versions if b.is_active), None)
            if not active_bom:
                errors.append(f"Row {group.index[0] + 2}: No active BOM found for SKU: {sku_code}")
                continue

            fg_qty = group['FG Quantity'].iloc[0]
            if fg_qty <= 0:
                errors.append(f"Row {group.index[0] + 2}: FG Quantity must be > 0 for SKU: {sku_code}")
                continue
                
            # Create a lookup for remaining quantities
            remaining_lookup = {}
            for _, row in group.iterrows():
                mat_code = row['Material']
                rem_qty = Decimal(str(row['Remaining Quantity']))
                if rem_qty < 0:
                    errors.append(f"Row {row.name + 2}: Negative Remaining Quantity for material {mat_code}")
                remaining_lookup[mat_code] = rem_qty

            sku_items = []
            
            for bom_item in active_bom.items:
                mat = bom_item.material
                bom_qty = bom_item.quantity_per_unit
                gross_required = Decimal(str(fg_qty)) * bom_qty
                
                # If material is explicitly listed in excel, use its remaining qty, else 0
                remaining = remaining_lookup.get(mat.code, Decimal("0"))
                requested = max(gross_required - remaining, Decimal("0"))
                
                sku_items.append({
                    "material_code": mat.code,
                    "material_name": mat.name,
                    "material_type": mat.material_type.name if mat.material_type else "RM",
                    "gross_required_qty": float(gross_required),
                    "remaining_from_previous_day": float(remaining),
                    "requested_qty": float(requested),
                    "bom_qty_per_unit": float(bom_qty)
                })

            parsed_data.append({
                "business_date": business_date.isoformat(),
                "sku_code": sku.code,
                "sku_name": sku.name,
                "fg_quantity": float(fg_qty),
                "items": sku_items
            })

        return {
            "parsed_data": parsed_data,
            "errors": errors
        }

    def commit_upload(self, payload: dict, current_user_id: int) -> dict:
        """Create MaterialRequests from parsed JSON payload."""
        data = payload.get("parsed_data", [])
        if not data:
            raise HTTPException(status_code=400, detail="No data to commit.")

        ods_warehouse = self.db.query(Warehouse).filter(Warehouse.type == 'ODS', Warehouse.deleted_at.is_(None)).first()
        rmpm_warehouse = self.db.query(Warehouse).filter(Warehouse.type == 'RMPM', Warehouse.deleted_at.is_(None)).first()
        
        if not ods_warehouse or not rmpm_warehouse:
            raise HTTPException(status_code=400, detail="System missing default ODS or RMPM warehouse.")

        # Group by Business Date since a single request is per day
        from collections import defaultdict
        daily_requests = defaultdict(list)
        for row in data:
            daily_requests[row['business_date']].append(row)

        created_requests = []

        for b_date_str, skus in daily_requests.items():
            b_date = datetime.fromisoformat(b_date_str).date()
            
            req = MaterialRequest(
                request_date=b_date,
                status="SUBMITTED",
                notes="Generated from Daily ODS Upload",
                ods_warehouse_id=ods_warehouse.id,
                rmpm_warehouse_id=rmpm_warehouse.id,
                created_by=current_user_id
            )
            self.db.add(req)
            self.db.flush()

            for sku_data in skus:
                sku = self.db.query(SKU).filter(SKU.code == sku_data['sku_code']).first()
                active_bom = next((b for b in sku.bom_versions if b.is_active), None)
                
                req_sku = MaterialRequestSKU(
                    request_id=req.id,
                    sku_id=sku.id,
                    planned_production_qty=Decimal(str(sku_data['fg_quantity'])),
                    bom_version_id=active_bom.id,
                    created_by=current_user_id
                )
                self.db.add(req_sku)
                self.db.flush()

                for item_data in sku_data['items']:
                    mat = self.db.query(Material).filter(Material.code == item_data['material_code']).first()
                    req_item = MaterialRequestItem(
                        request_sku_id=req_sku.id,
                        material_id=mat.id,
                        gross_required_qty=Decimal(str(item_data['gross_required_qty'])),
                        remaining_from_previous_day=Decimal(str(item_data['remaining_from_previous_day'])),
                        requested_qty=Decimal(str(item_data['requested_qty'])),
                        created_by=current_user_id
                    )
                    self.db.add(req_item)
            
            created_requests.append(str(req.public_id))
            
        self.db.commit()
        return {"message": f"Successfully created {len(created_requests)} material requests.", "request_ids": created_requests}
