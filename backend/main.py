"""FastAPI app: API routes under /api, frontend served as static files from /."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.routers import orders, queues, shops, timetable
from backend.services.queue_manager import queue_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    queue_manager.seed_admin_queue()
    queue_manager.start()
    yield
    await queue_manager.stop()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # hackathon demo: open CORS. Lock down before any real deployment.
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (shops.router, orders.router, queues.router, timetable.router):
    app.include_router(r)


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok", "app": settings.app_name, "sim_seconds_per_minute": settings.sim_seconds_per_minute}


# Mounted last so /api/* and /docs take priority over static files.
app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
