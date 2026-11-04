"""Single-command launcher: serves the FastAPI backend and the static frontend on one port."""
import sys

import uvicorn

from backend.config import settings

if __name__ == "__main__":
    # Windows consoles default to cp1252, which can't print emoji.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(f"🚀 Starting SyncFlow Campus Engine on http://localhost:{settings.port} ...")
    print(f"   Student app : http://localhost:{settings.port}/student/")
    print(f"   Vendor KDS  : http://localhost:{settings.port}/vendor/")
    print(f"   Admin desk  : http://localhost:{settings.port}/admin/")
    print(f"   API docs    : http://localhost:{settings.port}/docs")
    uvicorn.run("backend.main:app", host=settings.host, port=settings.port, reload=settings.debug)
