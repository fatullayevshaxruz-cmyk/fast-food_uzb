"""
Fast-food va restoran buyurtmalarini qabul qilishga mo'ljallangan
FSM (Finite State Machine) asosidagi to'liq va xavfsiz order.py moduli.
"""

import re
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton

from config import (
    WORKING_HOURS_START,
    WORKING_HOURS_END,
    MIN_ORDER_AMOUNT,
    MAX_DELIVERY_RADIUS_KM
)
from database import (
    get_user,
    save_or_update_user,
    get_cart_items,
    set_cart_items,
    clear_cart,
    check_promo_code,
    mark_promo_used,
    get_active_branches,
    create_order,
    add_feedback
)
from utils.geo import (
    is_within_uzbekistan,
    find_nearest_branch,
    calculate_delivery_fee,
    reverse_geocode
)
from utils.i18n import get_text
from utils.notifications import notify_admins_new_order
from utils.order_cancel import (
    start_order_cancel_window,
    handle_user_cancel_order,
    get_cancel_countdown_kb
)
from security.payment_guard import generate_click_link, generate_payme_link
from keyboards.order_kb import (
    get_delivery_type_reply_kb,
    get_location_reply_kb,
    get_phone_reply_kb,
    get_skip_or_cancel_reply_kb,
    get_skip_or_cancel_inline_kb,
    get_cancel_reply_kb,
    get_payment_method_reply_kb,
    get_payment_method_kb,
    get_online_payment_channels_kb,
    get_main_menu_keyboard
)

logger = logging.getLogger(__name__)


# ==========================================
# FSM HOLATLARI (STATES)
# ==========================================
class OrderStates(StatesGroup):
    waiting_for_delivery_type = State()
    waiting_for_table_number = State()
    waiting_for_location = State()
    waiting_for_phone = State()
    waiting_for_note = State()
    waiting_for_promo = State()
    waiting_for_payment_method = State()


# ==========================================
# YORDAMCHI FUNKSIYALAR
# ==========================================
def is_working_hours() -> bool:
    """Toshkent vaqti bo'yicha (UTC+5) ish vaqtini tekshiradi."""
    tashkent_now = datetime.utcnow() + timedelta(hours=5)
    current_hour = tashkent_now.hour
    return WORKING_HOURS_START <= current_hour < WORKING_HOURS_END


def clean_phone_number(raw_phone: str) -> Optional[str]:
    """Telefon raqamini tekshirib tozalaydi (+998901234567 formatida)."""
    digits = re.sub(r"\D", "", raw_phone)
    if digits.startswith("998") and len(digits) == 12:
        return f"+{digits}"
    elif len(digits) == 9:
        return f"+998{digits}"
    elif digits.startswith("8") and len(digits) == 10:
        return f"+998{digits[1:]}"
    return None


async def get_user_lang(user_id: int) -> str:
    """Foydalanuvchi tilini bazadan oladi (default: 'uz')."""
    user = await get_user(user_id)
    return user.get("language_code", "uz") if user else "uz"


# ==========================================
# 1. BOSHLANISH: CHECKOUT VA ISH VAQTI TEKSHIRUVI
# ==========================================
async def process_web_app_checkout(message: types.Message, state: FSMContext):
    """
    Telegram Web App orqali yuborilgan buyurtma savatini qabul qiladi
    va bevosita FSM zanjiriga ulaydi.
    """
    try:
        raw_data = message.web_app_data.data
        data = json.loads(raw_data)
    except Exception as e:
        logger.error(f"Error parsing web app data: {e}")
        return

    if data.get("action") != "web_app_checkout":
        return

    user_id = message.from_user.id
    lang = await get_user_lang(user_id)

    # Ish vaqti tekshiruvi (UTC+5)
    if not is_working_hours():
        alert_msg = get_text(
            "closed_alert",
            lang,
            start=WORKING_HOURS_START,
            end=WORKING_HOURS_END
        )
        await message.answer(alert_msg)
        return

    items = data.get("items", [])
    if not items:
        await message.answer(get_text("cart_empty", lang))
        return

    # Savatni bazaga to'liq saqlaymiz
    await set_cart_items(user_id, items)

    items_total = data.get("items_total", 0)
    promo_code = data.get("promo_code")
    discount_amount = data.get("discount_amount", 0)
    delivery_type = data.get("delivery_type", "delivery")

    # FSM xotirasiga kiritish
    await state.update_data(
        user_id=user_id,
        full_name=message.from_user.full_name,
        cart_items=items,
        items_total=items_total,
        lang=lang,
        promo_code=promo_code,
        discount_amount=discount_amount,
        delivery_type=delivery_type,
        delivery_fee=0
    )

    # Buyurtma tarkibi haqida qisqa ma'lumot
    summary_text = (
        f"🍔 <b>Web App orqali buyurtmangiz qabul qilindi!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Mahsulotlar: <b>{items_total:,} so'm</b> ({len(items)} xil)\n"
    )
    if discount_amount > 0:
        summary_text += f"🏷 Chegirma ({promo_code}): <b>-{discount_amount:,} so'm</b>\n"
    summary_text += f"━━━━━━━━━━━━━━━━━━━━\n"

    if delivery_type == "eat_in":
        summary_text += f"📌 Turi: <b>🍽 Shu yerda (Zalda)</b>\n\n"
        await state.update_data(delivery_fee=0)
        await OrderStates.waiting_for_table_number.set()
        await message.answer(
            text=summary_text + get_text("ask_table_number", lang),
            reply_markup=get_cancel_reply_kb(lang)
        )
    else:
        # Yetkazib berish
        summary_text += f"📌 Turi: <b>🛵 Yetkazib berish</b>\n\n"
        await OrderStates.waiting_for_location.set()
        await message.answer(
            text=summary_text + get_text("ask_location", lang),
            reply_markup=get_location_reply_kb(lang)
        )


