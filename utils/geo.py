import math
import logging
import aiohttp
from typing import Tuple, Dict, Any, List, Optional
from config import (
    DELIVERY_BASE_FEE,
    DELIVERY_EXTRA_PER_KM,
    DELIVERY_FREE_KM,
    MAX_DELIVERY_RADIUS_KM,
    RESTAURANT_LAT,
    RESTAURANT_LON
)

logger = logging.getLogger(__name__)

# O'zbekiston chegaralari (Bounding box)
UZB_MIN_LAT = 37.18
UZB_MAX_LAT = 45.60
UZB_MIN_LON = 55.99
UZB_MAX_LON = 73.15

# Standart filiallar ro'yxati (Baza bo'sh bo'lganda yoki fallback sifatida)
DEFAULT_BRANCHES = [
    {
        "id": 1,
        "name": "Bosh filial (Amir Temur)",
        "lat": RESTAURANT_LAT,
        "lon": RESTAURANT_LON,
        "channel_id": -1004376258203
    },
    {
        "id": 2,
        "name": "Chilonzor filiali",
        "lat": 41.275820,
        "lon": 69.204510,
        "channel_id": -1004376258203
    },
    {
        "id": 3,
        "name": "Yunusobod filiali",
        "lat": 41.365210,
        "lon": 69.289120,
        "channel_id": -1004376258203
    }
]


def is_within_uzbekistan(lat: float, lon: float) -> bool:
    """Koordinatalar O'zbekiston hududi chegarasida ekanligini tekshiradi."""
    return UZB_MIN_LAT <= lat <= UZB_MAX_LAT and UZB_MIN_LON <= lon <= UZB_MAX_LON


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Ikki koordinata orasidagi masofani (km) Haversine formulasi orqali aniq hisoblaydi.
    """
    R = 6371.0  # Yer radiusi (km)

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def find_nearest_branch(lat: float, lon: float, branches: Optional[List[Dict[str, Any]]] = None) -> Tuple[Dict[str, Any], float]:
    """
    Mijoz lokatsiyasiga eng yaqin filialni va oradagi masofani (km) qaytaradi.
    """
    branch_list = branches if branches else DEFAULT_BRANCHES
    if not branch_list:
        default_branch = DEFAULT_BRANCHES[0]
        dist = haversine_distance(lat, lon, default_branch["lat"], default_branch["lon"])
        return default_branch, dist

    nearest = None
    min_dist = float("inf")

    for branch in branch_list:
        b_lat = float(branch.get("lat", RESTAURANT_LAT))
        b_lon = float(branch.get("lon", RESTAURANT_LON))
        dist = haversine_distance(lat, lon, b_lat, b_lon)
        if dist < min_dist:
            min_dist = dist
            nearest = branch

    return nearest, min_dist


def calculate_delivery_fee(distance_km: float) -> int:
    """
    Masofaga qarab yetkazib berish narxini hisoblaydi va 1000 so'mga yaxlitlaydi.
    - distance <= DELIVERY_FREE_KM: DELIVERY_BASE_FEE
    - distance > DELIVERY_FREE_KM: DELIVERY_BASE_FEE + (distance - DELIVERY_FREE_KM) * DELIVERY_EXTRA_PER_KM
    - Yaxlitlash: har 1000 so'mga qarab (12500 -> 12000, 12550 -> 13000)
    """
    if distance_km <= DELIVERY_FREE_KM:
        raw_fee = DELIVERY_BASE_FEE
    else:
        extra_km = distance_km - DELIVERY_FREE_KM
        raw_fee = DELIVERY_BASE_FEE + (extra_km * DELIVERY_EXTRA_PER_KM)

    # 1000 so'mga yaxlitlash (round to nearest 1000)
    rounded_fee = int(round(raw_fee / 1000.0) * 1000)
    return max(rounded_fee, DELIVERY_BASE_FEE)


async def reverse_geocode(lat: float, lon: float, lang: str = "uz") -> str:
    """
    Koordinatalardan inson tushunadigan aniq manzilni (shahar, tuman, ko'cha, uy) oladi.
    Hech qachon xom koordinata qaytarmaydi!
    Nominatim OpenStreetMap API dan foydalanadi (fallback bilan).
    """
    headers = {
        "User-Agent": "FastFoodDeliveryBot/1.0 (contact: info@fastfood.uz)"
    }
    url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}&zoom=18&addressdetails=1&accept-language={lang}"

    try:
        async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=4)) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    addr = data.get("address", {})
                    
                    road = addr.get("road") or addr.get("pedestrian") or addr.get("street") or ""
                    house_number = addr.get("house_number") or ""
                    suburb = addr.get("suburb") or addr.get("neighbourhood") or addr.get("residential") or ""
                    city = addr.get("city") or addr.get("town") or addr.get("county") or addr.get("state") or "Toshkent"
                    
                    parts = []
                    if city:
                        parts.append(city)
                    if suburb and suburb != city:
                        parts.append(suburb)
                    if road:
                        street_part = road + (f", {house_number}" if house_number else "")
                        parts.append(street_part)
                    
                    if parts:
                        return ", ".join(parts)
                    
                    display_name = data.get("display_name")
                    if display_name:
                        return display_name.split(",")[0].strip()
    except Exception as e:
        logger.warning(f"Reverse geocode error: {e}")

    # Fallback: Agar tarmoqda muammo bo'lsa yoki API ishlamasa
    # Hech qachon xom koordinata yozmaymiz, tushunarli matn hosil qilamiz
    return f"Toshkent shahri, koordinata bo'yicha aniqlangan manzil"
