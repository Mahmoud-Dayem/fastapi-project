import hashlib
import os
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta, timezone
from email.message import EmailMessage

import aiosmtplib
from fastapi import (
    APIRouter,
    BackgroundTasks,
    FastAPI,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import select
from sqlalchemy import update
from pydantic import EmailStr
from app.config import settings
from starlette.exceptions import HTTPException as StarletteHTTPException

from database import SessionDep, init_db
from image_utils import PROFILE_PICS_DIR
from models.post import PostCreate, PostModel, PostPublic
from models.user import PasswordResetToken, UserCreate, UserModel, UserPublic,PasswordResetTokennew

# from posts import posts
from routers import auth_pages, post_pages, profile_pages, users

ENV = os.getenv("ENV", "development")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    docs_url="/docs" if ENV == "development" else None,
    redoc_url="/redoc" if ENV == "development" else None,
    openapi_url="/openapi.json" if ENV == "development" else None,
    lifespan=lifespan,
)
app.include_router(users.router)
app.include_router(auth_pages.router)
app.include_router(post_pages.router)
app.include_router(profile_pages.router)
app.mount(
    "/media/profile_pics",
    StaticFiles(directory=str(PROFILE_PICS_DIR)),
    name="profile_images",
)

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)
templates = Jinja2Templates(directory="templates")


# @app.get("/", include_in_schema=False)
# async def root(request: Request):
#     response = templates.TemplateResponse(
#         request, "home.html", context={"posts": posts, "title": "Welcome to Home Page"}
#     )
#     print(request)
#     return response
# @app.get("/", response_model=list[PostPublic])
# async def root(request: Request, session: SessionDep):

#     statement = select(PostModel).order_by(PostModel.date_posted.desc())

#     result = await session.execute(statement)

#     posts = result.scalars().all()

#     return templates.TemplateResponse(
#         request,
#         "home.html",
#         context={
#             "posts": posts,
#             "title": "Welcome to Home Page",
#         },
#     )


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root(
    request: Request,
    session: SessionDep,
    user: auth_pages.current_user_public,
    offset: int = Query(default=0, ge=0),
    fragment: bool = False,
):

    page_size = 4
    statement = (
        select(PostModel)
        .order_by(PostModel.date_posted.desc(), PostModel.id.desc())
        .offset(offset)
        .limit(page_size + 1)
    )
    result = await session.execute(statement)
    batch = result.scalars().all()
    current_user = await auth_pages.get_browser_user(request, session)
    return templates.TemplateResponse(
        request,
        "post_batch.html" if fragment else "home.html",
        context={
            "posts": batch[:page_size],
            "has_more": len(batch) > page_size,
            "next_offset": offset + page_size,
            "offset": offset,
            "title": "Welcome to Home Page",
            "current_user": current_user,
            "csrf_token": request.cookies.get("csrf_token", ""),
        },
    )


@app.get("/posts/{post_id}", response_class=HTMLResponse, include_in_schema=False)
async def get_post(post_id: int, request: Request, session: SessionDep):
    post = await session.get(PostModel, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return templates.TemplateResponse(
        request=request,
        name="post.html",
        context={
            "post": post,
            "current_user": await auth_pages.get_browser_user(request, session),
            "csrf_token": request.cookies.get("csrf_token", ""),
        },
    )


# @app.get("/posts/{post_id}", include_in_schema=False)
# def get_post(post_id: int, request: Request):

#     for post in posts:
#         if post["id"] == post_id:
#             response = templates.TemplateResponse(
#                 request,
#                 "post.html",
#                 context={
#                     "post": post,
#                 },
#             )

#             return response

#     raise HTTPException(status_code=404, detail=f"Post with id {post_id} not found")
# response = templates.TemplateResponse(
#     request,
#     "error.html",
#     context={
#         "message": f"Post {post_id} not found",
#         "status_code": status.HTTP_404_NOT_FOUND,
#     },
#     status_code=status.HTTP_404_NOT_FOUND,
# )

# return response


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
):

    if exc.status_code == 404:
        return templates.TemplateResponse(
            request,
            "error.html",
            context={"message": str(exc.detail)},
            status_code=404,
        )

    return HTMLResponse(
        content=str(exc.detail),
        status_code=exc.status_code,
    )


@app.get("/api/posts", response_model=list[PostPublic])
async def get_posts_api(session: SessionDep):

    statement = select(PostModel).order_by(PostModel.date_posted.desc())

    result = await session.execute(statement)

    return result.scalars().all()


# @app.post("/send-email")
# async def send_email():

#     message = EmailMessage()

#     message["From"] = "admin@myapp.com"
#     message["To"] = "user@gmail.com"
#     message["Subject"] = "Reset Your Password"

#     message.set_content("Click here to reset your password.")

#     await aiosmtplib.send(
#         message,
#         hostname="localhost",
#         port=1025,
#     )

#     return {"message": "Email sent to Mailpit"}


async def send_reset_email(
    to_email: str,
    reset_link: str,
):
    message = EmailMessage()

    message["From"] = "admin@myapp.local"
    message["To"] = to_email
    message["Subject"] = "Reset Your Password"

    message.set_content(
        f"""
You requested a password reset.

Click the following link:

{reset_link}

This link expires in 15 minutes.

If you did not request this, ignore this email.
"""
    )

    await aiosmtplib.send(
        message,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        start_tls=False,
        use_tls=False,
    )


