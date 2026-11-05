"""In-memory queue state machine.

Food sub-tickets:   STAGED -> COOKING -> READY -> COLLECTED  (timed by a background tick loop)
Admin desk tickets: WAITING -> CALLED -> IN_SERVICE -> COMPLETED  (moved by staff actions)
"""
import asyncio
import itertools
from collections import defaultdict
from datetime import datetime

from backend.config import settings
from backend.models.orders import (
    CheckoutRequest,
    MasterOrder,
    SubTicket,
    SubTicketLine,
    SubTicketStatus,
)
from backend.models.queues import AdminQueueTicket, JoinQueueRequest, QueueStatus
from backend.services.data_store import get_store
from backend.services.sync_fire_engine import calculate_sync_schedule

_STATUS_RANK = {s: i for i, s in enumerate(SubTicketStatus)}


class QueueManager:
    def __init__(self):
        self.orders: dict[str, MasterOrder] = {}
        self.sub_tickets: dict[str, SubTicket] = {}
        self.admin_tickets: dict[str, AdminQueueTicket] = {}
        self._order_seq = itertools.count(8801)
        self._sub_seq = itertools.count(1)
        self._admin_seq: dict[str, itertools.count] = defaultdict(lambda: itertools.count(1))
        self._task: asyncio.Task | None = None

    # ---------- food orders ----------
    def checkout(self, req: CheckoutRequest) -> MasterOrder:
        store = get_store()
        if not req.items:
            raise ValueError("Cart is empty")

        lines_by_shop: dict[str, list[dict]] = defaultdict(list)
        for cart_item in req.items:
            item = store.get_item(cart_item.shop_id, cart_item.item_id)
            if not item:
                raise ValueError(f"Unknown item {cart_item.shop_id}/{cart_item.item_id}")
            lines_by_shop[cart_item.shop_id].append(
                {
                    "item_id": item.id,
                    "name": item.name,
                    "quantity": cart_item.quantity,
                    "price": item.price,
                    "prep_minutes": item.prep_minutes,
                }
            )

        now = datetime.now()
        schedule = calculate_sync_schedule(lines_by_shop, now)
        order_id = f"ORD-{next(self._order_seq)}"

        subs = []
        for shop_id, lines in lines_by_shop.items():
            plan = schedule["shops"][shop_id]
            sub = SubTicket(
                id=f"SUB-{next(self._sub_seq):04d}",
                order_id=order_id,
                shop_id=shop_id,
                shop_name=store.get_shop(shop_id).name,
                lines=[SubTicketLine(**line) for line in lines],
                prep_minutes=plan["prep_minutes"],
                fire_delay_seconds=plan["fire_delay_seconds"],
                fire_at=plan["fire_at"],
                ready_at=plan["ready_at"],
            )
            self.sub_tickets[sub.id] = sub
            subs.append(sub)

        total = sum(l["price"] * l["quantity"] for lines in lines_by_shop.values() for l in lines)
        order = MasterOrder(
            id=order_id,
            student_name=req.student_name,
            student_id=req.student_id,
            created_at=now,
            target_ready_at=schedule["target_ready_at"],
            total=round(total, 2),
            sub_tickets=subs,
        )
        self.orders[order_id] = order
        self._refresh(now)
        return order

    def get_order(self, order_id: str) -> MasterOrder | None:
        return self.orders.get(order_id)

    def vendor_tickets(self, shop_id: str) -> list[SubTicket]:
        return sorted(
            (t for t in self.sub_tickets.values() if t.shop_id == shop_id),
            key=lambda t: t.fire_at,
        )

    def set_sub_status(self, ticket_id: str, status: SubTicketStatus) -> SubTicket:
        ticket = self.sub_tickets[ticket_id]
        ticket.status = status
        self._update_order_status(ticket.order_id)
        return ticket

    def _refresh(self, now: datetime) -> None:
        """Advance timed statuses. Never moves a ticket backwards, so vendor actions win."""
        for t in self.sub_tickets.values():
            t.seconds_until_fire = max(0.0, (t.fire_at - now).total_seconds())
            t.seconds_until_ready = max(0.0, (t.ready_at - now).total_seconds())
            if now < t.fire_at:
                timed = SubTicketStatus.STAGED
            elif now < t.ready_at:
                timed = SubTicketStatus.COOKING
            else:
                timed = SubTicketStatus.READY
            if _STATUS_RANK[timed] > _STATUS_RANK[t.status]:
                t.status = timed
        for order_id in self.orders:
            self._update_order_status(order_id)

    def _update_order_status(self, order_id: str) -> None:
        order = self.orders[order_id]
        # The master order is only as far along as its slowest sub-ticket.
        order.status = min((t.status for t in order.sub_tickets), key=_STATUS_RANK.get)

    # ---------- admin / service desk ----------
    def seed_admin_queue(self) -> None:
        for entry in get_store().admin_queue_seed:
            self.join_admin_queue(JoinQueueRequest(**entry))

    def join_admin_queue(self, req: JoinQueueRequest) -> AdminQueueTicket:
        counter = get_store().services.get(req.counter_id)
        if not counter:
            raise ValueError(f"Unknown counter {req.counter_id}")
        option = next((o for o in counter.options if o.id == req.option_id), None)
        if not option:
            raise ValueError(f"Unknown option {req.option_id}")

        prefix = "A" if req.counter_id == "academic-services" else "T"
        number = f"{prefix}-{next(self._admin_seq[req.counter_id]):03d}"
        ticket = AdminQueueTicket(
            id=f"ADM-{number}",
            number=number,
            counter_id=req.counter_id,
            option_id=option.id,
            option_name=option.name,
            student_name=req.student_name,
            matric_no=req.matric_no,
            inquiry=req.inquiry,
            created_at=datetime.now(),
        )
        self.admin_tickets[ticket.id] = ticket
        return ticket

    def admin_queue(self, counter_id: str | None = None) -> list[AdminQueueTicket]:
        tickets = [t for t in self.admin_tickets.values() if counter_id in (None, t.counter_id)]
        return sorted(tickets, key=lambda t: t.created_at)

    def call_next(self, counter_id: str) -> AdminQueueTicket | None:
        waiting = [t for t in self.admin_queue(counter_id) if t.status == QueueStatus.WAITING]
        if not waiting:
            return None
        waiting[0].status = QueueStatus.CALLED
        return waiting[0]

    def set_admin_status(self, ticket_id: str, status: QueueStatus) -> AdminQueueTicket:
        ticket = self.admin_tickets[ticket_id]
        ticket.status = status
        return ticket

    # ---------- demo helpers ----------
    def reset(self) -> None:
        """Wipe all orders and tickets and re-seed the admin queue, for clean demo reruns."""
        self.orders.clear()
        self.sub_tickets.clear()
        self.admin_tickets.clear()
        self._order_seq = itertools.count(8801)
        self._sub_seq = itertools.count(1)
        self._admin_seq.clear()
        self.seed_admin_queue()

    # ---------- background tick loop ----------
    async def _tick_loop(self) -> None:
        while True:
            self._refresh(datetime.now())
            await asyncio.sleep(settings.tick_interval_seconds)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._tick_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


queue_manager = QueueManager()
