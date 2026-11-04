from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class QueueStatus(str, Enum):
    WAITING = "WAITING"
    CALLED = "CALLED"
    IN_SERVICE = "IN_SERVICE"
    COMPLETED = "COMPLETED"


class AdminQueueTicket(BaseModel):
    id: str
    number: str            # display number, e.g. "A-012"
    counter_id: str
    option_id: str
    option_name: str
    student_name: str
    matric_no: str
    inquiry: str = ""
    status: QueueStatus = QueueStatus.WAITING
    created_at: datetime


class JoinQueueRequest(BaseModel):
    counter_id: str
    option_id: str
    student_name: str
    matric_no: str
    inquiry: str = ""


class TicketAction(BaseModel):
    """Status to move a ticket to. Accepts SubTicketStatus or QueueStatus values."""
    status: str
