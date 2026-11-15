import logging
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ASCENDING, ReturnDocument

from app.core.config import settings
from app.models.auth_model import GoogleUserInfo, LoginResult, UserPublic
from app.services.google_oauth_service import GoogleOAuthService
from app.shared.constants import CollectionNames, HTTPCodes
from app.shared.custom_error import raise_custom_error
from app.shared.custom_messages import CustomMessages
from app.shared.db_connections.mongo import mongodb
from app.shared.security import create_access_token


def is_admin_email(email: str) -> bool:
    """Return True when ``email`` is in ``ALLOWED_ADMIN_EMAILS`` (empty list = no admins)."""
    return email.lower() in settings.allowed_admin_emails_set


def _to_public(doc: dict) -> UserPublic:
    return UserPublic(
        id=str(doc["_id"]),
        email=doc["email"],
        name=doc.get("name", ""),
        picture=doc.get("picture", ""),
        is_admin=is_admin_email(doc["email"]),
        created_at=doc["created_at"],
    )


async def ensure_user_indexes() -> None:
    """Create the unique indexes on a user's Google id and email."""
    db = await mongodb.get_database()
    users = db[CollectionNames.USERS]
    await users.create_index([("google_sub", ASCENDING)], unique=True)
    await users.create_index([("email", ASCENDING)], unique=True)


class AuthService:
    """Google sign-in and token-to-user resolution.

    Anyone with a verified Google account can sign in and becomes a customer.
    Admin is not stored: it is the subset of users whose email is listed in
    ``ALLOWED_ADMIN_EMAILS``, checked on every request.
    """

    async def login_with_google(self, code: str) -> LoginResult:
        """Exchange a Google popup code for our access token, creating the user on first sign-in."""
        google = GoogleOAuthService()
        info = await google.verify_id_token(await google.exchange_code(code))
        doc = await self._upsert(info)
        if not doc.get("is_active", True):
            raise_custom_error(HTTPCodes.FORBIDDEN, CustomMessages.user_disabled)

        token, expires_in = create_access_token(str(doc["_id"]))
        user = _to_public(doc)
        logging.info("Login success — user=%s admin=%s", user.id, user.is_admin)
        return LoginResult(access_token=token, expires_in=expires_in, user=user)

    async def _upsert(self, info: GoogleUserInfo) -> dict:
        """Create the user on first sign-in; refresh email, name and photo on later ones."""
        db = await mongodb.get_database()
        now = datetime.now(timezone.utc)
        return await db[CollectionNames.USERS].find_one_and_update(
            {"google_sub": info.sub},
            {
                "$set": {"email": info.email, "name": info.name, "picture": info.picture, "last_login_at": now},
                "$setOnInsert": {"google_sub": info.sub, "is_active": True, "created_at": now},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

    async def get_active_user(self, user_id: str) -> UserPublic:
        """Load the user a token names, rejecting deleted or disabled accounts."""
        try:
            oid = ObjectId(user_id)
        except (InvalidId, TypeError):
            raise_custom_error(HTTPCodes.UNAUTHORIZED, CustomMessages.token_invalid)
        db = await mongodb.get_database()
        doc = await db[CollectionNames.USERS].find_one({"_id": oid})
        if not doc:
            raise_custom_error(HTTPCodes.UNAUTHORIZED, CustomMessages.user_not_found)
        if not doc.get("is_active", True):
            raise_custom_error(HTTPCodes.FORBIDDEN, CustomMessages.user_disabled)
        return _to_public(doc)
