from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SubTicketStatus(str, Enum):
    STAGED = "STAGED"        # held by Sync-Fire, waiting to fire
    COOKING = "COOKING"      # kitchen is preparing it now
    READY = "READY"          # waiting for pickup
    COLLECTED = "COLLECTED"  # handed to the student


class CartItem(BaseModel):
    shop_id: str
    item_id: str
    quantity: int = Field(default=1, ge=1)


class CheckoutRequest(BaseModel):
    student_name: str = "Demo Student"
    items: list[CartItem]


class SubTicketLine(BaseModel):
    item_id: str
    name: str
    quantity: int
    price: float
    prep_minutes: int


class SubTicket(BaseModel):
    id: str
    order_id: str
    shop_id: str
    shop_name: str
    lines: list[SubTicketLine]
    prep_minutes: int
    fire_delay_seconds: float
    fire_at: datetime
    ready_at: datetime
    status: SubTicketStatus = SubTicketStatus.STAGED
    seconds_until_fire: float = 0
    seconds_until_ready: float = 0


class MasterOrder(BaseModel):
    id: str
    student_name: str
    created_at: datetime
    target_ready_at: datetime
    total: float
    sub_tickets: list[SubTicket]
    status: SubTicketStatus = SubTicketStatus.STAGED
