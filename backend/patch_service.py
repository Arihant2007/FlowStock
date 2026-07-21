import re
import os

with open('app/domains/master/service.py', 'r') as f:
    content = f.read()

# 1. Add imports
imports_to_add = '''
import os
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from app.domains.master.models import BOMUploadSession, BOMUploadSessionStatus
'''
content = content.replace('from typing import Any', 'from typing import Any\n' + imports_to_add)

# 2. Replace preview_bom_upload
old_preview = '''    def preview_bom_upload(self, file_bytes: bytes, filename: str) -> BOMUploadPreview:
        \"\"\"Parse and validate a BOM Excel file without committing any changes.\"\"\"
        parsed_rows, global_errors, empty_sheets, warnings = self._parse_bom_excel(file_bytes, filename)'''

new_preview = '''    def preview_bom_upload(
        self, file_bytes: bytes | None, filename: str | None, session_id: str | None, *, current_user_id: int
    ) -> BOMUploadPreview:
        \"\"\"Parse and validate a BOM Excel file via session.\"\"\"
        import time
        if file_bytes:
            # Create new session
            staging_dir = "uploads/bom_staging"
            os.makedirs(staging_dir, exist_ok=True)
            sess_id = str(uuid.uuid4())
            file_path = os.path.join(staging_dir, f"{sess_id}.xlsx")
            with open(file_path, "wb") as f:
                f.write(file_bytes)
            
            file_size = len(file_bytes)
            sha256 = hashlib.sha256(file_bytes).hexdigest()
            
            session = BOMUploadSession(
                public_id=uuid.UUID(sess_id),
                created_by=current_user_id,
                filename=filename or "upload.xlsx",
                file_path=file_path,
                file_size=file_size,
                sha256_hash=sha256,
                status=BOMUploadSessionStatus.UPLOADED,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
            )
            self._db.add(session)
            self._db.flush()
        elif session_id:
            session = self._db.query(BOMUploadSession).filter_by(public_id=uuid.UUID(session_id)).first()
            if not session:
                raise NotFoundError("BOM Upload session not found.")
            if session.created_by != current_user_id:
                raise ValidationError("You do not have permission to access this session.")
            if session.expires_at < datetime.now(timezone.utc):
                raise ValidationError("This upload session has expired.")
                
            with open(session.file_path, "rb") as f:
                file_bytes = f.read()
            filename = session.filename
        else:
            raise ValidationError("Either file_bytes or session_id must be provided.")

        try:
            parsed_rows, global_errors, empty_sheets, warnings = self._parse_bom_excel(file_bytes, filename)
        except Exception as e:
            session.status = BOMUploadSessionStatus.FAILED
            raise
'''

content = content.replace(old_preview, new_preview)


# 3. Add Status update logic to preview
old_preview_return = '''        return BOMUploadPreview(
            total_rows=len(rows),
            valid_rows=len(rows) - error_count,
            error_rows=error_count,
            existing_skus=sorted(existing_skus),
            new_skus=sorted(new_skus),
            existing_materials=sorted(existing_materials),
            unknown_materials=sorted(unknown_materials),
            duplicate_material_codes=sorted(duplicate_material_codes),
            duplicate_sku_codes=sorted(duplicate_sku_codes),
            empty_sheets=empty_sheets,
            rows=rows,
            errors=global_errors,
            warnings=warnings,
            skus_affected=sorted(skus_affected),
        )'''

new_preview_return = '''        if unknown_materials:
            session.status = BOMUploadSessionStatus.WAITING_FOR_MATERIALS
        elif error_count == 0 and not global_errors:
            session.status = BOMUploadSessionStatus.READY_TO_COMMIT
        
        self._db.flush()

        return BOMUploadPreview(
            total_rows=len(rows),
            valid_rows=len(rows) - error_count,
            error_rows=error_count,
            existing_skus=sorted(existing_skus),
            new_skus=sorted(new_skus),
            existing_materials=sorted(existing_materials),
            unknown_materials=sorted(unknown_materials),
            duplicate_material_codes=sorted(duplicate_material_codes),
            duplicate_sku_codes=sorted(duplicate_sku_codes),
            empty_sheets=empty_sheets,
            rows=rows,
            errors=global_errors,
            warnings=warnings,
            skus_affected=sorted(skus_affected),
            session_id=str(session.public_id),
            session_status=session.status.value,
        )'''
