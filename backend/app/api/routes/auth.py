"""Authentication & user-management routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    Token,
    UserCreate,
    UserRead,
    UserUpdate,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])


def _issue_token(user: User) -> Token:
    access_token = create_access_token(subject=user.id, role=user.role.value)
    return Token(access_token=access_token, user=UserRead.model_validate(user))


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, db: DbSession) -> UserRead:
    """Public self-registration (always creates a standard user)."""
    from app.models.enums import UserRole

    service = AuthService(db)
    # Self-registration can never escalate privileges to admin.
    data.role = UserRole.USER
    try:
        user = service.create_user(data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return UserRead.model_validate(user)


@router.post("/login", response_model=Token)
def login(
    db: DbSession,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Token:
    """OAuth2-compatible login (username + password form)."""
    user = AuthService(db).authenticate(form_data.username, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _issue_token(user)


@router.post("/login/json", response_model=Token)
def login_json(data: LoginRequest, db: DbSession) -> Token:
    """JSON login convenience endpoint for the SPA frontend."""
    user = AuthService(db).authenticate(data.username, data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    return _issue_token(user)


@router.get("/me", response_model=UserRead)
def read_me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


# ---------- Admin user management ----------
@users_router.get("", response_model=list[UserRead])
def list_users(_: AdminUser, db: DbSession) -> list[UserRead]:
    return [UserRead.model_validate(u) for u in AuthService(db).list_users()]


@users_router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreate, _: AdminUser, db: DbSession) -> UserRead:
    try:
        user = AuthService(db).create_user(data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return UserRead.model_validate(user)


@users_router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int, data: UserUpdate, _: AdminUser, db: DbSession
) -> UserRead:
    service = AuthService(db)
    user = service.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        user = service.update_user(user, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return UserRead.model_validate(user)


@users_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, admin: AdminUser, db: DbSession) -> Response:
    service = AuthService(db)
    user = service.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    service.delete_user(user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
