import re
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from bson import Decimal128, ObjectId
from bson.errors import InvalidId
from fastapi import UploadFile
from pymongo import ASCENDING, DESCENDING, ReturnDocument

from app.models.product_model import ProductCreate, ProductPage, ProductPublic, ProductStats, ProductUpdate
from app.services.image_service import ImageService
from app.shared.constants import CollectionNames, HTTPCodes, ProductConstants, ProductSort, ProductStatus
from app.shared.custom_error import raise_custom_error
from app.shared.custom_messages import CustomMessages
from app.shared.db_connections.mongo import mongodb
from app.shared.ttl_cache import TTLCache

# Storefront listings and categories (public, read-heavy). Cleared on every write.
_public_cache = TTLCache(ProductConstants.PUBLIC_CACHE_TTL_SECONDS, ProductConstants.PUBLIC_CACHE_MAX_ENTRIES)

_CENTS = Decimal("0.01")

_SORTS = {
    ProductSort.NEWEST: [("created_at", DESCENDING), ("_id", DESCENDING)],
    ProductSort.PRICE_ASC: [("price", ASCENDING), ("_id", DESCENDING)],
    ProductSort.PRICE_DESC: [("price", DESCENDING), ("_id", DESCENDING)],
}

# A product is orderable only with stock left AND not switched off by staff.
# Documents written before the switch existed have no field — treated as False.
_IN_STOCK_QUERY = {"stock": {"$gt": 0}, "is_out_of_stock": {"$ne": True}}
_LOW_STOCK_QUERY = {
    "$or": [{"stock": {"$lte": ProductConstants.LOW_STOCK_THRESHOLD}}, {"is_out_of_stock": True}]
}


def _to_decimal128(value: Decimal) -> Decimal128:
    """Store money as an exact Decimal128 rounded to paise (no float drift)."""
    return Decimal128(value.quantize(_CENTS, rounding=ROUND_HALF_UP))


def _to_public(doc: dict) -> ProductPublic:
    price = doc.get("price")
    price_value = price.to_decimal() if isinstance(price, Decimal128) else Decimal(str(price or 0))
    stock = int(doc.get("stock", 0))
    return ProductPublic(
        id=str(doc["_id"]),
        name=doc["name"],
        description=doc.get("description", ""),
        price=float(price_value),
        stock=stock,
        category=doc.get("category", ""),
        image_url=ImageService.public_url(doc.get("image")),
        is_available=doc.get("is_available", True),
        is_out_of_stock=bool(doc.get("is_out_of_stock", False)),
        in_stock=stock > 0 and not doc.get("is_out_of_stock", False),
        created_at=doc["created_at"],
        updated_at=doc.get("updated_at", doc["created_at"]),
    )


def _object_id(product_id: str) -> ObjectId:
    try:
        return ObjectId(product_id)
    except (InvalidId, TypeError):
        raise_custom_error(HTTPCodes.NOT_FOUND, CustomMessages.product_not_found)


async def ensure_product_indexes() -> None:
    """Indexes for the storefront listing (available products, newest first, by category)."""
    db = await mongodb.get_database()
    products = db[CollectionNames.PRODUCTS]
    await products.create_index([("is_available", ASCENDING), ("created_at", DESCENDING)])
    await products.create_index([("category_lower", ASCENDING)])
    await products.create_index([("is_available", ASCENDING), ("price", ASCENDING)])


