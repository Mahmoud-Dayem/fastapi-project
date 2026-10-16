from datetime import UTC, datetime, timezone
from typing import TYPE_CHECKING

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel

# from models.post import PostPublic,PostModel

if TYPE_CHECKING:
    from models.post import PostModel


# What client sends
class UserCreate(SQLModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    


# Database table
class UserModel(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)

    username: str = Field(index=True, unique=True, max_length=50)
    email: EmailStr = Field(index=True, unique=True, max_length=255)

    hashed_password: str
    role: str  | None = Field(default="user")

    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)
    posts: list["PostModel"] = Relationship(back_populates="user")

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# What client receives
class UserPublic(SQLModel):
    # id: int
    username: str
    email: str
    # is_active: bool
    # is_admin: bool
    # created_at: datetime


class UserUpdate(SQLModel):
    email: EmailStr | None = None


class PassswordResetRequest(SQLModel):
    email: EmailStr


class PasswordResetToken(SQLModel, table=True):
    __tablename__ = "password_reset_tokens"

    id: int | None = Field(default=None, primary_key=True)

    user_id: int = Field(foreign_key="users.id", index=True)

    # token_hash: str = Field(unique=True, index=True)
    token: str = Field(unique=True, index=True)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    expires_at: datetime

    # used_at: datetime | None = Field(default=None)
    used: bool = Field(default=False)
