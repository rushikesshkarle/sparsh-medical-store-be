from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING

from app.models.cart_model import CartLine, CartPublic, CartUpdate
from app.services.product_service import _to_public as product_to_public
from app.shared.constants import CollectionNames
from app.shared.db_connections.mongo import mongodb


async def ensure_cart_indexes() -> None:
    """One cart per user."""
    db = await mongodb.get_database()
    await db[CollectionNames.CARTS].create_index([("user_id", ASCENDING)], unique=True)


def _oid(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


class CartService:
    """A signed-in user's cart, saved in MongoDB so it follows them across devices.

    Only product ids and quantities are stored. Name, price and stock are read
    from the product on every load, so a price change shows up in the cart, and
    a deleted or hidden product silently drops out of it.
    """

    async def get_cart(self, user_id: str) -> CartPublic:
        """Return the user's cart (empty if they have none yet)."""
        db = await mongodb.get_database()
        doc = await db[CollectionNames.CARTS].find_one({"user_id": user_id})
        return await self._hydrate(doc["items"] if doc else [])

    async def replace_cart(self, user_id: str, body: CartUpdate) -> CartPublic:
        """Replace the user's cart with ``body`` (unknown/hidden products are dropped)."""
        # Collapse duplicate ids, keeping the larger quantity.
        wanted: dict[str, int] = {}
        for line in body.items:
            wanted[line.id] = max(wanted.get(line.id, 0), line.quantity)

        cart = await self._hydrate([{"product_id": pid, "quantity": qty} for pid, qty in wanted.items()])
        db = await mongodb.get_database()
        await db[CollectionNames.CARTS].update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "items": [{"product_id": line.id, "quantity": line.quantity} for line in cart.items],
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
        return cart

    async def _hydrate(self, stored: list[dict]) -> CartPublic:
        """Join stored lines with live products, keeping cart order and dropping missing ones."""
        oids = [oid for oid in (_oid(line["product_id"]) for line in stored) if oid]
        if not oids:
            return CartPublic(items=[])
        db = await mongodb.get_database()
        products = {
            str(doc["_id"]): product_to_public(doc)
            async for doc in db[CollectionNames.PRODUCTS].find({"_id": {"$in": oids}, "is_available": True})
        }
        lines = []
        for line in stored:
            product = products.get(line["product_id"])
            if product:
                lines.append(
                    CartLine(
                        id=product.id,
                        name=product.name,
                        price=product.price,
                        quantity=line["quantity"],
                        image_url=product.image_url,
                        in_stock=product.in_stock,
                    )
                )
        return CartPublic(items=lines)
