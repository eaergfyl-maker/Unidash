from pydantic import BaseModel


class TimetableSlot(BaseModel):
    day: str | None = None
    date: str | None = None
    start: str            # "13:30"
    end: str | None = None
    label: str | None = None


class BreakWindow(BaseModel):
    start: str
    end: str
    break_minutes: int
    walk_buffer_minutes: int
    max_prep_minutes: int


class ParseRequest(BaseModel):
    text: str
    previous_class_end: str | None = None   # "13:00"; if missing, assumes a default break
    walk_buffer_minutes: int | None = None


class ParseResult(BaseModel):
    slots: list[TimetableSlot]
    break_window: BreakWindow | None = None
    source: str = "regex"   # "regex" or "gemini"


class GapRecommendation(BaseModel):
    shop_id: str
    shop_name: str
    estimated_ready_minutes: int
    walk_minutes: int
    fits_break: bool
    risk: str              # "SAFE" | "TIGHT" | "HIGH"
    message: str
