import asyncio
import unittest

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel

from app.auth import create_access_token
from database import get_session
from main import app
from models.post import PostModel
from models.user import UserModel


class PostPermissionsTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        async def setup():
            async with self.engine.begin() as connection:
                await connection.run_sync(SQLModel.metadata.create_all)
            async with AsyncSession(self.engine) as session:
                owner = UserModel(username="owner", email="owner@example.com", hashed_password="unused")
                other = UserModel(username="other", email="other@example.com", hashed_password="unused")
                session.add_all([owner, other])
                await session.flush()
                post = PostModel(title="Original title", content="Original content", author="Owner", user_id=owner.id)
                session.add(post)
                await session.commit()
                await session.refresh(post)
                self.post_id = post.id

        asyncio.run(setup())

        async def override_session():
            async with AsyncSession(self.engine) as session:
                yield session

        app.dependency_overrides[get_session] = override_session
        self.client = TestClient(app)
        self.client.cookies.set("csrf_token", "test-csrf")
        self.path = f"/posts/{self.post_id}"

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        asyncio.run(self.engine.dispose())

    def sign_in(self, email):
        self.client.cookies.set("access_token", create_access_token({"sub": email, "type": "access_token"}))

    def test_home_loads_six_posts_per_batch(self):
        async def add_posts():
            async with AsyncSession(self.engine) as session:
                session.add_all([
                    PostModel(title=f"Pagination post {i}", content="Content", author="Owner", user_id=1)
                    for i in range(12)
                ])
                await session.commit()
        asyncio.run(add_posts())
        import re
        seen = set()
        for offset, expected in [(0, 6), (6, 6), (12, 1)]:
            response = self.client.get("/", params={"offset": offset, "fragment": offset > 0})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.text.count('class="post-card"'), expected)
            links = set(re.findall(r'<a href="([^"]+)" class="post-link">', response.text))
            self.assertFalse(seen & links)
            seen.update(links)
            self.assertEqual('class="auth-button load-more-button"' in response.text, offset < 12)
        self.assertEqual(len(seen), 13)
        self.assertEqual(self.client.get("/?offset=-1").status_code, 422)

    def test_anonymous_and_non_owner_cannot_manage_post(self):
        data = {"title": "Changed title", "content": "Changed content", "csrf_token": "test-csrf"}
        for status, email in [(401, None), (403, "other@example.com")]:
            if email:
                self.sign_in(email)
            self.assertNotIn('class="post-actions"', self.client.get('/').text)
            self.assertNotIn('class="post-actions"', self.client.get(self.path).text)
            self.assertEqual(self.client.get(self.path + '/edit').status_code, status)
            self.assertEqual(self.client.post(self.path + '/edit', data=data).status_code, status)
            self.assertEqual(self.client.post(self.path + '/delete', data=data).status_code, status)
        self.assertIn("Original title", self.client.get(self.path).text)

    def test_owner_can_edit_and_delete_with_csrf(self):
        self.sign_in("owner@example.com")
        self.assertIn('class="post-actions"', self.client.get('/').text)
        self.assertIn('class="post-actions"', self.client.get(self.path).text)
        self.assertEqual(self.client.get(self.path + '/edit').status_code, 200)
        self.assertEqual(self.client.post(self.path + '/delete').status_code, 403)
        data = {"title": "Updated title", "content": "Updated content", "csrf_token": "test-csrf", "user_id": "999"}
        self.assertEqual(self.client.post(self.path + '/edit', data={**data, 'title': ''}).status_code, 422)
        self.assertEqual(self.client.post(self.path + '/edit', data={**data, 'csrf_token': ''}).status_code, 403)
        response = self.client.post(self.path + '/edit', data=data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Updated title", response.text)
        self.assertIn("Updated content", response.text)
        self.assertIn('class="post-actions"', response.text)
        self.assertEqual(self.client.post(self.path + '/delete', data=data).status_code, 200)
        self.assertEqual(self.client.get(self.path).status_code, 404)

    def test_post_title_character_limit(self):
        self.sign_in("owner@example.com")
        data = {"title": "x" * 101, "content": "Valid content", "csrf_token": "test-csrf"}
        self.assertEqual(self.client.post('/posts', data=data).status_code, 422)
        self.assertEqual(self.client.post(self.path + '/edit', data=data).status_code, 422)
        data["title"] = "x" * 100
        self.assertEqual(self.client.post('/posts', data=data).status_code, 201)
        self.assertEqual(self.client.post(self.path + '/edit', data=data, follow_redirects=False).status_code, 303)

    def test_create_post_requires_login_csrf_and_valid_fields(self):
        data = {"title": "New post", "content": "New content", "csrf_token": "test-csrf"}
        self.assertEqual(self.client.post('/posts', data=data).status_code, 401)
        self.sign_in("owner@example.com")
        self.assertIn('id="create-post-form"', self.client.get('/').text)
        self.assertEqual(self.client.post('/posts', data={**data, "csrf_token": ""}).status_code, 403)
        for field in ("title", "content"):
            self.assertEqual(self.client.post('/posts', data={**data, field: "   "}).status_code, 422)
        response = self.client.post('/posts', data={**data, "author": "other", "user_id": "999"})
        self.assertEqual(response.status_code, 201)
        page = self.client.get(response.json()["url"])
        self.assertEqual(page.status_code, 200)
        self.assertIn("New content", page.text)
        self.assertIn('class="post-actions"', page.text)

        async def check_author():
            async with AsyncSession(self.engine) as session:
                post = await session.get(PostModel, int(response.json()["url"].split('/')[-1]))
                self.assertEqual(post.author, "owner")
                self.assertEqual(post.user_id, 1)

        asyncio.run(check_author())


if __name__ == "__main__":
    unittest.main()
