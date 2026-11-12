import aiosqlite
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from config import DATABASE_PATH, RESTAURANT_LAT, RESTAURANT_LON, ADMIN_CHANNEL_ID

logger = logging.getLogger(__name__)


async def init_db():
    """Ma'lumotlar bazasi jadvallarini yaratish va boshlang'ich ma'lumotlarni kiritish."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON;")

        # Foydalanuvchilar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                phone TEXT,
                language_code TEXT DEFAULT 'uz',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Filiallar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS branches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                channel_id INTEGER,
                is_active INTEGER DEFAULT 1
            );
        """)

        # Mahsulotlar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                description TEXT,
                is_available INTEGER DEFAULT 1
            );
        """)

        # Savat jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cart (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (product_id) REFERENCES products (id),
                UNIQUE(user_id, product_id)
            );
        """)

        # Promokodlar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                discount_percent INTEGER NOT NULL,
                min_order_amount INTEGER DEFAULT 0,
                usage_limit INTEGER DEFAULT 100,
                used_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                valid_until TIMESTAMP
            );
        """)

        # Buyurtmalar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                delivery_type TEXT NOT NULL, -- 'eat_in' yoki 'delivery'
                table_number INTEGER,
                address TEXT,
                lat REAL,
                lon REAL,
                branch_id INTEGER,
                branch_name TEXT,
                distance_km REAL,
                phone TEXT,
                note TEXT,
                promo_code TEXT,
                discount_amount INTEGER DEFAULT 0,
                items_total INTEGER NOT NULL,
                delivery_fee INTEGER DEFAULT 0,
                final_total INTEGER NOT NULL,
                payment_method TEXT DEFAULT 'cash',
                status TEXT DEFAULT 'new', -- 'new', 'accepted', 'preparing', 'delivering', 'completed', 'cancelled'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Buyurtma mahsulotlari jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER,
                product_name TEXT NOT NULL,
                price INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                total_price INTEGER NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders (id)
            );
        """)

        await db.commit()

        # Standart filiallar mavjudligini tekshirish
        async with db.execute("SELECT COUNT(*) FROM branches") as cursor:
            count = (await cursor.fetchone())[0]
            if count == 0:
                await db.execute("""
                    INSERT INTO branches (name, lat, lon, channel_id, is_active)
                    VALUES 
                    ('Amir Temur (Bosh filial)', ?, ?, ?, 1),
                    ('Chilonzor filiali', 41.275820, 69.204510, ?, 1),
                    ('Yunusobod filiali', 41.365210, 69.289120, ?, 1)
                """, (RESTAURANT_LAT, RESTAURANT_LON, ADMIN_CHANNEL_ID, ADMIN_CHANNEL_ID, ADMIN_CHANNEL_ID))
                await db.commit()

        # Standart mahsulotlar mavjudligini tekshirish
        async with db.execute("SELECT COUNT(*) FROM products") as cursor:
            prod_count = (await cursor.fetchone())[0]
            if prod_count == 0:
                await db.execute("""
                    INSERT INTO products (name, price, description)
                    VALUES 
                    ('Cheeseburger Maxi', 35000, 'Katta mol go''shti kotleti, pishloq, bodring, maxsus sous'),
                    ('Lavash Standart (Mol go''shti)', 32000, 'Mol go''shti, pomidor, bodring, chipslar, mayonez'),
                    ('Pizza Pepperoni 30cm', 65000, 'Pepperoni kolbasasi, motsarella, tomat sousi'),
                    ('Fri kartoshkasi', 15000, 'Qarsildoq kartoshka fri va sous'),
                    ('Coca-Cola 0.5L', 8000, 'Muzdek Coca-Cola')
                """)
                await db.commit()

        # Standart test promokodlarini kiritish
        async with db.execute("SELECT COUNT(*) FROM promos") as cursor:
            promo_count = (await cursor.fetchone())[0]
            if promo_count == 0:
                await db.execute("""
                    INSERT INTO promos (code, discount_percent, min_order_amount, usage_limit, is_active)
                    VALUES 
                    ('FAST10', 10, 30000, 100, 1),
                    ('YANGI20', 20, 50000, 50, 1)
                """)
                await db.commit()

    logger.info("Database initialized successfully.")


# ---------------- Foydalanuvchilar bilan ishlash ----------------

