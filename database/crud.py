"""
CRUD Operations for Fast-Food System (PostgreSQL + SQLite Dual-Engine)
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from database.connection import (
    init_connection,
    close_connection,
    execute,
    execute_insert,
    fetch_one,
    fetch_all,
    IS_POSTGRES
)
from database.models import init_models
from config import BRANCH_1_CHANNEL_ID, RESTAURANT_LAT, RESTAURANT_LON

logger = logging.getLogger(__name__)

async def init_db():
    """Baza ulanishi va jadvallarni yaratadi, boshlang'ich ma'lumotlarni kiritadi."""
    await init_connection()
    await init_models()
    await seed_initial_data()

async def seed_initial_data():
    """Boshlang'ich filiallar, toifalar va mahsulotlarni kiritadi."""
    # Filiallar tekshiruvi
    branches = await fetch_all("SELECT id FROM branches")
    if not branches:
        await execute(
            "INSERT INTO branches (name, latitude, longitude, admin_chat_id, max_delivery_km, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("Markaziy Filial (Amir Temur)", RESTAURANT_LAT, RESTAURANT_LON, BRANCH_1_CHANNEL_ID, 15.0, 1)
        )
        await execute(
            "INSERT INTO branches (name, latitude, longitude, admin_chat_id, max_delivery_km, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("Chilonzor Filiali", 41.272100, 69.204300, BRANCH_1_CHANNEL_ID, 15.0, 1)
        )

    # Toifalar tekshiruvi
    cats = await fetch_all("SELECT id, name_uz FROM categories")
    if not cats:
        cat_ids = {}
        for name_uz, name_ru, name_en, order in [
            ("Burgerlar", "Бургеры", "Burgers", 1),
            ("Lavash & Donar", "Лаваш и Донар", "Lavash & Doner", 2),
            ("Pitsa", "Пицца", "Pizza", 3),
            ("Ichimliklar", "Напитки", "Drinks", 4),
            ("Sneklar & Desertlar", "Снеки и Десерты", "Snacks & Desserts", 5)
        ]:
            cid = await execute_insert(
                "INSERT INTO categories (name_uz, name_ru, name_en, sort_order, is_active) VALUES (?, ?, ?, ?, 1)",
                (name_uz, name_ru, name_en, order)
            )
            cat_ids[name_uz] = cid
    else:
        cat_ids = {c["name_uz"]: c["id"] for c in cats}

    # Mahsulotlar tekshiruvi
    prods = await fetch_all("SELECT id FROM products")
    if not prods:
        b_id = cat_ids.get("Burgerlar", 1)
        l_id = cat_ids.get("Lavash & Donar", 2)
        p_id = cat_ids.get("Pitsa", 3)
        d_id = cat_ids.get("Ichimliklar", 4)
        s_id = cat_ids.get("Sneklar & Desertlar", 5)

        sample_products = [
            (b_id, "Cheeseburger Max", "Чизбургер Макс", "Cheeseburger Max", 38000, "Shirali mol go'shti, erigan cheddar pishlog'i va maxsus sous.", "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=600", 1, 35000),
            (b_id, "Double Beef Burger", "Двойной Бургер", "Double Beef Burger", 48000, "Ikki qavatli barra mol go'shti va karamellangan piyoz.", "https://images.unsplash.com/photo-1586190848861-99aa4a171e90?w=600", 1, 0),
            (l_id, "Mol Go'shtli Lavash Classic", "Классический Лаваш с говядиной", "Beef Lavash Classic", 34000, "Tandir go'shti, bodring, pomidor, qarsildoq chips va sous.", "https://images.unsplash.com/photo-1626700051175-6818013e1d4f?w=600", 1, 0),
            (l_id, "Pishloqli Tovuq Lavash", "Сырный Лаваш с курицей", "Cheese Chicken Lavash", 36000, "Tovuq go'shti, ko'p miqdorda mozzarella va oq sous.", "https://images.unsplash.com/photo-1561651823-34feb02250e4?w=600", 1, 0),
            (p_id, "Pepperoni Pitsa 30cm", "Пепперони 30см", "Pepperoni Pizza 30cm", 65000, "Achchiq pepperoni kolbasasi, mozzarella va pomidor sousi.", "https://images.unsplash.com/photo-1628840042765-356cda07504e?w=600", 1, 59000),
            (s_id, "Fri Kartoshkasi (Katta)", "Картофель Фри (Большой)", "French Fries (Large)", 18000, "Qarsildoq oltin rang kartoshka fri.", "https://images.unsplash.com/photo-1576107232684-1279f3908594?w=600", 1, 0),
            (d_id, "Coca-Cola 0.5L", "Coca-Cola 0.5л", "Coca-Cola 0.5L", 9000, "Muzdek tetiklashtiruvchi klassik ichimlik.", "https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=600", 1, 0),
            (d_id, "Qulupnayli Mojito", "Клубничный Мохито", "Strawberry Mojito", 22000, "Muz, yalpiz, qulupnay va laym bilan yangi limonad.", "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?w=600", 1, 0)
        ]
        for p in sample_products:
            await execute(
                "INSERT INTO products (category_id, name, name_ru, name_en, price, description, image_url, is_active, discount_price) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                p
            )

    # Promokodlar tekshiruvi
    promos = await fetch_all("SELECT id FROM promo_codes")
    if not promos:
        await execute(
            "INSERT INTO promo_codes (code, discount_percent, max_uses, used_count, min_order_amount, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("FAST10", 10, 500, 0, 30000, 1)
        )
        await execute(
            "INSERT INTO promo_codes (code, discount_percent, max_uses, used_count, min_order_amount, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("SUPER20", 20, 100, 0, 50000, 1)
        )

