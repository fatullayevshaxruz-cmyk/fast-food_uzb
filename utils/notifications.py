"""
Telegram Bildirishnomalari (Oshxona, Kuryer va Mijoz)
"""
import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Dict, Any, List, Optional, Tuple
from config import ADMIN_CHANNEL_ID, DELIVERY_CHANNEL_ID
from keyboards.admin_keyboard import get_kitchen_channel_kb, get_courier_start_kb

logger = logging.getLogger(__name__)

def get_rating_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Buyurtma yetkazilgandan so'ng 1-5 yulduzli baholash tugmalari."""
    kb = InlineKeyboardMarkup(row_width=5)
    buttons = [
        InlineKeyboardButton(text=f"⭐ {i}", callback_data=f"rate_{order_id}_{i}")
        for i in range(1, 6)
    ]
    kb.row(*buttons)
    return kb

async def notify_admins_new_order(bot: Bot, order_data: Dict[str, Any], items: List[Dict[str, Any]], order_id: int) -> Tuple[Optional[int], Optional[int]]:
    """
    Yangi buyurtma haqida oshxona/filial kanaliga va kuryer kanaliga xabar yuboradi.
    (channel_id, channel_msg_id) ni qaytaradi.
    """
    delivery_type = order_data.get("delivery_type", "delivery")
    is_delivery = (delivery_type == "delivery")
    
    delivery_type_str = "Yetkazib berish" if is_delivery else f"Shu yerda (Stol #{order_data.get('table_number', '-')})"
    
    pay_raw = str(order_data.get("payment_method", "cash")).lower()
    if pay_raw == "cash":
        payment_display = "Naqd pul (Yetkazib berilganda)"
    elif pay_raw == "click":
        payment_display = "Karta orqali to'landi (Click)"
    elif pay_raw == "payme":
        payment_display = "Karta orqali to'landi (Payme)"
    else:
        payment_display = pay_raw.capitalize()

    # Mahsulotlar ro'yxati
    items_text = ""
    for idx, itm in enumerate(items, 1):
        name = itm.get("name") or itm.get("product_name", "Noma'lum")
        qty = itm.get("quantity", 1)
        price = itm.get("price") or itm.get("price_at_time", 0)
        total = itm.get("total_price", qty * price)
        items_text += f"  ▫️ {name} x {qty} = {total:,} so'm\n"

    user_name = order_data.get('full_name', 'Mijoz')
    username = order_data.get('username')
    username_display = f"@{username}" if username else f"ID: {order_data.get('user_id')}"
    phone = order_data.get('phone') or order_data.get('phone_number', '-')
    address = order_data.get('address') or order_data.get('delivery_address', 'Kiritilmagan')
    distance_km = order_data.get('distance_km', 0)
    final_total = order_data.get('final_total') or order_data.get('total_amount', 0)

    # 4. Oshxona kanali xabari (Section 4 dizayni)
    kitchen_msg = (
        f"🆕 <b>Yangi buyurtma #{order_id}</b>\n"
        f"⏳ <i>Holat: Kafe tasdiqlashi kutilmoqda...</i>\n\n"
        f"👤 <b>Mijoz:</b> {user_name} ({username_display})\n"
        f"📞 <b>Telefon:</b> {phone}\n"
        f"🛵 <b>Turi:</b> {delivery_type_str}\n"
    )

    if is_delivery:
        kitchen_msg += f"📍 <b>Manzil:</b> {address} ({distance_km:.1f} km)\n"
    else:
        kitchen_msg += f"🪑 <b>Stol raqami:</b> #{order_data.get('table_number', '-')}\n"

    if order_data.get("note"):
        kitchen_msg += f"📝 <b>Izoh:</b> <i>{order_data.get('note')}</i>\n"

    kitchen_msg += (
        f"\n🍛 <b>Buyurtma tarkibi:</b>\n"
        f"{items_text}\n"
        f"💰 <b>Umumiy summa:</b> {final_total:,} so'm\n"
        f"💳 <b>To'lov:</b> {payment_display}"
    )

    target_channel = order_data.get("branch_channel_id") or ADMIN_CHANNEL_ID
    channel_msg_id = None
    try:
        sent = await bot.send_message(
            chat_id=target_channel,
            text=kitchen_msg,
            parse_mode="HTML",
            reply_markup=get_kitchen_channel_kb(order_id)
        )
        channel_msg_id = sent.message_id
        logger.info(f"Kitchen notification sent to channel {target_channel} for order #{order_id}")
    except Exception as e:
        logger.error(f"Error sending kitchen notification to {target_channel}: {e}")

    # Kuryer kanaliga yuborish
    if is_delivery and DELIVERY_CHANNEL_ID:
        courier_msg = (
            f"🛵 <b>KURYER UCHUN BUYURTMA #{order_id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏢 <b>Filial:</b> {order_data.get('branch_name', 'Darxan Burger')}\n"
            f"📍 <b>Manzil:</b> {address} ({distance_km:.1f} km)\n"
            f"📞 <b>Mijoz telefoni:</b> <a href=\"tel:{phone}\">{phone}</a>\n"
            f"💰 <b>Mijozdan olinadigan summa:</b> <b>{final_total:,} so'm</b> ({payment_display})\n"
        )
        if order_data.get("note"):
            courier_msg += f"📝 <b>Izoh:</b> <i>{order_data.get('note')}</i>\n"

        try:
            await bot.send_message(
                chat_id=DELIVERY_CHANNEL_ID,
                text=courier_msg,
                parse_mode="HTML",
                reply_markup=get_courier_start_kb(order_id)
            )
            lat = order_data.get("lat") or order_data.get("latitude")
            lon = order_data.get("lon") or order_data.get("longitude")
            if lat and lon:
                await bot.send_location(chat_id=DELIVERY_CHANNEL_ID, latitude=lat, longitude=lon)
            logger.info(f"Courier notification sent to {DELIVERY_CHANNEL_ID} for order #{order_id}")
        except Exception as e:
            logger.error(f"Error sending courier notification to {DELIVERY_CHANNEL_ID}: {e}")

    return target_channel, channel_msg_id

async def send_status_update_to_user(bot: Bot, user_id: int, order_id: int, new_status: str):
    """Mijozga buyurtma statusi o'zgarganida bildirishnoma yuborish."""
    status_messages = {
        "preparing": "👨‍🍳 <b>Buyurtmangiz #{order_id} qabul qilindi va oshxonada tayyorlanmoqda!</b>\nTez orada kuryerga topshiriladi.",
        "delivering": "🛵 <b>Buyurtmangiz #{order_id} kuryerga berildi va yo'lga chiqdi!</b>\nKuryer yaqinlashganda siz bilan bog'lanadi.",
        "completed": "✅ <b>Buyurtmangiz #{order_id} muvaffaqiyatli yetkazib berildi!</b>\nYoqimli ishtaha! Xizmatimiz sifatini yaxshilash uchun taom va yetkazishni baholang:",
        "cancelled": "❌ <b>Afsuski, buyurtmangiz #{order_id} bekor qilindi.</b>\nSavollar bo'lsa ma'muriyat bilan bog'laning."
    }
    
    text = status_messages.get(new_status)
    if not text:
        return

    formatted_text = text.format(order_id=order_id)
    reply_markup = get_rating_keyboard(order_id) if new_status == "completed" else None

    try:
        await bot.send_message(
            chat_id=user_id,
            text=formatted_text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.warning(f"Foydalanuvchiga status bildirishnomasini yuborib bo'lmadi ({user_id}): {e}")
