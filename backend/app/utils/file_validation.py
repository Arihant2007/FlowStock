import json

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.settings.models import Setting

ALLOWED_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.ms-excel": "xls",
}

async def validate_upload_file(file: UploadFile, db: Session) -> bytes:
    """Validate uploaded file for size, MIME type, extension, and emptiness."""
    # 1. Fetch settings
    max_mb_setting = db.scalar(select(Setting).where(Setting.key == "upload_max_mb"))
    ext_setting = db.scalar(select(Setting).where(Setting.key == "allowed_upload_extensions"))

    max_bytes = int(max_mb_setting.value) * 1024 * 1024 if max_mb_setting else 5 * 1024 * 1024
    allowed_exts = json.loads(ext_setting.value) if ext_setting else ["xlsx", "xls"]

    # 2. Check Extension
    filename = file.filename or ""
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file extension '.{extension}'. Allowed: {', '.join(allowed_exts)}"
        )

    # 3. Read and check size
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty."
        )
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum allowed size is {max_bytes / (1024 * 1024):.1f} MB."
        )

    # 4. Check MIME type via magic bytes (ZIP for xlsx, OLE for xls)
    # XLSX files are ZIP files and start with PK (50 4B 03 04)
    # XLS files are OLE files and start with D0 CF 11 E0
    header = content[:4]
    if header != b"PK\x03\x04" and header != b"\xd0\xcf\x11\xe0":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Does not match Excel signature."
        )

    return content