async def start_checkout(call: types.CallbackQuery, state: FSMContext):
    """
    Buyurtmani rasmiylashtirish boshlanishi:
    - Savat bo'shligi tekshiriladi
    - Ish vaqti tekshiriladi
    - Yetkazib berish turini tanlash taklif etiladi
    """
    user_id = call.from_user.id
    lang = await get_user_lang(user_id)

    # 1. Savat tekshiruvi
    cart_items = await get_cart_items(user_id)
    if not cart_items:
        await call.answer(get_text("cart_empty", lang), show_alert=True)
        return

    # 2. Ish vaqti tekshiruvi (UTC+5)
    if not is_working_hours():
        alert_msg = get_text(
            "closed_alert",
            lang,
            start=WORKING_HOURS_START,
            end=WORKING_HOURS_END
        )
        await call.answer(alert_msg, show_alert=True)
        return

    await call.answer()

    # Mahsulotlar summasini hisoblash
    items_total = sum(item["total_price"] for item in cart_items)

    # FSM xotirasiga boshlang'ich ma'lumotlarni yozamiz
    await state.update_data(
        user_id=user_id,
        full_name=call.from_user.full_name,
        cart_items=cart_items,
        items_total=items_total,
        lang=lang,
        discount_amount=0,
        promo_code=None,
        delivery_fee=0
    )

    # Yetkazish turini tanlash holatiga o'tish (Section 2.1)
    await OrderStates.waiting_for_delivery_type.set()
    await call.message.delete()
    await call.message.answer(
        text="🛵 <b>Yetkazib berish turini tanlang:</b>",
        reply_markup=get_delivery_type_reply_kb(lang),
        parse_mode="HTML"
    )


# ==========================================
# 2. YETKAZIB BERISH TURINI TANLASH
# ==========================================
async def process_delivery_type(call: types.CallbackQuery, state: FSMContext):
    """
    «🍽 Shu yerda» yoki «🛵 Yetkazib berish» tanlanganda ishlaydi.
    """
    choice = call.data.split(":")[1]
    data = await state.get_data()
    lang = data.get("lang", "uz")
    items_total = data.get("items_total", 0)

    await call.answer()

    if choice == "eat_in":
        # Shu yerda: Stol raqami so'raladi (Section 2.2)
        await state.update_data(delivery_type="eat_in", delivery_fee=0)
        await OrderStates.waiting_for_table_number.set()
        try:
            await call.message.delete()
        except Exception:
            pass
        await call.message.answer(
            text="🪑 <b>Stol raqamini kiriting:</b>\n<i>(Masalan: 5 yoki 12)</i>",
            reply_markup=get_cancel_reply_kb(lang),
            parse_mode="HTML"
        )

    elif choice == "delivery":
        # Yetkazib berish: Minimal summa tekshiriladi (Section 2.3)
        if items_total < MIN_ORDER_AMOUNT:
            diff = MIN_ORDER_AMOUNT - items_total
            await call.message.answer(
                f"⚠️ Minimal buyurtma summasi: <b>{MIN_ORDER_AMOUNT:,} so'm</b>!\n"
                f"Sizda: {items_total:,} so'm (Yana {diff:,} so'mlik mahsulot qo'shing).",
                parse_mode="HTML"
            )
            return

        await state.update_data(delivery_type="delivery")
        await OrderStates.waiting_for_location.set()
        try:
            await call.message.delete()
        except Exception:
            pass
        await call.message.answer(
            text="📍 <b>Yetkazib berish manzilini yuboring:</b>\n\n<i>Pastdagi tugma orqali GPS lokatsiyangizni jo'nating yoki xaritadan tanlang:</i>",
            reply_markup=get_location_reply_kb(lang),
            parse_mode="HTML"
        )


