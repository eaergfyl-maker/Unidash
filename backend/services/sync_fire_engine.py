"""Sync-Fire: stagger each shop's start so every sub-ticket finishes at the same moment.

    max_prep      = max(shop_prep_times)
    delay_seconds = (max_prep - shop_prep) * 60

Example: Tokyo Bento needs 14 min and BrewLab 3 min, so Bento fires at T=0 and
BrewLab fires at T=11 min. Both are ready at T=14 and the iced coffee stays cold.
"""
from datetime import datetime, timedelta

from backend.config import settings


def shop_prep_minutes(lines: list[dict]) -> int:
    """A shop cooks items in parallel, so its prep time is its slowest item."""
    return max((line["prep_minutes"] for line in lines), default=0)


def calculate_sync_schedule(items_by_shop: dict[str, list[dict]], now: datetime | None = None) -> dict:
    """items_by_shop: {shop_id: [{"prep_minutes": int, ...}, ...]}

    Returns:
        {
          "max_prep_minutes": 14,
          "target_ready_at": datetime,
          "shops": {shop_id: {"prep_minutes", "fire_delay_seconds", "fire_at", "ready_at"}}
        }
    fire_delay_seconds follows the formula in real seconds. fire_at / ready_at are scaled by
    settings.sim_seconds_per_minute so the demo can run faster than real time.
    """
    now = now or datetime.now()
    sec_per_min = settings.sim_seconds_per_minute

    preps = {shop_id: shop_prep_minutes(lines) for shop_id, lines in items_by_shop.items()}
    max_prep = max(preps.values(), default=0)
    target_ready_at = now + timedelta(seconds=max_prep * sec_per_min)

    shops = {}
    for shop_id, prep in preps.items():
        delay_minutes = max_prep - prep
        shops[shop_id] = {
            "prep_minutes": prep,
            "fire_delay_seconds": delay_minutes * 60,
            "fire_at": now + timedelta(seconds=delay_minutes * sec_per_min),
            "ready_at": target_ready_at,
        }

    return {"max_prep_minutes": max_prep, "target_ready_at": target_ready_at, "shops": shops}
