import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from models.user import PasswordResetTokennew, UserModel
from routers.users import password_hash
from test_post_permissions import PostPermissionsTest


class PasswordResetTest(PostPermissionsTest):
    def test_forgot_password_form(self):
        self.assertIn("Forgot password?", self.client.get("/login").text)
        self.assertEqual(self.client.get("/forgot-password").status_code, 200)
        self.assertEqual(self.client.post("/forgot-password", data={"email": "owner@example.com"}).status_code, 403)
        self.assertEqual(self.client.post("/forgot-password", data={"email": "invalid", "csrf_token": "test-csrf"}).status_code, 422)
        with patch("main.send_reset_email", new_callable=AsyncMock) as send:
            response = self.client.post("/forgot-password", data={"email": "owner@example.com", "csrf_token": "test-csrf"})
            self.assertEqual(response.status_code, 200)
            self.assertIn("If the account exists", response.text)
            send.assert_awaited_once()

    def test_reset_link_and_single_use(self):
        with patch("main.send_reset_email", new_callable=AsyncMock) as send:
            response = self.client.post("/password-forget-request", params={"email": "owner@example.com"})
            self.assertEqual(response.status_code, 200)
            link = send.call_args.args[1]
            token = parse_qs(urlsplit(link).query)["token"][0]
            self.assertEqual(send.call_args.args[0], "owner@example.com")
            self.assertEqual(self.client.get(link).status_code, 200)
            data = {"token": token, "csrf_token": "test-csrf", "password": "new-password-123", "confirm_password": "new-password-123"}
            self.assertEqual(self.client.post("/reset-password", data={**data, "csrf_token": ""}).status_code, 403)
            self.assertEqual(self.client.post("/reset-password", data={**data, "password": "short"}).status_code, 422)
            response = self.client.post("/reset-password", data=data, follow_redirects=False)
            self.assertEqual(response.status_code, 303)
            self.assertEqual(self.client.post("/reset-password", data=data).status_code, 400)
            self.assertEqual(self.client.get(link).status_code, 400)
        async def check():
            async with AsyncSession(self.engine) as session:
                user = await session.get(UserModel, 1)
                self.assertTrue(password_hash.verify("new-password-123", user.hashed_password))
                record = (await session.execute(select(PasswordResetTokennew))).scalar_one()
                self.assertEqual(record.token_hash, hashlib.sha256(token.encode()).hexdigest())
                self.assertTrue(record.used)
        asyncio.run(check())

    def test_unknown_email_and_expired_token(self):
        with patch("main.send_reset_email", new_callable=AsyncMock) as send:
            response = self.client.post("/password-forget-request", params={"email": "unknown@example.com"})
            self.assertEqual(response.status_code, 200)
            send.assert_not_called()
        self.assertEqual(self.client.get("/reset-password?token=invalid").status_code, 400)
        async def expired():
            async with AsyncSession(self.engine) as session:
                session.add(PasswordResetTokennew(user_id=1, email="owner@example.com", token_hash=hashlib.sha256(b"expired").hexdigest(), expires_at=datetime.now(UTC)-timedelta(minutes=1)))
                await session.commit()
        asyncio.run(expired())
        self.assertEqual(self.client.get("/reset-password?token=expired").status_code, 400)
