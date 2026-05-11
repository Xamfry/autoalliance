from fastapi import APIRouter, Depends, Form, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.web.auth import authenticate_user, create_session_token
from src.web.deps import get_db


router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="src/web/templates")


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    next_url: str = Query("/courier", alias="next"),
):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "title": "Вход",
            "error": None,
            "next_url": next_url,
        },
    )


@router.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    next_url: str = Form("/courier"),
):
    user = authenticate_user(db, username, password)

    if not user:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Неверный логин или пароль"},
            status_code=401,
        )

    if not next_url.startswith("/"):
        next_url = "/courier"

    response = RedirectResponse(url=next_url, status_code=303)
    response.set_cookie(
        key="session",
        value=create_session_token(user.id),
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session")
    return response