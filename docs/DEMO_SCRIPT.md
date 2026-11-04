# SyncFlow: 3-Minute Demo Script

Owner: Person 5 (UX Polish, Pitch Deck & Demo Director)

## Before going on stage
1. Start the server in fast demo mode so a 14-minute order finishes in about 70 seconds:
   - PowerShell: `$env:SIM_SECONDS_PER_MINUTE = "5"; python run.py`
   - macOS / Linux: `SIM_SECONDS_PER_MINUTE=5 python run.py`
2. Open http://localhost:8000/ (the split-screen hub) full screen.
   Left: student phone. Right top: Tokyo Bento KDS. Right bottom: BrewLab KDS.
3. Restart the server right before the pitch so the boards are empty.

## Timeline

| Time | Beat | On screen |
| :--- | :--- | :--- |
| 0:00 – 0:45 | **Hook.** Breaks are 15–30 min, queues take 25 min. Students skip meals or arrive late. Replacement-class notices make it worse. | Slides 1–2 |
| 0:45 – 1:45 | **Live order.** Tap *Load Replacement Class Notice* → *Find my break window*. SyncFlow shows the gap and flags risky shops. Add Teriyaki Chicken Rice Bowl + Iced Spanish Latte → one checkout. | Student phone |
| 1:45 – 2:30 | **Magic moment.** Bento ticket jumps straight to *COOK NOW*; the latte sits in *Held by AI* with a countdown so it doesn't melt. Both turn READY together. Student sees *Start walking now*. | Both KDS boards |
| 2:30 – 3:00 | **Impact.** Less waiting, no cold coffee or soggy food, one QR for every stall, same engine runs the admin and IT helpdesk queues. | Slide 3 + /admin |

## Lines to land
- "Two kitchens, one finish line."
- "The coffee waits for the bento, not the student."

## Backup plan
- If Wi-Fi drops: everything runs on localhost. Tailwind loads from a CDN, so open each page once beforehand to cache it.
- If the demo breaks: show http://localhost:8000/docs and run `POST /api/order/checkout` from Swagger.

> TODO (Person 5): replace the impact line with measured numbers before quoting any percentages on stage.
