import os
import sys
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from app.infrastructure.database import SessionLocal
from app.domains.master.models import Material, MaterialCategory, MaterialType, MaterialGroup

def seed():
    with SessionLocal() as db:
        df = pd.read_excel('Skus_Bom.xlsx')
        
        # Get defaults
        cat = db.query(MaterialCategory).filter_by(name='Raw Material').first()
        typ = db.query(MaterialType).filter_by(name='RM').first()
        grp = db.query(MaterialGroup).filter_by(name='Default').first()
        
        added = 0
        seen = set()
        for i, row in df.iterrows():
            code = str(row.iloc[0]).strip()
            name = str(row.iloc[1]).strip()
            uom = str(row.iloc[3]).strip()
            
            if code == 'nan' or code == 'Material Code' or code == 'SKU Code' or not code:
                continue
            if code in seen:
                continue
                
            # If UOM is nan, default to 'KG'
            if uom == 'nan':
                uom = 'KG'
                
            mat = db.query(Material).filter_by(code=code).first()
            if not mat:
                m = Material(code=code, name=name, uom=uom, category_id=cat.id, type_id=typ.id, group_id=grp.id)
                db.add(m)
                seen.add(code)
                added += 1
        db.commit()
        print(f"Added {added} materials.")

if __name__ == '__main__':
    seed()
