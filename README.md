# SyncFlow (repo: Unidash)

**Problem Statement 02: Intelligent Automation & Digital Transformation**

One campus app for every queue:
- **Global multi-shop cart:** order from several stalls with a single checkout.
- **Sync-Fire engine:** staggers each kitchen's start time so every part of the order is ready at the same moment.
- **Timetable-aware ordering:** paste a class or replacement-class notice; SyncFlow finds your break and warns you about shops that would make you late.
- **Virtual service-desk queues:** Academic Services and IT Helpdesk tickets without standing in line.

## Quick start

Requires Python 3.13.

```bash
pip install -r requirements.txt
python run.py
```

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

Sub-ticket lifecycle: `STAGED → COOKING → READY → COLLECTED`. A background loop advances it every second; vendors can mark tickets ready early.

## API

| Method | Path | Purpose |
| :--- | :--- | :--- |
| GET | `/api/shops` | All stalls with menus |
| GET | `/api/shops/{id}/menu` | One stall's menu |
| GET | `/api/services` | Service counters (admin, IT) |
| POST | `/api/order/checkout` | Split cart into MasterOrder + SubTickets |
| GET | `/api/order/{id}/status` | Live order status |
| GET | `/api/queue/vendor/{shop_id}` | KDS board for a stall |
| GET | `/api/queue/admin?counter_id=` | Service-desk queue |
| POST | `/api/queue/admin/join` | Join a service-desk queue |
| POST | `/api/queue/admin/{counter_id}/call-next` | Call the next waiting ticket |
| POST | `/api/queue/ticket/{id}/action` | Change a ticket's status (`READY`, `COMPLETED`, ...) |
| POST | `/api/timetable/parse` | Parse a class notice into slots + break window |
| GET | `/api/timetable/recommendations` | Shops ranked by whether they fit your break |
| GET | `/api/timetable/samples` | Demo replacement-class notices |

## Project layout

```
backend/
  main.py, config.py
  models/      Pydantic schemas (shops, orders, queues, timetable)
  services/    data_store, sync_fire_engine, queue_manager, timetable_parser
  routers/     shops, orders, queues, timetable
  data/        seed_campus.json
frontend/
  index.html   split-screen presentation hub
  student/     phone app (catalog, cart, tracker, schedule sync)
  vendor/      multi-stall kitchen display
  admin/       service-desk terminal
  assets/      custom.css, images/
docs/
  TEAM_INSTRUCTIONS.md   who owns what
  DEMO_SCRIPT.md         3-minute pitch
```

State is in memory and resets on restart. Seed data lives in `backend/data/seed_campus.json`.
