import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "9054732573:AAEbllPQYRCOcDOxeHGTyQqVHWI_wqz3FAY")
raw_admin_id = os.getenv("ADMIN_ID", "1233117662")
ADMIN_IDS = [int(i.strip()) for i in raw_admin_id.split(",") if i.strip().isdigit()]
ADMIN_ID = ADMIN_IDS[0] if ADMIN_IDS else 1233117662


def is_admin(user_id: int) -> bool:
    """Foydalanuvchi admin ekanligini tekshiradi."""
    return user_id in ADMIN_IDS
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL_ID", "-1004376258203"))
BRANCH_1_CHANNEL_ID = int(os.getenv("BRANCH_1_CHANNEL_ID", "-1004376258203"))
DELIVERY_CHANNEL_ID = int(os.getenv("DELIVERY_CHANNEL_ID", "-1003957592099"))

# Ish vaqti sozlamalari (Toshkent vaqti UTC+5)
WORKING_HOURS_START = int(os.getenv("WORKING_HOURS_START", "9"))
WORKING_HOURS_END = int(os.getenv("WORKING_HOURS_END", "23"))

# Yetkazib berish sozlamalari
MIN_ORDER_AMOUNT = int(os.getenv("MIN_ORDER_AMOUNT", "30000"))
DELIVERY_BASE_FEE = int(os.getenv("DELIVERY_BASE_FEE", "10000"))
DELIVERY_EXTRA_PER_KM = int(os.getenv("DELIVERY_EXTRA_PER_KM", "2000"))
DELIVERY_FREE_KM = float(os.getenv("DELIVERY_FREE_KM", "3.0"))
MAX_DELIVERY_RADIUS_KM = float(os.getenv("MAX_DELIVERY_RADIUS_KM", "15.0"))

# Standart restoran lokatsiyasi
RESTAURANT_LAT = float(os.getenv("RESTAURANT_LAT", "41.311081"))
RESTAURANT_LON = float(os.getenv("RESTAURANT_LON", "69.240562"))

# Web App / Server sozlamalari
raw_web_url = os.getenv("WEB_APP_URL") or os.getenv("RENDER_EXTERNAL_URL") or os.getenv("RENDER_URL") or ""
if not raw_web_url or "fastfood-bot-webapp" in raw_web_url or "fast-food-1-p4bx" in raw_web_url:
    WEB_APP_URL = "https://fast-food-uzb.onrender.com"
else:
    WEB_APP_URL = raw_web_url.rstrip("/")

PORT = int(os.getenv("PORT", "8080"))

# Database
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "fastfood.db"))
DATABASE_URL = os.getenv("DATABASE_URL")

