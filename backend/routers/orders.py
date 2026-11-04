from fastapi import APIRouter, HTTPException

from backend.models.orders import CheckoutRequest, MasterOrder
from backend.services.queue_manager import queue_manager

router = APIRouter(prefix="/api/order", tags=["orders"])


@router.post("/checkout", response_model=MasterOrder)
def checkout(req: CheckoutRequest):
    """Split a multi-shop cart into one MasterOrder + one SubTicket per shop, timed by Sync-Fire."""
    try:
        return queue_manager.checkout(req)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/{order_id}/status", response_model=MasterOrder)
def order_status(order_id: str):
    order = queue_manager.get_order(order_id)
    if not order:
        raise HTTPException(404, f"Order '{order_id}' not found")
    return order