# ---------------- FOYDALANUVCHILAR (USERS) ----------------
async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    return await fetch_one("SELECT * FROM users WHERE user_id = ?", (user_id,))

async def save_or_update_user(user_id: int, full_name: str = None, phone: str = None, language_code: str = None, username: str = None):
    existing = await get_user(user_id)
    if existing:
        updates = []
        params = []
        if full_name:
            updates.append("full_name = ?")
            params.append(full_name)
        if phone:
            updates.append("phone_number = ?")
            params.append(phone)
        if language_code:
            updates.append("language = ?")
            params.append(language_code)
        if username:
            updates.append("username = ?")
            params.append(username)
        if updates:
            params.append(user_id)
            sql = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"
            await execute(sql, tuple(params))
    else:
        lang = language_code or "uz"
        await execute(
            "INSERT INTO users (user_id, username, full_name, phone_number, language) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, full_name, phone, lang)
        )

async def get_all_user_ids() -> List[int]:
    rows = await fetch_all("SELECT user_id FROM users")
    return [r["user_id"] for r in rows]

async def get_all_users_count() -> int:
    row = await fetch_one("SELECT COUNT(*) as c FROM users")
    return row["c"] if row else 0

# ---------------- MAHSULOTLAR VA TOIFALAR (PRODUCTS & CATEGORIES) ----------------
async def get_all_categories() -> List[Dict[str, Any]]:
    return await fetch_all("SELECT * FROM categories WHERE is_active = 1 ORDER BY sort_order ASC")

async def get_all_products() -> List[Dict[str, Any]]:
    sql = """
    SELECT p.*, c.name_uz as category_name 
    FROM products p 
    LEFT JOIN categories c ON p.category_id = c.id
    ORDER BY p.id ASC
    """
    rows = await fetch_all(sql)
    # UI uchun moslashtirish (category, image kalitlari)
    for r in rows:
        r["category"] = r.get("category_name") or "Burgerlar"
        r["image"] = r.get("image_url") or ""
        r["badge"] = f"-{int((1 - r['discount_price']/r['price'])*100)}%" if r.get("discount_price") and r["discount_price"] > 0 else ""
    return rows

async def get_product_by_id(product_id: int) -> Optional[Dict[str, Any]]:
    sql = "SELECT p.*, c.name_uz as category_name FROM products p LEFT JOIN categories c ON p.category_id = c.id WHERE p.id = ?"
    row = await fetch_one(sql, (product_id,))
    if row:
        row["category"] = row.get("category_name") or "Burgerlar"
        row["image"] = row.get("image_url") or ""
        row["badge"] = f"-{int((1 - row['discount_price']/row['price'])*100)}%" if row.get("discount_price") and row["discount_price"] > 0 else ""
    return row

