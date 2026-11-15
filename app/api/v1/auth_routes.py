from fastapi import APIRouter, Depends, Request

from app.models.auth_model import AdminPublic, LoginRequest
from app.services.auth_service import AuthService
from app.shared.constants import HTTPCodes
from app.shared.custom_messages import CustomMessages
from app.shared.custom_response import CustomResponse
from app.shared.security import get_current_admin

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=CustomResponse)
async def login(body: LoginRequest, request: Request):
    """Exchange the admin username/password (from the server env) for a Bearer token."""
    client_ip = request.client.host if request.client else "unknown"
    result = AuthService().login(body, client_ip)
    return CustomResponse(
        status_code=HTTPCodes.OK, message=CustomMessages.login_success, result=result.model_dump()
    )


@router.get("/me", response_model=CustomResponse)
async def me(admin: AdminPublic = Depends(get_current_admin)):
    """Return the signed-in admin."""
    return CustomResponse(
        status_code=HTTPCodes.OK, message=CustomMessages.admin_fetched, result=admin.model_dump()
    )
