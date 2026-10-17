import secrets

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from PIL import Image, UnidentifiedImageError
from starlette.datastructures import UploadFile

from database import SessionDep
from image_utils import MAX_PROFILE_IMAGE_BYTES, PROFILE_PICS_DIR, process_profile_image
from routers.auth_pages import get_browser_user, valid_csrf

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory="templates")


def render_profile(request, user, *, error=None, status_code=200, updated=False):
    csrf = request.cookies.get("csrf_token") or secrets.token_urlsafe(32)
    response = templates.TemplateResponse(
        request=request, name="profile.html",
        context={"title": "Your profile", "current_user": user,
                 "csrf_token": csrf, "error": error, "updated": updated},
        status_code=status_code,
    )
    response.set_cookie("csrf_token", csrf, httponly=True, samesite="lax",
                        secure=request.url.scheme == "https")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/profile", name="profile_page")
async def profile_page(request: Request, session: SessionDep):
    user = await get_browser_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return render_profile(request, user, updated=request.query_params.get("updated") == "1")


@router.post("/profile/image", name="profile_image_upload")
async def profile_image_upload(request: Request, session: SessionDep):
    user = await get_browser_user(request, session)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    async with request.form(max_files=1, max_fields=4) as form:
        if not valid_csrf(request, form):
            return render_profile(request, user, error="Please refresh the page and try again.", status_code=403)
        upload = form.get("image")
        if not isinstance(upload, UploadFile) or not upload.filename:
            return render_profile(request, user, error="Choose a JPEG or PNG image.", status_code=400)
        content = await upload.read(MAX_PROFILE_IMAGE_BYTES + 1)
        if len(content) > MAX_PROFILE_IMAGE_BYTES:
            return render_profile(request, user, error="Image must be 5 MB or smaller.", status_code=413)
        try:
            filename = process_profile_image(content)
        except (ValueError, UnidentifiedImageError, OSError, Image.DecompressionBombError):
            return render_profile(request, user, error="Choose a valid JPEG or PNG image with no more than 20 million pixels.", status_code=400)
    user.profile_image = filename
    session.add(user)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        (PROFILE_PICS_DIR / filename).unlink(missing_ok=True)
        raise
    return RedirectResponse("/profile?updated=1", status_code=303)
