from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from database import SessionDep
from models.post import PostBase, PostModel
from routers.auth_pages import get_browser_user, valid_csrf

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory="templates")


@router.post("/posts", name="create_post")
async def create_post(request: Request, session: SessionDep):
    user = await get_browser_user(request, session)
    if not user:
        return JSONResponse({"detail": "Please log in to create a post."}, status_code=401)
    form = await request.form()
    if not valid_csrf(request, form):
        return JSONResponse({"detail": "Please refresh the page and try again."}, status_code=403)
    values = {key: str(form.get(key, "")).strip() for key in ("title", "content")}
    try:
        validated = PostBase(author=user.username, **values)
    except ValidationError as exc:
        error = " ".join(f"{e['loc'][0].capitalize()}: {e['msg']}" for e in exc.errors())
        return JSONResponse({"detail": error}, status_code=422)
    post = PostModel(**validated.model_dump(), user_id=user.id)
    session.add(post)
    await session.commit()
    await session.refresh(post)
    return JSONResponse({"url": f"/posts/{post.id}"}, status_code=201)


async def owned_post(request, session, post_id):
    user = await get_browser_user(request, session)
    if not user:
        raise HTTPException(status_code=401, detail="Please log in to manage posts.")
    post = await session.get(PostModel, post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.user_id != user.id:
        raise HTTPException(status_code=403, detail="You can only manage your own posts.")
    return post, user


def edit_response(request, post, user, *, values=None, error=None, status_code=200):
    return templates.TemplateResponse(
        request=request, name="edit_post.html", status_code=status_code,
        context={"title": "Edit post", "post": post, "current_user": user,
                 "csrf_token": request.cookies.get("csrf_token", ""),
                 "values": values if values is not None else {"title": post.title, "content": post.content},
                 "error": error})


@router.get("/posts/{post_id}/edit", name="edit_post")
async def edit_post(post_id: int, request: Request, session: SessionDep):
    post, user = await owned_post(request, session, post_id)
    return edit_response(request, post, user)


@router.post("/posts/{post_id}/edit", name="update_post")
async def update_post(post_id: int, request: Request, session: SessionDep):
    post, user = await owned_post(request, session, post_id)
    form = await request.form()
    if not valid_csrf(request, form):
        raise HTTPException(status_code=403, detail="Please refresh the page and try again.")
    values = {key: str(form.get(key, "")).strip() for key in ("title", "content")}
    try:
        validated = PostBase(author=post.author, **values)
    except ValidationError as exc:
        error = " ".join(f"{e['loc'][0].capitalize()}: {e['msg']}" for e in exc.errors())
        return edit_response(request, post, user, values=values, error=error, status_code=422)
    post.title = validated.title
    post.content = validated.content
    await session.commit()
    return RedirectResponse(f"/posts/{post_id}", status_code=303)


@router.post("/posts/{post_id}/delete", name="delete_post")
async def delete_post(post_id: int, request: Request, session: SessionDep):
    post, _ = await owned_post(request, session, post_id)
    form = await request.form()
    if not valid_csrf(request, form):
        raise HTTPException(status_code=403, detail="Please refresh the page and try again.")
    await session.delete(post)
    await session.commit()
    return RedirectResponse("/", status_code=303)
