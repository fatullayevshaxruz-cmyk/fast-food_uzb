import logging
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import BOT_TOKEN
from database import (
    init_db,
    save_or_update_user,
    get_user,
    get_cart_items,
    add_to_cart,
    clear_cart
)
from handlers.order import register_order_handlers
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


async def on_startup(dispatcher: Dispatcher):
    """Bot ishga tushganda ma'lumotlar bazasini yuklash."""
    logger.info("Initializing database...")
    await init_db()
    logger.info("Bot is ready and listening!")


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
        f"Assalomu alaykum, <b>{full_name}</b>! 🍔🍕\n"
        f"<b>Fast Food</b> yetkazib berish xizmatiga xush kelibsiz!\n\n"
        f"Quyidagi menyudan taomlarni tanlashingiz va tez fursatda buyurtma berishingiz mumkin."
    )

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🍔 Menyu", callback_data="show_menu"),
        InlineKeyboardButton("🛒 Savat", callback_data="show_cart")
    )
    await message.answer(text, reply_markup=kb)


# ---------------- MENYU VA MAHSULOTLAR ----------------
@dp.callback_query_handler(lambda c: c.data == "show_menu", state="*")
async def show_menu(call: types.CallbackQuery):
    await call.answer()
    import aiosqlite
    from config import DATABASE_PATH

    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM products WHERE is_available = 1") as cursor:
            products = await cursor.fetchall()

    kb = InlineKeyboardMarkup(row_width=1)
    for p in products:
        kb.add(
            InlineKeyboardButton(
                f"➕ {p['name']} - {p['price']:,} so'm",
                callback_data=f"add_cart:{p['id']}"
            )
        )
    kb.add(InlineKeyboardButton("🛒 Savatga o'tish", callback_data="show_cart"))

    await call.message.edit_text("📋 <b>Bizning menyu:</b>\nSavatga qo'shish uchun taomni bosing:", reply_markup=kb)


# ---------------- SAVATGA QO'SHISH ----------------
@dp.callback_query_handler(lambda c: c.data.startswith("add_cart:"), state="*")
async def add_item_to_cart(call: types.CallbackQuery):
    product_id = int(call.data.split(":")[1])
    user_id = call.from_user.id

    await add_to_cart(user_id, product_id, 1)
    await call.answer("✅ Mahsulot savatga qo'shildi!", show_alert=False)


# ---------------- SAVATNI KO'RISH ----------------
@dp.message_handler(commands=["cart"], state="*")
@dp.callback_query_handler(lambda c: c.data == "show_cart", state="*")
async def show_cart_handler(event: types.Message or types.CallbackQuery):
    user_id = event.from_user.id
    user = await get_user(user_id)
    lang = user.get("language_code", "uz") if user else "uz"

    items = await get_cart_items(user_id)
    if not items:
        msg_text = get_text("cart_empty", lang)
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("🍔 Menyu", callback_data="show_menu"))
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
        InlineKeyboardButton("🍔 Menyu", callback_data="show_menu")
    )

    if isinstance(event, types.CallbackQuery):
        await event.message.edit_text(cart_text, reply_markup=kb)
    else:
        await event.answer(cart_text, reply_markup=kb)


@dp.callback_query_handler(lambda c: c.data == "clear_cart", state="*")
async def handle_clear_cart(call: types.CallbackQuery):
    await clear_cart(call.from_user.id)
    await call.answer("🗑 Savatingiz tozalandi.")
    await show_menu(call)


# ==========================================
# ORDER HANDLERLARINI RO'YXATGA OLISH
# ==========================================
register_order_handlers(dp)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup, loop=loop)


