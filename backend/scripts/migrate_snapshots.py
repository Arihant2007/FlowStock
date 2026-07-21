"""Migration script to update InventorySnapshot table with versioning.
Run manually to apply changes.
"""

from sqlalchemy import text
from app.infrastructure.database import SessionLocal

def run_migration():
    print("Starting migration for InventorySnapshot versioning...")
    
    with SessionLocal() as db:
        # 1. Add version column if it doesn't exist
        try:
            db.execute(text("ALTER TABLE inventory_snapshots ADD COLUMN version INTEGER NOT NULL DEFAULT 1"))
            print("Added 'version' column.")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                print("'version' column already exists.")
            else:
                db.rollback()
                raise e
        
        # 2. Add is_active column if it doesn't exist
        try:
            db.execute(text("ALTER TABLE inventory_snapshots ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT true"))
            print("Added 'is_active' column.")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                print("'is_active' column already exists.")
            else:
                db.rollback()
                raise e
                
        # 3. Drop the old unique constraint
        try:
            db.execute(text("ALTER TABLE inventory_snapshots DROP CONSTRAINT IF EXISTS uq_inv_snapshot_mat_wh_date"))
            print("Dropped old unique constraint 'uq_inv_snapshot_mat_wh_date'.")
        except Exception as e:
            print(f"Error dropping constraint (might not exist): {e}")
            db.rollback()

        # 4. Add the new unique constraint with version
        try:
            db.execute(text(
                "ALTER TABLE inventory_snapshots ADD CONSTRAINT uq_inv_snapshot_mat_wh_date_ver "
                "UNIQUE (material_id, warehouse_id, snapshot_date, version)"
            ))
            print("Added new unique constraint 'uq_inv_snapshot_mat_wh_date_ver'.")
        except Exception as e:
            if "already exists" in str(e).lower():
                print("New constraint already exists.")
            else:
                db.rollback()
                raise e

        db.commit()
        print("Migration completed successfully.")

if __name__ == "__main__":
    run_migration()
