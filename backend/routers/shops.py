from fastapi import APIRouter, HTTPException

from backend.models.shops import MenuItem, ServiceCounter, Shop
from backend.services.data_store import get_store

router = APIRouter(prefix="/api", tags=["shops"])


@router.get("/shops", response_model=list[Shop])
def list_shops():
    return get_store().list_shops()


@router.get("/shops/{shop_id}/menu", response_model=list[MenuItem])
def shop_menu(shop_id: str):
    shop = get_store().get_shop(shop_id)
    if not shop:
        raise HTTPException(404, f"Shop '{shop_id}' not found")
    return shop.menu


@router.get("/services", response_model=list[ServiceCounter])
def list_services():
    return get_store().list_services()
