"""
Fast-food va restoran Telegram boti uchun to'liq funksional,
xavfsiz va qulay Admin Panel moduli.
"""

import io
import csv
import string
import random
import logging
import asyncio
from datetime import datetime
from typing import Optional

from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.exceptions import BotBlocked, ChatNotFound, UserDeactivated, RetryAfter

from config import is_admin, ADMIN_IDS
from database import (
    get_dashboard_stats,
    get_analytics_stats,
    get_top_products,
    get_average_rating_and_count,
    get_feedbacks,
    add_feedback,
    get_orders_by_status,
    get_order_by_id,
    update_order_status,
    get_orders_for_export,
    get_all_products,
    get_product_by_id,
    add_product,
    toggle_product_status,
    update_product_discount,
    update_product_image,
    delete_product,
    get_all_promos,
    add_promo,
    delete_promo,
    toggle_promo_status,
    get_all_user_ids,
    get_all_users_count
)
from keyboards.admin_keyboard import (
    get_admin_reply_kb,
    get_admin_dashboard_kb,
    get_orders_filter_kb,
    get_order_detail_kb,
    get_order_status_change_kb,
    get_analytics_kb,
    get_feedbacks_page_kb,
    get_menu_categories_kb,
    get_products_admin_kb,
    get_product_card_admin_kb,
    get_promos_admin_kb,
    get_promo_card_admin_kb,
    get_broadcast_confirm_kb,
    get_export_kb,
    get_courier_complete_kb,
    get_feedback_rating_kb
)

logger = logging.getLogger(__name__)


# ==========================================
# FSM HOLATLARI (ADMIN STATES)
# ==========================================

class AdminAddProduct(StatesGroup):
    waiting_for_category = State()
    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_description = State()
    waiting_for_image = State()


class AdminEditProduct(StatesGroup):
    waiting_for_discount = State()
    waiting_for_new_image = State()


class AdminAddPromo(StatesGroup):
    waiting_for_code = State()
    waiting_for_percent = State()
    waiting_for_limit = State()


class AdminBroadcast(StatesGroup):
    waiting_for_content = State()
    waiting_for_confirm = State()


class CustomerFeedback(StatesGroup):
    waiting_for_comment = State()


# ==========================================
# YORDAMCHI FUNKSIYALAR
# ==========================================

async def generate_dashboard_text() -> str:
    """Jonli dashboard matnini generatsiya qiladi."""
    stats = await get_dashboard_stats()

    text = (
        f"🛠 <b>DARXAN BURGER — BOSHQARUV PANELI</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 <b>Bugungi tushum:</b> {stats['today_revenue']:,} so'm ({stats['today_orders']} ta zakaz)\n"
        f"👥 <b>Jami mijozlar:</b> {stats.get('total_users', stats.get('users_count', 0))} ta\n\n"
        f"📊 <b>Faol buyurtmalar:</b>\n"
        f"  ▫️ ⏳ Kutilmoqda: {stats['pending_count']} ta\n"
        f"  ▫️ 👨‍🍳 Oshxonada: {stats['preparing_count']} ta\n"
        f"  ▫️ 🛵 Yo'lda: {stats['delivering_count']} ta\n"
        f"━━━━━━━━━━━━━━━━━━━━━"
    )
    return text


