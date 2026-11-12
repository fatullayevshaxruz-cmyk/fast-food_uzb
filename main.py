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
    clear_cart,
    create_order,
    check_promo_code,
    mark_promo_used,
    get_active_branches,
    get_product_by_id,
    get_order_by_id,
    mark_order_paid,
    get_order_payment_status,
    get_user_orders
)
from handlers.order import (
    register_order_handlers,
    OrderStates,
    is_working_hours,
    get_user_lang,
    clean_phone_number
)
from utils.geo import (
    is_within_uzbekistan,
    find_nearest_branch,
    calculate_delivery_fee,
    reverse_geocode
)
from utils.notifications import notify_admins_new_order
from handlers.admin import register_admin_handlers
from keyboards.order_kb import get_cancel_reply_kb, get_location_reply_kb
from config import WORKING_HOURS_START, WORKING_HOURS_END, MAX_DELIVERY_RADIUS_KM
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


# ---------------- WEB APP SERVER (STATIC FILES & RICH REST API) ----------------
async def start_web_server():
    """Web App statik sahifalari va to'liq Checkout REST API ni beruvchi aiohttp veb-server."""
    app = web.Application()

    CORS_HEADERS = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }

    async def index_handler(request):
        index_file = STATIC_DIR / "index.html"
        return web.FileResponse(index_file)

    async def map_handler(request):
        map_file = STATIC_DIR / "map.html"
        return web.FileResponse(map_file)

    async def options_handler(request):
        return web.Response(headers=CORS_HEADERS)

    # 1. FILIALLAR RO'YXATI
    async def api_branches_handler(request):
        branches = await get_active_branches()
        return web.json_response({"ok": True, "branches": branches}, headers=CORS_HEADERS)

    # 2. PROMOKODNI TEKSHIRISH
    async def api_promo_check_handler(request):
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "Invalid JSON"}, headers=CORS_HEADERS)

        code = (data.get("code") or "").strip().upper()
        amount = int(data.get("amount") or 0)

        is_valid, promo_data, reason = await check_promo_code(code, amount)
        if not is_valid or not promo_data:
            err_msg = {
                "not_found": "Bunday promokod mavjud emas!",
                "inactive": "Ushbu promokod faol emas!",
                "limit_reached": "Promokodning foydalanish limiti tugagan!",
                "min_amount_not_met": f"Minimal buyurtma summasi: {promo_data.get('min_order_amount', 0):,} so'm!" if promo_data else "Summa yetarli emas!"
            }.get(reason, "Promokod yaroqsiz!")
            return web.json_response({"ok": False, "error": err_msg}, headers=CORS_HEADERS)

        discount_percent = promo_data.get("discount_percent", 0)
        discount_amount = int((amount * discount_percent) / 100)
        return web.json_response({
            "ok": True,
            "code": code,
            "discount_percent": discount_percent,
            "discount_amount": discount_amount
        }, headers=CORS_HEADERS)

    # 3. GEO / MASOFA VA YETKAZISH NARXINI HISOBLASH
    async def api_calculate_delivery_handler(request):
        try:
            data = await request.json()
            lat = float(data.get("lat"))
            lon = float(data.get("lon"))
        except Exception:
            return web.json_response({"ok": False, "error": "Noto'g'ri koordinatalar"}, headers=CORS_HEADERS)

        if not is_within_uzbekistan(lat, lon):
            return web.json_response({
                "ok": False,
                "error": "Belgilangan nuqta O'zbekiston hududidan tashqarida!"
            }, headers=CORS_HEADERS)

        branches = await get_active_branches()
        nearest_branch, distance_km = find_nearest_branch(lat, lon, branches)

        if distance_km > MAX_DELIVERY_RADIUS_KM:
            return web.json_response({
                "ok": False,
                "error": f"Yetkazib berish zonasi cheklangan ({MAX_DELIVERY_RADIUS_KM:.0f} km). Siz {distance_km:.1f} km uzoqlikdasiz."
            }, headers=CORS_HEADERS)

        fee = calculate_delivery_fee(distance_km)
        address = await reverse_geocode(lat, lon)

        return web.json_response({
            "ok": True,
            "address": address,
            "distance_km": round(distance_km, 1),
            "delivery_fee": fee,
            "branch_id": nearest_branch.get("id"),
            "branch_name": nearest_branch.get("name")
        }, headers=CORS_HEADERS)

    # 4. BUYURTMA YARATISH (POST /api/order/create)
    async def api_order_create_handler(request):
        try:
            data = await request.json()
        except Exception as e:
            return web.json_response({"ok": False, "error": f"Invalid JSON: {e}"}, headers=CORS_HEADERS)

        user_id = data.get("user_id")
        if not user_id:
            user_data = data.get("user") or {}
            user_id = user_data.get("id")

        if not user_id:
            return web.json_response({"ok": False, "error": "Foydalanuvchi ma'lumotlari topilmadi!"}, headers=CORS_HEADERS)

        user_id = int(user_id)
        phone = clean_phone_number(data.get("phone") or "")
        if not phone:
            return web.json_response({"ok": False, "error": "Iltimos, to'g'ri telefon raqamingizni kiriting (+998901234567)"}, headers=CORS_HEADERS)

        # Foydalanuvchi telefonini bazaga yozib qo'yamiz
        await save_or_update_user(user_id, phone=phone, full_name=(data.get("user") or {}).get("first_name", ""))

        raw_items = data.get("items", [])
        if not raw_items:
            return web.json_response({"ok": False, "error": "Savatingiz bo'sh!"}, headers=CORS_HEADERS)

        # Xavfsizlik: Mahsulot narxlarini bazadan qayta hisoblaymiz (soxtalashtirishdan himoya)
        verified_items = []
        items_total = 0
        for item in raw_items:
            p_id = item.get("id") or item.get("product_id")
            qty = max(1, int(item.get("quantity") or item.get("count", 1)))
            p_data = await get_product_by_id(p_id)
            if p_data and p_data.get("is_available") == 1:
                real_price = p_data["price"]
                item_sum = real_price * qty
                items_total += item_sum
                verified_items.append({
                    "product_id": p_id,
                    "name": p_data["name"],
                    "price": real_price,
                    "quantity": qty,
                    "total_price": item_sum
                })

        if not verified_items:
            return web.json_response({"ok": False, "error": "Tanlangan mahsulotlar hozirda mavjud emas!"}, headers=CORS_HEADERS)

        delivery_type = data.get("delivery_type", "delivery")
        lat = data.get("lat")
        lon = data.get("lon")
        table_number = data.get("table_number")
        address = data.get("address", "")
        branch_id = data.get("branch_id")
        branch_name = data.get("branch_name")
        distance_km = data.get("distance_km")

        if delivery_type == "eat_in":
            delivery_fee = 0
            if not table_number:
                return web.json_response({"ok": False, "error": "Stol raqami kiritilmadi!"}, headers=CORS_HEADERS)
            address = f"Stol raqami: #{table_number}"
            branch_name = branch_name or "Restoran zali"
        else:
            # Yetkazib berish
            if not lat or not lon:
                return web.json_response({"ok": False, "error": "Yetkazib berish manzili yoki koordinatasi ko'rsatilmadi!"}, headers=CORS_HEADERS)
            lat = float(lat)
            lon = float(lon)
            branches = await get_active_branches()
            nearest_branch, calc_dist = find_nearest_branch(lat, lon, branches)
            if calc_dist > MAX_DELIVERY_RADIUS_KM:
                return web.json_response({"ok": False, "error": "Manzil yetkazib berish zonasidan tashqarida!"}, headers=CORS_HEADERS)
            distance_km = calc_dist
            branch_id = nearest_branch.get("id")
            branch_name = nearest_branch.get("name")
            delivery_fee = calculate_delivery_fee(distance_km)
            if not address or len(address) < 3:
                address = await reverse_geocode(lat, lon)

        # Promokod chegirmasi
        promo_code = data.get("promo_code")
        discount_amount = 0
        if promo_code:
            is_valid, p_dict, _ = await check_promo_code(promo_code, items_total)
            if is_valid and p_dict:
                discount_amount = int((items_total * p_dict["discount_percent"]) / 100)
                await mark_promo_used(p_dict["id"])

        final_total = max(0, items_total - discount_amount) + delivery_fee
        payment_method = data.get("payment_method", "cash")

        # To'lov holati
        payment_status = "cash" if payment_method == "cash" else "unpaid"

        # Bazaga buyurtmani yozish
        order_id = await create_order(
            user_id=user_id,
            delivery_type=delivery_type,
            table_number=table_number,
            address=address,
            lat=lat,
            lon=lon,
            branch_id=branch_id,
            branch_name=branch_name,
            distance_km=distance_km,
            phone=phone,
            note=data.get("note", ""),
            promo_code=promo_code,
            discount_amount=discount_amount,
            items_total=items_total,
            delivery_fee=delivery_fee,
            final_total=final_total,
            payment_method=payment_method,
            items=verified_items,
            payment_status=payment_status
        )

        # Savatni tozalash
        await clear_cart(user_id)

        # Marshrutlash:
        if payment_method == "cash":
            # NAQD: darhol kanalga yuboriladi
            try:
                order_full_data = {
                    "delivery_type": delivery_type,
                    "table_number": table_number,
                    "branch_name": branch_name,
                    "address": address,
                    "distance_km": distance_km,
                    "lat": lat,
                    "lon": lon,
                    "phone": phone,
                    "full_name": (data.get("user") or {}).get("first_name", "Mijoz"),
                    "user_id": user_id,
                    "note": data.get("note", ""),
                    "items_total": items_total,
                    "discount_amount": discount_amount,
                    "promo_code": promo_code,
                    "delivery_fee": delivery_fee,
                    "final_total": final_total,
                    "payment_method": "cash"
                }
                await notify_admins_new_order(bot, order_full_data, verified_items, order_id)
            except Exception as ex:
                logger.error(f"Error notifying channel for cash order #{order_id}: {ex}")

            # Mijozga botda chek
            try:
                await bot.send_message(
                    user_id,
                    f"✅ <b>Buyurtmangiz #{order_id} qabul qilindi!</b>\n"
                    f"To'lov turi: 💵 Naqd pul\n"
                    f"Jami summa: <b>{final_total:,} so'm</b>\n"
                    f"Operatorlarimiz tez orada siz bilan bog'lanishadi! 😊",
                    parse_mode="HTML"
                )
            except Exception:
                pass

            return web.json_response({
                "ok": True,
                "order_id": order_id,
                "payment_status": "cash",
                "final_total": final_total
            }, headers=CORS_HEADERS)

        else:
            # CLICK yoki PAYME:
            # QAT'IY QOIDA: Toki to'lov o'tmaguncha OSHXONA KANALIGA YUBORILMAYDI!
            payment_url = ""
            if payment_method == "click":
                # Click to'lov havolasi (Deep link)
                payment_url = f"https://my.click.uz/services/pay?service_id=32456&merchant_id=23451&amount={final_total}&transaction_param={order_id}"
            elif payment_method == "payme":
                # Payme to'lov havolasi
                payment_url = f"https://checkout.paycom.uz/checkout/{order_id}?amount={final_total * 100}"

            return web.json_response({
                "ok": True,
                "order_id": order_id,
                "payment_status": "unpaid",
                "payment_url": payment_url,
                "final_total": final_total
            }, headers=CORS_HEADERS)

    # 5. TO'LOV HOLATINI TEKSHIRISH (POLLING ENDPOINT)
    async def api_order_payment_status_handler(request):
        order_id_str = request.query.get("order_id")
        if not order_id_str or not order_id_str.isdigit():
            return web.json_response({"ok": False, "error": "order_id required"}, headers=CORS_HEADERS)

        order_id = int(order_id_str)
        status_info = await get_order_payment_status(order_id)
        if not status_info:
            return web.json_response({"ok": False, "error": "Order not found"}, headers=CORS_HEADERS)

        return web.json_response({
            "ok": True,
            "order_id": order_id,
            "status": status_info.get("status"),
            "payment_status": status_info.get("payment_status"),
            "final_total": status_info.get("final_total")
        }, headers=CORS_HEADERS)

    # 6. TO'LOVNI SIMULYATSIYA QILISH / TASDIQLASH (TEST & WEBHOOK)
    async def api_order_pay_simulate_handler(request):
        try:
            data = await request.json()
            order_id = int(data.get("order_id"))
        except Exception:
            return web.json_response({"ok": False, "error": "order_id required"}, headers=CORS_HEADERS)

        order = await get_order_by_id(order_id)
        if not order:
            return web.json_response({"ok": False, "error": "Order topilmadi"}, headers=CORS_HEADERS)

        # To'langan deb belgilash
        await mark_order_paid(order_id)

        # ENDI OSHXONA KANALIGA YUBORILADI!
        try:
            await notify_admins_new_order(
                bot,
                order,
                order.get("items", []),
                order_id
            )
        except Exception as e:
            logger.error(f"Error sending paid order to kitchen: {e}")

        # Mijozga botda bildirishnoma
        try:
            await bot.send_message(
                order["user_id"],
                f"🎉 <b>To'lov muvaffaqiyatli qabul qilindi!</b>\n"
                f"Buyurtma #{order_id} oshxonaga topshirildi va tayyorlanmoqda. 👨‍🍳",
                parse_mode="HTML"
            )
        except Exception:
            pass

        return web.json_response({"ok": True, "order_id": order_id, "payment_status": "paid"}, headers=CORS_HEADERS)

    # 7. FOYDALANUVCHINING BUYURTMALARI (ORDER TRACKING)
    async def api_user_orders_handler(request):
        user_id_str = request.query.get("user_id")
        if not user_id_str or not user_id_str.isdigit():
            return web.json_response({"ok": False, "error": "user_id required"}, headers=CORS_HEADERS)

        user_id = int(user_id_str)
        orders = await get_user_orders(user_id, limit=10)
        return web.json_response({"ok": True, "orders": orders}, headers=CORS_HEADERS)

    # Routerlarni ulash
    app.router.add_get("/", index_handler)
    app.router.add_get("/index.html", index_handler)
    app.router.add_get("/menu", index_handler)
    app.router.add_get("/app", index_handler)
    app.router.add_get("/map", map_handler)

    # API Route lar
    app.router.add_get("/api/branches", api_branches_handler)
    app.router.add_options("/api/branches", options_handler)

    app.router.add_post("/api/promo", api_promo_check_handler)
    app.router.add_options("/api/promo", options_handler)

    app.router.add_post("/api/order/calculate", api_calculate_delivery_handler)
    app.router.add_options("/api/order/calculate", options_handler)

    app.router.add_post("/api/order/create", api_order_create_handler)
    app.router.add_options("/api/order/create", options_handler)

    app.router.add_get("/api/order/payment-status", api_order_payment_status_handler)
    app.router.add_options("/api/order/payment-status", options_handler)

    app.router.add_post("/api/order/pay-simulate", api_order_pay_simulate_handler)
    app.router.add_options("/api/order/pay-simulate", options_handler)

    app.router.add_get("/api/user/orders", api_user_orders_handler)
    app.router.add_options("/api/user/orders", options_handler)

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
