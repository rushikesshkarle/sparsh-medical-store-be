from fastapi import APIRouter

from app.api.v1.auth_routes import router as auth_router
from app.api.v1.product_routes import admin_router as admin_product_router
from app.api.v1.product_routes import router as product_router
from app.services.health_service import HealthService
from app.shared.constants import HealthConstants, HTTPCodes
from app.shared.custom_messages import CustomMessages
from app.shared.custom_response import CustomResponse

router = APIRouter()


@router.get("/health", response_model=CustomResponse, tags=["Health"])
async def health_check():
    """Report the API's liveness and MongoDB's.

    The HTTP status is always 200 — the body carries the verdict, so a platform
    probe pointed here never restarts the container over a database blip.
    """
    report = await HealthService().check()
    message = (
        CustomMessages.healthy_service
        if report.status == HealthConstants.STATUS_HEALTHY
        else CustomMessages.degraded_service
    )
    return CustomResponse(status_code=HTTPCodes.OK, message=message, result=report.model_dump())


# Mount feature routers under /api/v1.
router.include_router(auth_router)
router.include_router(product_router)
router.include_router(admin_product_router)