async def process_delivery_type_message(message: types.Message, state: FSMContext):
    """
    «🍽 Shu yerda (Kafe)» yoki «🛵 Yetkazib berish» Reply tugmasi bosilganda ishlaydi.
    """
    text = (message.text or "").strip()
    data = await state.get_data()
    lang = data.get("lang", "uz")
    items_total = data.get("items_total", 0)

    if any(k in text for k in ["Shu yerda", "Kafe", "Eat", "Здесь", "В кафе"]):
        await state.update_data(delivery_type="eat_in", delivery_fee=0)
        await OrderStates.waiting_for_table_number.set()
        await message.answer(
            text="🪑 <b>Stol raqamini kiriting:</b>\n<i>(Masalan: 5 yoki 12)</i>",
            reply_markup=get_cancel_reply_kb(lang),
            parse_mode="HTML"
        )
    elif any(k in text for k in ["Yetkazib", "Delivery", "Доставка"]):
        if items_total < MIN_ORDER_AMOUNT:
            diff = MIN_ORDER_AMOUNT - items_total
            await message.answer(
                f"⚠️ Minimal buyurtma summasi: <b>{MIN_ORDER_AMOUNT:,} so'm</b>!\n"
                f"Sizda: {items_total:,} so'm (Yana {diff:,} so'mlik mahsulot qo'shing).",
                parse_mode="HTML"
            )
            return

        await state.update_data(delivery_type="delivery")
        await OrderStates.waiting_for_location.set()
        await message.answer(
            text="📍 <b>Yetkazib berish manzilini yuboring:</b>\n\n<i>Pastdagi tugma orqali GPS lokatsiyangizni jo'nating yoki xaritadan tanlang:</i>",
            reply_markup=get_location_reply_kb(lang),
            parse_mode="HTML"
        )
    elif any(k in text for k in ["Bekor", "Cancel", "Отмена"]):
        await cancel_order_handler(message, state)
    else:
        await message.answer(
            "Iltimos, yetkazib berish turini tanlang:",
            reply_markup=get_delivery_type_reply_kb(lang)
        )


# ==========================================
# 2.1. STOL RAQAMINI QABUL QILISH (EAT_IN)
# ==========================================
async def process_table_number(message: types.Message, state: FSMContext):
    """
    Stol raqamini qabul qiladi: faqat musbat butun son bo'lishi shart.
    Telefon va manzil so'ralmasdan to'g'ridan-to'g'ri izoh bosqichiga o'tiladi.
    """
    data = await state.get_data()
    lang = data.get("lang", "uz")
    text = (message.text or "").strip()

    if any(k in text for k in ["Bekor", "Cancel", "Отмена"]):
        await cancel_order_handler(message, state)
        return

    if not text.isdigit() or int(text) <= 0:
        await message.answer(
            "⚠️ Iltimos, faqat musbat butun son kiriting (Masalan: 5 yoki 12):",
            reply_markup=get_cancel_reply_kb(lang)
        )
        return

    table_num = int(text)
    user_info = await get_user(message.from_user.id)
    phone = user_info.get("phone", "Stolda buyurtma") if user_info else "Stolda buyurtma"

    await state.update_data(
        table_number=table_num,
        address=f"Stol raqami: #{table_num}",
        branch_name="Restoran zali",
        distance_km=0.0,
        phone=phone
    )

    # To'g'ridan-to'g'ri Izoh bosqichiga o'tamiz (Section 2.5)
    await OrderStates.waiting_for_note.set()
    note_text = (
        "💬 <b>Buyurtma uchun qo'shimcha izohingiz bormi?</b>\n"
        "<i>(Masalan: Domofon kodi: 45, achchiq bo'lmasin)</i>"
    )
    await message.answer(
        text=note_text,
        reply_markup=get_skip_or_cancel_reply_kb(lang),
        parse_mode="HTML"
    )


