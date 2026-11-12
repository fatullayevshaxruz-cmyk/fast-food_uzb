import aiosqlite
import logging
from typing import Dict, Any, List, Optional, Tuple
from config import DATABASE_PATH, RESTAURANT_LAT, RESTAURANT_LON, ADMIN_CHANNEL_ID

logger = logging.getLogger(__name__)

# Boshlang'ich kategoriyalar va mahsulotlar (Yuqori sifatli rasmlar bilan)
INITIAL_PRODUCTS = [
    # Burgerlar
    {
        "category": "burgers",
        "name": "Cheeseburger Double Black",
        "price": 42000,
        "description": "2 qavat xushbo'y mol go'shti, erigan cheddar pishlog'i, maxsus sous va tuzlangan bodring",
        "image": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=600&q=80",
        "badge": "🔥 Hit"
    },
    {
        "category": "burgers",
        "name": "Chicken Crispy Burger",
        "price": 34000,
        "description": "Qarsildoq tovuq filesi, aysberg salati, yangi pomidor va yengil mayonez",
        "image": "https://images.unsplash.com/photo-1625813506062-0aeb1d7a094b?auto=format&fit=crop&w=600&q=80",
        "badge": ""
    },
    {
        "category": "burgers",
        "name": "Barbecue Bacon Burger",
        "price": 46000,
        "description": "Mol go'shti kotleti, qarsildoq bekon, dudlangan BBQ sousi va qovurilgan piyoz",
        "image": "https://images.unsplash.com/photo-1553979459-d2229ba7433b?auto=format&fit=crop&w=600&q=80",
        "badge": "Yangi"
    },

    # Lavash & Shaurma
    {
        "category": "lavash",
        "name": "Mol go'shtli Lavash Standart",
        "price": 36000,
        "description": "Yumshoq xamir, mayin mol go'shti, pomidor, bodring, maxsus chipslar va tomat sousi",
        "image": "https://images.unsplash.com/photo-1626700051175-6818013e1d4f?auto=format&fit=crop&w=600&q=80",
        "badge": "🔥 Hit"
    },
    {
        "category": "lavash",
        "name": "Pishloqli Tovuq Lavash",
        "price": 38000,
        "description": "Tandirda pishgan tovuq go'shti, erigan motsarella pishlog'i, yashil ko'katlar va sous",
        "image": "https://images.unsplash.com/photo-1561651823-34feb02250e4?auto=format&fit=crop&w=600&q=80",
        "badge": ""
    },
    {
        "category": "lavash",
        "name": "Shaurma Mini (Doner)",
        "price": 28000,
        "description": "Pita nonida mol go'shti doneri, yangi sabzavotlar va sarimsoqli sous",
        "image": "https://images.unsplash.com/photo-1529006557810-274b9b2fc783?auto=format&fit=crop&w=600&q=80",
        "badge": ""
    },

    # Pizzalar
    {
        "category": "pizza",
        "name": "Pizza Pepperoni Maxi",
        "price": 68000,
        "description": "Italyancha ingichka xamir, ko'p miqdorda pepperoni kolbasasi va motsarella pishlog'i",
        "image": "https://images.unsplash.com/photo-1628840042765-356cda07504e?auto=format&fit=crop&w=600&q=80",
        "badge": "🔥 Hit"
    },
    {
        "category": "pizza",
        "name": "Pizza 4 Pishloq (Quattro Formaggi)",
        "price": 72000,
        "description": "Motsarella, gorgonzola, parmezan va cheddar pishloqlarining ajoyib uyg'unligi",
        "image": "https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=600&q=80",
        "badge": ""
    },
    {
        "category": "pizza",
        "name": "Pizza Kombi Go'shtli",
        "price": 75000,
        "description": "Mol go'shti, tovuq filesi, ovchi kolbasalari, shirin bulg'or qalampiri va zaytun",
        "image": "https://images.unsplash.com/photo-1574071318508-1cdbab80d002?auto=format&fit=crop&w=600&q=80",
        "badge": "To'yimli"
    },

    # Gazaklar
    {
        "category": "snacks",
        "name": "Oltin Kartoshka Fri",
        "price": 16000,
        "description": "Tashqarisi qarsildoq, ichi mayin oltin rangli kartoshka fri",
        "image": "https://images.unsplash.com/photo-1576107232684-1279f3908594?auto=format&fit=crop&w=600&q=80",
        "badge": "Mashhur"
    },
    {
        "category": "snacks",
        "name": "Tovuq Qanotchalari BBQ (6 dona)",
        "price": 32000,
        "description": "Maxsus marinadlangan va qizartirib pishirilgan tovuq qanotchalari",
        "image": "https://images.unsplash.com/photo-1567620832903-9fc6debc209f?auto=format&fit=crop&w=600&q=80",
        "badge": "Achchiq"
    },
    {
        "category": "snacks",
        "name": "Pishloqli Naggets (8 dona)",
        "price": 26000,
        "description": "Motsarella pishlog'i bilan to'ldirilgan nozik tovuq naggetslari",
        "image": "https://images.unsplash.com/photo-1562967914-608f82629710?auto=format&fit=crop&w=600&q=80",
        "badge": ""
    },

    # Ichimliklar
    {
        "category": "drinks",
        "name": "Coca-Cola Original 0.5L",
        "price": 9000,
        "description": "Muzdek salqin va tetiklashtiruvchi klassik ichimlik",
        "image": "https://images.unsplash.com/photo-1622483767028-3f66f32aef97?auto=format&fit=crop&w=600&q=80",
        "badge": ""
    },
    {
        "category": "drinks",
        "name": "Yalpizli Yangi Mojito 0.4L",
        "price": 18000,
        "description": "Laym, yangi yalpiz barglari va yaxna muzli limonad",
        "image": "https://images.unsplash.com/photo-1551024709-8f23befc6f87?auto=format&fit=crop&w=600&q=80",
        "badge": "Yozgi"
    },
    {
        "category": "drinks",
        "name": "Fanta Orange 0.5L",
        "price": 9000,
        "description": "Yorqin apelsin ta'mli tetiklantiruvchi gazlangan ichimlik",
        "image": "https://images.unsplash.com/photo-1624517452488-04869289c4ca?auto=format&fit=crop&w=600&q=80",
        "badge": ""
    }
]


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

        # Mahsulotlar jadvali (image, category, badge ustunlari bilan)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT DEFAULT 'burgers',
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                description TEXT,
                image TEXT,
                badge TEXT DEFAULT '',
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
                delivery_type TEXT NOT NULL,
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
                status TEXT DEFAULT 'new',
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

        # Standart filiallar
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

        # Mahsulotlarni rasmlari bilan kiritish / yangilash
        async with db.execute("SELECT COUNT(*) FROM products") as cursor:
            prod_count = (await cursor.fetchone())[0]
            if prod_count < 10:
                # Eski yoki bo'sh jadvallarni yangi rasmli ro'yxat bilan boyitamiz
                await db.execute("DELETE FROM products;")
                for p in INITIAL_PRODUCTS:
                    await db.execute("""
                        INSERT INTO products (category, name, price, description, image, badge, is_available)
                        VALUES (?, ?, ?, ?, ?, ?, 1)
                    """, (p["category"], p["name"], p["price"], p["description"], p["image"], p.get("badge", "")))
                await db.commit()

        # Standart promokodlar
        async with db.execute("SELECT COUNT(*) FROM promos") as cursor:
            promo_count = (await cursor.fetchone())[0]
            if promo_count == 0:
                await db.execute("""
                    INSERT INTO promos (code, discount_percent, min_order_amount, usage_limit, is_active)
                    VALUES 
                    ('FAST10', 10, 30000, 100, 1),
                    ('MAZZALI20', 20, 50000, 50, 1)
                """)
                await db.commit()

    logger.info("Database initialized with rich products successfully.")


