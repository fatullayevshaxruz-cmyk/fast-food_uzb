import logging
from aiogram import Bot
from typing import Dict, Any, List
from config import ADMIN_CHANNEL_ID, DELIVERY_CHANNEL_ID

logger = logging.getLogger(__name__)


async def notify_admins_new_order(bot: Bot, order_data: Dict[str, Any], items: List[Dict[str, Any]], order_id: int):
    """
    Yangi buyurtma haqida oshxona/filial kanaliga va kuryer kanaliga xabar yuboradi.
    """
    delivery_type = order_data.get("delivery_type", "delivery")
    is_delivery = (delivery_type == "delivery")
    
    type_badge = "🛵 Yetkazib berish" if is_delivery else f"🍽 Shu yerda (Stol #{order_data.get('table_number', '-')})"
    payment_badge = order_data.get("payment_method", "cash").upper()

    # Mahsulotlar ro'yxati
    items_text = ""
    for idx, itm in enumerate(items, 1):
        name = itm.get("name", "Noma'lum")
        qty = itm.get("quantity", 1)
        price = itm.get("price", 0)
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
            f"📍 <b>Manzil:</b> {order_data.get('address', 'Kiritilmagan')}\n"
            f"📏 <b>Masofa:</b> {order_data.get('distance_km', 0):.1f} km\n"
        )
    else:
        kitchen_msg += f"🍽 <b>Stol raqami:</b> #{order_data.get('table_number', '-')}\n"

    kitchen_msg += (
        f"📞 <b>Telefon:</b> {order_data.get('phone', '-')}\n"
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

    kitchen_msg += (
        f"💰 <b>JAMI:</b> <b>{order_data.get('final_total', 0):,} so'm</b>\n"
        f"💳 <b>To'lov turi:</b> <b>{payment_badge}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

    # Oshxona kanaliga yuborish
    target_channel = order_data.get("branch_channel_id") or ADMIN_CHANNEL_ID
    try:
        await bot.send_message(chat_id=target_channel, text=kitchen_msg, parse_mode="HTML")
        logger.info(f"Kitchen notification sent to channel {target_channel} for order #{order_id}")
    except Exception as e:
        logger.error(f"Error sending kitchen notification to {target_channel}: {e}")

    # Agar yetkazib berish bo'lsa, Kuryer kanaliga alohida yuborish
    if is_delivery and DELIVERY_CHANNEL_ID:
        courier_msg = (
            f"🛵 <b>KURYER UCHUN BUYURTMA #{order_id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏢 <b>Filialdan:</b> {order_data.get('branch_name', 'Bosh filial')}\n"
            f"📍 <b>Manzil:</b> {order_data.get('address', 'Kiritilmagan')}\n"
            f"📏 <b>Masofa:</b> {order_data.get('distance_km', 0):.1f} km\n"
            f"📞 <b>Mijoz telefoni:</b> <a href=\"tel:{order_data.get('phone')}\">{order_data.get('phone')}</a>\n"
            f"💰 <b>Mijozdan olinadigan summa:</b> <b>{order_data.get('final_total', 0):,} so'm</b> ({payment_badge})\n"
            f"🛵 <b>Yetkazish haqi:</b> {order_data.get('delivery_fee', 0):,} so'm\n"
        )
        if order_data.get("note"):
            courier_msg += f"📝 <b>Izoh:</b> {order_data.get('note')}\n"

        try:
            await bot.send_message(chat_id=DELIVERY_CHANNEL_ID, text=courier_msg, parse_mode="HTML")
            # Agar koordinatalar mavjud bo'lsa, xaritadagi joylashuvni ham yuboramiz
            lat = order_data.get("lat")
            lon = order_data.get("lon")
            if lat and lon:
                await bot.send_location(chat_id=DELIVERY_CHANNEL_ID, latitude=lat, longitude=lon)
            logger.info(f"Courier notification sent to {DELIVERY_CHANNEL_ID} for order #{order_id}")
        except Exception as e:
            logger.error(f"Error sending courier notification to {DELIVERY_CHANNEL_ID}: {e}")
