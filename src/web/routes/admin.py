from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.web.auth import hash_password
from src.web.deps import get_db, require_admin
from src.web.models import WebUser, CourierActionLog


router = APIRouter(
    prefix="/admin",
    tags=["admin"],
)

templates = Jinja2Templates(directory="src/web/templates")

COURIER_STATUS_RU = {
    None: "Новый",
    "new": "Новый",
    "collecting": "Собирается",
    "ready": "Готово",
    "problem": "Проблема",
}   


@router.get("", response_class=HTMLResponse)
def admin_index(
    request: Request,
    admin: WebUser = Depends(require_admin),
):
    return templates.TemplateResponse(
        request=request,
        name="admin/index.html",
        context={
            "title": "Админ-панель",
            "admin": admin,
        },
    )


@router.get("/users", response_class=HTMLResponse)
def users_page(
    request: Request,
    db: Session = Depends(get_db),
    admin: WebUser = Depends(require_admin),
):
    users = db.scalars(
        select(WebUser).order_by(WebUser.id.asc())
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="admin/users.html",
        context={
            "title": "Пользователи",
            "admin": admin,
            "users": users,
        },
    )


@router.post("/users/create")
def create_user(
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),
    admin: WebUser = Depends(require_admin),
):
    allowed_roles = {"admin", "courier"}

    if role not in allowed_roles:
        return RedirectResponse("/admin/users", status_code=303)

    existing = db.scalar(
        select(WebUser).where(WebUser.username == username)
    )

    if existing:
        return RedirectResponse("/admin/users", status_code=303)

    user = WebUser(
        username=username,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )

    db.add(user)
    db.commit()

    return RedirectResponse("/admin/users", status_code=303)


@router.post("/users/{user_id}/toggle")
def toggle_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: WebUser = Depends(require_admin),
):
    user = db.get(WebUser, user_id)

    if user:
        user.is_active = not user.is_active
        db.commit()

    if user_id == admin.id:
        return RedirectResponse("/admin/users", status_code=303)

    return RedirectResponse("/admin/users", status_code=303)


@router.get("/logs", response_class=HTMLResponse)
def logs_page(
    request: Request,
    db: Session = Depends(get_db),
    admin: WebUser = Depends(require_admin),
):
    logs = db.scalars(
        select(CourierActionLog)
        .order_by(CourierActionLog.created_at.desc())
        .limit(200)
    ).all()

    for log in logs:
        log.old_status_ru = COURIER_STATUS_RU.get(
            log.old_status,
            log.old_status or "-",
        )

        log.new_status_ru = COURIER_STATUS_RU.get(
            log.new_status,
            log.new_status or "-",
        )

        if log.action == "change_courier_status":
            log.action_ru = "Изменение статуса"
        else:
            log.action_ru = log.action

    return templates.TemplateResponse(
        request=request,
        name="admin/logs.html",
        context={
            "title": "Журнал действий",
            "admin": admin,
            "logs": logs,
        },
    )


@router.get("/logs/list", response_class=HTMLResponse)
def logs_list_partial(
    request: Request,
    db: Session = Depends(get_db),
    admin: WebUser = Depends(require_admin),
):
    logs = db.scalars(
        select(CourierActionLog)
        .order_by(CourierActionLog.created_at.desc())
        .limit(200)
    ).all()

    for log in logs:
        log.old_status_ru = COURIER_STATUS_RU.get(
            log.old_status,
            log.old_status or "-",
        )

        log.new_status_ru = COURIER_STATUS_RU.get(
            log.new_status,
            log.new_status or "-",
        )

        if log.action == "change_courier_status":
            log.action_ru = "Изменение статуса"
        else:
            log.action_ru = log.action

    return templates.TemplateResponse(
        request=request,
        name="admin/_logs_table.html",
        context={
            "logs": logs,
            "admin": admin,
        },
    )