content = content.replace(old_preview_return, new_preview_return)

# 4. Replace commit_bom_upload
old_commit_sig = '''    def commit_bom_upload(
        self, file_bytes: bytes, filename: str, *, created_by: int
    ) -> dict[str, int]:
        \"\"\"Parse, validate, and commit a BOM Excel file.\"\"\"
        parsed_rows, global_errors, empty_sheets, _ = self._parse_bom_excel(file_bytes, filename)'''

new_commit_sig = '''    def commit_bom_upload(
        self, session_id: str, *, current_user_id: int
    ) -> dict[str, int]:
        \"\"\"Parse, validate, and commit a BOM Excel file from session.\"\"\"
        session = self._db.query(BOMUploadSession).filter_by(public_id=uuid.UUID(session_id)).first()
        if not session:
            raise NotFoundError("BOM Upload session not found.")
        if session.created_by != current_user_id:
            raise ValidationError("You do not have permission to access this session.")
        if session.expires_at < datetime.now(timezone.utc):
            raise ValidationError("This upload session has expired.")
        if session.status == BOMUploadSessionStatus.COMMITTED:
            raise ValidationError("This BOM import has already been completed.")
        if session.status != BOMUploadSessionStatus.READY_TO_COMMIT:
            raise ValidationError("Session is not ready to commit. Please resolve preview errors.")
            
        with open(session.file_path, "rb") as f:
            file_bytes = f.read()
        filename = session.filename
        created_by = current_user_id
        
        parsed_rows, global_errors, empty_sheets, _ = self._parse_bom_excel(file_bytes, filename)'''

content = content.replace(old_commit_sig, new_commit_sig)

old_commit_return = '''        logger.info(
            "bom_upload_committed",
            skus_updated=skus_updated,
            items_created=items_created,
            created_by=created_by,
        )
        return {"skus_updated": skus_updated, "items_created": items_created}'''

new_commit_return = '''        import time
        start_time = time.time()
        
        logger.info(
            "bom_upload_committed",
            skus_updated=skus_updated,
            items_created=items_created,
            created_by=created_by,
        )
        
        duration = time.time() - start_time
        session.status = BOMUploadSessionStatus.COMMITTED
        session.import_results = {
            "skus_updated": skus_updated,
            "items_created": items_created,
            "duration_seconds": round(duration, 2)
        }
        self._db.flush()
        
        return {"skus_updated": skus_updated, "items_created": items_created}

    def cancel_bom_upload(self, session_id: str, current_user_id: int) -> None:
        session = self._db.query(BOMUploadSession).filter_by(public_id=uuid.UUID(session_id)).first()
        if not session:
            return
        if session.created_by != current_user_id:
            raise ValidationError("Permission denied.")
        session.status = BOMUploadSessionStatus.CANCELLED
        # We optionally delete the file
        if os.path.exists(session.file_path):
            os.remove(session.file_path)
        self._db.flush()

    def cleanup_expired_sessions(self) -> None:
        expired = self._db.query(BOMUploadSession).filter(
            BOMUploadSession.expires_at < datetime.now(timezone.utc),
            BOMUploadSession.status != BOMUploadSessionStatus.EXPIRED,
            BOMUploadSession.status != BOMUploadSessionStatus.COMMITTED
        ).all()
        for session in expired:
            session.status = BOMUploadSessionStatus.EXPIRED
            if os.path.exists(session.file_path):
                os.remove(session.file_path)
        self._db.commit()'''

content = content.replace(old_commit_return, new_commit_return)

with open('app/domains/master/service.py', 'w') as f:
    f.write(content)
