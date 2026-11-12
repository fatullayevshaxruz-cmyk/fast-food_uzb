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
from keyboards.order_kb import get_main_menu_keyboard, get_language_inline_kb
from database import (
    init_db,
    save_or_update_user,
    get_user,
    get_cart_items,
    clear_cart,
    get_user_orders
)
from handlers.order import register_order_handlers
from handlers.admin import register_admin_handlers, cmd_admin
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


# ---------------- XUSH KELIBSIZ MATNI ----------------
def get_welcome_text(name: str) -> str:
    """Asosiy Xush kelibsiz xabari (Section 1.2 dizayni)."""
    return (
        f"🍔 <b>Darxan Burger</b> ga xush kelibsiz, <b>{name}</b>!\n\n"
        f"Tez va mazali taomlar — bir tugma bilan! 🚀\n\n"
        f"📱 <b>Buyurtma berish:</b> \"🍽 Menyu\" tugmasini bosing\n"
        f"🔍 <b>Mahsulot izlash:</b> \"🔍 Izlash\" tugmasini bosing\n"
        f"📦 <b>Buyurtmalaringiz:</b> \"📦 Buyurtmalarim\"\n\n"
        f"🕐 <b>Ish vaqti:</b> 09:00 — 23:00\n"
        f"🛵 <b>Yetkazib berish:</b> 10,000 so'm\n"
        f"📋 <b>Minimal buyurtma:</b> 30,000 so'm\n\n"
        f"Yoqimli ishtaha tilaymiz! 😋"
    )


# ---------------- START VA TIL TANLASH (ONBOARDING) ----------------
@dp.message_handler(commands=["start"], state="*")
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    full_name = message.from_user.full_name or "Mijoz"
    username = message.from_user.username

    user = await get_user(user_id)
    if not user or not user.get("language_code"):
        # 1.1. Til tanlash (Yangi foydalanuvchi bo'lsa)
        await save_or_update_user(user_id=user_id, full_name=full_name, username=username)
        await message.answer(
            text="🌐 Tilni tanlang / Выберите язык / Choose language:",
            reply_markup=get_language_inline_kb()
        )
        return

    lang = user.get("language_code", "uz")
    await save_or_update_user(user_id=user_id, full_name=full_name, username=username)
    name = message.from_user.first_name or full_name

    # 1.2. Asosiy Xush kelibsiz xabari
    await message.answer(
        text=get_welcome_text(name),
        reply_markup=get_main_menu_keyboard(lang, user_id=user_id),
        parse_mode="HTML"
    )


@dp.callback_query_handler(lambda c: c.data.startswith("set_lang:"), state="*")
async def callback_set_language(call: types.CallbackQuery):
    """Til tanlanganda ishlaydi."""
    lang_code = call.data.split(":")[1]
    user_id = call.from_user.id
    full_name = call.from_user.full_name or "Mijoz"
    name = call.from_user.first_name or full_name

    await save_or_update_user(
        user_id=user_id,
        full_name=full_name,
        username=call.from_user.username,
        language_code=lang_code
    )
    await call.answer()
    try:
        await call.message.delete()
    except Exception:
        pass

    await call.message.answer(
        text=get_welcome_text(name),
        reply_markup=get_main_menu_keyboard(lang_code, user_id=user_id),
        parse_mode="HTML"
    )


# ---------------- MENYU VA QIDIRUV (WEB APP INTEGRATSIYASI) ----------------
@dp.message_handler(lambda m: m.text in ["🍽 Menyu", "🍽 Menyu (Web App)", "Menyu", "🍔 Menyu & Buyurtma berish", "/menu"], state="*")
async def menu_handler(message: types.Message):
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("🍔 Web App Menyuni ochish", web_app=WebAppInfo(url=WEB_APP_URL))
    )
    await message.answer(
        "🍽 <b>Darxan Burger Menyu</b>\n\nBarcha taomlar, souslar va ichimliklarni ko'rish va buyurtma berish uchun quyidagi tugmani bosing:",
        reply_markup=kb,
        parse_mode="HTML"
    )


@dp.message_handler(lambda m: m.text in ["🔍 Izlash", "Izlash", "/search"], state="*")
async def search_handler(message: types.Message):
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("🔍 Qidiruv (Web App)", web_app=WebAppInfo(url=WEB_APP_URL))
    )
    await message.answer(
        "🔍 <b>Mahsulot izlash:</b>\n\nMenyudagi istalgan burger yoki taomni topish uchun quyidagi tugma orqali Web App ni oching:",
        reply_markup=kb,
        parse_mode="HTML"
    )


@dp.message_handler(lambda m: m.text in ["❤️ Sevimlilar", "Sevimlilar", "/favorites"], state="*")
async def favorites_handler(message: types.Message):
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("❤️ Sevimlilar ro'yxati (Web App)", web_app=WebAppInfo(url=WEB_APP_URL))
    )
    await message.answer(
        "❤️ <b>Sevimli taomlaringiz:</b>\n\nSevimli taomlaringizni ko'rish va buyurtma qilish uchun quyidagi tugmani bosing:",
        reply_markup=kb,
        parse_mode="HTML"
    )


