from typing import List, Optional

from pydantic import BaseModel, Field


class ApplicabilityItem(BaseModel):
    type_id: int = Field(alias="typeId")
    type_code: str = Field(alias="typeCode")
    mark_id: int = Field(alias="markId")
    mark_code: str = Field(alias="markCode")
    model_id: int = Field(alias="modelId")
    model_code: str = Field(alias="modelCode")
    group_number: int = Field(alias="groupNumber")
    mark_icon: str = Field(alias="markIcon")
    mark_name: str = Field(alias="markName")
    model_name: str = Field(alias="modelName")
    part_number: str = Field(alias="partNumber")
    part_name: str = Field(alias="partName")
    group_name: str = Field(alias="groupName")


class MarkItem(BaseModel):
    id: int
    code: Optional[str] = None
    name_short: str = Field(alias="nameShort")
    name_full: Optional[str] = Field(alias="nameFull")
    icon: Optional[str]
    html_full: Optional[str] = Field(alias="htmlFull")
    type_id: Optional[int] = Field(alias="typeId")
    type_code: Optional[str] = Field(alias="typeCode")
    type: Optional[str] = None
    brand_id: Optional[int] = Field(alias="brandId")
    has_relation_with_catalog: bool = Field(alias="hasRelationWithCatalog")


class ApplicabilitiesResponse(BaseModel):
    applicabilities: List[ApplicabilityItem]
    total_count: int = Field(alias="totalCount")
    marks: List[MarkItem]
    models: list
