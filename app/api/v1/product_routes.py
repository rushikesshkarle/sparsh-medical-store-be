from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.models.product_model import ProductCreate, ProductUpdate
from app.services.product_service import ProductService
from app.shared.constants import HTTPCodes, ProductConstants, ProductSort, ProductStatus
from app.shared.custom_messages import CustomMessages
from app.shared.custom_response import CustomResponse
from app.shared.security import require_admin

# Public storefront reads.
router = APIRouter(prefix="/products", tags=["Products"])

# Admin catalogue management — every route requires a signed-in admin (ALLOWED_ADMIN_EMAILS).
admin_router = APIRouter(
    prefix="/admin/products", tags=["Admin · Products"], dependencies=[Depends(require_admin)]
)

SearchQuery = Annotated[Optional[str], Query(max_length=ProductConstants.SEARCH_MAX_LENGTH)]
CategoryQuery = Annotated[Optional[str], Query(max_length=ProductConstants.CATEGORY_MAX_LENGTH)]
PageQuery = Annotated[int, Query(ge=1)]
PageSizeQuery = Annotated[int, Query(ge=1, le=ProductConstants.MAX_PAGE_SIZE)]
SortQuery = Annotated[
    Literal[ProductSort.NEWEST, ProductSort.PRICE_ASC, ProductSort.PRICE_DESC], Query()
]
StatusQuery = Annotated[
    Literal[ProductStatus.ALL, ProductStatus.LIVE, ProductStatus.HIDDEN, ProductStatus.LOW_STOCK], Query()
]


def _build(model, fields: dict):
    """Validate multipart form fields with a Pydantic model, sending only the fields given.

    A ValidationError is re-raised as RequestValidationError so it gets the same
    422 envelope as any other bad request.
    """
    try:
        return model(**{k: v for k, v in fields.items() if v is not None})
    except ValidationError as e:
        raise RequestValidationError(
            [{**err, "loc": ("body", *err["loc"])} for err in e.errors(include_url=False, include_context=False)]
        )


def product_create_form(
    name: Annotated[str, Form()],
    price: Annotated[str, Form()],
    description: Annotated[Optional[str], Form()] = None,
    stock: Annotated[Optional[str], Form()] = None,
    category: Annotated[Optional[str], Form()] = None,
    is_available: Annotated[Optional[str], Form()] = None,
    is_out_of_stock: Annotated[Optional[str], Form()] = None,
) -> ProductCreate:
    """Product fields of a create request (multipart form)."""
    return _build(ProductCreate, locals())


def product_update_form(
    name: Annotated[Optional[str], Form()] = None,
    price: Annotated[Optional[str], Form()] = None,
    description: Annotated[Optional[str], Form()] = None,
    stock: Annotated[Optional[str], Form()] = None,
    category: Annotated[Optional[str], Form()] = None,
    is_available: Annotated[Optional[str], Form()] = None,
    is_out_of_stock: Annotated[Optional[str], Form()] = None,
) -> ProductUpdate:
    """Product fields of an update request (multipart form); omitted fields stay unchanged."""
    return _build(ProductUpdate, locals())


def _uploaded(image: Optional[UploadFile]) -> Optional[UploadFile]:
    """A form with an empty file input still sends a part with no filename — treat it as none."""
    return image if image is not None and image.filename else None


# ---- Public ------------------------------------------------------------------


@router.get("", response_model=CustomResponse)
async def list_products(
    q: SearchQuery = None,
    category: CategoryQuery = None,
    page: PageQuery = 1,
    page_size: PageSizeQuery = ProductConstants.DEFAULT_PAGE_SIZE,
    sort: SortQuery = ProductSort.NEWEST,
    in_stock: bool = False,
):
    """Available products. ``q`` searches name, description and category; ``in_stock=true`` hides sold-out items."""
    result = await ProductService().list_products(
        search=(q or "").strip() or None,
        category=category,
        page=page,
        page_size=page_size,
        sort=sort,
        in_stock_only=in_stock,
    )
    return CustomResponse(
        status_code=HTTPCodes.OK, message=CustomMessages.products_fetched, result=result.model_dump()
    )


@router.get("/categories", response_model=CustomResponse)
async def list_categories():
    """Categories for the storefront's category cards."""
    result = await ProductService().list_categories()
    return CustomResponse(status_code=HTTPCodes.OK, message=CustomMessages.categories_fetched, result=result)


@router.get("/{product_id}", response_model=CustomResponse)
async def get_product(product_id: str):
    """One available product."""
    result = await ProductService().get_product(product_id)
    return CustomResponse(
        status_code=HTTPCodes.OK, message=CustomMessages.product_fetched, result=result.model_dump()
    )


# ---- Admin -------------------------------------------------------------------


@admin_router.get("", response_model=CustomResponse)
async def admin_list_products(
    q: SearchQuery = None,
    category: CategoryQuery = None,
    page: PageQuery = 1,
    page_size: PageSizeQuery = ProductConstants.DEFAULT_PAGE_SIZE,
    status: StatusQuery = ProductStatus.ALL,
    sort: SortQuery = ProductSort.NEWEST,
):
    """Every product, including hidden ones; ``status`` narrows to live, hidden or low stock."""
    result = await ProductService().list_products(
        search=(q or "").strip() or None,
        category=category,
        page=page,
        page_size=page_size,
        include_unavailable=True,
        status=status,
        sort=sort,
    )
    return CustomResponse(
        status_code=HTTPCodes.OK, message=CustomMessages.products_fetched, result=result.model_dump()
    )


@admin_router.get("/stats", response_model=CustomResponse)
async def admin_product_stats():
    """Counts for the admin dashboard: total, live, hidden, low stock (≤ threshold or switched off) and out of stock."""
    result = await ProductService().stats()
    return CustomResponse(
        status_code=HTTPCodes.OK, message=CustomMessages.product_stats_fetched, result=result.model_dump()
    )


@admin_router.get("/{product_id}", response_model=CustomResponse)
async def admin_get_product(product_id: str):
    """One product, including a hidden one."""
    result = await ProductService().get_product(product_id, include_unavailable=True)
    return CustomResponse(
        status_code=HTTPCodes.OK, message=CustomMessages.product_fetched, result=result.model_dump()
    )


@admin_router.post("", response_model=CustomResponse, status_code=HTTPCodes.CREATED)
async def create_product(
    body: Annotated[ProductCreate, Depends(product_create_form)],
    image: Annotated[Optional[UploadFile], File()] = None,
):
    """Create a product (multipart form: product fields + optional ``image``)."""
    result = await ProductService().create_product(body, _uploaded(image))
    return CustomResponse(
        status_code=HTTPCodes.CREATED, message=CustomMessages.product_created, result=result.model_dump()
    )


@admin_router.put("/{product_id}", response_model=CustomResponse)
async def update_product(
    product_id: str,
    body: Annotated[ProductUpdate, Depends(product_update_form)],
    image: Annotated[Optional[UploadFile], File()] = None,
    remove_image: Annotated[bool, Form()] = False,
):
    """Update the fields sent; a new ``image`` replaces the old one, ``remove_image=true`` clears it."""
    result = await ProductService().update_product(product_id, body, _uploaded(image), remove_image)
    return CustomResponse(
        status_code=HTTPCodes.OK, message=CustomMessages.product_updated, result=result.model_dump()
    )


@admin_router.delete("/{product_id}", response_model=CustomResponse)
async def delete_product(product_id: str):
    """Delete a product and its image."""
    await ProductService().delete_product(product_id)
    return CustomResponse(
        status_code=HTTPCodes.OK, message=CustomMessages.product_deleted, result={"id": product_id}
    )
