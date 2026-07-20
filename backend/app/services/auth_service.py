"""Authentication & user management business logic."""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import UserCreate, UserUpdate

logger = logging.getLogger(__name__)


class AuthService:
    """Encapsulates all user/auth persistence and validation logic."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ---- Queries ----
    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.db.get(User, user_id)

    def get_by_username(self, username: str) -> Optional[User]:
        stmt = select(User).where(User.username == username)
        return self.db.scalar(stmt)

    def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email)
        return self.db.scalar(stmt)

    def list_users(self) -> list[User]:
        return list(self.db.scalars(select(User).order_by(User.id)))

    # ---- Mutations ----
    def create_user(self, data: UserCreate) -> User:
        if self.get_by_username(data.username):
            raise ValueError("Username already registered")
        if self.get_by_email(data.email):
            raise ValueError("Email already registered")

        user = User(
            username=data.username,
            email=data.email,
            password_hash=hash_password(data.password),
            role=data.role,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        logger.info("Created user %s (role=%s)", user.username, user.role.value)
        return user

    def update_user(self, user: User, data: UserUpdate) -> User:
        if data.email is not None:
            existing = self.get_by_email(data.email)
            if existing and existing.id != user.id:
                raise ValueError("Email already in use")
            user.email = data.email
        if data.password is not None:
            user.password_hash = hash_password(data.password)
        if data.role is not None:
            user.role = data.role
        if data.is_active is not None:
            user.is_active = data.is_active
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(self, user: User) -> None:
        self.db.delete(user)
        self.db.commit()

    # ---- Authentication ----
    def authenticate(self, username: str, password: str) -> Optional[User]:
        user = self.get_by_username(username)
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    # ---- Bootstrap ----
    def ensure_admin(
        self, username: str, email: str, password: str
    ) -> Optional[User]:
        """Create the bootstrap admin if no users exist yet."""
        existing = self.db.scalar(select(User).limit(1))
        if existing is not None:
            return None
        admin = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
        )
        self.db.add(admin)
        self.db.commit()
        self.db.refresh(admin)
        logger.warning(
            "Bootstrap admin '%s' created. Change the default password!", username
        )
        return admin
