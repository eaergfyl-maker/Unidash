"""Parse class / replacement-class notices and work out the break window before a class.

Handles text like:  "Tue, 17-Nov-2026 | 1:30 pm - 3:30 pm"
  -> day="Tue", date="17-Nov-2026", start="13:30", end="15:30"

Regex runs first. If it finds nothing and GEMINI_API_KEY is set, Gemini is asked instead.
"""
import json
import re
from datetime import datetime, timedelta

from backend.config import settings
from backend.models.timetable import BreakWindow, ParseResult, TimetableSlot

_TIME = r"\d{1,2}(?::\d{2})?\s*(?:[ap]\.?m\.?)?"
_SLOT_RE = re.compile(
    r"(?:(?P<day>Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\.?,?\s*)?"
    r"(?:(?P<date>\d{1,2}[-/ ][A-Za-z]{3,9}[-/ ]\d{2,4})\s*)?"
    r"(?:\|\s*)?"
    r"(?P<start>" + _TIME + r")\s*(?:-|–|to)\s*(?P<end>" + _TIME + r")"
    r"(?:\s*\((?P<label>[^)]+)\))?",
    re.IGNORECASE,
)
_HAS_MERIDIEM = re.compile(r"([ap])\.?m", re.IGNORECASE)


def to_24h(raw: str) -> str:
    """'1:30 pm' -> '13:30', '11 am' -> '11:00', '13:30' -> '13:30'."""
    s = raw.strip().lower().replace(".", "").replace(" ", "")
    meridiem = s[-2:] if s.endswith(("am", "pm")) else None
    if meridiem:
        s = s[:-2]
    hour, _, minute = s.partition(":")
    h, m = int(hour), int(minute or 0)
    if meridiem == "pm" and h != 12:
        h += 12
    if meridiem == "am" and h == 12:
        h = 0
    return f"{h:02d}:{m:02d}"


def _regex_parse(raw_text: str) -> list[TimetableSlot]:
    slots = []
    for m in _SLOT_RE.finditer(raw_text):
        start, end = m.group("start"), m.group("end")
        # "1:30 - 3:30 pm": borrow the end's am/pm for the start.
        if not _HAS_MERIDIEM.search(start):
            mer = _HAS_MERIDIEM.search(end)
            if mer:
                start = f"{start} {mer.group(1)}m"
        day = m.group("day")
        slots.append(
            TimetableSlot(
                day=day.title() if day else None,
                date=m.group("date"),
                start=to_24h(start),
                end=to_24h(end),
                label=m.group("label"),
            )
        )
    return slots


def _gemini_parse(raw_text: str) -> list[TimetableSlot]:
    """Fallback for messy announcements. Returns [] if Gemini is unavailable or fails."""
    if not settings.gemini_api_key:
        return []
    try:
        from google import genai

        client = genai.Client(api_key=settings.gemini_api_key)
        prompt = (
            "Extract every class time slot from this announcement. Reply with JSON only, like: "
            '[{"day": "Thu", "date": "19-Nov-2026", "start": "14:00", '
            '"end": "16:00", "label": null, "room": "Lab 4"}]. '
            "Use 24-hour HH:MM times. Use null for unknown fields, "
            "including dates that are not stated.\n\n" + raw_text
        )
        resp = client.models.generate_content(model=settings.gemini_model, contents=prompt)
        text = resp.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
        return [TimetableSlot(**s) for s in json.loads(text)]
    except Exception:  # noqa: BLE001 - parsing must never crash the API
        return []


def compute_break_window(
    next_class_start: str,
    previous_class_end: str | None = None,
    walk_buffer: int | None = None,
) -> BreakWindow:
    """Break = previous class end -> next class start. Max prep = break - walking buffer."""
    walk = settings.default_walk_buffer if walk_buffer is None else walk_buffer
    fmt = "%H:%M"
    start_dt = datetime.strptime(next_class_start, fmt)
    if previous_class_end:
        prev_dt = datetime.strptime(previous_class_end, fmt)
    else:
        prev_dt = start_dt - timedelta(minutes=settings.default_break_minutes)
    minutes = max(0, int((start_dt - prev_dt).total_seconds() // 60))
    return BreakWindow(
        start=prev_dt.strftime(fmt),
        end=start_dt.strftime(fmt),
        break_minutes=minutes,
        walk_buffer_minutes=walk,
        max_prep_minutes=max(0, minutes - walk),
    )


def parse_schedule_text(
    raw_text: str,
    previous_class_end: str | None = None,
    walk_buffer: int | None = None,
) -> ParseResult:
    slots, source = _regex_parse(raw_text), "regex"
    if not slots:
        slots, source = _gemini_parse(raw_text), "gemini"

    window = None
    if slots:
        slots.sort(key=lambda s: s.start)
        target = slots[-1]  # the class the student needs to make it to
        prev_end = previous_class_end
        if prev_end is None and len(slots) > 1:
            prev_end = slots[-2].end  # back-to-back classes in one notice
        window = compute_break_window(target.start, prev_end, walk_buffer)

    return ParseResult(slots=slots, break_window=window, source=source)
