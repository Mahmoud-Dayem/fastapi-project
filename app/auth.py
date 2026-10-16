from datetime import UTC, datetime, timedelta, timezone
from enum import Enum
from typing import Annotated, Literal
from uuid import uuid4

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import select

from app.config import settings
from database import SessionDep
from models.user import UserModel

TokenType = Literal["access_token", "refresh_token"]

INVALID_TOKEN = HTTPException(
    detail="UNAUTHORIZED", status_code=status.HTTP_401_UNAUTHORIZED
)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/users/login",
    scopes={
        "read:users": "Read users",
        "write:users": "Create and  update users",
        "delete:users": "delete users",
    },
)


async def get_current_user(
    session: SessionDep, token: Annotated[str, Depends(oauth2_scheme)]
):

    payload = decode_token(token, token_type="access_token")

    if not payload:
        raise INVALID_TOKEN

    if payload.get("type") != "access_token":
        raise INVALID_TOKEN
    email = payload.get("sub")
    if not email:
        raise INVALID_TOKEN
    result = await session.execute(select(UserModel).where(UserModel.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise INVALID_TOKEN
    return user


CurrentUser = Annotated[UserModel, Depends(get_current_user)]


Role = Literal["admin", "user"]


# class Role(str, Enum):
#     ADMIN = "admin"
#     USER = "user"


class RoleRequired:
    def __init__(self, role: Role):
        self.role = role

    def __call__(self, current_user: CurrentUser):

        if current_user.role != self.role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires the '{self.role}' role",
            )

        return current_user


# admin_required = RoleRequired("admin")
user_required = RoleRequired("user")

admin_required = Annotated[UserModel, Depends(RoleRequired("admin"))]


class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


def create_access_token(user_data: dict):
    expire = datetime.now(UTC) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )

    payload = {
        **user_data,
        "iat": datetime.now(UTC),
        "exp": expire,
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    return token


def decode_token(token: str, token_type: TokenType = "access_token") -> dict | None:

    secret_key = (
        settings.jwt_secret_key
        if token_type == "access_token"
        else settings.jwt_refresh_secret_key
    )

    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        if payload.get("type") != token_type:
            return None

        return payload

    except jwt.ExpiredSignatureError:
        print(f"{token_type} token has expired")
        return None

    except jwt.InvalidTokenError as error:
        print(f"Invalid {token_type} token: {error}")
        return None


def create_refresh_token(user_data: dict) -> str:
    now = datetime.now(UTC)

    payload = {
        **user_data,
        "type": "refresh",
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + timedelta(days=7),
    }

    return jwt.encode(
        payload,
        settings.jwt_refresh_secret_key,
        algorithm=settings.jwt_algorithm,
    )


# get current user