# ---------------- Foydalanuvchilar bilan ishlash ----------------

async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def save_or_update_user(user_id: int, full_name: str = None, phone: str = None, language_code: str = None):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)) as cursor:
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


# ---------------- Mahsulotlar ro'yxatini olish ----------------

async def get_all_products() -> List[Dict[str, Any]]:
    """Barcha mavjud mahsulotlarni kategoriyasi bo'yicha oladi."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM products WHERE is_available = 1 ORDER BY id ASC") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


# ---------------- Savat bilan ishlash ----------------

async def get_cart_items(user_id: int) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT c.product_id, p.name, p.price, p.image, c.quantity, (p.price * c.quantity) as total_price
            FROM cart c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = ?
        """
        async with db.execute(query, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def clear_cart(user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        await db.commit()


async def add_to_cart(user_id: int, product_id: int, quantity: int = 1):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            INSERT INTO cart (user_id, product_id, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, product_id) DO UPDATE SET quantity = quantity + excluded.quantity
        """, (user_id, product_id, quantity))
        await db.commit()


async def set_cart_items(user_id: int, items: List[Dict[str, Any]]):
    """Web App dan kelgan butun savatni to'liq yangilaydi."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        for it in items:
            p_id = it.get("product_id") or it.get("id")
            qty = it.get("quantity") or it.get("count", 1)
            if p_id and qty > 0:
                await db.execute("""
                    INSERT INTO cart (user_id, product_id, quantity)
                    VALUES (?, ?, ?)
                """, (user_id, p_id, qty))
        await db.commit()


# ---------------- Promokod bilan ishlash ----------------

async def check_promo_code(code: str, order_amount: int) -> Tuple[bool, Optional[Dict[str, Any]], str]:
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
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE promos SET used_count = used_count + 1 WHERE id = ?", (promo_id,))
        await db.commit()


# ---------------- Filiallar ----------------

async def get_active_branches() -> List[Dict[str, Any]]:
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
                item.get("product_id") or item.get("id"),
                item.get("name", "Noma'lum mahsulot"),
                item.get("price", 0),
                item.get("quantity", 1),
                item.get("total_price", item.get("price", 0) * item.get("quantity", 1))
            ))

        await db.commit()
        return order_id