class ProductService:
    """All product reads and writes. The only layer that touches the products collection."""

    async def list_products(
        self,
        *,
        search: Optional[str],
        category: Optional[str],
        page: int,
        page_size: int,
        include_unavailable: bool = False,
        sort: str = ProductSort.NEWEST,
        in_stock_only: bool = False,
        status: str = ProductStatus.ALL,
    ) -> ProductPage:
        """List products (newest first by default).

        ``search`` matches name, description or category (case-insensitive,
        substring) — the same as the Django view's ``icontains`` filter. Regex
        metacharacters in the query are escaped, so it is always a literal match.
        ``status`` (admin only) narrows to live, hidden or low-stock products.
        """
        # The public storefront is served from a short cache; admin views are always fresh.
        cache_key = None
        if not include_unavailable:
            cache_key = ("list", search, category, page, page_size, sort, in_stock_only)
            cached = _public_cache.get(cache_key)
            if cached is not None:
                return cached

        query: dict = {} if include_unavailable else {"is_available": True}
        if include_unavailable and status == ProductStatus.LIVE:
            query["is_available"] = True
        elif include_unavailable and status == ProductStatus.HIDDEN:
            query["is_available"] = False
        # Extra conditions go in $and so they never clash with the search's $or.
        conditions: list[dict] = []
        if status == ProductStatus.LOW_STOCK:
            conditions.append(_LOW_STOCK_QUERY)
        if in_stock_only:
            conditions.append(_IN_STOCK_QUERY)
        if conditions:
            query["$and"] = conditions
        if search:
            pattern = {"$regex": re.escape(search), "$options": "i"}
            query["$or"] = [{"name": pattern}, {"description": pattern}, {"category": pattern}]
        if category:
            query["category_lower"] = category.strip().lower()

        db = await mongodb.get_database()
        products = db[CollectionNames.PRODUCTS]
        total = await products.count_documents(query)
        cursor = (
            products.find(query)
            .sort(_SORTS.get(sort, _SORTS[ProductSort.NEWEST]))
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        items = [_to_public(doc) async for doc in cursor]
        result = ProductPage(items=items, total=total, page=page, page_size=page_size)
        if cache_key is not None:
            _public_cache.set(cache_key, result)
        return result

    async def stats(self) -> ProductStats:
        """Counts for the admin dashboard, in one aggregation round trip."""
        db = await mongodb.get_database()
        threshold = ProductConstants.LOW_STOCK_THRESHOLD
        flagged = {"$eq": ["$is_out_of_stock", True]}
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "live": {"$sum": {"$cond": ["$is_available", 1, 0]}},
                    "out_of_stock": {"$sum": {"$cond": [{"$or": [{"$lte": ["$stock", 0]}, flagged]}, 1, 0]}},
                    "low_stock": {"$sum": {"$cond": [{"$or": [{"$lte": ["$stock", threshold]}, flagged]}, 1, 0]}},
                }
            }
        ]
        rows = await db[CollectionNames.PRODUCTS].aggregate(pipeline).to_list(1)
        row = rows[0] if rows else {"total": 0, "live": 0, "out_of_stock": 0, "low_stock": 0}
        return ProductStats(
            total=row["total"],
            live=row["live"],
            hidden=row["total"] - row["live"],
            low_stock=row["low_stock"],
            out_of_stock=row["out_of_stock"],
        )

    async def list_categories(self) -> list[str]:
        """Return the suggested categories plus any others used by available products."""
        cached = _public_cache.get("categories")
        if cached is not None:
            return cached
        db = await mongodb.get_database()
        used = await db[CollectionNames.PRODUCTS].distinct("category", {"is_available": True})
        seen = {c.lower() for c in ProductConstants.SUGGESTED_CATEGORIES}
        extra = sorted({c for c in used if c and c.lower() not in seen}, key=str.lower)
        result = [*ProductConstants.SUGGESTED_CATEGORIES, *extra]
        _public_cache.set("categories", result)
        return result

    async def get_product(self, product_id: str, *, include_unavailable: bool = False) -> ProductPublic:
        """Fetch one product; hidden products are 404 for the public storefront."""
        db = await mongodb.get_database()
        query: dict = {"_id": _object_id(product_id)}
        if not include_unavailable:
            query["is_available"] = True
        doc = await db[CollectionNames.PRODUCTS].find_one(query)
        if not doc:
            raise_custom_error(HTTPCodes.NOT_FOUND, CustomMessages.product_not_found)
        return _to_public(doc)

    async def create_product(self, body: ProductCreate, image: Optional[UploadFile]) -> ProductPublic:
        """Insert a product, storing its image first when one is given."""
        image_service = ImageService()
        image_path = await image_service.save(image) if image else None
        now = datetime.now(timezone.utc)
        doc = {
            "name": body.name,
            "description": body.description,
            "price": _to_decimal128(body.price),
            "stock": body.stock,
            "is_out_of_stock": body.is_out_of_stock,
            "category": body.category,
            "category_lower": body.category.lower(),
            "image": image_path,
            "is_available": body.is_available,
            "created_at": now,
            "updated_at": now,
        }
        db = await mongodb.get_database()
        try:
            result = await db[CollectionNames.PRODUCTS].insert_one(doc)
        except Exception:
            image_service.delete(image_path)
            raise
        doc["_id"] = result.inserted_id
        _public_cache.clear()
        return _to_public(doc)

    async def update_product(
        self,
        product_id: str,
        body: ProductUpdate,
        image: Optional[UploadFile],
        remove_image: bool = False,
    ) -> ProductPublic:
        """Apply the fields that were sent; a new image replaces (and deletes) the old one."""
        oid = _object_id(product_id)
        changes = body.model_dump(exclude_unset=True, exclude_none=True)
        if not changes and image is None and not remove_image:
            raise_custom_error(HTTPCodes.BAD_REQUEST, CustomMessages.nothing_to_update)

        db = await mongodb.get_database()
        products = db[CollectionNames.PRODUCTS]
        existing = await products.find_one({"_id": oid}, {"image": 1})
        if not existing:
            raise_custom_error(HTTPCodes.NOT_FOUND, CustomMessages.product_not_found)

        if "price" in changes:
            changes["price"] = _to_decimal128(changes["price"])
        if "category" in changes:
            changes["category_lower"] = changes["category"].lower()

        image_service = ImageService()
        new_image = await image_service.save(image) if image else None
        if new_image or remove_image:
            changes["image"] = new_image
        changes["updated_at"] = datetime.now(timezone.utc)

        try:
            doc = await products.find_one_and_update(
                {"_id": oid}, {"$set": changes}, return_document=ReturnDocument.AFTER
            )
        except Exception:
            image_service.delete(new_image)
            raise
        if not doc:
            image_service.delete(new_image)
            raise_custom_error(HTTPCodes.NOT_FOUND, CustomMessages.product_not_found)

        if "image" in changes:
            image_service.delete(existing.get("image"))
        _public_cache.clear()
        return _to_public(doc)

    async def delete_product(self, product_id: str) -> None:
        """Delete a product and its stored image."""
        db = await mongodb.get_database()
        doc = await db[CollectionNames.PRODUCTS].find_one_and_delete({"_id": _object_id(product_id)})
        if not doc:
            raise_custom_error(HTTPCodes.NOT_FOUND, CustomMessages.product_not_found)
        _public_cache.clear()
        ImageService().delete(doc.get("image"))
