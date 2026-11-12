from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from utils.i18n import get_text


def get_delivery_type_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    """Yetkazib berish turini tanlash klaviaturasi."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(
            text=get_text("btn_eat_in", lang),
            callback_data="delivery_type:eat_in"
        ),
        InlineKeyboardButton(
            text=get_text("btn_delivery", lang),
            callback_data="delivery_type:delivery"
        )
    )
    kb.add(
        InlineKeyboardButton(
            text=get_text("btn_cancel", lang),
            callback_data="cancel_order"
        )
    )
    return kb


def get_location_reply_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Lokatsiya yuborish uchun Reply klaviatura."""
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton(text=get_text("btn_send_location", lang), request_location=True))
    kb.add(KeyboardButton(text=get_text("btn_cancel", lang)))
    return kb


def get_phone_reply_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Telefon raqam yuborish uchun Reply klaviatura."""
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton(text=get_text("btn_send_phone", lang), request_contact=True))
    kb.add(KeyboardButton(text=get_text("btn_cancel", lang)))
    return kb


def get_skip_or_cancel_inline_kb(skip_callback: str, lang: str = "uz") -> InlineKeyboardMarkup:
    """O'tkazib yuborish va bekor qilish klaviaturasi."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(
            text=get_text("btn_skip", lang),
            callback_data=skip_callback
        ),
        InlineKeyboardButton(
            text=get_text("btn_cancel", lang),
            callback_data="cancel_order"
        )
    )
    return kb


def get_cancel_reply_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Faqat bekor qilish tugmasi bo'lgan reply klaviatura."""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton(text=get_text("btn_cancel", lang)))
    return kb


def get_payment_method_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    """To'lov turini tanlash klaviaturasi."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(text=get_text("pay_cash", lang), callback_data="pay_method:cash"),
        InlineKeyboardButton(text=get_text("pay_click", lang), callback_data="pay_method:click"),
    )
    kb.add(
        InlineKeyboardButton(text=get_text("pay_payme", lang), callback_data="pay_method:payme")
    )
    kb.add(
        InlineKeyboardButton(text=get_text("btn_cancel", lang), callback_data="cancel_order")
    )
    return kb

