from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

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


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/login", status_code=303)

    if exc.status_code == 403:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "title": "Доступ запрещён",
                "message": "У вас нет прав для просмотра этой страницы.",
                "back_url": "/courier",
            },
            status_code=403,
        )

    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "title": "Ошибка",
            "message": str(exc.detail),
            "back_url": "/courier",
        },
        status_code=exc.status_code,
    )
