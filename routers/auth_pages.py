import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.auth import create_access_token, decode_token
from app.config import settings
from database import SessionDep
from models.user import UserCreate, UserModel, UserPublic
from routers.users import DUMMY_HASHED_PASSWORD, password_hash

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory="templates")


async def get_browser_user(request: Request, session):
    token = request.cookies.get("access_token")
    payload = decode_token(token) if token else None
    if not payload or not payload.get("sub"):
        return None
    result = await session.execute(
        select(UserModel).where(
            UserModel.email == payload["sub"], UserModel.is_active == True
        )
    )
    return result.scalar_one_or_none()


def render_form(request, page, *, error=None, values=None, status_code=200):
    csrf = request.cookies.get("csrf_token") or secrets.token_urlsafe(32)
    response = templates.TemplateResponse(
        request=request,
        name=f"{page}.html",
        context={
            "title": "Log in" if page == "login" else "Create account",
            "error": error,
            "values": values or {},
            "csrf_token": csrf,
        },
        status_code=status_code,
    )
    response.set_cookie(
        "csrf_token",
        csrf,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def valid_csrf(request, form):
    cookie = request.cookies.get("csrf_token", "")
    return bool(cookie) and secrets.compare_digest(
        cookie, str(form.get("csrf_token", ""))
    )


@router.get("/login", name="login_page")
async def login_page(request: Request):
    return render_form(request, "login")


@router.get("/signup", name="signup_page")
async def signup_page(request: Request):
    return render_form(request, "signup")


@router.post("/signup", name="signup_submit")
async def signup_submit(request: Request, session: SessionDep):

    form = await request.form()
    values = {key: str(form.get(key, "")).strip() for key in ("username", "email")}
    values["username"] = values["username"].lower()
    values["email"] = values["email"].lower()
    if not valid_csrf(request, form):
        return render_form(
            request,
            "signup",
            error="Please refresh the page and try again.",
            status_code=403,
        )
    try:
        user = UserCreate(**values, password=str(form.get("password", "")))
    except ValidationError as exc:
        error = " ".join(
            f"{e['loc'][0].capitalize()}: {e['msg']}" for e in exc.errors()
        )
        return render_form(
            request, "signup", error=error, values=values, status_code=422
        )
    if user.password != form.get("confirm_password"):
        return render_form(
            request,
            "signup",
            error="Passwords do not match.",
            values=values,
            status_code=400,
        )
    existing = await session.execute(
        select(UserModel).where(
            (UserModel.username == user.username) | (UserModel.email == user.email)
        )
    )
    if existing.first():
        return render_form(
            request,
            "signup",
            error="That username or email is already registered.",
            values=values,
            status_code=400,
        )
    session.add(
        UserModel(
            username=user.username,
            email=user.email,
            hashed_password=password_hash.hash(user.password),
        )
    )
    try:
        await session.commit()

    except IntegrityError:
        await session.rollback()
        return render_form(
            request,
            "signup",
            error="That username or email is already registered.",
            values=values,
            status_code=400,
        )
    return RedirectResponse("/login?registered=1", status_code=303)


@router.post("/login", name="login_submit")
async def login_submit(request: Request, session: SessionDep):
    form = await request.form()
    values = {"email": str(form.get("email", "")).strip()}
    if not valid_csrf(request, form):
        return render_form(
            request,
            "login",
            error="Please refresh the page and try again.",
            status_code=403,
        )
    result = await session.execute(
        select(UserModel).where(UserModel.email == values["email"])
    )
    user = result.scalar_one_or_none()
    valid = password_hash.verify(
        str(form.get("password", "")),
        user.hashed_password if user else DUMMY_HASHED_PASSWORD,
    )
    if not valid or not user or not user.is_active:
        return render_form(
            request,
            "login",
            error="Invalid email or password.",
            values=values,
            status_code=401,
        )
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        "access_token",
        create_access_token({"sub": user.email, "type": "access_token"}),
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        max_age=settings.jwt_access_token_expire_minutes * 60,
    )
    return response


@router.post("/logout", name="logout")
async def logout(request: Request):
    form = await request.form()
    if not valid_csrf(request, form):
        return render_form(
            request,
            "login",
            error="Please refresh the page and try again.",
            status_code=403,
        )
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("access_token")
    return response


# routers/auth_pages.py
async def get_public_browser_user(request: Request, session: SessionDep):
    user = await get_browser_user(request, session)
    if user is None:
        return None
    return UserPublic.model_validate(user, from_attributes=True)


current_user_public = Annotated[
    UserPublic | None, Depends(get_public_browser_user)
]

 