async def add_product(category: str, name: str, price: int, description: str, image: str, badge: str = "") -> int:
    cat = await fetch_one("SELECT id FROM categories WHERE name_uz = ? OR name_ru = ? LIMIT 1", (category, category))
    if cat:
        category_id = cat["id"]
    else:
        category_id = await execute_insert("INSERT INTO categories (name_uz, sort_order) VALUES (?, 99)", (category,))
    
    return await execute_insert(
        "INSERT INTO products (category_id, name, price, description, image_url, is_active, discount_price) "
        "VALUES (?, ?, ?, ?, ?, 1, 0)",
        (category_id, name, price, description, image)
    )

async def toggle_product_status(product_id: int) -> int:
    prod = await get_product_by_id(product_id)
    if not prod:
        return 0
    new_status = 0 if prod.get("is_active", 1) == 1 else 1
    await execute("UPDATE products SET is_active = ? WHERE id = ?", (new_status, product_id))
    return new_status

async def update_product_discount(product_id: int, discount_price: int):
    await execute("UPDATE products SET discount_price = ? WHERE id = ?", (discount_price, product_id))

async def update_product_image(product_id: int, new_image: str):
    await execute("UPDATE products SET image_url = ? WHERE id = ?", (new_image, product_id))

async def delete_product(product_id: int):
    await execute("DELETE FROM products WHERE id = ?", (product_id,))

# ---------------- FILIALLAR (BRANCHES) ----------------
async def get_active_branches() -> List[Dict[str, Any]]:
    return await fetch_all("SELECT * FROM branches WHERE is_active = 1")

# ---------------- SAVATCHA (CART) ----------------
async def get_cart_items(user_id: int) -> List[Dict[str, Any]]:
    sql = """
    SELECT c.quantity, p.* 
    FROM cart_items c 
    JOIN products p ON c.product_id = p.id 
    WHERE c.user_id = ? AND p.is_active = 1
    """
    rows = await fetch_all(sql)
    for r in rows:
        r["image"] = r.get("image_url") or ""
    return rows

async def add_to_cart(user_id: int, product_id: int, quantity: int = 1):
    existing = await fetch_one("SELECT quantity FROM cart_items WHERE user_id = ? AND product_id = ?", (user_id, product_id))
    if existing:
        new_q = existing["quantity"] + quantity
        if new_q > 0:
            await execute("UPDATE cart_items SET quantity = ? WHERE user_id = ? AND product_id = ?", (new_q, user_id, product_id))
        else:
            await execute("DELETE FROM cart_items WHERE user_id = ? AND product_id = ?", (user_id, product_id))
    else:
        if quantity > 0:
            await execute("INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, ?)", (user_id, product_id, quantity))

async def set_cart_items(user_id: int, items: List[Dict[str, Any]]):
    await clear_cart(user_id)
    for it in items:
        pid = it.get("product_id") or it.get("id")
        q = it.get("quantity", 1)
        if pid and q > 0:
            await execute("INSERT INTO cart_items (user_id, product_id, quantity) VALUES (?, ?, ?)", (user_id, pid, q))

async def clear_cart(user_id: int):
    await execute("DELETE FROM cart_items WHERE user_id = ?", (user_id,))

# ---------------- PROMOKODLAR (PROMO CODES) ----------------
async def check_promo_code(code: str, order_amount: int) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    if not code:
        return False, None, "Promokod kiritilmadi"
    promo = await fetch_one("SELECT * FROM promo_codes WHERE code = ? COLLATE NOCASE", (code.strip(),))
    if not promo:
        return False, None, "Bunday promokod mavjud emas"
    if not promo.get("is_active"):
        return False, None, "Ushbu promokod faol emas"
    if promo.get("used_count", 0) >= promo.get("max_uses", 100):
        return False, None, "Ushbu promokodning foydalanish limiti tugagan"
    if order_amount < promo.get("min_order_amount", 0):
        return False, None, f"Minimal buyurtma summasi {promo.get('min_order_amount'):,} so'm bo'lishi kerak"
    return True, promo, "Muvaffaqiyatli qo'llandi"

async def mark_promo_used(promo_id: int):
    await execute("UPDATE promo_codes SET used_count = used_count + 1 WHERE id = ?", (promo_id,))

async def get_all_promos() -> List[Dict[str, Any]]:
    return await fetch_all("SELECT * FROM promo_codes ORDER BY id DESC")

