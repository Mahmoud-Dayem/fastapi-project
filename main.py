from fastapi import FastAPI , Request
from fastapi.templating import Jinja2Templates
from posts import posts
app = FastAPI()


tempaltes = Jinja2Templates(directory = "templates")

@app.get("/")
async def root():
    return f"<h1>{posts[5]['title']}</h1>"

@app.get("/api/posts")
def get_posts():
    return posts
 