# ==========================================
# 3. JOYLASHUV, GEO-ROUTING VA XAVFSIZLIK
# ==========================================
async def process_location(message: types.Message, state: FSMContext):
    """
    GPS, Telegram WebApp yoki matnli lokatsiyani qabul qiladi va tahlil qiladi:
    1. O'zbekiston chegarasi tekshiruvi
    2. Reverse Geocoding (aniq manzil)
    3. Eng yaqin filial va 15 km zona tekshiruvi
    4. Smart phone autofill
    """
    data = await state.get_data()
    lang = data.get("lang", "uz")
    lat, lon = None, None
    raw_address_text = None

    # 1. Telegram GPS yoki Venue
    if message.location:
        lat = message.location.latitude
        lon = message.location.longitude
    elif message.venue and message.venue.location:
        lat = message.venue.location.latitude
        lon = message.venue.location.longitude

    # 2. Telegram WebApp ma'lumoti
    elif message.web_app_data:
        try:
            web_data = json.loads(message.web_app_data.data)
            lat = float(web_data.get("lat"))
            lon = float(web_data.get("lon"))
            raw_address_text = web_data.get("address")
        except Exception as e:
            logger.warning(f"WebApp parse error: {e}")

    # 3. Matnli manzil (agar koordinata bo'lmasa)
    elif message.text:
        raw_address_text = message.text.strip()
        # Standart Toshkent koordinatasi fallback
        from config import RESTAURANT_LAT, RESTAURANT_LON
        lat, lon = RESTAURANT_LAT, RESTAURANT_LON

    if lat is None or lon is None:
        await message.answer(get_text("ask_location", lang), reply_markup=get_location_reply_kb(lang))
        return

    # O'zbekiston chegarasi tekshiruvi
    if not is_within_uzbekistan(lat, lon):
        await message.answer(get_text("location_out_of_uzb", lang), reply_markup=get_location_reply_kb(lang))
        return

    # Eng yaqin filialni aniqlash
    branches = await get_active_branches()
    nearest_branch, distance_km = find_nearest_branch(lat, lon, branches)

    # 15 km yetkazib berish zonasi tekshiruvi
    if distance_km > MAX_DELIVERY_RADIUS_KM:
        await message.answer(
            get_text(
                "location_too_far",
                lang,
                branch=nearest_branch.get("name", "Bosh filial"),
                distance=distance_km,
                max_radius=MAX_DELIVERY_RADIUS_KM
            ),
            reply_markup=get_location_reply_kb(lang)
        )
        return

    # Inson tushunadigan manzilni olish (Reverse Geocode)
    if raw_address_text:
        address = raw_address_text
    else:
        address = await reverse_geocode(lat, lon, lang)

    # Yetkazish narxini hisoblash
    delivery_fee = calculate_delivery_fee(distance_km)

    await state.update_data(
        lat=lat,
        lon=lon,
        address=address,
        branch_id=nearest_branch.get("id"),
        branch_name=nearest_branch.get("name"),
        branch_channel_id=nearest_branch.get("channel_id"),
        distance_km=distance_km,
        delivery_fee=delivery_fee
    )

    # Manzil qabul qilinganligi haqida xabar
    await message.answer(
        get_text(
            "location_confirmed",
            lang,
            address=address,
            branch=nearest_branch.get("name"),
            distance=distance_km
        ),
        reply_markup=ReplyKeyboardRemove()
    )

    # 4. SMART PHONE AUTOFILL
    # Agar telefon raqami bazada oldindan mavjud bo'lsa, qayta so'ramasdan izohga o'tiladi
    user_info = await get_user(message.from_user.id)
    saved_phone = user_info.get("phone") if user_info else None

    if saved_phone and len(saved_phone) >= 9:
        await state.update_data(phone=saved_phone)
        await OrderStates.waiting_for_note.set()
        await message.answer(
            text="💬 <b>Buyurtma uchun qo'shimcha izohingiz bormi?</b>\n<i>(Masalan: Domofon kodi: 45, achchiq bo'lmasin)</i>",
            reply_markup=get_skip_or_cancel_reply_kb(lang),
            parse_mode="HTML"
        )
    else:
        # Raqam bo'lmasa, so'rash (Section 2.4)
        await OrderStates.waiting_for_phone.set()
        phone_prompt = (
            f"📞 <b>Telefon raqamingizni tasdiqlang:</b>\n\n"
            f"<i>Pastdagi tugma orqali telefon raqamingizni yuboring yoki quyidagi formatda yozing (+998901234567):</i>\n"
            f"📍 <b>Sizga eng yaqin filial:</b> {nearest_branch.get('name', 'Filial')} ({distance_km:.1f} km)"
        )
        await message.answer(
            text=phone_prompt,
            reply_markup=get_phone_reply_kb(lang),
            parse_mode="HTML"
        )


# ==========================================
# 4. TELEFON RAQAMINI QABUL QILISH
# ==========================================
async def process_phone(message: types.Message, state: FSMContext):
    """
    Telefon raqamini tekshirib qabul qiladi (Contact yoki Text).
    Bazada saqlaydi va keyingi bosqichga o'tadi.
    """
    data = await state.get_data()
    lang = data.get("lang", "uz")

    if message.text and any(k in message.text for k in ["Bekor", "Cancel", "Отмена"]):
        await cancel_order_handler(message, state)
        return

    raw_phone = None
    if message.contact:
        raw_phone = message.contact.phone_number
    elif message.text:
        raw_phone = message.text

    phone = clean_phone_number(raw_phone or "")
    if not phone:
        await message.answer(
            get_text("invalid_phone", lang),
            reply_markup=get_phone_reply_kb(lang)
        )
        return

    # Foydalanuvchi ma'lumotlar bazasiga telefonni yozib qo'yamiz (keyingi safar autofill bo'lishi uchun)
    await save_or_update_user(message.from_user.id, phone=phone)
    await state.update_data(phone=phone)

    # Izoh bosqichiga o'tish (Section 2.5)
    await OrderStates.waiting_for_note.set()
    await message.answer(
        text="💬 <b>Buyurtma uchun qo'shimcha izohingiz bormi?</b>\n<i>(Masalan: Domofon kodi: 45, achchiq bo'lmasin)</i>",
        reply_markup=get_skip_or_cancel_reply_kb(lang),
        parse_mode="HTML"
    )