async def add_promo(code: str, discount_percent: int, min_order_amount: int = 0, usage_limit: int = 100) -> int:
    return await execute_insert(
        "INSERT INTO promo_codes (code, discount_percent, min_order_amount, max_uses, used_count, is_active) "
        "VALUES (?, ?, ?, ?, 0, 1)",
        (code.upper().strip(), discount_percent, min_order_amount, usage_limit)
    )

async def delete_promo(promo_id: int):
    await execute("DELETE FROM promo_codes WHERE id = ?", (promo_id,))

async def toggle_promo_status(promo_id: int) -> int:
    p = await fetch_one("SELECT is_active FROM promo_codes WHERE id = ?", (promo_id,))
    if not p:
        return 0
    new_s = 0 if p["is_active"] == 1 else 1
    await execute("UPDATE promo_codes SET is_active = ? WHERE id = ?", (new_s, promo_id))
    return new_s

# ---------------- BUYURTMALAR (ORDERS) ----------------
async def create_order(
    user_id: int,
    total_amount: int,
    phone_number: str,
    items: List[Dict[str, Any]],
    delivery_type: str = "delivery",
    delivery_address: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    payment_method: str = "cash",
    payment_status: str = "unpaid",
    branch_id: Optional[int] = None,
    promo_code: Optional[str] = None,
    discount_amount: int = 0
) -> int:
    order_id = await execute_insert(
        "INSERT INTO orders (user_id, total_amount, phone_number, delivery_type, delivery_address, "
        "latitude, longitude, payment_method, payment_status, status, branch_id, promo_code, discount_amount) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)",
        (user_id, total_amount, phone_number, delivery_type, delivery_address, latitude, longitude,
         payment_method, payment_status, branch_id, promo_code, discount_amount)
    )
    for it in items:
        pid = it.get("product_id") or it.get("id")
        q = it.get("quantity", 1)
        price = it.get("price", 0)
        await execute(
            "INSERT INTO order_items (order_id, product_id, quantity, price_at_time) VALUES (?, ?, ?, ?)",
            (order_id, pid, q, price)
        )
    return order_id

async def get_order_by_id(order_id: int) -> Optional[Dict[str, Any]]:
    order = await fetch_one("SELECT * FROM orders WHERE id = ?", (order_id,))
    if not order:
        return None
    items = await fetch_all(
        "SELECT oi.*, p.name as product_name FROM order_items oi "
        "LEFT JOIN products p ON oi.product_id = p.id WHERE oi.order_id = ?",
        (order_id,)
    )
    order["items"] = items
    return order

async def update_order_status(order_id: int, new_status: str) -> bool:
    await execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
    return True

async def mark_order_paid(order_id: int, transaction_id: Optional[str] = None) -> bool:
    if transaction_id:
        await execute("UPDATE orders SET payment_status = 'paid', transaction_id = ? WHERE id = ?", (transaction_id, order_id))
    else:
        await execute("UPDATE orders SET payment_status = 'paid' WHERE id = ?", (order_id,))
    return True

async def get_order_payment_status(order_id: int) -> Optional[Dict[str, Any]]:
    return await fetch_one("SELECT id, payment_status, status, total_amount FROM orders WHERE id = ?", (order_id,))

