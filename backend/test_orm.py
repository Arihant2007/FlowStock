import sys
import logging
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.domains.auth.models import User, Role, RolePermission, Permission

try:
    stmt = (
        select(User)
        .where(User.deleted_at.is_(None))
        .options(
            selectinload(User.role)
            .selectinload(Role.permissions)
            .selectinload(RolePermission.permission)
        )
    )
    print("Success:", stmt)
except Exception as e:
    print("Error:", repr(e))
