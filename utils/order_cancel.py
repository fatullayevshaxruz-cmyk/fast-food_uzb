"""
1 Daqiqalik Buyurtmani Bekor Qilish Tizimi (60-second Order Cancellation Window)
Server tomonida qat'iy nazorat qilinuvchi bekor qilish mexanizmi.
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional, Tuple
from aiogram import Bot
from database.crud import get_order_by_id, update_order_status

logger = logging.getLogger(__name__)

# Faol bekor qilish oynalari: order_id -> metadata
active_cancel_timers: Dict[int, Dict[str, Any]] = {}

def get_cancel_countdown_kb(order_id: int):
    """Mijoz uchun 60 soniyalik bekor qilish inline tugmasi."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(
            text="❌ Buyurtmani bekor qilish (60s)",
            callback_data=f"user_cancel_order_{order_id}"
        )
    )
    return kb

async def start_order_cancel_window(
    bot: Bot,
    order_id: int,
    user_id: int,
    user_chat_id: int,
    user_msg_id: int,
    channel_id: Optional[int] = None,
    channel_msg_id: Optional[int] = None,
    duration: int = 60
):
    """
    Buyurtma uchun 60 soniyalik bekor qilish hisoblagichini boshlaydi.
    Vaqt tugashi bilan bekor qilish tugmasini avtomatik o'chiradi.
    """
    expire_at = time.time() + duration
    active_cancel_timers[order_id] = {
        "user_id": user_id,
        "user_chat_id": user_chat_id,
        "user_msg_id": user_msg_id,
        "channel_id": channel_id,
        "channel_msg_id": channel_msg_id,
        "expire_at": expire_at,
        "cancelled": False
    }

    asyncio.create_task(_cancel_timer_worker(bot, order_id, duration))

async def _cancel_timer_worker(bot: Bot, order_id: int, duration: int):
    """60 soniya kutib, bekor qilish tugmasini olib tashlaydi."""
    await asyncio.sleep(duration)
    
    meta = active_cancel_timers.get(order_id)
    if not meta or meta.get("cancelled"):
        return

    # Bazadan holatini tekshirish
    order = await get_order_by_id(order_id)
    if order and order.get("status") == "pending":
        # 60s tugadi - mijoz xabaridagi bekor qilish tugmasini olib tashlash
        try:
            await bot.edit_message_reply_markup(
                chat_id=meta["user_chat_id"],
                message_id=meta["user_msg_id"],
                reply_markup=None
            )
        except Exception as e:
            logger.debug(f"Timer expire edit markup error: {e}")

    # Xotiradan tozalash
    active_cancel_timers.pop(order_id, None)

async def handle_user_cancel_order(bot: Bot, order_id: int, user_id: int) -> Tuple[bool, str]:
    """
    Mijoz tomonidan buyurtmani bekor qilish jarayoni.
    Qat'iy tekshiruv: faqat 60s ichida va status 'pending' bo'lganda ruxsat beriladi.
    """
    order = await get_order_by_id(order_id)
    if not order:
        return False, "Buyurtma topilmadi."

    if order.get("user_id") != user_id:
        return False, "Siz faqat o'z buyurtmangizni bekor qila olasiz."

    if order.get("status") != "pending":
        return False, "Buyurtma allaqachon qabul qilingan yoki oshxonada tayyorlanmoqda, bekor qilib bo'lmaydi."

    meta = active_cancel_timers.get(order_id)
    if meta:
        if time.time() > meta["expire_at"]:
            return False, "1 daqiqalik bekor qilish vaqti tugagan. Buyurtma oshxonaga uzatildi."
        meta["cancelled"] = True

    # 1. Bazada statusni cancelled qilish
    await update_order_status(order_id, "cancelled")

    # 2. Filial kanalidagi xabarni tahrirlash (tugmalarni olib tashlash)
    channel_id = meta.get("channel_id") if meta else None
    channel_msg_id = meta.get("channel_msg_id") if meta else None

    if channel_id and channel_msg_id:
        try:
            cancel_notice = (
                f"❌❌❌ <b>BUYURTMA #{order_id} MIJOZ TOMONIDAN BEKOR QILINDI!</b> ❌❌❌\n"
                f"Ushbu buyurtmani tayyorlash shart emas."
            )
            await bot.edit_message_text(
                chat_id=channel_id,
                message_id=channel_msg_id,
                text=cancel_notice,
                parse_mode="HTML",
                reply_markup=None
            )
        except Exception as e:
            logger.error(f"Error updating channel on user cancel: {e}")

    # 3. Foydalanuvchi xabaridagi tugmani olib tashlash
    if meta:
        try:
            await bot.edit_message_reply_markup(
                chat_id=meta["user_chat_id"],
                message_id=meta["user_msg_id"],
                reply_markup=None
            )
        except Exception:
            pass

    return True, "✅ Buyurtmangiz muvaffaqiyatli bekor qilindi."
