from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.app.db import init_db
from src.web.routes.courier import router as courier_router


app = FastAPI(title="AutoAlliance Courier")

templates = Jinja2Templates(directory="src/web/templates")

app.mount("/static", StaticFiles(directory="src/web/static"), name="static")

app.include_router(courier_router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
def root():
    return {"status": "ok", "page": "/courier"}