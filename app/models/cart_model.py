from pydantic import BaseModel, Field

from app.shared.constants import CartConstants


class CartLineIn(BaseModel):
    """One cart line as the client sends it: which product and how many."""

    id: str = Field(min_length=1, max_length=64)
    quantity: int = Field(ge=1, le=CartConstants.MAX_QUANTITY)


class CartUpdate(BaseModel):
    """Body of ``PUT /cart``: the whole cart, replacing what is stored."""

    items: list[CartLineIn] = Field(default_factory=list, max_length=CartConstants.MAX_LINES)


class CartLine(BaseModel):
    """One cart line as it leaves the API, with the product's CURRENT name and price."""

    id: str
    name: str
    price: float
    quantity: int
    image_url: str | None = None
    in_stock: bool


class CartPublic(BaseModel):
    """A signed-in user's saved cart."""

    items: list[CartLine]
