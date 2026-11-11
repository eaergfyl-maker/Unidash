# SyncFlow (repo: Unidash)

**Problem Statement 02: Intelligent Automation & Digital Transformation**

One campus app for every queue:
- **Global multi-shop cart:** order from several stalls with a single checkout.
- **Sync-Fire engine:** staggers each kitchen's start time so every part of the order is ready at the same moment.
- **Timetable-aware ordering:** paste a class or replacement-class notice, or upload a school timetable (PDF, PNG, or JPG); SyncFlow finds your break and warns you about shops that would make you late.
- **Virtual service-desk queues:** Academic Services and IT Helpdesk tickets without standing in line.

> **Note on Campus Data:** All food stalls (`Tokyo Bento Bowl`, `BrewLab Artisan Coffee`, `Green Garden Salad & Wraps`), menu items, prices, and locations in `backend/data/seed_campus.json` are temporary placeholders for development and demo purposes, and will be replaced with real campus vendors upon onboarding.

## Quick start

Requires Python 3.13.

```bash
pip install -r requirements.txt
python run.py
```

PNG and JPG timetable uploads require Tesseract OCR on the machine running
the server. Make sure `tesseract --version` works in the same terminal you
use to start the server. PDF timetable uploads work without Tesseract.

| Page | URL |
| :--- | :--- |
| Presentation hub (split screen) | http://localhost:8000/ |
| Student app | http://localhost:8000/student/ |
| Vendor kitchen display | http://localhost:8000/vendor/ |
| Admin / helpdesk desk | http://localhost:8000/admin/ |
| API docs (Swagger) | http://localhost:8000/docs |

### Settings (environment variables)

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `PORT` | `8000` | Server port |
| `DEBUG` | `true` | Auto-reload on code changes |
| `SIM_SECONDS_PER_MINUTE` | `60` | Real seconds per kitchen minute. Use `5` for a fast stage demo. |
| `GEMINI_API_KEY` | unset | Turns on the Gemini fallback for messy timetable notices |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model used by the parser |

## How Sync-Fire works

```
max_prep      = max(prep time of each shop in the order)
delay_seconds = (max_prep - shop_prep) * 60
```

Tokyo Bento (14 min) + BrewLab latte (3 min): Bento fires at T=0, BrewLab fires at T=11 min, and both are ready at T=14.

Sub-ticket lifecycle: `STAGED → COOKING → READY → COLLECTED`. A background loop advances it every second; vendors can also trigger `Cook now` on a held ticket or mark tickets `READY` early. When a stall finishes early, **Early Completion Cascading** automatically fires any remaining `STAGED` sibling tickets in the same order and re-syncs `target_ready_at` so ready food never sits waiting.

## API

| Method | Path | Purpose |
| :--- | :--- | :--- |
| GET | `/api/health` | Health check and current `sim_seconds_per_minute` |
| GET | `/api/shops` | All stalls with menus |
| GET | `/api/shops/{id}/menu` | One stall's menu |
| GET | `/api/services` | Service counters (admin, IT) |
| POST | `/api/order/checkout` | Split cart into MasterOrder + SubTickets |
| GET | `/api/order/{id}/status` | Live order status |
| GET | `/api/queue/vendor/{shop_id}` | KDS board for a stall |
| GET | `/api/queue/admin?counter_id=` | Service-desk queue |
| POST | `/api/queue/admin/join` | Join a service-desk queue |
| POST | `/api/queue/admin/{counter_id}/call-next` | Call the next waiting ticket |
| POST | `/api/queue/ticket/{id}/action` | Change a ticket's status (`COOKING`, `READY`, `COLLECTED`, `IN_SERVICE`, `COMPLETED`) |
| POST | `/api/timetable/parse` | Parse a class notice into slots + break window |
| POST | `/api/timetable/import` | Upload a timetable PDF, PNG, or JPG to extract classes and breaks |
| GET | `/api/timetable/recommendations` | Shops ranked by whether they fit your break |
| GET | `/api/timetable/samples` | Demo replacement-class notices |
| POST | `/api/demo/reset` | Wipe all orders/tickets, restart `ORD-8801` numbering, and restore seeded admin queue |

## Testing

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q
```

## Project layout

```
backend/
  main.py, config.py
  models/      Pydantic schemas (shops, orders, queues, timetable)
  services/    data_store, sync_fire_engine, queue_manager, timetable_parser, timetable_import
  routers/     shops, orders, queues, timetable, demo
  data/        seed_campus.json (placeholder stalls, menus, and service counters)
frontend/
  index.html   split-screen presentation hub
  student/     phone app (catalog, cart, tracker with QR, schedule sync & upload)
  vendor/      multi-stall kitchen display (sound chime, Cook now, Reset demo)
  admin/       service-desk terminal
  assets/      custom.css, images/
tests/
  test_backend.py     checkout, Sync-Fire, early cascade, validation, admin queue, demo reset
  test_timetable.py   notice parsing, Gemini fallback, upload validation, break windows
docs/
  TEAM_INSTRUCTIONS.md            who owns what
  DEMO_SCRIPT.md                  3-minute pitch
  API_HANDOFF_MEMBERS_2_AND_4.md  API contract & sample payloads
  demo_assets/                    sample timetable PDF and PNG for live demo
```

State is in memory and resets on restart (or via `POST /api/demo/reset`). Seed data lives in `backend/data/seed_campus.json`.
