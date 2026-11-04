from fastapi import APIRouter, HTTPException

from backend.models.orders import SubTicket, SubTicketStatus
from backend.models.queues import AdminQueueTicket, JoinQueueRequest, QueueStatus, TicketAction
from backend.services.queue_manager import queue_manager

router = APIRouter(prefix="/api/queue", tags=["queues"])


# ---------- admin / service desk ----------
@router.get("/admin", response_model=list[AdminQueueTicket])
def admin_queue(counter_id: str | None = None):
    return queue_manager.admin_queue(counter_id)


@router.post("/admin/join", response_model=AdminQueueTicket)
def join_admin_queue(req: JoinQueueRequest):
    try:
        return queue_manager.join_admin_queue(req)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/admin/{counter_id}/call-next", response_model=AdminQueueTicket | None)
def call_next(counter_id: str):
    return queue_manager.call_next(counter_id)


# ---------- vendor KDS ----------
@router.get("/vendor/{shop_id}", response_model=list[SubTicket])
def vendor_board(shop_id: str):
    return queue_manager.vendor_tickets(shop_id)


# ---------- shared action endpoint ----------
@router.post("/ticket/{ticket_id}/action")
def ticket_action(ticket_id: str, action: TicketAction):
    """Move a ticket. SUB-xxxx = food sub-ticket (e.g. READY), ADM-xxx = desk ticket (e.g. COMPLETED)."""
    status = action.status.upper()
    try:
        if ticket_id in queue_manager.sub_tickets:
            return queue_manager.set_sub_status(ticket_id, SubTicketStatus(status))
        if ticket_id in queue_manager.admin_tickets:
            return queue_manager.set_admin_status(ticket_id, QueueStatus(status))
    except ValueError as e:
        raise HTTPException(400, f"Invalid status '{action.status}' for {ticket_id}") from e
    raise HTTPException(404, f"Ticket '{ticket_id}' not found")