# ==========================================
# 5. IZOH (NOTE) VA PROMOKOD BOSQICHI
# ==========================================
async def process_note_text(message: types.Message, state: FSMContext):
    """Izoh matn shaklida kiritilganda."""
    data = await state.get_data()
    lang = data.get("lang", "uz")
    note = (message.text or "").strip()

    if any(k in note for k in ["O'tkazib", "Otqazib", "Пропустить", "Skip"]):
        note = ""
    elif any(k in note for k in ["Bekor", "Cancel", "Отмена"]):
        await cancel_order_handler(message, state)
        return

    await state.update_data(note=note)
    await OrderStates.waiting_for_promo.set()
    await message.answer(
        text="🎟 <b>Chegirma uchun promokodingiz bormi?</b>\n<i>(Masalan: DARXAN10 yoki FASTFOOD)</i>",
        reply_markup=get_skip_or_cancel_reply_kb(lang),
        parse_mode="HTML"
    )


async def process_note_skip(call: types.CallbackQuery, state: FSMContext):
    """Izohni o'tkazib yuborish tugmasi bosilganda."""
    data = await state.get_data()
    lang = data.get("lang", "uz")

    await call.answer()
    await state.update_data(note="")
    await OrderStates.waiting_for_promo.set()
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.message.answer(
        text="🎟 <b>Chegirma uchun promokodingiz bormi?</b>\n<i>(Masalan: DARXAN10 yoki FASTFOOD)</i>",
        reply_markup=get_skip_or_cancel_reply_kb(lang),
        parse_mode="HTML"
    )


async def process_promo_text(message: types.Message, state: FSMContext):
    """
    Promokod kiritilganda uni tekshiradi:
    Mavjudligi, faolligi, limitlari va buyurtma summasi.
    """
    data = await state.get_data()
    lang = data.get("lang", "uz")
    text = (message.text or "").strip()

    if any(k in text for k in ["O'tkazib", "Otqazib", "Пропустить", "Skip"]):
        await state.update_data(promo_code=None, discount_amount=0)
        await ask_payment_method(message, state, is_callback=False)
        return
    elif any(k in text for k in ["Bekor", "Cancel", "Отмена"]):
        await cancel_order_handler(message, state)
        return

    items_total = data.get("items_total", 0)
    code = text.upper()
    is_valid, promo_data, reason = await check_promo_code(code, items_total)

    if not is_valid or not promo_data:
        await message.answer(
            "⚠️ Kiritilgan promokod yaroqsiz yoki muddati tugagan.\nQaytadan kiriting yoki o'tkazib yuboring:",
            reply_markup=get_skip_or_cancel_reply_kb(lang)
        )
        return

    discount_percent = promo_data.get("discount_percent", 0)
    discount_amount = int((items_total * discount_percent) / 100)
    promo_id = promo_data.get("id")

    await state.update_data(
        promo_code=code,
        promo_id=promo_id,
        discount_percent=discount_percent,
        discount_amount=discount_amount
    )

    await message.answer(
        f"✅ <b>Promokod qabul qilindi!</b>\nChegirma: <b>{discount_percent}% (-{discount_amount:,} so'm)</b> 🎉",
        parse_mode="HTML"
    )

    # To'lov turini tanlash bosqichiga yo'naltirish
    await ask_payment_method(message, state, is_callback=False)


async def process_promo_skip(call: types.CallbackQuery, state: FSMContext):
    """Promokodni o'tkazib yuborish."""
    await call.answer()
    await state.update_data(promo_code=None, discount_amount=0)
    await ask_payment_method(call, state, is_callback=True)


async def ask_payment_method(message_or_target, state: FSMContext, is_callback: bool = False):
    """To'lov usulini tanlashni so'raydi (Section 3.1)."""
    data = await state.get_data()
    lang = data.get("lang", "uz")

    await OrderStates.waiting_for_payment_method.set()

    text = "💳 <b>To'lov usulini tanlang:</b>"
    if is_callback and isinstance(message_or_target, types.CallbackQuery):
        try:
            await message_or_target.message.delete()
        except Exception:
            pass
        await message_or_target.message.answer(
            text=text,
            reply_markup=get_payment_method_reply_kb(lang),
            parse_mode="HTML"
        )
    elif isinstance(message_or_target, types.Message):
        await message_or_target.answer(
            text=text,
            reply_markup=get_payment_method_reply_kb(lang),
            parse_mode="HTML"
        )
    else:
        await message_or_target.answer(
            text=text,
            reply_markup=get_payment_method_reply_kb(lang),
            parse_mode="HTML"
        )


# ==========================================
# 6. TO'LOV VA BUYURTMANI YAKUNLASH (FINISH ORDER)
# ==========================================
async def process_payment_method(call: types.CallbackQuery, state: FSMContext):
    """To'lov turini callback orqali qabul qilish."""
    payment_method = call.data.split(":")[1]
    await call.answer()
    await finish_order_process(call, state, payment_method)


