import asyncio
from typing import Annotated

import models.user
from fastapi import Depends
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlmodel import Session, SQLModel

from models.post import PostCreate, PostModel, PostPublic

sqlite_file_name = "database.db"
sqlite_url = f"sqlite+aiosqlite:///{sqlite_file_name}"

engine = create_async_engine(sqlite_url, echo=True)


@event.listens_for(engine.sync_engine, "connect")
def enable_foreign_keys(dpapi_connection, connection_record):
    dpapi_connection.execute("PRAGMA foreign_keys=ON")


async def init_db():

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        # create_all does not add columns to existing SQLite tables.
        columns = await conn.execute(text("PRAGMA table_info(users)"))
        if "profile_image" not in {row[1] for row in columns}:
            await conn.execute(text("ALTER TABLE users ADD COLUMN profile_image VARCHAR"))


async def get_session():
    async with AsyncSession(engine) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
