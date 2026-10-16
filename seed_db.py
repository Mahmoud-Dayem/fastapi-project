"""Load the sample rooms into database.db: python seed_db.py."""

import asyncio

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import engine, init_db
from models.post import PostModel as Post
from posts import posts


async def seed_rooms() -> int:
    """Insert missing rooms and return the number added."""

    await init_db()

    async with AsyncSession(engine) as session:
        result = await session.exec(select(Post.id))
        existing_ids = set(result.all())

        new_post = [
            Post.model_validate(data) for data in posts if data["id"] not in existing_ids
        ]

        session.add_all(new_post)

        await session.commit()

        return len(new_post)


if __name__ == "__main__":
    inserted = asyncio.run(seed_rooms())
    print(f"Inserted {inserted} rooms into database.db.")