async def get_user_orders(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    orders = await fetch_all("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))
    for o in orders:
        o["items"] = await fetch_all(
            "SELECT oi.*, p.name as product_name FROM order_items oi "
            "LEFT JOIN products p ON oi.product_id = p.id WHERE oi.order_id = ?",
            (o["id"],)
        )
    return orders

async def get_orders_by_status(status: Optional[str] = None, page: int = 1, limit: int = 6) -> Tuple[List[Dict[str, Any]], int]:
    offset = (page - 1) * limit
    if status and status != "all":
        count_row = await fetch_one("SELECT COUNT(*) as c FROM orders WHERE status = ?", (status,))
        orders = await fetch_all("SELECT * FROM orders WHERE status = ? ORDER BY id DESC LIMIT ? OFFSET ?", (status, limit, offset))
    else:
        count_row = await fetch_one("SELECT COUNT(*) as c FROM orders")
        orders = await fetch_all("SELECT * FROM orders ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
    
    total = count_row["c"] if count_row else 0
    for o in orders:
        o["items"] = await fetch_all(
            "SELECT oi.*, p.name as product_name FROM order_items oi "
            "LEFT JOIN products p ON oi.product_id = p.id WHERE oi.order_id = ?",
            (o["id"],)
        )
    return orders, total

# ---------------- FIKRLAR VA REYTING (RATINGS & FEEDBACK) ----------------
async def add_feedback(user_id: int, order_id: Optional[int], rating: int, comment: str = ""):
    oid = order_id or 0
    await execute(
        "INSERT INTO order_ratings (order_id, user_id, rating, comment) VALUES (?, ?, ?, ?)",
        (oid, user_id, rating, comment)
    )

async def get_average_rating_and_count() -> Tuple[float, int]:
    row = await fetch_one("SELECT AVG(rating) as avg_r, COUNT(*) as c FROM order_ratings")
    if not row or not row.get("c"):
        return 5.0, 0
    return round(float(row["avg_r"] or 5.0), 1), int(row["c"])

async def get_feedbacks(page: int = 1, limit: int = 5) -> Tuple[List[Dict[str, Any]], int]:
    offset = (page - 1) * limit
    count_row = await fetch_one("SELECT COUNT(*) as c FROM order_ratings")
    total = count_row["c"] if count_row else 0
    sql = """
    SELECT r.*, u.full_name, u.phone_number 
    FROM order_ratings r 
    LEFT JOIN users u ON r.user_id = u.user_id 
    ORDER BY r.id DESC LIMIT ? OFFSET ?
    """
    rows = await fetch_all(sql, (limit, offset))
    return rows, total

# ---------------- STATISTIKA VA DASHBOARD (ANALYTICS & EXPORT) ----------------
async def get_dashboard_stats() -> Dict[str, Any]:
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Bugungi buyurtmalar va kassa (PostgreSQL / SQLite ga mos)
    today_row = await fetch_one(
        "SELECT COUNT(*) as orders_count, COALESCE(SUM(total_amount), 0) as revenue "
        "FROM orders WHERE created_at LIKE ? AND status != 'cancelled'",
        (f"{today_str}%",)
    )
    
    pending_row = await fetch_one("SELECT COUNT(*) as c FROM orders WHERE status = 'pending'")
    preparing_row = await fetch_one("SELECT COUNT(*) as c FROM orders WHERE status = 'preparing'")
    delivering_row = await fetch_one("SELECT COUNT(*) as c FROM orders WHERE status = 'delivering'")
    users_count = await get_all_users_count()

    return {
        "today_orders": today_row["orders_count"] if today_row else 0,
        "today_revenue": today_row["revenue"] if today_row else 0,
        "pending_count": pending_row["c"] if pending_row else 0,
        "preparing_count": preparing_row["c"] if preparing_row else 0,
        "delivering_count": delivering_row["c"] if delivering_row else 0,
        "total_users": users_count
    }

async def get_analytics_stats(days: int = 7) -> Dict[str, Any]:
    since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
    row = await fetch_one(
        "SELECT COUNT(*) as orders_count, COALESCE(SUM(total_amount), 0) as revenue "
        "FROM orders WHERE created_at >= ? AND status != 'cancelled'",
        (since_date,)
    )
    return {
        "orders_count": row["orders_count"] if row else 0,
        "revenue": row["revenue"] if row else 0
    }

async def get_top_products(limit: int = 5) -> List[Dict[str, Any]]:
    sql = """
    SELECT p.name, SUM(oi.quantity) as sold_count, SUM(oi.quantity * oi.price_at_time) as total_revenue
    FROM order_items oi
    JOIN products p ON oi.product_id = p.id
    JOIN orders o ON oi.order_id = o.id
    WHERE o.status != 'cancelled'
    GROUP BY p.id, p.name
    ORDER BY sold_count DESC
    LIMIT ?
    """
    return await fetch_all(sql, (limit,))

async def get_orders_for_export(days: Optional[int] = None) -> List[Dict[str, Any]]:
    if days:
        since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
        sql = "SELECT * FROM orders WHERE created_at >= ? ORDER BY id DESC"
        orders = await fetch_all(sql, (since_date,))
    else:
        sql = "SELECT * FROM orders ORDER BY id DESC"
        orders = await fetch_all(sql)
    for o in orders:
        o["items"] = await fetch_all(
            "SELECT oi.*, p.name as product_name FROM order_items oi "
            "LEFT JOIN products p ON oi.product_id = p.id WHERE oi.order_id = ?",
            (o["id"],)
        )
    return orders
