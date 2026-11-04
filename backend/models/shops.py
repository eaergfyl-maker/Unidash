from enum import Enum

from pydantic import BaseModel


class Category(str, Enum):
    FOOD = "Food"
    COFFEE = "Coffee"
    QUICK_BITES = "Quick Bites"


class MenuItem(BaseModel):
    id: str
    name: str
    price: float
    prep_minutes: int
    category: Category
    image: str | None = None


class Shop(BaseModel):
    id: str
    name: str
    location: str
    category: Category
    prep_range_minutes: tuple[int, int]
    walk_minutes: int
    image: str | None = None
    menu: list[MenuItem] = []


class ServiceOption(BaseModel):
    id: str
    name: str
    avg_service_minutes: int


class ServiceCounter(BaseModel):
    id: str
    name: str
    location: str
    options: list[ServiceOption] = []