async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Foydalanuvchini id bo'yicha oladi."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def save_or_update_user(user_id: int, full_name: str = None, phone: str = None, language_code: str = None):
    """Foydalanuvchi ma'lumotlarini kiritadi yoki yangilaydi."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT user_id, phone, language_code FROM users WHERE user_id = ?", (user_id,)) as cursor:
            existing = await cursor.fetchone()

        if existing:
            updates = []
            params = []
            if full_name:
                updates.append("full_name = ?")
                params.append(full_name)
            if phone:
                updates.append("phone = ?")
                params.append(phone)
            if language_code:
                updates.append("language_code = ?")
                params.append(language_code)
            
            if updates:
                params.append(user_id)
                query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"
                await db.execute(query, tuple(params))
        else:
            lang = language_code or "uz"
            await db.execute(
                "INSERT INTO users (user_id, full_name, phone, language_code) VALUES (?, ?, ?, ?)",
                (user_id, full_name or "", phone or "", lang)
            )
        await db.commit()


# ---------------- Savat bilan ishlash ----------------

async def get_cart_items(user_id: int) -> List[Dict[str, Any]]:
    """Foydalanuvchi savatidagi mahsulotlar ro'yxatini qaytaradi."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT c.product_id, p.name, p.price, c.quantity, (p.price * c.quantity) as total_price
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = ?
        """
        async with db.execute(query, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def clear_cart(user_id: int):
    """Foydalanuvchi savatini tozalaydi."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        await db.commit()


async def add_to_cart(user_id: int, product_id: int, quantity: int = 1):
    """Savatga mahsulot qo'shadi."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO cart (user_id, product_id, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, product_id) DO UPDATE SET quantity = quantity + excluded.quantity
        """, (user_id, product_id, quantity))
        await db.commit()


# ---------------- Promokod bilan ishlash ----------------

async def check_promo_code(code: str, order_amount: int) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Promokodni tekshiradi.
    Qaytaradi: (is_valid, promo_data, error_reason)
    """
    clean_code = code.strip().upper()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM promos WHERE code = ?", (clean_code,)) as cursor:
            promo = await cursor.fetchone()

        if not promo:
            return False, None, "not_found"

        promo_dict = dict(promo)
        if not promo_dict.get("is_active"):
            return False, None, "inactive"

        if promo_dict.get("usage_limit") and promo_dict.get("used_count", 0) >= promo_dict["usage_limit"]:
            return False, None, "limit_reached"

        if order_amount < promo_dict.get("min_order_amount", 0):
            return False, None, "min_amount_not_met"

        return True, promo_dict, "ok"


async def mark_promo_used(promo_id: int):
    """Promokod ishlatilganligini qayd etadi."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            UPDATE promos 
            SET used_count = used_count + 1 
            WHERE id = ?
        """, (promo_id,))
        await db.commit()


# ---------------- Filiallar ----------------

async def get_active_branches() -> List[Dict[str, Any]]:
    """Barcha faol filiallar ro'yxatini qaytaradi."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM branches WHERE is_active = 1") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


# ---------------- Buyurtma yaratish ----------------

async def create_order(
    user_id: int,
    delivery_type: str,
    table_number: Optional[int],
    address: str,
    lat: Optional[float],
    lon: Optional[float],
    branch_id: Optional[int],
    branch_name: Optional[str],
    distance_km: Optional[float],
    phone: str,
    note: Optional[str],
    promo_code: Optional[str],
    discount_amount: int,
    items_total: int,
    delivery_fee: int,
    final_total: int,
    payment_method: str,
    items: List[Dict[str, Any]]
) -> int:
    """
    Buyurtmani va uning mahsulotlarini bazaga tranzaksiya bilan yozadi.
    Order ID ni qaytaradi.
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("BEGIN TRANSACTION;")
        cursor = await db.execute("""
            INSERT INTO orders (
                user_id, delivery_type, table_number, address, lat, lon,
                branch_id, branch_name, distance_km, phone, note,
                promo_code, discount_amount, items_total, delivery_fee,
                final_total, payment_method, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new')
        """, (
            user_id, delivery_type, table_number, address, lat, lon,
            branch_id, branch_name, distance_km, phone, note or "",
            promo_code or "", discount_amount, items_total, delivery_fee,
            final_total, payment_method
        ))
        order_id = cursor.lastrowid

        for item in items:
            await db.execute("""
                INSERT INTO order_items (order_id, product_id, product_name, price, quantity, total_price)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                order_id,
                item.get("product_id"),
                item.get("name", "Noma'lum mahsulot"),
                item.get("price", 0),
                item.get("quantity", 1),
                item.get("total_price", 0)
            ))

        await db.commit()
        return order_id
