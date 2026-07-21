import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.infrastructure.database import SessionLocal
from app.domains.master.service import MasterService

def test_commit():
    with SessionLocal() as db:
        try:
            service = MasterService(db)
            
            import pandas as pd
            from io import BytesIO
            
            df = pd.DataFrame({
                "Material Code": ["FPSX03391-TEST"],
                "Material Name": ["CFC - Bingo PC Laser coding Rs 30 50p"],
                "UOM": ["EA"],
                "Category": ["Packaging Material"],
                "Material Type": ["PM"],
                "Group": ["Cartons"]
            })
            
            excel_io = BytesIO()
            df.to_excel(excel_io, index=False)
            excel_bytes = excel_io.getvalue()
            
            preview = service.preview_material_upload(excel_bytes, "test.xlsx")
            print("Preview success!", preview.error_rows, preview.valid_rows)
            
            if preview.error_rows == 0:
                result = service.commit_material_upload(excel_bytes, "test.xlsx", created_by=1)
                db.commit()
                print("Commit success!", result)
            else:
                db.rollback()

        except Exception as e:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_commit()
