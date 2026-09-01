from fastapi import FastAPI , Request
from fastapi.templating import Jinja2Templates
from posts import posts
app = FastAPI()


templates = Jinja2Templates(directory = "templates")

@app.get("/")
async def root(request:Request):
    response = templates.TemplateResponse(request,"home.html",context={
        "posts":posts,
        'title':"Welcome to Home Page"
    })

    return response

@app.get("/api/posts")
def get_posts():
    return posts
 