from fastapi import APIRouter, Depends

from app.models.auth_model import GoogleAuthRequest, UserPublic
from app.services.auth_service import AuthService
from app.shared.constants import HTTPCodes
from app.shared.custom_messages import CustomMessages
from app.shared.custom_response import CustomResponse
from app.shared.security import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/google", response_model=CustomResponse)
async def login_with_google(body: GoogleAuthRequest):
    """Exchange a Google popup authorization code for our Bearer token.

    Any verified Google account may sign in; ``user.is_admin`` says whether it
    gets the admin dashboard (email listed in ``ALLOWED_ADMIN_EMAILS``).
    """
    result = await AuthService().login_with_google(body.code)
    return CustomResponse(
        status_code=HTTPCodes.OK, message=CustomMessages.login_success, result=result.model_dump()
    )


@router.get("/me", response_model=CustomResponse)
async def me(user: UserPublic = Depends(get_current_user)):
    """Return the signed-in user, including ``is_admin``."""
    return CustomResponse(
        status_code=HTTPCodes.OK, message=CustomMessages.user_fetched, result=user.model_dump()
    )
