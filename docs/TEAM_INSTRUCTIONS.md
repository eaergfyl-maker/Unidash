# TEAM_STEP_BY_STEP_INSTRUCTIONS.md
# SyncFlow: 5-Member Team Role Guide & Step-by-Step Hackathon Sprint

> **Welcome Team!**  
> We are building **SyncFlow** for **Problem Statement 02: Intelligent Automation & Digital Transformation**.  
> Here are the exact responsibilities, assigned files, and chronological step-by-step instructions for each of the 5 team members so everyone can work in parallel without blocking each other.

---

## Team Roster & File Ownership Matrix

| Member | Role | Files Owned | Difficulty |
| :--- | :--- | :--- | :--- |
| **Person 1** | **Backend & Sync-Fire Engine Lead** | `backend/main.py`, `backend/services/sync_fire_engine.py`, `backend/routers/orders.py`, `backend/routers/shops.py` | ⭐⭐⭐⭐⭐ (5/5) |
| **Person 2** | **Student UI & Global Cart Lead** | `frontend/student/index.html`, `frontend/student/app.js`, `frontend/assets/css/custom.css` | ⭐⭐⭐⭐☆ (4/5) |
| **Person 3** | **Timetable & AI Gap Intelligence Lead** | `backend/services/timetable_parser.py`, `backend/routers/timetable.py`, Student Timetable UI component | ⭐⭐⭐☆☆ (3.5/5) |
| **Person 4** | **Vendor & Admin KDS Lead** | `frontend/vendor/index.html`, `frontend/vendor/kds.js`, `frontend/admin/index.html`, `frontend/admin/admin.js` | ⭐⭐⭐☆☆ (3/5) |
| **Person 5** | **UX Polish, Pitch Deck & Demo Director** | `docs/DEMO_SCRIPT.md`, `backend/data/seed_campus.json`, Pitch Slides, Live Demo Rehearsal | ⭐⭐☆☆☆ (2/5) |

---

## Detailed Step-by-Step Instructions by Role

### 👤 Person 1: Backend & Sync-Fire Engine Lead
**Goal:** Build the brain of SyncFlow that receives multi-shop orders and orchestrates the timing.

* **Step 1.1 (Setup):** Ensure `requirements.txt` packages are installed. Run `python run.py` and confirm FastAPI docs are up at `http://localhost:8000/docs`.
* **Step 1.2 (Data Store):** Implement `backend/services/data_store.py` to read `backend/data/seed_campus.json` into memory so shops, menus, and queues are queryable.
* **Step 1.3 (Order Splitting):** In `backend/routers/orders.py`, write the `POST /api/order/checkout` endpoint. When a student submits a cart with items from multiple stalls, create:
  * A `MasterOrder` (e.g. `#ORD-8801`, total price, status).
  * Multiple child `SubTicket` objects (one for each unique `shop_id`).
* **Step 1.4 (Sync-Fire Engine):** In `backend/services/sync_fire_engine.py`, implement the stagger formula:
  * Find the longest prep time: $T_{\max} = \max(\text{prep\_times})$.
  * For each sub-ticket: $\text{delay\_seconds} = (T_{\max} - \text{prep\_time}) \times 60$.
  * If Tokyo Bento takes 14 mins and BrewLab Coffee takes 3 mins: Bento fires at $T=0$, BrewLab fires at $T=11$ mins.
* **Step 1.5 (Tick & State Updater):** Add an asynchronous background tick loop (or endpoint) that updates remaining seconds and automatically flips status from `STAGED` $\to$ `COOKING` $\to$ `READY`.
* **Step 1.6 (Handoff to P2 & P4):** Provide the exact JSON responses for:
  * `GET /api/shops`
  * `POST /api/order/checkout`
  * `GET /api/order/{id}/status`
  * `POST /api/queue/ticket/{ticket_id}/action` (for vendors to mark "Ready")

---

### 👤 Person 2: Student UI & Global Cart Lead
**Goal:** Build the high-converting, intuitive student mobile experience that judges will love.

* **Step 2.1 (Layout & Mobile Shell):** In `frontend/student/index.html`, build a clean smartphone frame view (max-w-md centered) styled with TailwindCSS.
* **Step 2.2 (Multi-Shop Catalog):** Render shop cards (Tokyo Bento, BrewLab Cafe, Salad Bar). Allow filtering by category (Food, Coffee, Quick Bites).
* **Step 2.3 (Global Cart Drawer):** Build a bottom floating cart bar:
  * Shows total items count across different shops.
  * Clicking opens a drawer grouping items by stall with individual prep times:
    * *Stall A: Tokyo Bento ($6.50) • Prep: 14 mins*
    * *Stall B: BrewLab Iced Latte ($4.20) • Prep: 3 mins*
