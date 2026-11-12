from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from typing import List, Dict, Any, Optional


def get_admin_dashboard_kb() -> InlineKeyboardMarkup:
    """Jonli boshqaruv paneli (Dashboard) inline klaviaturasi."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📦 Buyurtmalar", callback_data="admin:orders:all:1"),
        InlineKeyboardButton("📊 Statistika", callback_data="admin:analytics")
    )
    kb.add(
        InlineKeyboardButton("🍔 Mahsulotlar (Menyu)", callback_data="admin:products:all"),
        InlineKeyboardButton("🎟 Promokodlar", callback_data="admin:promos")
    )
    kb.add(
        InlineKeyboardButton("📢 Xabar tarqatish", callback_data="admin:broadcast"),
        InlineKeyboardButton("📥 CSV Eksport", callback_data="admin:export")
    )
    kb.add(
        InlineKeyboardButton("⭐ Oxirgi fikrlar", callback_data="admin:feedbacks:1"),
        InlineKeyboardButton("🔄 Yangilash", callback_data="admin:refresh_dashboard")
    )
    return kb


def get_orders_filter_kb(current_status: str, orders: List[Dict[str, Any]], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Buyurtmalar ro'yxati va holat filtrlari klaviaturasi."""
    kb = InlineKeyboardMarkup(row_width=3)

    # Filtrlar
    filters = [
        ("Barchasi", "all"),
        ("⏳ Kutilmoqda", "pending"),
        ("👨‍🍳 Tayyorlanmoqda", "preparing"),
        ("🛵 Yetkazilmoqda", "delivering"),
        ("✅ Yetkazildi", "completed"),
        ("❌ Bekor", "cancelled")
    ]
    filter_btns = []
    for title, st in filters:
        label = f"• {title} •" if st == current_status else title
        filter_btns.append(InlineKeyboardButton(label, callback_data=f"admin:orders:{st}:1"))
    kb.add(*filter_btns[:3])
    kb.add(*filter_btns[3:])

    # Buyurtmalar ro'yxati
    for o in orders:
        status_emoji = {
            "new": "⏳",
            "pending": "⏳",
            "preparing": "👨‍🍳",
            "delivering": "🛵",
            "completed": "✅",
            "cancelled": "❌"
        }.get(o.get("status"), "📦")

        d_type = "🛵" if o.get("delivery_type") == "delivery" else f"🍽 #{o.get('table_number', '-')}"
        btn_text = f"{status_emoji} #{o['id']} • {d_type} • {o['final_total']:,} so'm"
        kb.add(InlineKeyboardButton(btn_text, callback_data=f"admin:order_view:{o['id']}"))

    # Sahifalash (Pagination)
    nav_btns = []
    if page > 1:
        nav_btns.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"admin:orders:{current_status}:{page - 1}"))
    nav_btns.append(InlineKeyboardButton(f"{page}/{max(1, total_pages)}", callback_data="noop"))
    if page < total_pages:
        nav_btns.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"admin:orders:{current_status}:{page + 1}"))
    kb.row(*nav_btns)

    kb.add(InlineKeyboardButton("🔙 Boshqaruv paneli", callback_data="admin:dashboard"))
    return kb


def get_order_detail_kb(order_id: int, status: str, lat: Optional[float], lon: Optional[float]) -> InlineKeyboardMarkup:
    """Alohida buyurtma kartasi klaviaturasi."""
    kb = InlineKeyboardMarkup(row_width=2)
    if lat and lon:
        kb.add(InlineKeyboardButton("📍 Lokatsiyani ko'rish", callback_data=f"admin:order_loc:{order_id}"))

    kb.add(
        InlineKeyboardButton("🔄 Holatni o'zgartirish", callback_data=f"admin:order_change_status:{order_id}"),
        InlineKeyboardButton("🔙 Buyurtmalarga qaytish", callback_data="admin:orders:all:1")
    )
    return kb


