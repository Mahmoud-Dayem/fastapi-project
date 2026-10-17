import uuid
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageOps

PROFILE_PICS_DIR = Path("media/profile_pics")
PROFILE_PICS_DIR.mkdir(parents=True, exist_ok=True)
MAX_PROFILE_IMAGE_BYTES = 5 * 1024 * 1024


def process_profile_image(content: bytes) -> str:
    with Image.open(BytesIO(content)) as original:
        if original.format not in {"JPEG", "PNG"}:
            raise ValueError("Only JPEG and PNG allowed")
        if original.width * original.height > 20_000_000:
            raise ValueError("Image dimensions too large")
        img = ImageOps.exif_transpose(original)
        img = ImageOps.fit(img, (300, 300), method=Image.Resampling.LANCZOS).convert("RGB")
        filename = f"{uuid.uuid4().hex}.jpg"
        img.save(PROFILE_PICS_DIR / filename, "JPEG", quality=85, optimize=True)
        return filename
