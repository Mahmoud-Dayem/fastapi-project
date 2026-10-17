from io import BytesIO
from pathlib import Path
from contextlib import contextmanager
from uuid import uuid4


@contextmanager
def image_directory():
    folder = Path("media") / uuid4().hex
    folder.mkdir()
    try:
        yield folder
    finally:
        for file in folder.iterdir():
            file.unlink()
        folder.rmdir()
from unittest.mock import patch

from PIL import Image
from test_post_permissions import PostPermissionsTest


class ProfileTest(PostPermissionsTest):
    def test_profile_upload_and_home_avatar(self):
        self.sign_in("owner@example.com")
        page = self.client.get("/profile")
        self.assertEqual(page.status_code, 200)
        self.assertIn("owner@example.com", page.text)
        self.assertNotIn("hashed_password", page.text)
        image = BytesIO()
        Image.new("RGB", (640, 400), "blue").save(image, "PNG")
        with image_directory() as folder:
            directory = Path(folder)
            with patch("image_utils.PROFILE_PICS_DIR", directory):
                response = self.client.post("/profile/image", data={"csrf_token": "test-csrf"},
                    files={"image": ("photo.png", image.getvalue(), "image/png")}, follow_redirects=False)
            self.assertEqual(response.status_code, 303)
            saved = list(directory.glob("*.jpg"))
            self.assertEqual(len(saved), 1)
            with Image.open(saved[0]) as avatar:
                self.assertEqual(avatar.size, (300, 300))
            self.assertIn(saved[0].name, self.client.get("/").text)
            self.assertIn(saved[0].name, self.client.get("/profile").text)
        self.sign_in("other@example.com")
        self.assertNotIn(saved[0].name, self.client.get("/").text)

    def test_profile_upload_access_and_validation(self):
        self.assertEqual(self.client.get("/profile", follow_redirects=False).status_code, 303)
        self.assertEqual(self.client.post("/profile/image", follow_redirects=False).status_code, 303)
        self.sign_in("owner@example.com")
        self.assertEqual(self.client.post("/profile/image").status_code, 403)
        for content, expected in [(b"invalid", 400), (b"x" * (5 * 1024 * 1024 + 1), 413)]:
            response = self.client.post("/profile/image", data={"csrf_token": "test-csrf"},
                files={"image": ("photo.png", content, "image/png")})
            self.assertEqual(response.status_code, expected)
