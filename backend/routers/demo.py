from fastapi import APIRouter

from backend.services.queue_manager import queue_manager

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/reset")
def reset_demo():
    """Clear all orders/tickets and restore the seeded admin queue so the demo can be rerun."""
    queue_manager.reset()
    return {"status": "reset", "admin_tickets": len(queue_manager.admin_tickets)}
