from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import APIRouter, HTTPException, UploadFile
from pdfminer.pdfparser import PDFSyntaxError

from backend.config import settings
from backend.models.orders import SubTicketStatus
from backend.models.timetable import GapRecommendation, ParseRequest, ParseResult
from backend.services.data_store import get_store
from backend.services.queue_manager import queue_manager
from backend.services.timetable_import import find_gaps, import_timetable
from backend.services.timetable_parser import compute_break_window, parse_schedule_text

router = APIRouter(prefix="/api/timetable", tags=["timetable"])

# Rough extra wait per ticket already active at a shop (minutes). Tune with real data.
_MINUTES_PER_ACTIVE_TICKET = 2


@router.post("/parse", response_model=ParseResult)
def parse(req: ParseRequest):
    return parse_schedule_text(req.text, req.previous_class_end, req.walk_buffer_minutes)

@router.post("/import")
def import_schedule(file: UploadFile):
    """Read a school timetable PDF and return its classes and same-day breaks."""
    if Path(file.filename or "").suffix.lower() != ".pdf":
        raise HTTPException(status_code=415, detail="Choose a school timetable PDF.")

    max_bytes = 5 * 1024 * 1024
    content = file.file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="Choose a PDF under 5 MB.")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=422, detail="The file is not a readable PDF.")

    try:
        with TemporaryDirectory() as folder:
            path = Path(folder) / "timetable.pdf"
            path.write_bytes(content)
            classes = import_timetable(path)
    except (ValueError, PDFSyntaxError) as exc:
        raise HTTPException(
            status_code=422,
            detail="Could not read the timetable. Try the original school PDF export.",
        ) from exc

    slots = [
        {
            "day": date.fromisoformat(slot.date).strftime("%a"),
            "date": date.fromisoformat(slot.date).strftime("%d-%b-%Y"),
            "start": slot.start_time,
            "end": slot.end_time,
            "label": slot.module,
            "room": slot.room,
        }
        for slot in classes
    ]
    breaks = [
        {
            "date": gap["date"],
            "next_room": gap["next_room"],
            "break_window": compute_break_window(
                next_class_start=gap["end_time"],
                previous_class_end=gap["start_time"],
            ),
        }
        for gap in find_gaps(classes)
    ]
    return {"slots": slots, "breaks": breaks}
    
@router.get("/samples", response_model=list[str])
def samples():
    """Demo notices for the 1-tap "Load Replacement Class Notice" button."""
    return get_store().sample_notices


@router.get("/recommendations", response_model=list[GapRecommendation])
def recommendations(max_prep_minutes: int | None = None, class_label: str = "your next class"):
    """Rank shops by whether their food will be ready (and walked to) inside the break."""
    window = max_prep_minutes
    if window is None:
        window = settings.default_break_minutes - settings.default_walk_buffer

    active = [
        t for t in queue_manager.sub_tickets.values()
        if t.status in (SubTicketStatus.STAGED, SubTicketStatus.COOKING)
    ]
    recs = []
    for shop in get_store().list_shops():
        load = sum(1 for t in active if t.shop_id == shop.id) * _MINUTES_PER_ACTIVE_TICKET
        ready = shop.prep_range_minutes[1] + load
        total = ready + shop.walk_minutes
        if total <= window - 5:
            risk, msg = "SAFE", f"Guaranteed ready with {window - total} min to spare"
        elif total <= window:
            risk, msg = "TIGHT", "Cutting it close, order now"
        else:
            risk, msg = "HIGH", f"⚠️ High Risk: will make you late for {class_label}!"
        recs.append(
            GapRecommendation(
                shop_id=shop.id,
                shop_name=shop.name,
                estimated_ready_minutes=ready,
                walk_minutes=shop.walk_minutes,
                fits_break=total <= window,
                risk=risk,
                message=msg,
            )
        )
    return sorted(recs, key=lambda r: r.estimated_ready_minutes + r.walk_minutes)
