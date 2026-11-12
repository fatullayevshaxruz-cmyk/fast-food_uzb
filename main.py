"""
Fast-Food va Restoran Telegram Boti + Web App Mini App (Dual Engine Architecture)
"""
import logging
import asyncio
from pathlib import Path
import aiohttp
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo,
    MenuButtonWebApp
)
from aiohttp import web

from config import BOT_TOKEN, WEB_APP_URL, PORT, is_admin
from database import (
    init_db,
    save_or_update_user,
    get_user,
    get_cart_items,
    clear_cart
)
from handlers.order import register_order_handlers
from handlers.admin import register_admin_handlers
from security.rate_limiter import AntiFloodMiddleware
from webapp_api import register_webapp_routes
from utils.i18n import get_text

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Bot va Dispatcher
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(AntiFloodMiddleware(limit=0.5))

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


# ---------------- KEEP-ALIVE FON XIZMATI ----------------
async def keep_alive():
    """Render.com serveri 15 daqiqada uxlab qolmasligi uchun fon ping xizmati."""
    await asyncio.sleep(60)
    while True:
        try:
            if WEB_APP_URL and "render.com" in WEB_APP_URL:
                async with aiohttp.ClientSession() as session:
                    async with session.get(WEB_APP_URL, timeout=15) as resp:
                        logger.info(f"Keep-alive ping to {WEB_APP_URL}: status {resp.status}")
        except Exception as e:
            logger.debug(f"Keep-alive ping error: {e}")
        await asyncio.sleep(600)  # Har 10 daqiqada ping


# ---------------- WEB APP SERVER (STATIC FILES & RICH REST API) ----------------
async def start_web_server():
    """Web App statik sahifalari va to'liq Checkout REST API ni beruvchi aiohttp veb-server."""
    app = web.Application()
    register_webapp_routes(app, bot, STATIC_DIR)
    app.router.add_static("/static", path=str(STATIC_DIR), name="static")

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"Web App server started at http://0.0.0.0:{PORT} (Serving {STATIC_DIR})")


async def on_startup(dispatcher: Dispatcher):
    """Bot ishga tushganda ma'lumotlar bazasini va veb-serverni ishga tushirish."""
    logger.info("Initializing database...")
    await init_db()

    # Chatning chap pastki burchagidagi Menyu tugmasini Web App ga sozlash
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="🍔 Menyu",
                web_app=WebAppInfo(url=WEB_APP_URL)
            )
        )
        logger.info(f"Chat Menu button configured with WebApp URL: {WEB_APP_URL}")
    except Exception as e:
        logger.warning(f"Could not set chat menu button: {e}")

    # Web App statik serverini fonda ishga tushirish
    try:
        asyncio.create_task(start_web_server())
    except Exception as e:
        logger.warning(f"Web server start warning: {e}")

    # Keep-alive xizmatini fonda ishga tushirish
    try:
        asyncio.create_task(keep_alive())
    except Exception as e:
        logger.warning(f"Keep alive start warning: {e}")

    logger.info("Bot is ready and listening!")


# ---------------- ASOSIY MENYU TUGMALARI ----------------
def get_main_menu_keyboard(lang: str = "uz", user_id: int = None) -> ReplyKeyboardMarkup:
    """Asosiy ekran Reply klaviaturasi (Katta jozibali Web App tugmasi va Admin tugmasi bilan)."""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        KeyboardButton(
            text="🍔 Menyu & Buyurtma berish",
            web_app=WebAppInfo(url=WEB_APP_URL)
        )
    )
    kb.add(
        KeyboardButton(text="🛒 Savatcha"),
        KeyboardButton(text="ℹ️ Biz haqimizda")
    )
    # Agar foydalanuvchi admin bo'lsa, maxsus Admin Panel tugmasi chiqadi
    if user_id and is_admin(user_id):
        kb.add(KeyboardButton(text="🛠 Admin Panel"))
    return kb


