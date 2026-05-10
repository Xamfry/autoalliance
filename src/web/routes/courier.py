import httpx
from fastapi import APIRouter, Depends, Query, Request, Form
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.autoalliance.models import SourceProduct
from src.ozon.models import OzonPosting, OzonPostingProduct, OzonShop
from src.ozon.client import OzonClient
from src.web.deps import get_db


router = APIRouter(prefix="/courier", tags=["courier"])
templates = Jinja2Templates(directory="src/web/templates")


COURIER_STATUS_RU = {
    None: "Новый",
    "new": "Новый",
    "collecting": "Собран",
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
        .outerjoin(SourceProduct, SourceProduct.article == OzonPostingProduct.offer_id)
        .order_by(OzonPosting.in_process_at.desc())
    )

    if status != "all":
        stmt = stmt.where(OzonPosting.status == status)

    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                OzonPosting.posting_number.ilike(like),
                OzonPostingProduct.offer_id.ilike(like),
                OzonPostingProduct.manufacturer_article.ilike(like),
                OzonPostingProduct.name.ilike(like),
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
            }
        )

    return rows


@router.get("", response_class=HTMLResponse)
def courier_page(
    request: Request,
    db: Session = Depends(get_db),
    status: str = Query("awaiting_packaging"),
    search: str = Query(""),
):
    rows = get_courier_rows(db, status=status, search=search)

    return templates.TemplateResponse(
        request=request,
        name="courier/index.html",
        context={
            "rows": rows,
            "status": status,
            "search": search,
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
):
    allowed = {"new", "collecting", "ready", "problem"}

    if courier_status in allowed:
        posting = db.get(OzonPosting, posting_id)

        if posting:
            posting.courier_status = courier_status
            db.commit()

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


@router.get("/list", response_class=HTMLResponse)
def courier_cards_partial(
    request: Request,
    db: Session = Depends(get_db),
    status: str = Query("awaiting_packaging"),
    search: str = Query(""),
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
    posting_id: int,
    db: Session = Depends(get_db),
    ):
    posting = db.get(OzonPosting, posting_id)

    allowed_ozon_statuses = {
        "awaiting_packaging",
        "awaiting_deliver",
    }

    if posting.status not in allowed_ozon_statuses:
        return Response(
            content=f"Стикер недоступен для статуса Ozon: {posting.status}",
            status_code=409,
            media_type="text/plain; charset=utf-8",
        )

    if not posting:
        return Response(
            "Отправление не найдено", 
            status_code=404,
            media_type="text/plain; charset=utf-8",)

    if posting.courier_status != "collecting":
        return Response(
            "Стикер доступен только после нажатия «Собрать»",
            status_code=403,
            media_type="text/plain; charset=utf-8",
        )

    shop = db.get(OzonShop, posting.shop_id)

    if not shop:
        return Response(
            "Магазин не найден", 
            status_code=404, 
            media_type="text/plain; charset=utf-8"
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
            return Response(
                content=f"Не удалось получить стикер: {exc}",
                status_code=502,
                media_type="text/plain; charset=utf-8",
            )

    filename = f"ozon_label_{posting.posting_number}.pdf"

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )

