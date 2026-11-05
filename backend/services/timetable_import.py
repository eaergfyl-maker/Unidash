"""Import APU timetable files and calculate same-day gaps."""

import argparse
import json
import re
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import pdfplumber


DATE = re.compile(r"\b(\d{1,2}\s*-\s*[A-Za-z]{3}\s*-\s*\d{4})\b")
CLOCK = re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b")
ROOM = re.compile(r"\b(?:[A-Z]-\d{2}-\d{2}|Tech\s+Lab\s+\d+-\s*\d+)\b", re.I)
MODULE = re.compile(r"\b[A-Z]{4}\d{3}(?:-\s*[A-Z0-9]+){5}\b", re.I)


@dataclass(frozen=True)
class ClassSlot:
    date: str
    start_time: str
    end_time: str
    room: str | None
    module: str | None


def _clean(value):
    return " ".join((value or "").split()).replace("- ", "-")


def _slot(date, times, room, module):
    start, end = (datetime.strptime(time, "%H:%M").strftime("%H:%M") for time in times)
    if end <= start:
        raise ValueError("The class end time must be after its start time.")
    return ClassSlot(
        datetime.strptime(re.sub(r"\s", "", date), "%d-%b-%Y").date().isoformat(),
        start, end, _clean(room) or None, _clean(module) or None,
    )


def _ocr_text(image_path):
    try:
        result = subprocess.run(
            ["tesseract", str(image_path), "stdout", "--psm", "6"],
            capture_output=True, text=True, encoding="utf-8", check=True, timeout=60,
        )
    except FileNotFoundError as exc:
        raise ValueError("Screenshot import requires Tesseract on PATH.") from exc
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError("OCR failed. Try a clearer image or the school-exported PDF.") from exc
    return result.stdout


def _ocr_slots(text):
    # In the school layout, the year may wrap below the first line of a row.
    row_start = re.compile(
        r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+([\dO]{1,2})(\s*-\s*[A-Za-z]{3}\s*-)\s*(\d{4})?",
        re.I,
    )
    text = re.split(r"\bLegend\b", text, maxsplit=1, flags=re.I)[0]
    rows = list(row_start.finditer(text))
    for index, row in enumerate(rows):
        end = rows[index + 1].start() if index + 1 < len(rows) else len(text)
        content = text[row.end():end]
        wrapped_year = re.search(r"(?m)^\s*(\d{4})\b", content)
        year = row[4] or (wrapped_year[1] if wrapped_year else None)
        times = CLOCK.findall(content)
        if not year or len(times) != 2:
            raise ValueError(f"Check the date and times in the row starting with {row[0]!r}.")
        room, module = ROOM.search(content), MODULE.search(content)
        day_number = row[2].upper().replace("O", "0")
        slot = _slot(day_number + row[3] + year, times,
                     room[0] if room else None, module[0] if module else None)
        if datetime.fromisoformat(slot.date).strftime("%a").lower() != row[1].lower():
            raise ValueError("A timetable date and weekday disagree. Try a clearer screenshot.")
        yield slot


def _pdf_slots(path):
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            if not page.chars and page.images:
                with tempfile.TemporaryDirectory() as scratch:
                    image_path = Path(scratch) / "page.png"
                    page.to_image(resolution=250).save(image_path)
                    yield from _ocr_slots(_ocr_text(image_path))
                continue

            for table in page.extract_tables():
                in_schedule = False
                for row in table:
                    if row[:2] == ["DATE", "TIME"]:
                        in_schedule = True
                        continue
                    if not in_schedule or len(row) < 5:
                        continue
                    date = DATE.search(row[0] or "")
                    if not date:
                        continue
                    times = CLOCK.findall(row[1] or "")
                    if len(times) != 2:
                        raise ValueError(f"Check the class times on PDF page {page.page_number}.")
                    yield _slot(date[1], times, row[2], row[4])


def import_timetable(path):
    path = Path(path)
    extension = path.suffix.lower()
    if extension == ".pdf":
        slots = list(_pdf_slots(path))
    elif extension in {".png", ".jpg", ".jpeg"}:
        slots = list(_ocr_slots(_ocr_text(path)))
    else:
        raise ValueError("Upload a PDF, PNG, or JPG timetable.")
    if not slots:
        raise ValueError("No class rows found. Try a clear, full timetable export.")
    return sorted(set(slots), key=lambda slot: (slot.date, slot.start_time, slot.end_time))


def find_gaps(slots, walking_minutes=0):
    if walking_minutes < 0:
        raise ValueError("Walking minutes must be zero or positive.")
    gaps = []
    latest = None
    for slot in sorted(slots, key=lambda item: (item.date, item.start_time)):
        if latest is None or latest.date != slot.date:
            latest = slot
            continue
        if slot.start_time > latest.end_time:
            start = datetime.strptime(latest.end_time, "%H:%M")
            end = datetime.strptime(slot.start_time, "%H:%M")
            minutes = (end - start).seconds // 60
            gaps.append({
                "date": slot.date,
                "start_time": latest.end_time,
                "end_time": slot.start_time,
                "from_room": latest.room,
                "next_room": slot.room,
                "gap_minutes": minutes,
                "pickup_minutes": max(0, minutes - walking_minutes),
            })
        if slot.end_time > latest.end_time:
            latest = slot
    return gaps


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("timetable", type=Path)
    parser.add_argument("--walking-minutes", type=int, default=0)
    args = parser.parse_args()
    try:
        classes = import_timetable(args.timetable)
        gaps = find_gaps(classes, args.walking_minutes)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"classes": [asdict(slot) for slot in classes], "gaps": gaps}, indent=2))