# ---------------- START KOMANDASI ----------------
@dp.message_handler(commands=["start"], state="*")
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    lang = message.from_user.language_code or "uz"
    if lang not in ("uz", "ru", "en"):
        lang = "uz"

    await save_or_update_user(user_id=user_id, full_name=full_name, language_code=lang)

    text = (
        f"Assalomu alaykum, <b>{full_name}</b>! 🍔🍕\n\n"
        f"<b>FastFood Express</b> – eng mazali fast-food va tezkor yetkazib berish xizmati!\n\n"
        f"🚀 <b>Yangi interaktiv Web App</b> orqali barcha taomlar rasmlarini ko'rishingiz, "
        f"saralashingiz va bir zumda buyurtma berishingiz mumkin.\n\n"
        f"👇 <i>Pastdagi tugmani bosing va menyuni oching:</i>"
    )

    # Inline klaviatura
    inline_kb = InlineKeyboardMarkup(row_width=1)
    inline_kb.add(
        InlineKeyboardButton(
            text="✨ Web App Menyu (Taomlar va Rasmlar)",
            web_app=WebAppInfo(url=WEB_APP_URL)
        ),
        InlineKeyboardButton(
            text="🛒 Savatni ko'rish",
            callback_data="show_cart"
        )
    )

    await message.answer(
        text=text,
        reply_markup=get_main_menu_keyboard(lang, user_id=user_id)
    )
    await message.answer("Menyuni ochish uchun tugmani bosing:", reply_markup=inline_kb)


# ---------------- BIZ HAQIMIZDA (ABOUT) ----------------
@dp.message_handler(lambda m: m.text in ["ℹ️ Biz haqimizda", "Biz haqimizda", "/about"], state="*")
async def about_handler(message: types.Message):
    about_text = (
        f"🏢 <b>FastFood Express</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 Bosh filial: Amir Temur ko'chasi\n"
        f"⏰ Ish vaqti: 09:00 dan 23:00 gacha\n"
        f"🛵 Yetkazib berish: 25-35 daqiqa (15 km radiusda)\n"
        f"📞 Bog'lanish: +998 (71) 200-00-00\n"
        f"🎟 Maxsus promokod: <b>FAST10</b> (-10% chegirma)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Mazali taomlar faqat bizda!</i>"
    )
    await message.answer(about_text)


# ---------------- SAVATNI KO'RISH ----------------
@dp.message_handler(lambda m: m.text in ["🛒 Savatcha", "Savatcha", "/cart"], state="*")
@dp.callback_query_handler(lambda c: c.data == "show_cart", state="*")
async def show_cart_handler(event: types.Message or types.CallbackQuery):
    user_id = event.from_user.id
    user = await get_user(user_id)
    lang = user.get("language_code", "uz") if user else "uz"

    items = await get_cart_items(user_id)
    if not items:
        msg_text = get_text("cart_empty", lang)
        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton(
                text="🍔 Menyu (Web App)",
                web_app=WebAppInfo(url=WEB_APP_URL)
            )
        )
        if isinstance(event, types.CallbackQuery):
            await event.message.edit_text(msg_text, reply_markup=kb)
        else:
            await event.answer(msg_text, reply_markup=kb)
        return

    total = sum((i.get("price", 0) * i.get("quantity", 1)) for i in items)
    cart_text = "🛒 <b>Sizning savatingiz:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    for idx, item in enumerate(items, 1):
        q = item.get("quantity", 1)
        p = item.get("price", 0)
        cart_text += f"{idx}. <b>{item['name']}</b> x {q} = {p * q:,} so'm\n"
    cart_text += f"━━━━━━━━━━━━━━━━━━━━\n💰 <b>Jami:</b> <b>{total:,} so'm</b>"

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🚀 Rasmiylashtirish (Checkout)", callback_data="checkout")
    )
    kb.add(
        InlineKeyboardButton("🗑 Tozalash", callback_data="clear_cart"),
        InlineKeyboardButton("🍔 Menyu (Web App)", web_app=WebAppInfo(url=WEB_APP_URL))
    )

    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(cart_text, reply_markup=kb)
    else:
        await event.answer(cart_text, reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data == "clear_cart", state="*")
async def handle_clear_cart(call: types.CallbackQuery):
    await clear_cart(call.from_user.id)
    await call.answer("🗑 Savatingiz tozalandi.")
    await call.message.edit_text(
        "🛒 Savatingiz bo'shatildi.\nTaom tanlash uchun Web App ni oching:",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🍔 Menyuni ochish", web_app=WebAppInfo(url=WEB_APP_URL))
        )
    )


# ==========================================
# ORDER VA ADMIN HANDLERLARINI RO'YXATGA OLISH
# ==========================================
register_order_handlers(dp)
register_admin_handlers(dp)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup, loop=loop)