* **Step 2.4 (Single Checkout):** Connect checkout button to `POST /api/order/checkout`. Show a simulated "Campus Pay / Quick Pay" confirmation modal.
* **Step 2.5 (Live "Sync-Prep" Radar Screen):** After checkout, transition to the live order tracker:
  * Dynamic animated status: *"Syncing kitchen timers... Bento cooking now, coffee brewing in 11 mins."*
  * **"Walk Now" Alert Box:** Highlighted card: *"Relax in Library (8 mins left)"* $\to$ changes to vibrant green *"Start Walking Now (4 min walk to Canteen 1)"*.
  * Single Master QR code display for zero-contact pickup.

---

### 👤 Person 3: Timetable & AI Gap Intelligence Lead
**Goal:** Build the "Class-to-Counter" bridge connecting student schedules with queue ordering.

* **Step 3.1 (Regex & NLP Parser):** In `backend/services/timetable_parser.py`, write a function `parse_schedule_text(raw_text)` that handles:
  * Format: `Tue, 17-Nov-2026 | 1:30 pm - 3:30 pm`
  * Extracts: `day="Tue"`, `date="17-Nov-2026"`, `start="13:30"`, `end="15:30"`.
* **Step 3.2 (Break Gap Calculator):**
  * Assuming current class ends at 1:00 PM and next class starts at 1:30 PM:
  * Free break duration = 30 minutes. Walking buffer = 7 minutes. Max viable prep window = 23 minutes.
* **Step 3.3 (Smart Recommendations API):** In `backend/routers/timetable.py`, create `GET /api/timetable/recommendations`:
  * If a shop's queue + prep time exceeds the student's break window (e.g., 35 min rush), flag it with ⚠️ *"High Risk: Will make you late for CS101!"*
  * Highlight shops with shortest wait times as *"Guaranteed Ready Before 1:20 PM"*.
* **Step 3.4 (Student UI Integration):** Add a sleek "Sync My Schedule" widget at the top of `frontend/student/index.html` where students can paste replacement class announcements or click a 1-tap demo button ("Load Replacement Class Notice").

---

### 👤 Person 4: Vendor & Admin KDS Lead
**Goal:** Build the operational screens that prove the automation works behind the scenes.

* **Step 4.1 (Split KDS Screen):** In `frontend/vendor/index.html`, create a multi-tenant kitchen display view with tabs:
  * Tab 1: **Tokyo Bento (Stall A)**
  * Tab 2: **BrewLab Coffee (Stall B)**
* **Step 4.2 (Kanban Board Columns):** Each shop has 3 columns:
  1. `Staged / Held (Smart Queue Delay)`: Shows orders waiting for the Sync-Fire trigger with a countdown badge: *"Held by AI — Firing in 6:42"*.
  2. `Active Cooking / Prepare Now`: Orders whose timers reached zero. Has a flashing "COOK NOW" tag.
  3. `Ready for Collection`: Food waiting for student pickup.
* **Step 4.3 (Vendor Action Buttons):**
  * Add a 1-click button on each ticket: `[Mark as Ready]`.
  * Calls `POST /api/queue/ticket/{id}/action` with status `READY`.
* **Step 4.4 (Campus Admin / Service Desk View):** In `frontend/admin/index.html`:
  * Displays student queue for Academic / Medical Leave submissions.
  * Shows ticket number, student name, matric number, and attached inquiry.
  * Buttons: `[Call Next Ticket]`, `[Mark Complete]`.

---

### 👤 Person 5: UX Polish, Pitch Deck & Demo Director
**Goal:** Guarantee the team wins the pitch by orchestrating the narrative, realistic data, and live demo.

* **Step 5.1 (Problem Framing for Slide Deck):**
  * Pitch slide 1: Problem Statement 02 alignment. Show the real problem: university breaks are 15-30 minutes, queues take 25 minutes, students skip meals or arrive late.
  * Pitch slide 2: Introduce the replacement class screenshot: unstructured announcements cause sudden scheduling panics.
  * Pitch slide 3: The solution — **SyncFlow**.
* **Step 5.2 (Seed Data Curation):** Review `backend/data/seed_campus.json`:
  * Ensure dish names, prices, and prep times sound realistic.
  * Add high-quality Unsplash image URLs for food items.
* **Step 5.3 (Master Index / Split-Screen Switcher):** In `frontend/index.html`, create a presentation hub:
  * Left half: **Live Student Mobile View**.
  * Right half (top): **Stall A (Tokyo Bento) KDS**.
  * Right half (bottom): **Stall B (BrewLab) KDS**.
  * This allows the judges to see the order placed on the left, and watch the tickets synchronize live on the right!
* **Step 5.4 (3-Minute Stage Rehearsal):**
  * **0:00 - 0:45:** Story hook (the pain of campus rush and replacement classes).
  * **0:45 - 1:45:** Live Order (paste replacement class text $\to$ timetable gap auto-detected $\to$ add Bento + Iced Coffee $\to$ 1-click checkout).
  * **1:45 - 2:30:** The Magic Moment (show Tokyo Bento cooking immediately while BrewLab coffee is staged by AI to avoid melting).
  * **2:30 - 3:00:** Impact & metrics (73% wait time reduction, zero food waste, cross-campus operational efficiency).
