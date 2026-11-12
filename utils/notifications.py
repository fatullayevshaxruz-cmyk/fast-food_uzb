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
    
    type_badge = "🛵 Yetkazib berish" if is_delivery else f"🍽 Shu yerda (Stol #{order_data.get('table_number', '-')})"
    payment_badge = order_data.get("payment_method", "cash").upper()

    # Mahsulotlar ro'yxati
    items_text = ""
    for idx, itm in enumerate(items, 1):
        name = itm.get("name") or itm.get("product_name", "Noma'lum")
        qty = itm.get("quantity", 1)
        price = itm.get("price") or itm.get("price_at_time", 0)
        total = itm.get("total_price", qty * price)
        items_text += f"{idx}. <b>{name}</b> x {qty} dona — <i>{total:,} so'm</i>\n"

    # Filial / oshxona uchun to'liq xabar
    kitchen_msg = (
        f"🔔 <b>YANGI BUYURTMA #{order_id}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>Turi:</b> {type_badge}\n"
        f"🏢 <b>Filial:</b> {order_data.get('branch_name', 'Bosh filial')}\n"
    )

    if is_delivery:
        kitchen_msg += (
            f"📍 <b>Manzil:</b> {order_data.get('address') or order_data.get('delivery_address', 'Kiritilmagan')}\n"
            f"📏 <b>Masofa:</b> {order_data.get('distance_km', 0):.1f} km\n"
        )
    else:
        kitchen_msg += f"🍽 <b>Stol raqami:</b> #{order_data.get('table_number', '-')}\n"

    kitchen_msg += (
        f"📞 <b>Telefon:</b> {order_data.get('phone') or order_data.get('phone_number', '-')}\n"
        f"👤 <b>Mijoz:</b> {order_data.get('full_name', 'Mijoz')} (ID: <code>{order_data.get('user_id')}</code>)\n"
    )

    if order_data.get("note"):
        kitchen_msg += f"📝 <b>Izoh:</b> {order_data.get('note')}\n"

    kitchen_msg += (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>Tarkib:</b>\n{items_text}"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Mahsulotlar: {order_data.get('items_total', 0):,} so'm\n"
    )

    if order_data.get("discount_amount", 0) > 0:
        kitchen_msg += f"🏷 Chegirma ({order_data.get('promo_code', '')}): -{order_data.get('discount_amount', 0):,} so'm\n"

    if is_delivery:
        kitchen_msg += f"🛵 Yetkazish narxi: {order_data.get('delivery_fee', 0):,} so'm\n"

    final_total = order_data.get('final_total') or order_data.get('total_amount', 0)
    kitchen_msg += (
        f"💰 <b>JAMI:</b> <b>{final_total:,} so'm</b>\n"
        f"💳 <b>To'lov turi:</b> <b>{payment_badge}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
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
        phone_val = order_data.get('phone') or order_data.get('phone_number', '-')
        courier_msg = (
            f"🛵 <b>KURYER UCHUN BUYURTMA #{order_id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏢 <b>Filialdan:</b> {order_data.get('branch_name', 'Bosh filial')}\n"
            f"📍 <b>Manzil:</b> {order_data.get('address') or order_data.get('delivery_address', 'Kiritilmagan')}\n"
            f"📏 <b>Masofa:</b> {order_data.get('distance_km', 0):.1f} km\n"
            f"📞 <b>Mijoz telefoni:</b> <a href=\"tel:{phone_val}\">{phone_val}</a>\n"
            f"💰 <b>Mijozdan olinadigan summa:</b> <b>{final_total:,} so'm</b> ({payment_badge})\n"
            f"🛵 <b>Yetkazish haqi:</b> {order_data.get('delivery_fee', 0):,} so'm\n"
        )
        if order_data.get("note"):
            courier_msg += f"📝 <b>Izoh:</b> {order_data.get('note')}\n"

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
