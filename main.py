from fastapi import FastAPI , Request
from fastapi.templating import Jinja2Templates
from posts import posts
import os 
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
ENV = os.getenv("ENV", "development")

app = FastAPI(
    docs_url="/docs" if ENV == "development" else None,
    redoc_url="/redoc" if ENV == "development" else None,
    openapi_url="/openapi.json" if ENV == "development" else None,
)
 


templates = Jinja2Templates(directory = "templates")

@app.get("/")
async def root(request:Request):
    response = templates.TemplateResponse(request,"home.html",context={
        "posts":posts,
        'title':"Welcome to Home Page"
    })
    print(request)
    return response

@app.get("/api/posts")
def get_posts():
    return posts
 
 
 

@app.get("/posts/{post_id}")
def get_post(post_id: int,   request: Request):

    print(f"user requested post {post_id}")

    for post in posts:
        if post["id"] == post_id:
            response = templates.TemplateResponse(request,"post.html",context={
                "post":post,
             })
            print(post)
            return response

    raise HTTPException(
        status_code=404,
        detail=f"Post with id {post_id} not found"
    )


 