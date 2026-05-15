import httpx
from pathlib import Path
from fastapi import APIRouter, Depends, Query, Request, Form
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.autoalliance.models import SourceProduct
from src.ozon.models import OzonPosting, OzonPostingProduct, OzonShop
from src.ozon.client import OzonClient
from src.web.deps import get_db, get_current_user
from src.web.models import WebUser, CourierActionLog


router = APIRouter(prefix="/courier", tags=["courier"])
templates = Jinja2Templates(directory="src/web/templates")


COURIER_STATUS_RU = {
    None: "Новый",
    "new": "Новый",
    "collecting": "Собирается",
    "ready": "Готово",
    "problem": "Проблема",
}


def _status_to_ru(status: str | None) -> str:
    statuses = {
        "acceptance_in_progress": "Идёт приёмка",
        "arbitration": "Арбитраж",
        "awaiting_approve": "Ожидает подтверждения",
        "awaiting_deliver": "Ожидает отгрузки",
        "awaiting_packaging": "Ожидает сборки",
        "awaiting_registration": "Ожидает регистрации",
        "awaiting_verification": "Создано",
        "cancelled": "Отменено",
        "cancelled_from_split_pending": "Отменено после разделения",
        "client_arbitration": "Клиентский арбитраж",
        "delivering": "Доставляется",
        "driver_pickup": "У водителя",
        "not_accepted": "Не принято",
        "delivered": "Доставлено",
    }

    return statuses.get(status or "", status or "-")


def get_courier_rows(
    db: Session,
    *,
    status: str = "awaiting_packaging",
    search: str = "",
    ):
    stmt = (
        select(
            OzonPosting,
            OzonPostingProduct,
            OzonShop,
            SourceProduct,
        )
        .join(OzonPostingProduct, OzonPostingProduct.posting_id == OzonPosting.id)
        .join(OzonShop, OzonShop.id == OzonPosting.shop_id)
        .outerjoin(
            SourceProduct,
            or_(
                SourceProduct.article == OzonPostingProduct.offer_id,
                SourceProduct.manufacturer_article == OzonPostingProduct.offer_id,
                SourceProduct.factory_article == OzonPostingProduct.offer_id,
                SourceProduct.article == OzonPostingProduct.manufacturer_article,
                SourceProduct.manufacturer_article == OzonPostingProduct.manufacturer_article,
                SourceProduct.factory_article == OzonPostingProduct.manufacturer_article,
            ),
        )
        .order_by(OzonPosting.in_process_at.desc())
    )

    if status != "all":
        stmt = stmt.where(OzonPosting.status == status)

    if search:
        like = f"%{search.strip()}%"

        stmt = stmt.where(
            or_(
                OzonPosting.posting_number.ilike(like),
                OzonPosting.order_number.ilike(like),

                OzonPostingProduct.offer_id.ilike(like),
                OzonPostingProduct.manufacturer_article.ilike(like),
                OzonPostingProduct.name.ilike(like),

                SourceProduct.article.ilike(like),
                SourceProduct.manufacturer_article.ilike(like),
                SourceProduct.factory_article.ilike(like),
                SourceProduct.source_code.ilike(like),
                SourceProduct.source_name.ilike(like),
            )
        )

    result = db.execute(stmt).all()

    rows = []

    for posting, product, shop, source_product in result:
        rows.append(
            {
                "posting_id": posting.id,
                "posting_number": posting.posting_number,
                "status": posting.status,
                "status_ru": _status_to_ru(posting.status),
                "in_process_at": posting.in_process_at,
                "shipment_date": posting.shipment_date,
                "shop_name": shop.shop_name,
                "offer_id": product.offer_id,
                "manufacturer_article": (
                    source_product.manufacturer_article
                    if source_product
                    else None
                ),
                "name": product.name,
                "quantity": product.quantity,
                "image_url": product.image_url,
                "courier_status": posting.courier_status or "new",
                "courier_status_ru": COURIER_STATUS_RU.get(posting.courier_status, 
                                                           posting.courier_status or "Новый"),
                "created_at": posting.in_process_at,
                "courier_username": posting.courier_username,
            }
        )

    return rows


@router.get("", response_class=HTMLResponse)
def courier_page(
    request: Request,
    db: Session = Depends(get_db),
    status: str = Query("awaiting_packaging"),
    search: str = Query(""),
    user: WebUser = Depends(get_current_user),
):
    rows = get_courier_rows(db, status=status, search=search)

    return templates.TemplateResponse(
        request=request,
        name="courier/index.html",
        context={
            "title": "Страница курьера",
            "rows": rows,
            "status": status,
            "search": search,
            "user": user,
        },
    )


