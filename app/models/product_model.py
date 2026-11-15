from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.shared.constants import ProductConstants


def _clean_text(value: Optional[str]) -> Optional[str]:
    """Trim whitespace; ``None`` stays ``None``."""
    return value.strip() if isinstance(value, str) else value


class ProductBase(BaseModel):
    """Fields shared by create and update — mirrors the Django ``Product`` model."""

    name: str = Field(min_length=1, max_length=ProductConstants.NAME_MAX_LENGTH)
    description: str = Field(default="", max_length=ProductConstants.DESCRIPTION_MAX_LENGTH)
    price: Decimal = Field(ge=0, le=ProductConstants.PRICE_MAX, decimal_places=2)
    stock: int = Field(default=0, ge=0)
    # Manual switch: staff mark a medicine out of stock without changing the count.
    is_out_of_stock: bool = False
    category: str = Field(default="", max_length=ProductConstants.CATEGORY_MAX_LENGTH)
    is_available: bool = True

    _strip = field_validator("name", "description", "category", mode="before")(_clean_text)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("name must not be blank")
        return value


class ProductCreate(ProductBase):
    """Body of ``POST /products`` (sent as multipart form fields + optional image)."""


class ProductUpdate(BaseModel):
    """Body of ``PUT /products/{id}``: every field optional, only those sent change."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=ProductConstants.NAME_MAX_LENGTH)
    description: Optional[str] = Field(default=None, max_length=ProductConstants.DESCRIPTION_MAX_LENGTH)
    price: Optional[Decimal] = Field(default=None, ge=0, le=ProductConstants.PRICE_MAX, decimal_places=2)
    stock: Optional[int] = Field(default=None, ge=0)
    is_out_of_stock: Optional[bool] = None
    category: Optional[str] = Field(default=None, max_length=ProductConstants.CATEGORY_MAX_LENGTH)
    is_available: Optional[bool] = None

    _strip = field_validator("name", "description", "category", mode="before")(_clean_text)


class ProductPublic(BaseModel):
    """A product as it leaves the API."""

    id: str
    name: str
    description: str
    price: float
    stock: int
    category: str
    image_url: Optional[str] = None
    is_available: bool
    is_out_of_stock: bool
    # True when the product can be ordered: stock > 0 and not marked out of stock.
    in_stock: bool
    created_at: datetime
    updated_at: datetime


class ProductPage(BaseModel):
    """One page of a product listing."""

    items: list[ProductPublic]
    total: int
    page: int
    page_size: int


class ProductStats(BaseModel):
    """Catalogue counts for the admin dashboard."""

    total: int
    live: int
    hidden: int
    low_stock: int
    out_of_stock: int
