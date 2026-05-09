from datetime import datetime, timedelta, timezone
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, AliasChoices


class PostingRequestLastChangedStatusDate(BaseModel):
    from_date: datetime = Field(..., alias="from")
    to_date: datetime = Field(..., alias="to")


class PostingRequestFilter(BaseModel):
    delivery_method_id: Optional[List[str]] = None
    is_quantum: Optional[bool] = None
    last_changed_status_date: Optional[PostingRequestLastChangedStatusDate] = None
    order_id: Optional[int] = None
    provider_id: Optional[List[str]] = None
    since: str
    to: str
    status: Optional[str] = None
    warehouse_id: Optional[List[str]] = None


class PostingRequestWith(BaseModel):
    analytics_data: Optional[bool] = None
    barcodes: Optional[bool] = None
    financial_data: Optional[bool] = None
    translit: Optional[bool] = None


class PostingRequest(BaseModel):
    dir: Literal["asc", "desc"] = "asc"
    filter: PostingRequestFilter
    limit: int = 1000
    offset: int = 0
    with_: Optional[PostingRequestWith] = Field(
        None, validation_alias=AliasChoices("with", "with_"), serialization_alias="with"
    )


    @classmethod
    def since_24h_request(cls):
        since = datetime.now(tz=timezone.utc) - timedelta(hours=24)
        to = datetime.now(tz=timezone.utc)
        return cls.date_interval_request(since, to)


    @classmethod
    def since_week_request(cls):
        since = datetime.now(tz=timezone.utc) - timedelta(weeks=1)
        to = datetime.now(tz=timezone.utc)
        return cls.date_interval_request(since, to)


    @classmethod
    def since_days_request(cls, days=1):
        since = datetime.now(tz=timezone.utc) - timedelta(days=days)
        to = datetime.now(tz=timezone.utc)
        return cls.date_interval_request(since, to)


    @classmethod
    def since_month_request(cls):
        since = datetime.now(tz=timezone.utc) - timedelta(days=31)
        to = datetime.now(tz=timezone.utc)
        return cls.date_interval_request(since, to)


    @classmethod
    def date_interval_request(cls, since: datetime, to: datetime):
        return PostingRequest(
            limit=1000,
            filter=PostingRequestFilter(since=since.isoformat(), to=to.isoformat()),
            with_=PostingRequestWith(
                financial_data=True, analytics_data=True, barcodes=True
            ),
        )