@router.post("/posting/{posting_id}/status", response_class=HTMLResponse)
def update_courier_status(
    request: Request,
    posting_id: int,
    courier_status: str = Form(...),
    db: Session = Depends(get_db),
    status: str = Query("awaiting_packaging"),
    search: str = Query(""),
    user: WebUser = Depends(get_current_user),
):
    allowed = {"new", "collecting", "ready", "problem"}

    if courier_status not in allowed:
        rows = get_courier_rows(db, status=status, search=search)

        return templates.TemplateResponse(
            request=request,
            name="courier/_cards.html",
            context={
                "rows": rows,
                "status": status,
                "search": search,
                "user": user,
            },
        )

    posting = db.get(OzonPosting, posting_id)

    if posting:
        old_status = posting.courier_status

        posting.courier_status = courier_status

        if courier_status == "collecting":
            posting.courier_user_id = user.id
            posting.courier_username = user.username

        if courier_status == "ready":
            if not posting.courier_user_id:
                posting.courier_user_id = user.id
                posting.courier_username = user.username

        log_item = CourierActionLog(
            user_id=user.id,
            username=user.username,
            posting_id=posting.id,
            posting_number=posting.posting_number,
            action="change_courier_status",
            old_status=old_status,
            new_status=courier_status,
        )

        db.add(log_item)
        db.commit()

    rows = get_courier_rows(db, status=status, search=search)

    return templates.TemplateResponse(
        request=request,
        name="courier/_cards.html",
        context={
            "rows": rows,
            "status": status,
            "search": search,
            "user": user,
        },
    )


@router.get("/list", response_class=HTMLResponse)
def courier_cards_partial(
    request: Request,
    db: Session = Depends(get_db),
    status: str = Query("awaiting_packaging"),
    search: str = Query(""),
    user: WebUser = Depends(get_current_user),
):
    rows = get_courier_rows(db, status=status, search=search)

    return templates.TemplateResponse(
        request=request,
        name="courier/_cards.html",
        context={
            "rows": rows,
            "status": status,
            "search": search,
        },
    )


@router.get("/posting/{posting_id}/label")
async def download_posting_label(
    request: Request,
    posting_id: int,
    db: Session = Depends(get_db),
    user: WebUser = Depends(get_current_user),
):
    posting = db.get(OzonPosting, posting_id)

    if not posting:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "title": "Стикер не найден",
                "message": "Отправление не найдено.",
                "back_url": "/courier",
            },
            status_code=404,
        )

    if posting.courier_status != "collecting":
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "title": "Стикер недоступен",
                "message": "Стикер доступен только после нажатия «Собрать».",
                "back_url": "/courier",
            },
            status_code=403,
        )

    allowed_ozon_statuses = {
        "awaiting_packaging",
        "awaiting_deliver",
    }

    if posting.status not in allowed_ozon_statuses:
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "title": "Стикер недоступен",
                "message": f"Стикер недоступен для статуса Ozon: {posting.status}",
                "back_url": "/courier",
            },
            status_code=409,
        )

    labels_dir = Path("data/labels")
    labels_dir.mkdir(parents=True, exist_ok=True)

    label_path = labels_dir / f"{posting.posting_number}.pdf"

    if label_path.exists() and label_path.stat().st_size > 0:
        pdf = label_path.read_bytes()
    else:
        shop = db.get(OzonShop, posting.shop_id)

        if not shop:
            return templates.TemplateResponse(
                request=request,
                name="error.html",
                context={
                    "title": "Магазин не найден",
                    "message": "Магазин для отправления не найден.",
                    "back_url": "/courier",
                },
                status_code=404,
            )

        headers = {
            "Client-Id": shop.client_id,
            "Api-Key": shop.token,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(
            base_url="https://api-seller.ozon.ru",
            headers=headers,
            timeout=60,
        ) as http_client:
            client = OzonClient(http_client=http_client, shop=shop)

            try:
                pdf = await client.get_fbs_package_label_pdf_with_wait(
                    posting_numbers=[posting.posting_number],
                    attempts=8,
                    delay_seconds=2,
                )
            except Exception as exc:
                return templates.TemplateResponse(
                    request=request,
                    name="error.html",
                    context={
                        "title": "Ошибка получения стикера",
                        "message": f"Не удалось получить стикер: {exc}",
                        "back_url": "/courier",
                    },
                    status_code=502,
                )

        label_path.write_bytes(pdf)

    filename = f"ozon_label_{posting.posting_number}.pdf"

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
