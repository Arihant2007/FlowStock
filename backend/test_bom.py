import asyncio
import pandas as pd
from io import BytesIO
from app.infrastructure.database import SessionLocal
from app.domains.master.service import MasterService
from app.domains.auth.models import User

def make_fake_bom():
    df = pd.DataFrame([
        ["Material Code", "Material Description", "Quantity for 1 ton", "UOM"],
        ["FG-001", "Finished Good 1", "", ""],
        ["RM-001", "Raw Material 1", "500", "kg"],
    ])
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, header=False)
    return output.getvalue()

async def main():
    db = SessionLocal()
    svc = MasterService(db)
    
    # create RM-001 if not exists
    from app.domains.master.models import Material, MaterialCategory, MaterialType, SKU, BOMVersion
    
    admin = db.query(User).filter_by(username="admin").first()
    if not admin:
        print("Admin user not found")
        return
        
    mat = db.query(Material).filter_by(code="RM-001").first()
    if not mat:
        cat = db.query(MaterialCategory).first()
        mtype = db.query(MaterialType).first()
        mat = Material(code="RM-001", name="RM 1", uom="kg", category_id=cat.id, type_id=mtype.id, created_by=admin.id)
        db.add(mat)
        db.commit()
        
    # preview
    bom_bytes = make_fake_bom()
    preview = svc.preview_bom_upload(file_bytes=bom_bytes, filename="bom.xlsx", session_id=None, current_user_id=admin.id)
    print("Preview:", preview)
    
    # get session_id
    from app.domains.master.models import BOMUploadSession
    sess = db.query(BOMUploadSession).order_by(BOMUploadSession.id.desc()).first()
    
    sess.status = "READY_TO_COMMIT"
    db.commit()
    
    # commit
    res = svc.commit_bom_upload(session_id=str(sess.public_id), current_user_id=admin.id)
    print("Commit result:", res)
    db.commit()
    
    # list SKUs
    skus, meta = svc.list_skus()
    print("SKUs in DB:")
    for s in skus:
        print(s.code, s.name)
        
if __name__ == "__main__":
    asyncio.run(main())
