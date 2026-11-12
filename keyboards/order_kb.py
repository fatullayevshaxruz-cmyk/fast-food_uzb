from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo
)
from config import WEB_APP_URL, is_admin
from utils.i18n import get_text


def get_language_inline_kb() -> InlineKeyboardMarkup:
    """Tilni tanlash inline klaviaturasi (1 qatorda 3 ta)."""
    kb = InlineKeyboardMarkup(row_width=3)
    kb.row(
        InlineKeyboardButton("🇺🇿 O'zbek", callback_data="set_lang:uz"),
        InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang:ru"),
        InlineKeyboardButton("🇬🇧 English", callback_data="set_lang:en")
    )
    return kb


def get_main_menu_keyboard(lang: str = "uz", user_id: int = None) -> ReplyKeyboardMarkup:
    """
    Asosiy menyu doimiy Reply klaviaturasi:
    [ 🍽 Menyu (Web App) ]
    [ 🛒 Savat ]  [ 🔍 Izlash ]
    [ ❤️ Sevimlilar ]  [ 📦 Buyurtmalarim ]
    [ 👤 Profil ]  [ ☎️ Bog'lanish ]
    (Admin bo'lsa: [ 🛠 Admin Panel ])
    """
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(
        KeyboardButton("🍽 Menyu", web_app=WebAppInfo(url=WEB_APP_URL))
    )
    kb.row(
        KeyboardButton("🛒 Savat"),
        KeyboardButton("🔍 Izlash")
    )
    kb.row(
        KeyboardButton("❤️ Sevimlilar"),
        KeyboardButton("📦 Buyurtmalarim")
    )
    kb.row(
        KeyboardButton("👤 Profil"),
        KeyboardButton("☎️ Bog'lanish")
    )
    if user_id and is_admin(user_id):
        kb.row(KeyboardButton("🛠 Admin Panel"))
    return kb


def get_delivery_type_reply_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Yetkazib berish turini tanlash Reply klaviaturasi."""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(
        KeyboardButton("🍽 Shu yerda (Kafe)"),
        KeyboardButton("🛵 Yetkazib berish")
    )
    kb.row(
        KeyboardButton("❌ Bekor qilish")
    )
    return kb


def get_location_reply_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Lokatsiya yuborish uchun Reply klaviatura."""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📍 Joylashuvni yuborish", request_location=True))
    kb.row(KeyboardButton("🗺 Xaritadan tanlash", web_app=WebAppInfo(url=f"{WEB_APP_URL}/map.html")))
    kb.row(KeyboardButton("❌ Bekor qilish"))
    return kb


def get_phone_reply_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Telefon raqam yuborish uchun Reply klaviatura."""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📱 Raqamni yuborish", request_contact=True))
    kb.row(KeyboardButton("❌ Bekor qilish"))
    return kb


def get_skip_or_cancel_reply_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Izoh va promokod uchun O'tkazib yuborish va Bekor qilish klaviaturasi."""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(
        KeyboardButton("⏭ O'tkazib yuborish"),
        KeyboardButton("❌ Bekor qilish")
    )
    return kb


def get_skip_or_cancel_inline_kb(skip_callback: str, lang: str = "uz") -> InlineKeyboardMarkup:
    """Izoh va promokod uchun Inline klaviatura."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data=skip_callback),
        InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_order")
    )
    return kb


def get_cancel_reply_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Faqat bekor qilish tugmasi bo'lgan reply klaviatura."""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("❌ Bekor qilish"))
    return kb


def get_payment_method_reply_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    """To'lov turini tanlash Reply klaviaturasi."""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(
        KeyboardButton("💵 Naqd (Yetkazib berilganda)"),
        KeyboardButton("💳 Online to'lov (Karta)")
    )
    kb.row(
        KeyboardButton("❌ Bekor qilish")
    )
    return kb


def get_payment_method_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    """To'lov turini tanlash Inline klaviaturasi."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.row(
        InlineKeyboardButton("💵 Naqd (Yetkazib berilganda)", callback_data="pay_method:cash"),
        InlineKeyboardButton("💳 Online to'lov (Karta)", callback_data="pay_method:online")
    )
    kb.row(
        InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_order")
    )
    return kb


def get_online_payment_channels_kb(order_id: int, final_total: int) -> InlineKeyboardMarkup:
    """Click va Payme ilovalari uchun to'lov inline tugmalari."""
    from security.payment_guard import generate_click_link, generate_payme_link
    click_url = generate_click_link(order_id, final_total)
    payme_url = generate_payme_link(order_id, final_total)

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("💳 Payme ilovasida to'lash", url=payme_url),
        InlineKeyboardButton("🔹 Click ilovasida to'lash", url=click_url),
        InlineKeyboardButton("🔄 To'lovni tekshirish", callback_data=f"chk_pay_{order_id}"),
        InlineKeyboardButton("❌ Buyurtmani bekor qilish (60s)", callback_data=f"user_cancel_order_{order_id}")
    )
    return kb