async def process_payment_method_message(message: types.Message, state: FSMContext):
    """To'lov turini Reply tugma orqali qabul qilish."""
    text = (message.text or "").strip()
    if any(k in text for k in ["Naqd", "Наличные", "Cash"]):
        await finish_order_process(message, state, "cash")
    elif any(k in text for k in ["Online", "Karta", "Payme", "Click", "Онлайн"]):
        await finish_order_process(message, state, "online")
    elif any(k in text for k in ["Bekor", "Cancel", "Отмена"]):
        await cancel_order_handler(message, state)
    else:
        data = await state.get_data()
        lang = data.get("lang", "uz")
        await message.answer(
            "Iltimos, to'lov turini tanlang:",
            reply_markup=get_payment_method_reply_kb(lang)
        )
    """To'lov turini Reply tugma orqali qabul qilish."""
    text = (message.text or "").strip()
    payment_method = "cash" if "Naqd" in text else "online"
    await finish_order_process(message, state, payment_method)


async def finish_order_process(event, state: FSMContext, payment_method: str):
    """Buyurtmani yakunlash va chek chiqarish (Section 3.2 va 3.3 dizayni)."""
    data = await state.get_data()
    lang = data.get("lang", "uz")
    user_id = event.from_user.id
    bot = event.bot

    items_total = data.get("items_total", 0)
    discount_amount = data.get("discount_amount", 0)
    delivery_fee = data.get("delivery_fee", 0)
    final_total = max(0, (items_total - discount_amount)) + delivery_fee

    await state.update_data(payment_method=payment_method, final_total=final_total)
    updated_data = await state.get_data()

    # 1. Bazaga yozish
    order_id = await create_order(
        user_id=user_id,
        total_amount=final_total,
        phone_number=updated_data.get("phone", ""),
        items=updated_data.get("cart_items", []),
        delivery_type=updated_data.get("delivery_type", "delivery"),
        delivery_address=updated_data.get("address", "Ko'rsatilmagan"),
        latitude=updated_data.get("lat"),
        longitude=updated_data.get("lon"),
        payment_method=payment_method,
        payment_status="cash" if payment_method == "cash" else "unpaid",
        branch_id=updated_data.get("branch_id"),
        promo_code=updated_data.get("promo_code"),
        discount_amount=discount_amount
    )

    promo_id = updated_data.get("promo_id")
    if promo_id:
        await mark_promo_used(promo_id)

    await clear_cart(user_id)

    # 2. Buyurtma tarkibi
    items_text = ""
    for itm in updated_data.get("cart_items", []):
        name = itm.get("name")
        qty = itm.get("quantity", 1)
        price = itm.get("price") or (itm.get("total_price", 0) // qty)
        items_text += f"    ▫️ {name} x {qty} = {price * qty:,} so'm\n"

    promo_code = updated_data.get("promo_code")
    discount_percent = updated_data.get("discount_percent", 10)
    promo_line = f"  🎟 <b>Promokod ({promo_code} - {discount_percent}%):</b> -{discount_amount:,} so'm\n" if discount_amount > 0 else ""
    note_line = f"  📝 <i>Izoh: {updated_data.get('note')}</i>\n" if updated_data.get("note") else ""
    address = updated_data.get("address", "-")

    chan_id, chan_msg_id = None, None

    if payment_method == "cash":
        # 3.2. Muvaffaqiyatli Chek kvitansiyasi (Naqd to'lov uchun)
        receipt = (
            f"🎉 <b>Buyurtmangiz qabul qilindi!</b>\n\n"
            f"Buyurtma raqami: <b>#{order_id}</b>\n"
            f"📍 <b>Manzil:</b> {address}\n\n"
            f"📋 <b>Buyurtma tarkibi:</b>\n"
            f"{items_text}\n"
            f"💵 <b>Mahsulotlar:</b> {items_total:,} so'm\n"
            f"{promo_line}"
            f"🛵 <b>Yetkazib berish:</b> {delivery_fee:,} so'm\n"
            f"💰 <b>Jami to'lov:</b> {final_total:,} so'm\n"
            f"💵 <b>To'lov turi:</b> Naqd pul (Yetkazib berilganda)\n"
            f"{note_line}\n"
            f"👨‍🍳 <i>Tez orada oshpazlarimiz taomingizni tayyorlashga kirishishadi!</i>"
        )
        receipt_kb = InlineKeyboardMarkup(row_width=1)
        receipt_kb.add(InlineKeyboardButton("❌ Buyurtmani bekor qilish (60s)", callback_data=f"user_cancel_order_{order_id}"))

        try:
            chan_id, chan_msg_id = await notify_admins_new_order(
                bot=bot,
                order_data=updated_data,
                items=updated_data.get("cart_items", []),
                order_id=order_id
            )
        except Exception as e:
            logger.error(f"Notify error: {e}")

    else:
        # 3.3. Muvaffaqiyatli Chek (Click va Payme online to'lov uchun)
        receipt = (
            f"🎉 <b>Buyurtmangiz qabul qilindi!</b>\n\n"
            f"Buyurtma raqami: <b>#{order_id}</b>\n"
            f"📍 <b>Manzil:</b> {address}\n\n"
            f"📋 <b>Buyurtma tarkibi:</b>\n"
            f"{items_text}\n"
            f"💵 <b>Mahsulotlar:</b> {items_total:,} so'm\n"
            f"{promo_line}"
            f"🛵 <b>Yetkazib berish:</b> {delivery_fee:,} so'm\n"
            f"💰 <b>Jami to'lov:</b> {final_total:,} so'm\n"
            f"💳 <b>To'lov turi:</b> Karta orqali to'lov (Click / Payme)\n"
            f"{note_line}\n"
            f"⏳ <b>DIQQAT:</b> Buyurtmangiz oshxonaga qabul qilinishi uchun to'lovni amalga oshiring.\n"
            f"👇 <i>To'lov amalga oshirilgach, buyurtma darhol oshxona kanaliga yuboriladi:</i>"
        )
        receipt_kb = get_online_payment_channels_kb(order_id, final_total)

    if isinstance(event, types.CallbackQuery):
        await event.message.delete()
        user_msg = await bot.send_message(
            chat_id=user_id,
            text=receipt,
            parse_mode="HTML",
            reply_markup=receipt_kb
        )
    else:
        user_msg = await event.answer(
            text=receipt,
            parse_mode="HTML",
            reply_markup=receipt_kb
        )

    # 60 soniyalik bekor qilish hisoblagichini boshlash
    await start_order_cancel_window(
        bot=bot,
        order_id=order_id,
        user_id=user_id,
        user_chat_id=user_msg.chat.id,
        user_msg_id=user_msg.message_id,
        channel_id=chan_id,
        channel_msg_id=chan_msg_id,
        duration=60
    )

    # Asosiy menyu klaviaturasini chiqarish
    await bot.send_message(
        chat_id=user_id,
        text="Yoqimli ishtaha tilaymiz! 😋",
        reply_markup=get_main_menu_keyboard(lang, user_id=user_id)
    )

    await state.finish()


# ==========================================
# 7. BEKOR QILISH (CANCELLATION)
# ==========================================
async def cancel_order_handler(event: types.CallbackQuery or types.Message, state: FSMContext):
    """
    Istalgan bosqichda buyurtmani bekor qilish.
    FSM xotirasi tozalanadi va foydalanuvchi asosiy menyuga qaytariladi.
    """
    current_state = await state.get_state()
    user_id = event.from_user.id
    lang = await get_user_lang(user_id)

    if current_state is not None:
        await state.finish()

    cancel_msg = (
        "❌ <b>Buyurtma bekor qilindi.</b>\n\n"
        "Asosiy menyuga qaytdingiz. Taom tanlash uchun «🍽 Menyu» tugmasini bosing:"
    )
    main_kb = get_main_menu_keyboard(lang, user_id=user_id)

    if isinstance(event, types.CallbackQuery):
        await event.answer()
        try:
            await event.message.delete()
        except Exception:
            pass
        await event.message.answer(cancel_msg, reply_markup=main_kb, parse_mode="HTML")
    else:
        await event.answer(cancel_msg, reply_markup=main_kb, parse_mode="HTML")


# ==========================================
# HANDLERLARNI RO'YXATGA OLISH (REGISTRATION)
# ==========================================
def register_order_handlers(dp: Dispatcher):
    """Barcha order handlerlarini Dispatcherga ro'yxatga oladi."""

    # Bekor qilish (Callback va Message)
    dp.register_callback_query_handler(
        cancel_order_handler,
        lambda c: c.data == "cancel_order",
        state="*"
    )
    dp.register_message_handler(
        cancel_order_handler,
        lambda m: m.text in [
            get_text("btn_cancel", "uz"),
            get_text("btn_cancel", "ru"),
            get_text("btn_cancel", "en"),
            "❌ Bekor qilish",
            "❌ Отмена",
            "❌ Cancel",
            "/cancel"
        ],
        state="*"
    )

    # 1. Web App Checkout boshlanishi
    dp.register_message_handler(
        process_web_app_checkout,
        content_types=types.ContentType.WEB_APP_DATA,
        state="*"
    )

    # 1.1. Callback orqali Checkout boshlanishi
    dp.register_callback_query_handler(
        start_checkout,
        lambda c: c.data == "checkout",
        state="*"
    )

    # 2. Yetkazib berish turi (Callback & Reply)
    dp.register_callback_query_handler(
        process_delivery_type,
        lambda c: c.data.startswith("delivery_type:"),
        state=OrderStates.waiting_for_delivery_type
    )
    dp.register_message_handler(
        process_delivery_type_message,
        content_types=types.ContentTypes.TEXT,
        state=OrderStates.waiting_for_delivery_type
    )

    # 2.1. Stol raqami (Eat In)
    dp.register_message_handler(
        process_table_number,
        content_types=types.ContentTypes.TEXT,
        state=OrderStates.waiting_for_table_number
    )

    # 3. Joylashuv (Delivery)
    dp.register_message_handler(
        process_location,
        content_types=[
            types.ContentType.LOCATION,
            types.ContentType.VENUE,
            types.ContentType.WEB_APP_DATA,
            types.ContentType.TEXT
        ],
        state=OrderStates.waiting_for_location
    )

    # 4. Telefon raqami
    dp.register_message_handler(
        process_phone,
        content_types=[types.ContentType.CONTACT, types.ContentType.TEXT],
        state=OrderStates.waiting_for_phone
    )

    # 5. Izoh
    dp.register_callback_query_handler(
        process_note_skip,
        lambda c: c.data == "skip_note",
        state=OrderStates.waiting_for_note
    )
    dp.register_message_handler(
        process_note_text,
        content_types=types.ContentTypes.TEXT,
        state=OrderStates.waiting_for_note
    )

    # 5.1. Promokod
    dp.register_callback_query_handler(
        process_promo_skip,
        lambda c: c.data == "skip_promo",
        state=OrderStates.waiting_for_promo
    )
    dp.register_message_handler(
        process_promo_text,
        content_types=types.ContentTypes.TEXT,
        state=OrderStates.waiting_for_promo
    )

    # 6. To'lov turi (Callback & Reply)
    dp.register_callback_query_handler(
        process_payment_method,
        lambda c: c.data.startswith("pay_method:"),
        state=OrderStates.waiting_for_payment_method
    )
    dp.register_message_handler(
        process_payment_method_message,
        content_types=types.ContentTypes.TEXT,
        state=OrderStates.waiting_for_payment_method
    )

    # 7. 60 soniyalik bekor qilish tugmasi
    dp.register_callback_query_handler(
        callback_user_cancel_order,
        lambda c: c.data.startswith("user_cancel_order_"),
        state="*"
    )

    # 7.1. To'lovni tekshirish
    dp.register_callback_query_handler(
        callback_check_payment,
        lambda c: c.data.startswith("chk_pay_"),
        state="*"
    )

    # 8. Mijoz baholashi (1-5 yulduz)
    dp.register_callback_query_handler(
        callback_rate_order,
        lambda c: c.data.startswith("rate_"),
        state="*"
    )


async def callback_check_payment(call: types.CallbackQuery):
    """Mijoz tomonidan to'lov amalga oshirilganligini tekshirish."""
    try:
        order_id = int(call.data.split("_")[-1])
    except Exception:
        await call.answer("Xatolik yuz berdi.", show_alert=True)
        return

    from database import get_order_by_id
    order = await get_order_by_id(order_id)
    if not order:
        await call.answer("Buyurtma topilmadi.", show_alert=True)
        return

    if order.get("payment_status") == "paid":
        await call.answer("✅ To'lovingiz tasdiqlandi! Buyurtma oshxonaga yuborildi.", show_alert=True)
        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    else:
        await call.answer(
            "⏳ To'lov hali qabul qilinmadi yoki tasdiqlanmadi.\nIltimos, to'lovni Click yoki Payme orqali yakunlang.",
            show_alert=True
        )


async def callback_user_cancel_order(call: types.CallbackQuery):
    """Mijoz tomonidan 60 soniya ichida buyurtmani bekor qilish."""
    try:
        order_id = int(call.data.split("_")[-1])
    except Exception:
        await call.answer("Xatolik yuz berdi.", show_alert=True)
        return

    success, msg = await handle_user_cancel_order(call.bot, order_id, call.from_user.id)
    await call.answer(msg, show_alert=True)
    if success:
        try:
            await call.message.edit_text(
                call.message.text + "\n\n❌ <b>BUYURTMA BEKOR QILINDI</b>",
                parse_mode="HTML",
                reply_markup=None
            )
        except Exception:
            pass


async def callback_rate_order(call: types.CallbackQuery):
    """Mijozning 1-5 yulduzli bahosini qabul qilish."""
    try:
        parts = call.data.split("_")
        order_id = int(parts[1])
        rating = int(parts[2])
    except Exception:
        await call.answer("Xatolik!", show_alert=True)
        return

    await add_feedback(call.from_user.id, order_id, rating, comment="")
    await call.answer(f"⭐ {rating} yulduzli bahoyingiz uchun katta rahmat!", show_alert=True)
    try:
        await call.message.edit_text(
            call.message.text + f"\n\n⭐ <b>Bahoyingiz:</b> {rating} yulduz qabul qilindi. Rahmat!",
            parse_mode="HTML",
            reply_markup=None
        )
    except Exception:
        pass

