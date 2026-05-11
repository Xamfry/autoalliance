from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse

from src.app.db import init_db
from src.web.routes.courier import router as courier_router
from src.web.routes.auth import router as auth_router
from src.web.routes.admin import router as admin_router


app = FastAPI(title="AutoAlliance Courier")

templates = Jinja2Templates(directory="src/web/templates")

app.mount("/static", StaticFiles(directory="src/web/static"), name="static")

app.include_router(courier_router)
app.include_router(auth_router)
app.include_router(admin_router)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
def root():
    return RedirectResponse(url="/login", status_code=303)