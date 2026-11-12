import logging
import asyncio
from pathlib import Path
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
    set_cart_items,
    add_to_cart,
    clear_cart
)
from handlers.order import (
    register_order_handlers,
    OrderStates,
    is_working_hours,
    get_user_lang
)
from handlers.admin import register_admin_handlers
from keyboards.order_kb import get_cancel_reply_kb, get_location_reply_kb
from config import WORKING_HOURS_START, WORKING_HOURS_END
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

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


# ---------------- WEB APP SERVER (STATIC FILES & API) ----------------
async def start_web_server():
    """Web App statik sahifalari va buyurtma API ni beruvchi aiohttp veb-server."""
    app = web.Application()

    async def index_handler(request):
        index_file = STATIC_DIR / "index.html"
        return web.FileResponse(index_file)

    async def map_handler(request):
        map_file = STATIC_DIR / "map.html"
        return web.FileResponse(map_file)

    async def api_order_handler(request):
        """Web App orqali yuborilgan buyurtmani qabul qilish va FSM ni faollashtirish."""
        try:
            data = await request.json()
        except Exception as e:
            logger.error(f"Invalid JSON in /api/order: {e}")
            return web.json_response({"ok": False, "error": "Invalid JSON"}, headers={"Access-Control-Allow-Origin": "*"})

        user_id = data.get("user_id")
        if not user_id:
            user_info = data.get("user") or {}
            user_id = user_info.get("id")

        if not user_id:
            return web.json_response({"ok": False, "error": "User ID topilmadi"}, headers={"Access-Control-Allow-Origin": "*"})

        user_id = int(user_id)
        user_info = data.get("user") or {}
        first_name = user_info.get("first_name", "Mijoz")
        lang = await get_user_lang(user_id)

        # Ish vaqti tekshiruvi (UTC+5)
        if not is_working_hours():
            alert_msg = get_text(
                "closed_alert",
                lang,
                start=WORKING_HOURS_START,
                end=WORKING_HOURS_END
            )
            try:
                await bot.send_message(user_id, alert_msg)
            except Exception:
                pass
            return web.json_response({"ok": False, "error": "closed"}, headers={"Access-Control-Allow-Origin": "*"})

        items = data.get("items", [])
        if not items:
            return web.json_response({"ok": False, "error": "Savatcha bo'sh"}, headers={"Access-Control-Allow-Origin": "*"})

        # Savatni bazaga to'liq yozamiz
        await set_cart_items(user_id, items)

        items_total = data.get("items_total", 0)
        promo_code = data.get("promo_code")
        discount_amount = data.get("discount_amount", 0)
        delivery_type = data.get("delivery_type", "delivery")

        # Foydalanuvchining FSM kontekstini olamiz
        state = dp.current_state(chat=user_id, user=user_id)
        await state.update_data(
            user_id=user_id,
            full_name=first_name,
            cart_items=items,
            items_total=items_total,
            lang=lang,
            promo_code=promo_code,
            discount_amount=discount_amount,
            delivery_type=delivery_type,
            delivery_fee=0
        )

        summary_text = (
            f"🍔 <b>Web App orqali buyurtmangiz qabul qilindi!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Mahsulotlar: <b>{items_total:,} so'm</b> ({len(items)} xil)\n"
        )
        if discount_amount > 0:
            summary_text += f"🏷 Chegirma ({promo_code}): <b>-{discount_amount:,} so'm</b>\n"
        summary_text += f"━━━━━━━━━━━━━━━━━━━━\n"

        try:
            if delivery_type == "eat_in":
                summary_text += f"📌 Turi: <b>🍽 Shu yerda (Zalda)</b>\n\n"
                await state.update_data(delivery_fee=0)
                await state.set_state(OrderStates.waiting_for_table_number)
                await bot.send_message(
                    chat_id=user_id,
                    text=summary_text + get_text("ask_table_number", lang),
                    reply_markup=get_cancel_reply_kb(lang)
                )
            else:
                summary_text += f"📌 Turi: <b>🛵 Yetkazib berish</b>\n\n"
                await state.set_state(OrderStates.waiting_for_location)
                await bot.send_message(
                    chat_id=user_id,
                    text=summary_text + get_text("ask_location", lang),
                    reply_markup=get_location_reply_kb(lang)
                )
        except Exception as e:
            logger.error(f"Error sending bot message for user {user_id}: {e}")

        return web.json_response({"ok": True}, headers={"Access-Control-Allow-Origin": "*"})

    async def options_handler(request):
        return web.Response(headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        })

    app.router.add_get("/", index_handler)
    app.router.add_get("/index.html", index_handler)
    app.router.add_get("/menu", index_handler)
    app.router.add_get("/app", index_handler)
    app.router.add_get("/map", map_handler)
    app.router.add_post("/api/order", api_order_handler)
    app.router.add_options("/api/order", options_handler)
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


# ---------------- BIZ HAQIMIZDA VA YORDAM ----------------
@dp.message_handler(lambda m: m.text in ["ℹ️ Biz haqimizda", "Biz haqimizda"], state="*")
async def cmd_about(message: types.Message):
    about_text = (
        f"🏢 <b>FastFood Express</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 Bosh filial: Amir Temur ko'chasi\n"
        f"⏰ Ish vaqti: 09:00 dan 23:00 gacha\n"
        f"🛵 Yetkazib berish: 25-35 daqiqa (15 km radiuda)\n"
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

    total = sum(i["total_price"] for i in items)
    cart_text = "🛒 <b>Sizning savatingiz:</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    for idx, item in enumerate(items, 1):
        cart_text += f"{idx}. <b>{item['name']}</b> x {item['quantity']} = {item['total_price']:,} so'm\n"
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
