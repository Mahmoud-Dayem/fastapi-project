import os
from contextlib import asynccontextmanager
from email.message import EmailMessage

import aiosmtplib
from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import select
from starlette.exceptions import HTTPException as StarletteHTTPException

from database import SessionDep, init_db
from image_utils import PROFILE_PICS_DIR
from models.post import PostCreate, PostModel, PostPublic

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


@app.post("/send-email")
async def send_email():

    message = EmailMessage()

    message["From"] = "admin@myapp.com"
    message["To"] = "user@gmail.com"
    message["Subject"] = "Reset Your Password"

    message.set_content("Click here to reset your password.")

    await aiosmtplib.send(
        message,
        hostname="localhost",
        port=1025,
    )

    return {"message": "Email sent to Mailpit"}