async def send_customer_status_notification(bot, user_id: int, order_id: int, new_status: str):
    """Mijozga buyurtma holati o'zgargani haqida push-notification jo'natadi."""
    status_messages = {
        "preparing": (
            f"👨‍🍳 <b>Buyurtmangiz #{order_id} qabul qilindi!</b>\n"
            f"Oshpazlarimiz sizning mazali taomlaringizni mehr bilan tayyorlashga kirishishdi. 🍔✨"
        ),
        "delivering": (
            f"🛵 <b>Buyurtmangiz #{order_id} yo'lga chiqdi!</b>\n"
            f"Kuryerimiz issiqqina taomlaringiz bilan manzilingiz sari shoshilmoqda. Iltimos, telefoningizni yoningizda tuting! 🚀"
        ),
        "completed": (
            f"🎉 <b>Buyurtmangiz #{order_id} yetkazildi!</b>\n"
            f"Darxan Burger'ni tanlaganingiz uchun rahmat! Yoqimli ishtaha! 😋❤️"
        ),
        "cancelled": (
            f"😔 <b>Buyurtmangiz #{order_id} bekor qilindi.</b>\n"
            f"Keltirilgan noqulayliklar uchun uzr so'raymiz. Savollaringiz bo'lsa, operatorimiz bilan bog'laning."
        )
    }

    msg = status_messages.get(new_status)
    if not msg:
        return

    try:
        if new_status == "completed":
            await bot.send_message(
                chat_id=user_id,
                text=msg,
                parse_mode="HTML",
                reply_markup=get_feedback_rating_kb(order_id)
            )
        else:
            await bot.send_message(chat_id=user_id, text=msg, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Could not send push notification to user {user_id}: {e}")


# ==========================================
# 1. ADMIN PANELGA KIRISH VA DASHBOARD
# ==========================================

async def cmd_admin(message: types.Message):
    """Admin panelga /admin yoki tugma orqali kirish (2-rasmdagi inline dashboard chiqadi)."""
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Kechirasiz, sizda admin huquqlari mavjud emas!")
        return

    dashboard_text = await generate_dashboard_text()
    await message.answer(
        dashboard_text,
        reply_markup=get_admin_dashboard_kb(),
        parse_mode="HTML"
    )


async def admin_reply_refresh(message: types.Message):
    """'🔄 Yangilash' tugmasi bosilganda."""
    if not is_admin(message.from_user.id):
        return
    dashboard_text = await generate_dashboard_text()
    await message.answer(
        dashboard_text,
        reply_markup=get_admin_dashboard_kb(),
        parse_mode="HTML"
    )


async def admin_reply_orders(message: types.Message):
    """Pastki '📦 Buyurtmalar' tugmasi bosilganda."""
    if not is_admin(message.from_user.id):
        return
    orders, total_count = await get_orders_by_status(status="all", page=1, limit=6)
    total_pages = (total_count + 6 - 1) // 6
    text = (
        f"📦 <b>BUYURTMALAR BOSHQARUVI</b>\n"
        f"Filtr: <b>Barcha buyurtmalar</b> (Jami: {total_count} ta)\n"
        f"<i>Batafsil ko'rish uchun buyurtma tugmasini bosing:</i>"
    )
    await message.answer(text, reply_markup=get_orders_filter_kb("all", orders, 1, total_pages), parse_mode="HTML")


async def admin_reply_analytics(message: types.Message):
    """Pastki '📊 Statistika' tugmasi bosilganda."""
    if not is_admin(message.from_user.id):
        return
    stats = await get_analytics_stats(days=7)
    top_products = await get_top_products(limit=5)
    avg_rating, rating_count = await get_average_rating_and_count()

    top_text = ""
    for idx, p in enumerate(top_products, 1):
        top_text += f"{idx}. <b>{p['product_name']}</b>: {p['total_qty']} dona (<i>{p['total_sum']:,} so'm</i>)\n"
    if not top_text:
        top_text = "<i>Hozircha sotuvlar mavjud emas</i>\n"

    text = (
        f"📊 <b>CHUQURLASHTIRILGAN ANALITIKA VA STATISTIKA</b>\n"
        f"Davr: <b>Oxirgi 7 kunlik</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Jami tushum:</b> <b>{stats['revenue']:,} so'm</b>\n"
        f"📦 <b>Jami buyurtmalar soni:</b> <b>{stats['orders_count']} ta</b>\n"
        f"⭐ <b>Mijozlar o'rtacha bahosi:</b> <b>{avg_rating} / 5.0</b> ({rating_count} ta fikr)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🍔 <b>ENG KO'P SOTILGAN TOP-5 MAHSULOT:</b>\n"
        f"{top_text}"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await message.answer(text, reply_markup=get_analytics_kb(), parse_mode="HTML")


async def admin_reply_products(message: types.Message):
    """Pastki '🍔 Mahsulotlar' tugmasi bosilganda."""
    if not is_admin(message.from_user.id):
        return
    products = await get_all_products()
    await message.answer(
        "🍔 <b>MAHSULOTLAR VA MENYU BOSHQARUVI</b>\n\n"
        "Mahsulotni tahrirlash, stop-listga qo'shish yoki narxini o'zgartirish uchun ustiga bosing:",
        reply_markup=get_products_admin_kb(products),
        parse_mode="HTML"
    )


async def admin_reply_promos(message: types.Message):
    """Pastki '🎟 Promokodlar' tugmasi bosilganda."""
    if not is_admin(message.from_user.id):
        return
    promos = await get_all_promos()
    await message.answer(
        "🎟 <b>PROMOKODLAR TIZIMI</b>\n\n"
        "Mavjud promokodlar ro'yxati va boshqaruvi:",
        reply_markup=get_promos_admin_kb(promos),
        parse_mode="HTML"
    )


async def admin_reply_broadcast(message: types.Message, state: FSMContext):
    """Pastki '📢 Xabar tarqatish' tugmasi bosilganda."""
    if not is_admin(message.from_user.id):
        return
    total_users = await get_all_users_count()
    await AdminBroadcast.waiting_for_content.set()
    await message.answer(
        f"📢 <b>OMMAVIY XABAR TARQATISH</b>\n\n"
        f"Hozirda botda jami <b>{total_users} nafar</b> foydalanuvchi mavjud.\n\n"
        f"Tarqatmoqchi bo'lgan xabaringizni yuboring (Matn, rasm, video yoki havola):",
        parse_mode="HTML"
    )


async def admin_reply_export(message: types.Message):
    """Pastki '📥 CSV Eksport' tugmasi bosilganda."""
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "📥 <b>BUXGALTERIYA VA HISOBOTLAR EKSPORTI</b>\n\n"
        "Buyurtmalar tarixini Excel/CSV formatida yuklab olish uchun davrni tanlang:",
        reply_markup=get_export_kb(),
        parse_mode="HTML"
    )


async def admin_reply_feedbacks(message: types.Message):
    """Pastki '⭐ Oxirgi fikrlar' tugmasi bosilganda."""
    if not is_admin(message.from_user.id):
        return
    feedbacks, total_count = await get_feedbacks(page=1, limit=5)
    total_pages = (total_count + 5 - 1) // 5
    if not feedbacks:
        await message.answer("⭐ Hozircha fikrlar mavjud emas.", reply_markup=get_analytics_kb())
        return

    text = f"⭐ <b>MIJOZLAR FIKRLARI ({total_count} ta):</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for f in feedbacks:
        stars = "⭐" * int(f.get("rating", 5))
        name = f.get("full_name") or "Mijoz"
        phone = f.get("phone") or "-"
        comment = f.get("comment") or "<i>Izoh qoldirilmagan</i>"
        time_str = f.get("created_at", "")[:16]
        text += (
            f"👤 <b>{name}</b> ({phone})\n"
            f"Baho: {stars} ({f.get('rating')}/5)\n"
            f"💬 Izoh: {comment}\n"
            f"🕒 {time_str}\n"
            f"────────────────────\n"
        )
    await message.answer(text, reply_markup=get_feedbacks_page_kb(1, total_pages), parse_mode="HTML")


async def admin_reply_back_main(message: types.Message):
    """Pastki '🔙 Asosiy menyuga qaytish' tugmasi bosilganda oddiy mijoz menyusiga qaytaradi."""
    from config import WEB_APP_URL
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

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
    kb.add(KeyboardButton(text="🛠 Admin Panel"))

    await message.answer(
        "Asosiy menyuga qaytdingiz. Taomlarni tanlash uchun Web App ni ochishingiz mumkin:",
        reply_markup=kb
    )


async def callback_refresh_dashboard(call: types.CallbackQuery):
    """Dashboardni real vaqtda yangilash."""
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ Ruxsat etilmagan!", show_alert=True)
        return

    dashboard_text = await generate_dashboard_text()
    try:
        await call.message.edit_text(dashboard_text, reply_markup=get_admin_dashboard_kb(), parse_mode="HTML")
        await call.answer("🔄 Dashboard yangilandi!")
    except Exception:
        await call.answer("Raqamlar allaqachon eng so'nggi holatda.")


# ==========================================
# 2. CHUQURLASHTIRILGAN ANALITIKA VA STATISTIKA
# ==========================================

async def callback_analytics_view(call: types.CallbackQuery):
    """Statistika bo'limi."""
    if not is_admin(call.from_user.id):
        return

    parts = call.data.split(":")
    days = int(parts[2]) if len(parts) > 2 else 7

    stats = await get_analytics_stats(days=days)
    top_products = await get_top_products(limit=5)
    avg_rating, rating_count = await get_average_rating_and_count()

    top_text = ""
    for idx, p in enumerate(top_products, 1):
        top_text += f"{idx}. <b>{p['product_name']}</b>: {p['total_qty']} dona (<i>{p['total_sum']:,} so'm</i>)\n"

    if not top_text:
        top_text = "<i>Hozircha sotuvlar mavjud emas</i>\n"

    period_title = {1: "Bugungi", 7: "Oxirgi 7 kunlik", 30: "Oxirgi 30 kunlik"}.get(days, f"{days} kunlik")

    text = (
        f"📊 <b>CHUQURLASHTIRILGAN ANALITIKA VA STATISTIKA</b>\n"
        f"Davr: <b>{period_title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Jami tushum:</b> <b>{stats['revenue']:,} so'm</b>\n"
        f"📦 <b>Jami buyurtmalar soni:</b> <b>{stats['orders_count']} ta</b>\n"
        f"⭐ <b>Mijozlar o'rtacha bahosi:</b> <b>{avg_rating} / 5.0</b> ({rating_count} ta fikr)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🍔 <b>ENG KO'P SOTILGAN TOP-5 MAHSULOT:</b>\n"
        f"{top_text}"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    await call.message.edit_text(text, reply_markup=get_analytics_kb(), parse_mode="HTML")
    await call.answer()


async def callback_feedbacks_view(call: types.CallbackQuery):
    """Mijozlar fikr-mulohazalarini ko'rish."""
    if not is_admin(call.from_user.id):
        return

    parts = call.data.split(":")
    page = int(parts[2]) if len(parts) > 2 else 1
    limit = 5

    feedbacks, total_count = await get_feedbacks(page=page, limit=limit)
    total_pages = (total_count + limit - 1) // limit

    if not feedbacks:
        await call.message.edit_text(
            "⭐ <b>Mijozlar fikrlari:</b>\n\nHozircha fikrlar mavjud emas.",
            reply_markup=get_analytics_kb(),
            parse_mode="HTML"
        )
        await call.answer()
        return

    text = f"⭐ <b>MIJOZLAR FIKRLARI ({total_count} ta):</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for f in feedbacks:
        stars = "⭐" * int(f.get("rating", 5))
        name = f.get("full_name") or "Mijoz"
        phone = f.get("phone") or "-"
        comment = f.get("comment") or "<i>Izoh qoldirilmagan</i>"
        time_str = f.get("created_at", "")[:16]
        text += (
            f"👤 <b>{name}</b> ({phone})\n"
            f"Baho: {stars} ({f.get('rating')}/5)\n"
            f"💬 Izoh: {comment}\n"
            f"🕒 {time_str}\n"
            f"────────────────────\n"
        )

    await call.message.edit_text(text, reply_markup=get_feedbacks_page_kb(page, total_pages), parse_mode="HTML")
    await call.answer()


# ==========================================
# 3. BUYURTMALAR BOSHQARUVI (STATUS CONTROL)
# ==========================================

async def callback_orders_list(call: types.CallbackQuery):
    """Buyurtmalar ro'yxatini filtrlash va sahifalash."""
    if not is_admin(call.from_user.id):
        return

    parts = call.data.split(":")
    status = parts[2] if len(parts) > 2 else "all"
    page = int(parts[3]) if len(parts) > 3 else 1
    limit = 6

    orders, total_count = await get_orders_by_status(status=status, page=page, limit=limit)
    total_pages = (total_count + limit - 1) // limit

    status_name = {
        "all": "Barcha buyurtmalar",
        "pending": "⏳ Kutilayotgan",
        "preparing": "👨‍🍳 Oshxonadagi",
        "delivering": "🛵 Kuryerdagi",
        "completed": "✅ Yetkazilgan",
        "cancelled": "❌ Bekor qilingan"
    }.get(status, status)

    text = (
        f"📦 <b>BUYURTMALAR BOSHQARUVI</b>\n"
        f"Filtr: <b>{status_name}</b> (Jami: {total_count} ta)\n"
        f"<i>Batafsil ko'rish uchun buyurtma tugmasini bosing:</i>"
    )

    await call.message.edit_text(
        text,
        reply_markup=get_orders_filter_kb(status, orders, page, total_pages),
        parse_mode="HTML"
    )
    await call.answer()


async def callback_order_view(call: types.CallbackQuery):
    """Alohida buyurtmaning to'liq kartasini ochadi."""
    if not is_admin(call.from_user.id):
        return

    order_id = int(call.data.split(":")[2])
    order = await get_order_by_id(order_id)
    if not order:
        await call.answer("⚠️ Buyurtma topilmadi!", show_alert=True)
        return

    is_delivery = (order.get("delivery_type") == "delivery")
    status_str = {
        "new": "⏳ Yangi (Kutilmoqda)",
        "pending": "⏳ Kutilmoqda",
        "preparing": "👨‍🍳 Oshxonada (Tayyorlanmoqda)",
        "delivering": "🛵 Kuryer yo'lida",
        "completed": "✅ Yetkazildi (Yakunlangan)",
        "cancelled": "❌ Bekor qilingan"
    }.get(order.get("status"), order.get("status"))

    items_text = ""
    for idx, it in enumerate(order.get("items", []), 1):
        items_text += f"{idx}. <b>{it['product_name']}</b> x {it['quantity']} = {it['total_price']:,} so'm\n"

    type_info = (
        f"🛵 Yetkazib berish\n📍 Manzil: {order.get('address')}\n🏢 Filial: {order.get('branch_name')} ({order.get('distance_km', 0):.1f} km)"
        if is_delivery
        else f"🍽 Shu yerda (Restoranda)\nStol: #{order.get('table_number', '-')}"
    )

    card_text = (
        f"📋 <b>BUYURTMA KARTASI #{order['id']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>Holat:</b> <b>{status_str}</b>\n"
        f"🕒 <b>Vaqt:</b> {order.get('created_at', '')[:16]}\n"
        f"👤 <b>Mijoz ID:</b> <code>{order['user_id']}</code>\n"
        f"📞 <b>Telefon:</b> <a href=\"tel:{order.get('phone')}\">{order.get('phone')}</a>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 <b>Xizmat turi:</b>\n{type_info}\n"
    )
    if order.get("note"):
        card_text += f"📝 <b>Izoh:</b> {order.get('note')}\n"

    card_text += (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 <b>Tarkib:</b>\n{items_text}"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Mahsulotlar: {order.get('items_total', 0):,} so'm\n"
    )
    if order.get("discount_amount", 0) > 0:
        card_text += f"🏷 Chegirma ({order.get('promo_code')}): -{order.get('discount_amount', 0):,} so'm\n"
    if is_delivery:
        card_text += f"🛵 Yetkazish haqi: {order.get('delivery_fee', 0):,} so'm\n"

    card_text += (
        f"💰 <b>JAMI TO'LOV:</b> <b>{order.get('final_total', 0):,} so'm</b>\n"
        f"💳 <b>To'lov turi:</b> {order.get('payment_method', 'cash').upper()}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    await call.message.edit_text(
        card_text,
        reply_markup=get_order_detail_kb(order['id'], order.get("status"), order.get("lat"), order.get("lon")),
        parse_mode="HTML"
    )
    await call.answer()


async def callback_order_location(call: types.CallbackQuery):
    """Mijoz lokatsiyasini adminga xarita qilib yuboradi."""
    if not is_admin(call.from_user.id):
        return

    order_id = int(call.data.split(":")[2])
    order = await get_order_by_id(order_id)
    if order and order.get("lat") and order.get("lon"):
        await call.message.answer_location(latitude=order["lat"], longitude=order["lon"])
        await call.answer("📍 Lokatsiya yuborildi.")
    else:
        await call.answer("Lokatsiya mavjud emas.", show_alert=True)


async def callback_order_change_status_menu(call: types.CallbackQuery):
    """Holatni o'zgartirish menyusi."""
    if not is_admin(call.from_user.id):
        return

    order_id = int(call.data.split(":")[2])
    await call.message.edit_text(
        f"🔄 <b>Buyurtma #{order_id} uchun yangi holatni tanlang:</b>",
        reply_markup=get_order_status_change_kb(order_id),
        parse_mode="HTML"
    )
    await call.answer()


async def callback_set_order_status(call: types.CallbackQuery):
    """Buyurtma holatini yangilash va mijozga bildirishnoma yuborish."""
    if not is_admin(call.from_user.id):
        return

    _, _, order_id_str, new_status = call.data.split(":")
    order_id = int(order_id_str)

    order = await get_order_by_id(order_id)
    if not order:
        await call.answer("Buyurtma topilmadi!", show_alert=True)
        return

    await update_order_status(order_id, new_status)
    await call.answer(f"✅ Holat {new_status} ga o'zgartirildi!")

    # Mijozga push notification jo'natish
    await send_customer_status_notification(call.bot, order["user_id"], order_id, new_status)

    # Qayta buyurtma kartasini ko'rsatish
    await callback_order_view(call)


# ==========================================
# 4. MAHSULOTLAR CRUD BOSHQARUVI
# ==========================================

async def callback_products_list(call: types.CallbackQuery):
    """Barcha mahsulotlar ro'yxatini ko'rsatish."""
    if not is_admin(call.from_user.id):
        return

    products = await get_all_products()
    await call.message.edit_text(
        "🍔 <b>MAHSULOTLAR VA MENYU BOSHQARUVI</b>\n\n"
        "Mahsulotni tahrirlash, stop-listga qo'shish yoki narxini o'zgartirish uchun ustiga bosing:",
        reply_markup=get_products_admin_kb(products),
        parse_mode="HTML"
    )
    await call.answer()


async def callback_product_view(call: types.CallbackQuery):
    """Alohida mahsulot kartasi."""
    if not is_admin(call.from_user.id):
        return

    product_id = int(call.data.split(":")[2])
    prod = await get_product_by_id(product_id)
    if not prod:
        await call.answer("Mahsulot topilmadi!", show_alert=True)
        return

    status_str = "🟢 Faol (Menyuda ko'rinadi)" if prod.get("is_available") == 1 else "🔴 Stop-listda (Yashirilgan)"
    text = (
        f"🍔 <b>{prod['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Narxi:</b> {prod['price']:,} so'm\n"
        f"📌 <b>Kategoriya:</b> {prod.get('category', '').upper()}\n"
        f"🏷 <b>Badge:</b> {prod.get('badge') or 'Yo''q'}\n"
        f"⚡️ <b>Holat:</b> {status_str}\n"
        f"📝 <b>Tavsif:</b> {prod.get('description', '')}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    await call.message.edit_text(text, reply_markup=get_product_card_admin_kb(product_id, prod.get("is_available", 1)), parse_mode="HTML")
    await call.answer()


async def callback_product_toggle(call: types.CallbackQuery):
    """Stop-listga kiritish yoki chiqarish."""
    if not is_admin(call.from_user.id):
        return

    product_id = int(call.data.split(":")[2])
    new_st = await toggle_product_status(product_id)
    msg = "🔴 Mahsulot Stop-listga kiritildi (Yashirildi)." if new_st == 0 else "🟢 Mahsulot qayta faollashtirildi!"
    await call.answer(msg, show_alert=True)
    await callback_product_view(call)


async def callback_product_delete(call: types.CallbackQuery):
    """Mahsulotni o'chirish."""
    if not is_admin(call.from_user.id):
        return

    product_id = int(call.data.split(":")[2])
    await delete_product(product_id)
    await call.answer("🗑 Mahsulot muvaffaqiyatli o'chirildi!", show_alert=True)
    await callback_products_list(call)


# --- Yangi mahsulot qo'shish FSM ---
async def start_add_product(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return

    await AdminAddProduct.waiting_for_category.set()
    await call.message.edit_text(
        "➕ <b>YANGI MAHSULOT QO'SHISH</b>\n\n1-bosqich: Mahsulot kategoriyasini tanlang:",
        reply_markup=get_menu_categories_kb(),
        parse_mode="HTML"
    )
    await call.answer()


async def process_add_prod_category(call: types.CallbackQuery, state: FSMContext):
    cat = call.data.split(":")[2]
    await state.update_data(category=cat)
    await AdminAddProduct.waiting_for_name.set()
    await call.message.edit_text("2-bosqich: Mahsulot nomini kiriting (masalan: <i>Double Beef Burger</i>):", parse_mode="HTML")
    await call.answer()


async def process_add_prod_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(name=name)
    await AdminAddProduct.waiting_for_price.set()
    await message.answer("3-bosqich: Mahsulot narxini so'mda kiriting (faqat raqam, masalan: <code>45000</code>):")


async def process_add_prod_price(message: types.Message, state: FSMContext):
    text = message.text.strip().replace(" ", "")
    if not text.isdigit() or int(text) <= 0:
        await message.answer("⚠️ Iltimos, faqat musbat raqam kiriting (masalan: 45000):")
        return

    await state.update_data(price=int(text))
    await AdminAddProduct.waiting_for_description.set()
    await message.answer("4-bosqich: Mahsulot tarkibi va tavsifini yozing:")


async def process_add_prod_desc(message: types.Message, state: FSMContext):
    desc = message.text.strip()
    await state.update_data(description=desc)
    await AdminAddProduct.waiting_for_image.set()
    await message.answer("5-bosqich: Mahsulot rasmini yuboring (yoki rasm URL havolasini yozing):")


async def process_add_prod_image(message: types.Message, state: FSMContext):
    image_url = ""
    if message.photo:
        image_url = message.photo[-1].file_id
    elif message.text and message.text.startswith("http"):
        image_url = message.text.strip()
    else:
        # Default rasm
        image_url = "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=600"

    data = await state.get_data()
    prod_id = await add_product(
        category=data["category"],
        name=data["name"],
        price=data["price"],
        description=data["description"],
        image=image_url,
        badge="Yangi"
    )

    await state.finish()
    await message.answer(
        f"✅ <b>Yangi mahsulot muvaffaqiyatli qo'shildi!</b>\n\n"
        f"Nomi: <b>{data['name']}</b>\n"
        f"Narxi: <b>{data['price']:,} so'm</b>",
        reply_markup=get_admin_dashboard_kb(),
        parse_mode="HTML"
    )


# --- Chegirma va aksiya belgilash ---
async def start_product_discount(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return

    product_id = int(call.data.split(":")[2])
    await state.update_data(edit_product_id=product_id)
    await AdminEditProduct.waiting_for_discount.set()
    await call.message.answer("🏷 Yangi chegirmali narxni kiriting (Chegirmani olib tashlash uchun 0 yozing):")
    await call.answer()


async def process_product_discount(message: types.Message, state: FSMContext):
    text = message.text.strip().replace(" ", "")
    if not text.isdigit():
        await message.answer("Iltimos, faqat raqam kiriting:")
        return

    data = await state.get_data()
    pid = data["edit_product_id"]
    new_price = int(text)

    await update_product_discount(pid, new_price)
    await state.finish()
    await message.answer("✅ Mahsulot narxi va chegirmasi muvaffaqiyatli yangilandi!", reply_markup=get_admin_dashboard_kb())


# ==========================================
# 5. PROMOKODLAR TIZIMI (PROMO CODE ENGINE)
# ==========================================

async def callback_promos_list(call: types.CallbackQuery):
    """Barcha promokodlarni ko'rsatish."""
    if not is_admin(call.from_user.id):
        return

    promos = await get_all_promos()
    await call.message.edit_text(
        "🎟 <b>PROMOKODLAR TIZIMI</b>\n\n"
        "Mavjud promokodlar ro'yxati va boshqaruvi:",
        reply_markup=get_promos_admin_kb(promos),
        parse_mode="HTML"
    )
    await call.answer()


async def callback_promo_view(call: types.CallbackQuery):
    """Alohida promokod kartasi."""
    if not is_admin(call.from_user.id):
        return

    promo_id = int(call.data.split(":")[2])
    promos = await get_all_promos()
    target = next((p for p in promos if p["id"] == promo_id), None)
    if not target:
        await call.answer("Promokod topilmadi!", show_alert=True)
        return

    status_str = "🟢 Faol" if target["is_active"] == 1 else "🔴 To'xtatilgan"
    text = (
        f"🎟 <b>PROMOKOD: <code>{target['code']}</code></b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷 <b>Chegirma foizi:</b> {target['discount_percent']}%\n"
        f"🔢 <b>Ishlatilganligi:</b> {target['used_count']} / {target['usage_limit']} marta\n"
        f"💰 <b>Minimal summa:</b> {target.get('min_order_amount', 0):,} so'm\n"
        f"⚡️ <b>Holat:</b> {status_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await call.message.edit_text(
        text,
        reply_markup=get_promo_card_admin_kb(promo_id, target["is_active"], target["code"]),
        parse_mode="HTML"
    )
    await call.answer()


async def callback_promo_toggle(call: types.CallbackQuery):
    """Promokodni to'xtatish yoki yoqish."""
    if not is_admin(call.from_user.id):
        return

    promo_id = int(call.data.split(":")[2])
    st = await toggle_promo_status(promo_id)
    msg = "🔴 Promokod to'xtatildi." if st == 0 else "🟢 Promokod faollashtirildi!"
    await call.answer(msg, show_alert=True)
    await callback_promo_view(call)


async def callback_promo_delete(call: types.CallbackQuery):
    """Promokodni o'chirish."""
    if not is_admin(call.from_user.id):
        return

    promo_id = int(call.data.split(":")[2])
    await delete_promo(promo_id)
    await call.answer("🗑 Promokod o'chirildi!", show_alert=True)
    await callback_promos_list(call)


async def callback_promo_random(call: types.CallbackQuery):
    """Tasodifiy 8 xonali promokod yaratish."""
    if not is_admin(call.from_user.id):
        return

    chars = string.ascii_uppercase + string.digits
    code = "FAST" + "".join(random.choices(chars, k=4))
    await add_promo(code=code, discount_percent=15, min_order_amount=30000, usage_limit=50)

    await call.answer(f"🎉 Yangi promokod yaratildi: {code} (15% chegirma)!", show_alert=True)
    await callback_promos_list(call)


async def start_add_promo(call: types.CallbackQuery, state: FSMContext):
    """Yangi promokod yaratishni boshlash."""
    if not is_admin(call.from_user.id):
        return

    await AdminAddPromo.waiting_for_code.set()
    await call.message.answer("🎟 Yangi promokod nomini kiriting (masalan: <code>YANGI20</code>):", parse_mode="HTML")
    await call.answer()


async def process_add_promo_code(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    await state.update_data(code=code)
    await AdminAddPromo.waiting_for_percent.set()
    await message.answer("Chegirma foizini kiriting (1 dan 100 gacha raqam, masalan: <code>20</code>):", parse_mode="HTML")


async def process_add_promo_percent(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() or not (1 <= int(text) <= 100):
        await message.answer("⚠️ Iltimos, 1 dan 100 gacha son kiriting:")
        return

    await state.update_data(percent=int(text))
    await AdminAddPromo.waiting_for_limit.set()
    await message.answer("Maksimal ishlatish sonini kiriting (masalan: <code>100</code>):", parse_mode="HTML")


async def process_add_promo_limit(message: types.Message, state: FSMContext):
    text = message.text.strip()
    limit = int(text) if text.isdigit() else 100
    data = await state.get_data()

    await add_promo(
        code=data["code"],
        discount_percent=data["percent"],
        min_order_amount=30000,
        usage_limit=limit
    )
    await state.finish()
    await message.answer(
        f"✅ <b>Promokod yaratildi!</b>\n\n"
        f"Kod: <code>{data['code']}</code>\n"
        f"Chegirma: <b>{data['percent']}%</b>\n"
        f"Limit: <b>{limit} marta</b>",
        reply_markup=get_admin_dashboard_kb(),
        parse_mode="HTML"
    )


# ==========================================
# 6. OMMAVIY XABAR TARQATISH (BROADCAST ENGINE)
# ==========================================

async def start_broadcast(call: types.CallbackQuery, state: FSMContext):
    """Xabar tarqatishni boshlash."""
    if not is_admin(call.from_user.id):
        return

    total_users = await get_all_users_count()
    await AdminBroadcast.waiting_for_content.set()
    await call.message.edit_text(
        f"📢 <b>OMMAVIY XABAR TARQATISH</b>\n\n"
        f"Hozirda botda jami <b>{total_users} nafar</b> foydalanuvchi mavjud.\n\n"
        f"Tarqatmoqchi bo'lgan xabaringizni yuboring (Matn, rasm, video yoki havola):",
        parse_mode="HTML"
    )
    await call.answer()


async def process_broadcast_content(message: types.Message, state: FSMContext):
    """Tarqatiladigan xabarni saqlash va ko'rsatish."""
    await state.update_data(
        content_type=message.content_type,
        message_id=message.message_id,
        chat_id=message.chat.id
    )
    await AdminBroadcast.waiting_for_confirm.set()

    await message.answer("👆 Yuqoridagi xabar barcha foydalanuvchilarga tarqatiladi.\n\nTasdiqlaysizmi?", reply_markup=get_broadcast_confirm_kb())


async def confirm_broadcast(call: types.CallbackQuery, state: FSMContext):
    """Xabarni barcha foydalanuvchilarga xavfsiz anti-flood bilan tarqatish."""
    if not is_admin(call.from_user.id):
        return

    data = await state.get_data()
    msg_id = data.get("message_id")
    from_chat_id = data.get("chat_id")

    user_ids = await get_all_user_ids()
    total = len(user_ids)

    await call.message.edit_text(f"⏳ <b>Xabar tarqatish boshlandi...</b>\nJami: {total} nafar mijoz.", parse_mode="HTML")

    success_count = 0
    fail_count = 0

    for idx, uid in enumerate(user_ids, 1):
        try:
            await call.bot.copy_message(
                chat_id=uid,
                from_chat_id=from_chat_id,
                message_id=msg_id
            )
            success_count += 1
        except RetryAfter as e:
            await asyncio.sleep(e.timeout)
            try:
                await call.bot.copy_message(chat_id=uid, from_chat_id=from_chat_id, message_id=msg_id)
                success_count += 1
            except Exception:
                fail_count += 1
        except (BotBlocked, ChatNotFound, UserDeactivated):
            fail_count += 1
        except Exception as e:
            logger.warning(f"Broadcast error for user {uid}: {e}")
            fail_count += 1

        # Anti-flood pauzasi
        await asyncio.sleep(0.05)

    await state.finish()
    report = (
        f"📢 <b>XABAR TARQATISH YAKUNLANDI!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Muvaffaqiyatli yetkazildi: <b>{success_count} nafar</b>\n"
        f"❌ Yetkazilmadi (bloklaganlar): <b>{fail_count} ta</b>\n"
        f"👥 Jami qamrov: <b>{total} nafar</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await call.message.answer(report, reply_markup=get_admin_dashboard_kb(), parse_mode="HTML")


async def cancel_broadcast(call: types.CallbackQuery, state: FSMContext):
    """Tarqatishni bekor qilish."""
    await state.finish()
    await call.message.edit_text("❌ Xabar tarqatish bekor qilindi.", reply_markup=get_admin_dashboard_kb())
    await call.answer()


async def callback_promo_broadcast(call: types.CallbackQuery):
    """Promokodni barcha foydalanuvchilarga reklama qilib tarqatish."""
    if not is_admin(call.from_user.id):
        return

    promo_id = int(call.data.split(":")[2])
    promos = await get_all_promos()
    target = next((p for p in promos if p["id"] == promo_id), None)
    if not target:
        await call.answer("Promokod topilmadi!", show_alert=True)
        return

    promo_text = (
        f"🎉 <b>MAXSUS AKSIYA VA CHEGIRMA!</b> 🍔🍕\n\n"
        f"Siz uchun maxsus promokod:\n"
        f"👉 <code>{target['code']}</code> 👈\n\n"
        f"Ushbu promokod orqali butun buyurtmangizga <b>{target['discount_percent']}% chegirma</b> olasiz!\n"
        f"Shoshiling, aksiya soni cheklangan! 🏃‍♂️💨"
    )

    user_ids = await get_all_user_ids()
    await call.answer("📢 Reklama xabari tarqatilmoqda...", show_alert=True)

    success = 0
    for uid in user_ids:
        try:
            await call.bot.send_message(uid, promo_text, parse_mode="HTML")
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass

    await call.message.answer(f"✅ Promokod {success} nafar foydalanuvchiga yuborildi!")


# ==========================================
# 7. EXCEL / CSV EKSPORT (ACCOUNTING)
# ==========================================

async def callback_export_menu(call: types.CallbackQuery):
    """CSV eksport davrini tanlash menyusi."""
    if not is_admin(call.from_user.id):
        return

    await call.message.edit_text(
        "📥 <b>BUXGALTERIYA VA HISOBOTLAR EKSPORTI</b>\n\n"
        "Buyurtmalar tarixini Excel/CSV formatida yuklab olish uchun davrni tanlang:",
        reply_markup=get_export_kb(),
        parse_mode="HTML"
    )
    await call.answer()


async def callback_export_csv(call: types.CallbackQuery):
    """CSV fayl yaratish va jo'natish."""
    if not is_admin(call.from_user.id):
        return

    period = call.data.split(":")[2]
    days = int(period) if period.isdigit() else None

    orders = await get_orders_for_export(days=days)
    if not orders:
        await call.answer("Bu davr uchun buyurtmalar mavjud emas!", show_alert=True)
        return

    await call.answer("⏳ CSV hisobot tayyorlanmoqda...")

    # CSV fayl yaratish (UTF-8 with BOM for Excel)
    output = io.StringIO()
    # UTF-8 BOM
    output.write("\ufeff")

    writer = csv.writer(output, delimiter=";")
    # Sarlavhalar
    writer.writerow([
        "Buyurtma ID",
        "Sana va Vaqt",
        "Mijoz Ismi",
        "Telefon",
        "Xizmat Turi",
        "Manzil / Stol",
        "Taomlar Tarkibi",
        "Mahsulotlar Summasi (so'm)",
        "Chegirma (so'm)",
        "Yetkazish Narxi (so'm)",
        "Jami To'lov (so'm)",
        "To'lov Turi",
        "Holati"
    ])

    for o in orders:
        d_type = "Yetkazib berish" if o.get("delivery_type") == "delivery" else f"Shu yerda (Stol #{o.get('table_number', '-')})"
        writer.writerow([
            f"#{o['id']}",
            o.get("created_at", ""),
            o.get("customer_name") or "Mijoz",
            o.get("phone") or "",
            d_type,
            o.get("address") or "",
            o.get("items_summary") or "",
            o.get("items_total", 0),
            o.get("discount_amount", 0),
            o.get("delivery_fee", 0),
            o.get("final_total", 0),
            o.get("payment_method", "").upper(),
            o.get("status", "")
        ])

    csv_bytes = output.getvalue().encode("utf-8-sig")
    output.close()

    filename = f"orders_report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    document = types.InputFile(io.BytesIO(csv_bytes), filename=filename)

    await call.bot.send_document(
        chat_id=call.from_user.id,
        document=document,
        caption=f"📊 <b>Buyurtmalar hisoboti tayyor!</b>\nJami: {len(orders)} ta buyurtma.",
        parse_mode="HTML"
    )


# ==========================================
# 8. OSHXONA VA KURYER KANALLARI INTERFEYSI
# ==========================================

async def callback_kitchen_accept(call: types.CallbackQuery):
    """Oshxona kanalida buyurtmani qabul qilish."""
    order_id = int(call.data.split(":")[2])
    order = await get_order_by_id(order_id)
    if not order:
        await call.answer("Buyurtma topilmadi!", show_alert=True)
        return

    await update_order_status(order_id, "preparing")
    await call.answer("👨‍🍳 Buyurtma qabul qilindi (Tayyorlanmoqda)!", show_alert=False)

    # Mijozga push notification
    await send_customer_status_notification(call.bot, order["user_id"], order_id, "preparing")

    # Xabar matnini yangilash
    try:
        updated_text = call.message.text + f"\n\n👨‍🍳 <b>QABUL QILINDI:</b> {call.from_user.full_name} tomonidan tayyorlanmoqda."
        await call.message.edit_text(updated_text, parse_mode="HTML")
    except Exception:
        pass


async def callback_kitchen_cancel(call: types.CallbackQuery):
    """Oshxona kanalida buyurtmani bekor qilish."""
    order_id = int(call.data.split(":")[2])
    order = await get_order_by_id(order_id)
    if not order:
        await call.answer("Buyurtma topilmadi!", show_alert=True)
        return

    await update_order_status(order_id, "cancelled")
    await call.answer("❌ Buyurtma bekor qilindi!", show_alert=False)

    # Mijozga bildirishnoma
    await send_customer_status_notification(call.bot, order["user_id"], order_id, "cancelled")

    try:
        updated_text = call.message.text + f"\n\n❌ <b>BEKOR QILINDI:</b> {call.from_user.full_name} tomonidan."
        await call.message.edit_text(updated_text, parse_mode="HTML")
    except Exception:
        pass


async def callback_courier_start(call: types.CallbackQuery):
    """Kuryer yo'lga chiqishi (1-bosqich)."""
    order_id = int(call.data.split(":")[2])
    order = await get_order_by_id(order_id)
    if not order:
        await call.answer("Buyurtma topilmadi!", show_alert=True)
        return

    await update_order_status(order_id, "delivering")
    await call.answer("🛵 Yetkazish boshlandi!", show_alert=False)

    # Mijozga push notification
    await send_customer_status_notification(call.bot, order["user_id"], order_id, "delivering")

    # Kuryer tugmasini 2-bosqichga o'zgartirish
    try:
        updated_text = call.message.text + f"\n\n🛵 <b>KURYER YO'LDA:</b> {call.from_user.full_name} olib ketmoqda."
        await call.message.edit_text(updated_text, parse_mode="HTML", reply_markup=get_courier_complete_kb(order_id))
    except Exception:
        pass


async def callback_courier_complete(call: types.CallbackQuery):
    """Kuryer buyurtmani topshirdi (2-bosqich)."""
    order_id = int(call.data.split(":")[2])
    order = await get_order_by_id(order_id)
    if not order:
        await call.answer("Buyurtma topilmadi!", show_alert=True)
        return

    await update_order_status(order_id, "completed")
    await call.answer("✅ Buyurtma topshirildi!", show_alert=False)

    # Mijozga yakuniy chek va baholash yuboriladi
    await send_customer_status_notification(call.bot, order["user_id"], order_id, "completed")

    try:
        updated_text = call.message.text + f"\n\n✅ <b>TOPSHIRILDI:</b> Buyurtma mijozga yetkazildi."
        await call.message.edit_text(updated_text, parse_mode="HTML")
    except Exception:
        pass


# ==========================================
# 9. MIJOZ BAHOLASH TIZIMI (FEEDBACK)
# ==========================================

async def callback_customer_rate(call: types.CallbackQuery, state: FSMContext):
    """Mijoz baho (1-5 yulduz) qo'yganda."""
    parts = call.data.split(":")
    order_id = int(parts[1])
    rating = int(parts[2])

    await add_feedback(user_id=call.from_user.id, order_id=order_id, rating=rating, comment="")
    await state.update_data(feedback_order_id=order_id, feedback_rating=rating)
    await CustomerFeedback.waiting_for_comment.set()

    stars = "⭐" * rating
    await call.message.edit_text(
        f"Katta rahmat! Siz {stars} ({rating}/5) baho qo'ydingiz. 😊\n\n"
        f"Xohlasangiz, qisqa fikr yoki taklifingizni yozib qoldiring (yoki /skip deb yozing):"
    )
    await call.answer()


async def process_feedback_comment(message: types.Message, state: FSMContext):
    """Mijozning yozma izohi."""
    comment = message.text.strip()
    data = await state.get_data()
    order_id = data.get("feedback_order_id")
    rating = data.get("feedback_rating", 5)

    if comment != "/skip":
        await add_feedback(user_id=message.from_user.id, order_id=order_id, rating=rating, comment=comment)

    await state.finish()
    await message.answer("Fikringiz uchun tashakkur! Keyingi safar yanada mazali taomlar bilan kutamiz! 🍔🍕")


# ==========================================
# HANDLERLARNI RO'YXATGA OLISH
# ==========================================

def register_admin_handlers(dp: Dispatcher):
    """Barcha admin handlerlarini ro'yxatga oladi."""

    # 1. Dashboard va Reply Klaviatura (1-rasm joyiga chiqadigan tugmalar)
    dp.register_message_handler(cmd_admin, commands=["admin"], state="*")
    dp.register_message_handler(cmd_admin, lambda m: m.text in ["🛠 Admin Panel", "Admin Panel"], state="*")
    dp.register_message_handler(admin_reply_orders, lambda m: m.text in ["📦 Buyurtmalar", "Buyurtmalar"], state="*")
    dp.register_message_handler(admin_reply_analytics, lambda m: m.text in ["📊 Statistika", "Statistika"], state="*")
    dp.register_message_handler(admin_reply_products, lambda m: m.text in ["🍔 Mahsulotlar", "Mahsulotlar"], state="*")
    dp.register_message_handler(admin_reply_promos, lambda m: m.text in ["🎟 Promokodlar", "Promokodlar"], state="*")
    dp.register_message_handler(admin_reply_broadcast, lambda m: m.text in ["📢 Xabar tarqatish", "Xabar tarqatish"], state="*")
    dp.register_message_handler(admin_reply_export, lambda m: m.text in ["📥 CSV Eksport", "CSV Eksport"], state="*")
    dp.register_message_handler(admin_reply_feedbacks, lambda m: m.text in ["⭐ Oxirgi fikrlar", "Oxirgi fikrlar"], state="*")
    dp.register_message_handler(admin_reply_refresh, lambda m: m.text in ["🔄 Yangilash", "Yangilash"], state="*")
    dp.register_message_handler(admin_reply_back_main, lambda m: m.text in ["🔙 Asosiy menyuga qaytish", "Asosiy menyuga qaytish"], state="*")

    dp.register_callback_query_handler(callback_refresh_dashboard, lambda c: c.data in ["admin:dashboard", "admin:refresh_dashboard"], state="*")

    # 2. Analitika va Fikrlar
    dp.register_callback_query_handler(callback_analytics_view, lambda c: c.data.startswith("admin:analytics"), state="*")
    dp.register_callback_query_handler(callback_feedbacks_view, lambda c: c.data.startswith("admin:feedbacks"), state="*")

    # 3. Buyurtmalar boshqaruvi
    dp.register_callback_query_handler(callback_orders_list, lambda c: c.data.startswith("admin:orders:"), state="*")
    dp.register_callback_query_handler(callback_order_view, lambda c: c.data.startswith("admin:order_view:"), state="*")
    dp.register_callback_query_handler(callback_order_location, lambda c: c.data.startswith("admin:order_loc:"), state="*")
    dp.register_callback_query_handler(callback_order_change_status_menu, lambda c: c.data.startswith("admin:order_change_status:"), state="*")
    dp.register_callback_query_handler(callback_set_order_status, lambda c: c.data.startswith("admin:set_status:"), state="*")

    # 4. Mahsulotlar CRUD
    dp.register_callback_query_handler(callback_products_list, lambda c: c.data == "admin:products:all", state="*")
    dp.register_callback_query_handler(callback_product_view, lambda c: c.data.startswith("admin:product_view:"), state="*")
    dp.register_callback_query_handler(callback_product_toggle, lambda c: c.data.startswith("admin:product_toggle:"), state="*")
    dp.register_callback_query_handler(callback_product_delete, lambda c: c.data.startswith("admin:product_delete:"), state="*")
    dp.register_callback_query_handler(start_add_product, lambda c: c.data == "admin:product_add_start", state="*")
    dp.register_callback_query_handler(process_add_prod_category, lambda c: c.data.startswith("admin:addprod_cat:"), state=AdminAddProduct.waiting_for_category)
    dp.register_message_handler(process_add_prod_name, state=AdminAddProduct.waiting_for_name)
    dp.register_message_handler(process_add_prod_price, state=AdminAddProduct.waiting_for_price)
    dp.register_message_handler(process_add_prod_desc, state=AdminAddProduct.waiting_for_description)
    dp.register_message_handler(process_add_prod_image, content_types=[types.ContentType.PHOTO, types.ContentType.TEXT], state=AdminAddProduct.waiting_for_image)

    # Mahsulot narxi / chegirmasi
    dp.register_callback_query_handler(start_product_discount, lambda c: c.data.startswith("admin:product_discount:"), state="*")
    dp.register_message_handler(process_product_discount, state=AdminEditProduct.waiting_for_discount)

    # 5. Promokodlar
    dp.register_callback_query_handler(callback_promos_list, lambda c: c.data == "admin:promos", state="*")
    dp.register_callback_query_handler(callback_promo_view, lambda c: c.data.startswith("admin:promo_view:"), state="*")
    dp.register_callback_query_handler(callback_promo_toggle, lambda c: c.data.startswith("admin:promo_toggle:"), state="*")
    dp.register_callback_query_handler(callback_promo_delete, lambda c: c.data.startswith("admin:promo_delete:"), state="*")
    dp.register_callback_query_handler(callback_promo_random, lambda c: c.data == "admin:promo_random", state="*")
    dp.register_callback_query_handler(callback_promo_broadcast, lambda c: c.data.startswith("admin:promo_broadcast:"), state="*")
    dp.register_callback_query_handler(start_add_promo, lambda c: c.data == "admin:promo_add_start", state="*")
    dp.register_message_handler(process_add_promo_code, state=AdminAddPromo.waiting_for_code)
    dp.register_message_handler(process_add_promo_percent, state=AdminAddPromo.waiting_for_percent)
    dp.register_message_handler(process_add_promo_limit, state=AdminAddPromo.waiting_for_limit)

    # 6. Xabar tarqatish (Broadcast)
    dp.register_callback_query_handler(start_broadcast, lambda c: c.data == "admin:broadcast", state="*")
    dp.register_message_handler(process_broadcast_content, content_types=types.ContentTypes.ANY, state=AdminBroadcast.waiting_for_content)
    dp.register_callback_query_handler(confirm_broadcast, lambda c: c.data == "admin:broadcast_confirm", state=AdminBroadcast.waiting_for_confirm)
    dp.register_callback_query_handler(cancel_broadcast, lambda c: c.data == "admin:broadcast_cancel", state=AdminBroadcast.waiting_for_confirm)

    # 7. CSV Eksport
    dp.register_callback_query_handler(callback_export_menu, lambda c: c.data == "admin:export", state="*")
    dp.register_callback_query_handler(callback_export_csv, lambda c: c.data.startswith("admin:export_csv:"), state="*")

    # 8. Oshxona va Kuryer kanallari callbacklari
    dp.register_callback_query_handler(callback_kitchen_accept, lambda c: c.data.startswith("kitchen:accept:"), state="*")
    dp.register_callback_query_handler(callback_kitchen_cancel, lambda c: c.data.startswith("kitchen:cancel:"), state="*")
    dp.register_callback_query_handler(callback_courier_start, lambda c: c.data.startswith("courier:start:"), state="*")
    dp.register_callback_query_handler(callback_courier_complete, lambda c: c.data.startswith("courier:complete:"), state="*")

    # 9. Mijoz baholash (Feedback)
    dp.register_callback_query_handler(callback_customer_rate, lambda c: c.data.startswith("rate:"), state="*")
    dp.register_message_handler(process_feedback_comment, state=CustomerFeedback.waiting_for_comment)

