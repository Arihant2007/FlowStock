import re

with open('app/domains/master/service.py', 'r') as f:
    content = f.read()

# 1. atomic file writes & logging in preview_bom_upload
preview_find = '''        if file_bytes:
            # Create new session
            staging_dir = "uploads/bom_staging"
            os.makedirs(staging_dir, exist_ok=True)
            sess_id = str(uuid.uuid4())
            file_path = os.path.join(staging_dir, f"{sess_id}.xlsx")
            with open(file_path, "wb") as f:
                f.write(file_bytes)'''

preview_repl = '''        if file_bytes:
            # Create new session
            staging_dir = "uploads/bom_staging"
            os.makedirs(staging_dir, exist_ok=True)
            sess_id = str(uuid.uuid4())
            file_path = os.path.join(staging_dir, f"{sess_id}.xlsx")
            
            # Atomic file write
            tmp_path = file_path + ".tmp"
            with open(tmp_path, "wb") as f:
                f.write(file_bytes)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, file_path)
            
            logger.info("bom_upload_preview_started", session_id=sess_id, user_id=current_user_id, action="new_upload", filename=filename)'''
content = content.replace(preview_find, preview_repl)

preview_resume_find = '''                raise ValidationError("This upload session has expired.")
                
            with open(session.file_path, "rb") as f:'''

preview_resume_repl = '''                raise ValidationError("This upload session has expired.")
                
            logger.info("bom_upload_preview_started", session_id=session_id, user_id=current_user_id, action="resume_upload")
                
            with open(session.file_path, "rb") as f:'''
content = content.replace(preview_resume_find, preview_resume_repl)


# 2. Transaction boundaries & logging in commit_bom_upload
commit_find = '''        parsed_rows, global_errors, empty_sheets, _ = self._parse_bom_excel(file_bytes, filename)
        if global_errors:
            raise ValidationError(global_errors[0])

        sku_codes = list({r["sku_code"] for r in parsed_rows})'''

commit_repl = '''        import time
        start_time = time.time()
        
        try:
            parsed_rows, global_errors, empty_sheets, _ = self._parse_bom_excel(file_bytes, filename)
            if global_errors:
                raise ValidationError(global_errors[0])
    
            sku_codes = list({r["sku_code"] for r in parsed_rows})'''
content = content.replace(commit_find, commit_repl)


commit_end_find = '''        import time
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
        
        return {"skus_updated": skus_updated, "items_created": items_created}'''

commit_end_repl = '''        except Exception as e:
            self._db.rollback()
            # Reload session to mark as FAILED
            failed_session = self._db.query(BOMUploadSession).filter_by(public_id=uuid.UUID(session_id)).first()
            if failed_session:
                failed_session.status = BOMUploadSessionStatus.FAILED
                self._db.flush()
                self._db.commit()
            logger.error("bom_upload_commit_failed", session_id=session_id, user_id=current_user_id, error=str(e))
            raise

        # If everything succeeded
        duration = time.time() - start_time
        
        logger.info(
            "bom_upload_committed",
            session_id=session_id,
            user_id=current_user_id,
            skus_updated=skus_updated,
            items_created=items_created,
            duration_seconds=round(duration, 2)
        )
        
        session.status = BOMUploadSessionStatus.COMMITTED
        session.import_results = {
            "skus_updated": skus_updated,
            "items_created": items_created,
            "duration_seconds": round(duration, 2)
        }
        self._db.flush()
        # We allow the router's dependency to call the final db.commit()
        
        return {"skus_updated": skus_updated, "items_created": items_created}'''
        
# The replace needs to indent the block in between.
# Let's do a regex replace to indent everything between commit_repl and commit_end_repl
content = content.replace(commit_end_find, commit_end_repl)

lines = content.split('\\n')
in_commit_block = False
new_lines = []
for line in lines:
    if 'sku_codes = list({r["sku_code"] for r in parsed_rows})' in line:
        in_commit_block = True
        new_lines.append(line)
        continue
    if '        except Exception as e:' in line:
        in_commit_block = False
        new_lines.append(line)
        continue
    
    if in_commit_block and line.startswith('        '):
        # add 4 spaces
        new_lines.append('    ' + line)
    else:
        new_lines.append(line)
content = '\\n'.join(new_lines)


# 3. cancel logging
cancel_find = '''        session.status = BOMUploadSessionStatus.CANCELLED
        # We optionally delete the file
        if os.path.exists(session.file_path):
            os.remove(session.file_path)
        self._db.flush()'''

cancel_repl = '''        session.status = BOMUploadSessionStatus.CANCELLED
        logger.info("bom_upload_cancelled", session_id=session_id, user_id=current_user_id)
        # We optionally delete the file
        try:
            if os.path.exists(session.file_path):
                os.remove(session.file_path)
        except Exception:
            pass
        self._db.flush()'''
content = content.replace(cancel_find, cancel_repl)


# 4. cleanup expired
cleanup_find = '''        for session in expired:
            session.status = BOMUploadSessionStatus.EXPIRED
            if os.path.exists(session.file_path):
                os.remove(session.file_path)
        self._db.commit()'''

cleanup_repl = '''        for session in expired:
            session.status = BOMUploadSessionStatus.EXPIRED
            logger.info("bom_upload_session_expired", session_id=str(session.public_id))
            try:
                if os.path.exists(session.file_path):
                    os.remove(session.file_path)
            except Exception as e:
                logger.warning("failed_to_delete_expired_session_file", session_id=str(session.public_id), error=str(e))
        self._db.commit()'''
content = content.replace(cleanup_find, cleanup_repl)

with open('app/domains/master/service.py', 'w') as f:
    f.write(content)
