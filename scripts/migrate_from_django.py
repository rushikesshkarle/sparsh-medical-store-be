"""One-off import of the old Django site's products into MongoDB.

Reads ``products_product`` from the Django ``db.sqlite3`` (read-only), copies
each product's image from the Django ``media/`` folder into ``MEDIA_DIR``, and
inserts the product. Re-running is safe: a product whose ``legacy_id`` is
already in MongoDB is skipped.

Django admin accounts are NOT migrated — admins now sign in with Google.
Create the admin through ``INITIAL_ADMIN_USERNAME`` / ``INITIAL_ADMIN_PASSWORD``.

Usage (from the repo root, with .env pointing at the target MongoDB):

    poetry run python -m scripts.migrate_from_django \
        --sqlite ../extracted/sparsh-medical-website-main/backend/db.sqlite3 \
        --media  ../extracted/sparsh-medical-website-main/backend/media
"""

import argparse
import asyncio
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from bson import Decimal128

from app.core.config import settings
from app.services.product_service import ensure_product_indexes
from app.shared.constants import CollectionNames, ImageConstants
from app.shared.db_connections.mongo import mongodb


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _copy_image(media_root: Path, relative: str | None) -> str | None:
    """Copy one Django media file into MEDIA_DIR under a fresh name; None if missing."""
    if not relative:
        return None
    source = (media_root / relative).resolve()
    if media_root.resolve() not in source.parents or not source.is_file():
        print(f"  ! image not found, skipping: {relative}")
        return None
    extension = source.suffix.lower().lstrip(".") or "jpg"
    target_relative = f"{ImageConstants.UPLOAD_SUBDIR}/{uuid.uuid4().hex}.{extension}"
    target = settings.media_dir / target_relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target_relative


async def migrate(sqlite_path: Path, media_root: Path) -> None:
    conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM products_product ORDER BY id").fetchall()
    conn.close()
    print(f"Found {len(rows)} product(s) in {sqlite_path}")

    await mongodb.connect()
    await ensure_product_indexes()
    products = (await mongodb.get_database())[CollectionNames.PRODUCTS]

    imported = skipped = 0
    for row in rows:
        if await products.find_one({"legacy_id": row["id"]}, {"_id": 1}):
            skipped += 1
            continue
        created = _parse_dt(row["created_at"])
        category = row["category"] or ""
        await products.insert_one(
            {
                "legacy_id": row["id"],
                "name": row["name"],
                "description": row["description"] or "",
                "price": Decimal128(Decimal(str(row["price"])).quantize(Decimal("0.01"))),
                "stock": int(row["stock"] or 0),
                "category": category,
                "category_lower": category.lower(),
                "image": _copy_image(media_root, row["image"] if "image" in row.keys() else None),
                "is_available": bool(row["is_available"]),
                "created_at": created,
                "updated_at": created,
            }
        )
        imported += 1
        print(f"  + {row['name']}")

    await mongodb.close()
    print(f"Done: {imported} imported, {skipped} already present")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sqlite", required=True, type=Path, help="Path to the Django db.sqlite3")
    parser.add_argument("--media", required=True, type=Path, help="Path to the Django media/ folder")
    args = parser.parse_args()
    asyncio.run(migrate(args.sqlite, args.media))


if __name__ == "__main__":
    main()