def get_order_status_change_kb(order_id: int) -> InlineKeyboardMarkup:
    """Buyurtma holatini tanlash inline klaviaturasi."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("⏳ Kutilmoqda", callback_data=f"admin:set_status:{order_id}:pending"),
        InlineKeyboardButton("👨‍🍳 Tayyorlanmoqda", callback_data=f"admin:set_status:{order_id}:preparing")
    )
    kb.add(
        InlineKeyboardButton("🛵 Yetkazilmoqda", callback_data=f"admin:set_status:{order_id}:delivering"),
        InlineKeyboardButton("✅ Yetkazildi", callback_data=f"admin:set_status:{order_id}:completed")
    )
    kb.add(
        InlineKeyboardButton("❌ Bekor qilish", callback_data=f"admin:set_status:{order_id}:cancelled")
    )
    kb.add(InlineKeyboardButton("🔙 Bekor qilish", callback_data=f"admin:order_view:{order_id}"))
    return kb


def get_analytics_kb() -> InlineKeyboardMarkup:
    """Statistika davrini tanlash klaviaturasi."""
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(
        InlineKeyboardButton("📅 Bugun", callback_data="admin:analytics:1"),
        InlineKeyboardButton("🗓 7 kun", callback_data="admin:analytics:7"),
        InlineKeyboardButton("📆 30 kun", callback_data="admin:analytics:30")
    )
    kb.add(
        InlineKeyboardButton("⭐ Mijozlar fikrlari", callback_data="admin:feedbacks:1"),
        InlineKeyboardButton("🔙 Boshqaruv paneli", callback_data="admin:dashboard")
    )
    return kb


def get_feedbacks_page_kb(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Fikrlar sahifalash klaviaturasi."""
    kb = InlineKeyboardMarkup(row_width=3)
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"admin:feedbacks:{page - 1}"))
    nav.append(InlineKeyboardButton(f"{page}/{max(1, total_pages)}", callback_data="noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"admin:feedbacks:{page + 1}"))
    kb.row(*nav)
    kb.add(InlineKeyboardButton("🔙 Boshqaruv paneli", callback_data="admin:dashboard"))
    return kb


def get_menu_categories_kb() -> InlineKeyboardMarkup:
    """Kategoriyalarni tanlash klaviaturasi."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🍔 Burgerlar", callback_data="admin:addprod_cat:burgers"),
        InlineKeyboardButton("🌯 Lavash", callback_data="admin:addprod_cat:lavash")
    )
    kb.add(
        InlineKeyboardButton("🍕 Pizzalar", callback_data="admin:addprod_cat:pizza"),
        InlineKeyboardButton("🍟 Gazaklar", callback_data="admin:addprod_cat:snacks")
    )
    kb.add(
        InlineKeyboardButton("🥤 Ichimliklar", callback_data="admin:addprod_cat:drinks"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data="admin:products:all")
    )
    return kb


def get_products_admin_kb(products: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Mahsulotlar ro'yxati boshqaruv klaviaturasi."""
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("➕ Yangi mahsulot qo'shish", callback_data="admin:product_add_start"))

    for p in products:
        status_icon = "🟢" if p.get("is_available") == 1 else "🔴 (Stop-list)"
        title = f"{status_icon} {p['name']} — {p['price']:,} so'm"
        kb.add(InlineKeyboardButton(title, callback_data=f"admin:product_view:{p['id']}"))

    kb.add(InlineKeyboardButton("🔙 Boshqaruv paneli", callback_data="admin:dashboard"))
    return kb


def get_product_card_admin_kb(product_id: int, is_available: int) -> InlineKeyboardMarkup:
    """Alohida mahsulot kartasi boshqaruvi."""
    kb = InlineKeyboardMarkup(row_width=2)
    toggle_title = "🔴 Stop-listga kiritish" if is_available == 1 else "🟢 Qayta yoqish"
    kb.add(
        InlineKeyboardButton(toggle_title, callback_data=f"admin:product_toggle:{product_id}"),
        InlineKeyboardButton("🏷 Chegirma / Aksiya", callback_data=f"admin:product_discount:{product_id}")
    )
    kb.add(
        InlineKeyboardButton("🖼 Rasmni yangilash", callback_data=f"admin:product_reimage:{product_id}"),
        InlineKeyboardButton("🗑 O'chirish", callback_data=f"admin:product_delete:{product_id}")
    )
    kb.add(InlineKeyboardButton("🔙 Mahsulotlarga qaytish", callback_data="admin:products:all"))
    return kb


def get_promos_admin_kb(promos: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Promokodlar ro'yxati klaviaturasi."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("➕ Yangi promokod", callback_data="admin:promo_add_start"),
        InlineKeyboardButton("🎲 Tasodifiy promo", callback_data="admin:promo_random")
    )
    for p in promos:
        status = "🟢" if p.get("is_active") == 1 else "🔴"
        title = f"{status} {p['code']} ({p['discount_percent']}%) — {p['used_count']}/{p['usage_limit']}"
        kb.add(InlineKeyboardButton(title, callback_data=f"admin:promo_view:{p['id']}"))

    kb.add(InlineKeyboardButton("🔙 Boshqaruv paneli", callback_data="admin:dashboard"))
    return kb


def get_promo_card_admin_kb(promo_id: int, is_active: int, code: str) -> InlineKeyboardMarkup:
    """Alohida promokod boshqaruvi."""
    kb = InlineKeyboardMarkup(row_width=2)
    toggle_title = "🔴 To'xtatish" if is_active == 1 else "🟢 Faollashtirish"
    kb.add(
        InlineKeyboardButton(toggle_title, callback_data=f"admin:promo_toggle:{promo_id}"),
        InlineKeyboardButton("📢 E'lon qilish (Broadcast)", callback_data=f"admin:promo_broadcast:{promo_id}")
    )
    kb.add(
        InlineKeyboardButton("🗑 O'chirish", callback_data=f"admin:promo_delete:{promo_id}"),
        InlineKeyboardButton("🔙 Promokodlarga qaytish", callback_data="admin:promos")
    )
    return kb


def get_broadcast_confirm_kb() -> InlineKeyboardMarkup:
    """Xabar tarqatishni tasdiqlash klaviaturasi."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Ha, tarqatilsin", callback_data="admin:broadcast_confirm"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data="admin:broadcast_cancel")
    )
    return kb


def get_export_kb() -> InlineKeyboardMarkup:
    """CSV eksport davrini tanlash klaviaturasi."""
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📅 Oxirgi 7 kunlik buyurtmalar (CSV)", callback_data="admin:export_csv:7"),
        InlineKeyboardButton("🗓 Oxirgi 30 kunlik buyurtmalar (CSV)", callback_data="admin:export_csv:30"),
        InlineKeyboardButton("📦 Barcha vaqtdagi buyurtmalar (CSV)", callback_data="admin:export_csv:all"),
        InlineKeyboardButton("🔙 Boshqaruv paneli", callback_data="admin:dashboard")
    )
    return kb


# Oshxona kanali tugmalari
def get_kitchen_channel_kb(order_id: int) -> InlineKeyboardMarkup:
    """Oshxona kanalidagi yangi buyurtma tugmalari."""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("👨‍🍳 Qabul qilish (Tayyorlash)", callback_data=f"kitchen:accept:{order_id}"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data=f"kitchen:cancel:{order_id}")
    )
    return kb


# Kuryer kanali tugmalari (2 bosqichli)
def get_courier_start_kb(order_id: int) -> InlineKeyboardMarkup:
    """Kuryer kanali 1-bosqich tugmasi."""
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🛵 Yo'lga chiqish (Yetkazish)", callback_data=f"courier:start:{order_id}")
    )
    return kb


def get_courier_complete_kb(order_id: int) -> InlineKeyboardMarkup:
    """Kuryer kanali 2-bosqich tugmasi."""
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("✅ Buyurtma yetkazildi (Topshirildi)", callback_data=f"courier:complete:{order_id}")
    )
    return kb


# Mijoz baholash klaviaturasi (Feedback)
def get_feedback_rating_kb(order_id: int) -> InlineKeyboardMarkup:
    """Buyurtma tugagach mijozga yuboriladigan 1-5 yulduzli baholash klaviaturasi."""
    kb = InlineKeyboardMarkup(row_width=5)
    kb.add(
        InlineKeyboardButton("⭐ 1", callback_data=f"rate:{order_id}:1"),
        InlineKeyboardButton("⭐ 2", callback_data=f"rate:{order_id}:2"),
        InlineKeyboardButton("⭐ 3", callback_data=f"rate:{order_id}:3"),
        InlineKeyboardButton("⭐ 4", callback_data=f"rate:{order_id}:4"),
        InlineKeyboardButton("⭐ 5", callback_data=f"rate:{order_id}:5")
    )
    return kb