@app.post("/password-forget-request")
async def password_forget_request(
    email: EmailStr,
    session: SessionDep,
    background_tasks: BackgroundTasks,
):
    result = await session.execute(select(UserModel).where(UserModel.email == email))

    user = result.scalar_one_or_none()

    message = {"message": "If the account exists, a reset link has been sent."}

    if not user or not user.is_active:
        return message

    token = secrets.token_urlsafe(32)

    token_hash = hashlib.sha256(token.encode()).hexdigest()

    reset_record = PasswordResetTokennew(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        email=user.email,
    )

    recipient = user.email
    session.add(reset_record)
    await session.commit()

    reset_link = f"{settings.app_base_url.rstrip('/')}/reset-password?token={token}"

    background_tasks.add_task(
        send_reset_email,
        recipient,
        reset_link,
    )

    return message


def render_password_reset(request, token, *, error=None, status_code=200):
    csrf = request.cookies.get("csrf_token") or secrets.token_urlsafe(32)
    response = templates.TemplateResponse(
        request=request, name="reset_password.html",
        context={"title": "Reset password", "token": token, "csrf_token": csrf, "error": error},
        status_code=status_code,
    )
    response.set_cookie("csrf_token", csrf, httponly=True, samesite="lax", secure=request.url.scheme == "https")
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


async def find_reset_record(session, token):
    result = await session.execute(select(PasswordResetTokennew).where(
        PasswordResetTokennew.token_hash == hashlib.sha256(token.encode()).hexdigest(),
        PasswordResetTokennew.used == False,
        PasswordResetTokennew.expires_at > datetime.now(UTC),
    ))
    return result.scalar_one_or_none()


@app.get("/reset-password", response_class=HTMLResponse, include_in_schema=False)
async def reset_password_page(request: Request, session: SessionDep, token: str = ""):
    record = await find_reset_record(session, token)
    if not record:
        return render_password_reset(request, "", error="This reset link is invalid or expired. Request a new link.", status_code=400)
    return render_password_reset(request, token)


@app.post("/reset-password", include_in_schema=False)
async def reset_password_submit(request: Request, session: SessionDep):
    form = await request.form()
    token = str(form.get("token", ""))
    if not auth_pages.valid_csrf(request, form):
        return render_password_reset(request, token, error="Please refresh the page and try again.", status_code=403)
    record = await find_reset_record(session, token)
    if not record:
        return render_password_reset(request, "", error="This reset link is invalid or expired. Request a new link.", status_code=400)
    password = str(form.get("password", ""))
    if not 8 <= len(password) <= 100:
        return render_password_reset(request, token, error="Password must be between 8 and 100 characters.", status_code=422)
    if password != form.get("confirm_password"):
        return render_password_reset(request, token, error="Passwords do not match.", status_code=400)
    user = await session.get(UserModel, record.user_id)
    if not user or not user.is_active:
        return render_password_reset(request, "", error="This reset link is invalid or expired.", status_code=400)
    # Claim the token atomically so concurrent requests cannot reuse it.
    claimed = await session.execute(update(PasswordResetTokennew).where(
        PasswordResetTokennew.id == record.id,
        PasswordResetTokennew.used == False,
        PasswordResetTokennew.expires_at > datetime.now(UTC),
    ).values(used=True).execution_options(synchronize_session=False))
    if claimed.rowcount != 1:
        await session.rollback()
        return render_password_reset(request, "", error="This reset link is invalid or expired.", status_code=400)
    user.hashed_password = users.password_hash.hash(password)
    session.add(user)
    await session.execute(update(PasswordResetTokennew).where(
        PasswordResetTokennew.user_id == user.id,
    ).values(used=True).execution_options(synchronize_session=False))
    await session.commit()
    from fastapi.responses import RedirectResponse
    response = RedirectResponse("/login?reset=1", status_code=303)
    response.delete_cookie("access_token")
    return response


def render_forgot_password(request, *, error=None, sent=False, email="", status_code=200):
    csrf = request.cookies.get("csrf_token") or secrets.token_urlsafe(32)
    response = templates.TemplateResponse(
        request=request, name="forgot_password.html",
        context={"title": "Forgot password", "csrf_token": csrf,
                 "error": error, "sent": sent, "email": email},
        status_code=status_code,
    )
    response.set_cookie("csrf_token", csrf, httponly=True, samesite="lax", secure=request.url.scheme == "https")
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/forgot-password", response_class=HTMLResponse, include_in_schema=False)
async def forgot_password_page(request: Request, session: SessionDep):
    user = await auth_pages.get_browser_user(request, session)
    return render_forgot_password(request, email=user.email if user else "")


@app.post("/forgot-password", response_class=HTMLResponse, include_in_schema=False)
async def forgot_password_submit(request: Request, session: SessionDep, background_tasks: BackgroundTasks):
    from pydantic import TypeAdapter, ValidationError
    form = await request.form()
    email = str(form.get("email", "")).strip()
    if not auth_pages.valid_csrf(request, form):
        return render_forgot_password(request, email=email, error="Please refresh the page and try again.", status_code=403)
    try:
        email = TypeAdapter(EmailStr).validate_python(email)
    except ValidationError:
        return render_forgot_password(request, email=email, error="Enter a valid email address.", status_code=422)
    await password_forget_request(email, session, background_tasks)
    return render_forgot_password(request, sent=True)
