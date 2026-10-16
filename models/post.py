from datetime import date
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from models.user import UserModel


class PostBase(SQLModel):
    author: str = Field(min_length=2, max_length=100)
    title: str = Field(min_length=3, max_length=100)
    content: str = Field(min_length=1)
    
   


class PostModel(PostBase, table=True):
    __tablename__ = "posts"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    date_posted: date = Field(default_factory=date.today)
    user: "UserModel" = Relationship(back_populates="posts")


class PostCreate(PostBase):
    pass


class PostPublic(PostBase):
    # model_config = ConfigDict(from_attributes=True)

    id: int
    user_id:int
    date_posted: date
