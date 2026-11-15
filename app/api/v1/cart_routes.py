from fastapi import APIRouter, Depends

from app.models.auth_model import UserPublic
from app.models.cart_model import CartUpdate
from app.services.cart_service import CartService
from app.shared.constants import HTTPCodes
from app.shared.custom_messages import CustomMessages
from app.shared.custom_response import CustomResponse
from app.shared.security import get_current_user

# Signed-in users only; guests keep their cart in the browser.
router = APIRouter(prefix="/cart", tags=["Cart"])


@router.get("", response_model=CustomResponse)
async def get_cart(user: UserPublic = Depends(get_current_user)):
    """The signed-in user's saved cart, with current product names and prices."""
    result = await CartService().get_cart(user.id)
    return CustomResponse(status_code=HTTPCodes.OK, message=CustomMessages.cart_fetched, result=result.model_dump())


@router.put("", response_model=CustomResponse)
async def replace_cart(body: CartUpdate, user: UserPublic = Depends(get_current_user)):
    """Save the whole cart (``items: [{id, quantity}]``); hidden or deleted products are dropped."""
    result = await CartService().replace_cart(user.id, body)
    return CustomResponse(status_code=HTTPCodes.OK, message=CustomMessages.cart_saved, result=result.model_dump())
