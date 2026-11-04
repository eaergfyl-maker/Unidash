"""Loads seed_campus.json into memory and gives typed lookups."""
import json
from functools import lru_cache

from backend.config import settings
from backend.models.shops import MenuItem, ServiceCounter, Shop


class DataStore:
    def __init__(self, seed: dict):
        self.raw = seed
        self.shops: dict[str, Shop] = {s["id"]: Shop(**s) for s in seed.get("shops", [])}
        self.services: dict[str, ServiceCounter] = {
            s["id"]: ServiceCounter(**s) for s in seed.get("services", [])
        }
        self.admin_queue_seed: list[dict] = seed.get("admin_queue_seed", [])
        self.sample_notices: list[str] = seed.get("sample_timetable_notices", [])

    def list_shops(self) -> list[Shop]:
        return list(self.shops.values())

    def get_shop(self, shop_id: str) -> Shop | None:
        return self.shops.get(shop_id)

    def get_item(self, shop_id: str, item_id: str) -> MenuItem | None:
        shop = self.get_shop(shop_id)
        if not shop:
            return None
        return next((i for i in shop.menu if i.id == item_id), None)

    def list_services(self) -> list[ServiceCounter]:
        return list(self.services.values())


@lru_cache
def get_store() -> DataStore:
    with open(settings.seed_file, encoding="utf-8") as f:
        return DataStore(json.load(f))