# ---------------- SAVATNI KO'RISH VA BOSHQARISH ----------------
@dp.message_handler(lambda m: m.text in ["🛒 Savat", "🛒 Savatcha", "Savatcha", "Savat", "/cart"], state="*")
@dp.callback_query_handler(lambda c: c.data == "show_cart", state="*")
async def show_cart_handler(event: types.Message or types.CallbackQuery):
    user_id = event.from_user.id
    user = await get_user(user_id)
    lang = user.get("language_code", "uz") if user else "uz"

    items = await get_cart_items(user_id)
    if not items:
        msg_text = (
            "🛒 <b>Sizning savatingiz bo'sh.</b>\n\n"
            "Taom tanlash uchun quyidagi tugma orqali menyuni oching:"
        )
        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton("🍔 Menyu (Web App)", web_app=WebAppInfo(url=WEB_APP_URL))
        )
        if isinstance(event, types.CallbackQuery):
            await event.message.edit_text(msg_text, reply_markup=kb, parse_mode="HTML")
        else:
            await event.answer(msg_text, reply_markup=kb, parse_mode="HTML")
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
        await event.message.edit_text(cart_text, reply_markup=kb, parse_mode="HTML")
    else:
        await event.answer(cart_text, reply_markup=kb, parse_mode="HTML")


@dp.callback_query_handler(lambda c: c.data == "clear_cart", state="*")
async def handle_clear_cart(call: types.CallbackQuery):
    await clear_cart(call.from_user.id)
    await call.answer("🗑 Savatingiz tozalandi.")
    await call.message.edit_text(
        "🛒 Savatingiz bo'shatildi.\nTaom tanlash uchun menyuni oching:",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🍔 Menyuni ochish", web_app=WebAppInfo(url=WEB_APP_URL))
        ),
        parse_mode="HTML"
    )


# ---------------- BUYURTMALAR TARIXI ----------------
@dp.message_handler(lambda m: m.text in ["📦 Buyurtmalarim", "Buyurtmalarim", "/orders"], state="*")
async def my_orders_handler(message: types.Message):
    user_id = message.from_user.id
    orders = await get_user_orders(user_id, limit=5)
    if not orders:
        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton("🍽 Menyu", web_app=WebAppInfo(url=WEB_APP_URL))
        )
        await message.answer(
            "📦 <b>Sizda hali hech qanday buyurtma yo'q.</b>\n\nBirinchi buyurtmangizni berish uchun menyuni oching:",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    status_names = {
        "pending": "⏳ Kutilmoqda",
        "preparing": "👨‍🍳 Tayyorlanmoqda",
        "delivering": "🛵 Yetkazilmoqda",
        "completed": "✅ Yetkazildi",
        "cancelled": "❌ Bekor qilindi"
    }

    text = "📦 <b>Sizning oxirgi buyurtmalaringiz:</b>\n\n"
    for o in orders:
        st = status_names.get(o.get("status"), o.get("status", ""))
        created_at = (o.get("created_at") or "")[:16]
        total = o.get("total_amount", 0)
        items = o.get("items", [])
        items_str = ", ".join(f"{it.get('product_name', 'Taom')} x {it.get('quantity', 1)}" for it in items[:3])
        if len(items) > 3:
            items_str += f" va yana {len(items)-3} ta"
        text += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🧾 <b>Buyurtma #{o['id']}</b> ({created_at})\n"
            f"📊 Holati: <b>{st}</b>\n"
            f"📋 Tarkib: {items_str or 'Taomlar'}\n"
            f"💰 Jami summa: <b>{total:,} so'm</b>\n"
        )
    text += "━━━━━━━━━━━━━━━━━━━━"
    await message.answer(text, parse_mode="HTML")


# ---------------- PROFIL ----------------
@dp.message_handler(lambda m: m.text in ["👤 Profil", "Profil", "/profile"], state="*")
async def profile_handler(message: types.Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    name = (user.get("full_name") if user else None) or message.from_user.full_name
    phone = (user.get("phone") if user else None) or (user.get("phone_number") if user else None) or "Kiritilmagan"
    lang = user.get("language_code", "uz") if user else "uz"
    lang_display = {"uz": "🇺🇿 O'zbek", "ru": "🇷🇺 Русский", "en": "🇬🇧 English"}.get(lang, "🇺🇿 O'zbek")

    text = (
        f"👤 <b>Sizning profilingiz:</b>\n\n"
        f"▫️ <b>Ismingiz:</b> {name}\n"
        f"▫️ <b>Telefon raqamingiz:</b> {phone}\n"
        f"▫️ <b>Tanlangan til:</b> {lang_display}\n\n"
        f"🌐 <i>Tilni o'zgartirish uchun quyidagi tugmalardan birini tanlang:</i>"
    )
    await message.answer(text, reply_markup=get_language_inline_kb(), parse_mode="HTML")


# ---------------- BOG'LANISH VA BIZ HAQIMIZDA ----------------
@dp.message_handler(lambda m: m.text in ["☎️ Bog'lanish", "Bog'lanish", "ℹ️ Biz haqimizda", "Biz haqimizda", "/contact", "/about"], state="*")
async def contact_handler(message: types.Message):
    contact_text = (
        f"☎️ <b>Darxan Burger bilan bog'lanish:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📞 <b>Telefon:</b> +998 (71) 200-00-00\n"
        f"💬 <b>Qo'llab-quvvatlash:</b> @darxan_support\n"
        f"📍 <b>Bosh filial:</b> Amir Temur ko'chasi, 45-uy\n"
        f"🕐 <b>Ish vaqti:</b> 09:00 — 23:00\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Har qanday savol yoki takliflaringiz bo'lsa, biz doim yordamga tayyormiz!</i>"
    )
    await message.answer(contact_text, parse_mode="HTML")


# ==========================================
# ORDER VA ADMIN HANDLERLARINI RO'YXATGA OLISH
# ==========================================
register_order_handlers(dp)
register_admin_handlers(dp)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup, loop=loop)
