"""
Database Models & Schemas (PostgreSQL & SQLite)
"""
from database.connection import IS_POSTGRES, execute

SQLITE_TABLES = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    phone_number TEXT,
    language TEXT DEFAULT 'uz',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_uz TEXT NOT NULL,
    name_ru TEXT,
    name_en TEXT,
    is_active INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER,
    name TEXT NOT NULL,
    name_ru TEXT,
    name_en TEXT,
    price INTEGER NOT NULL,
    description TEXT,
    image_url TEXT,
    is_active INTEGER DEFAULT 1,
    discount_price INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS branches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    admin_chat_id INTEGER NOT NULL,
    max_delivery_km REAL DEFAULT 15.0,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    total_amount INTEGER NOT NULL,
    delivery_address TEXT,
    latitude REAL,
    longitude REAL,
    phone_number TEXT,
    payment_method TEXT DEFAULT 'cash',
    payment_status TEXT DEFAULT 'unpaid',
    transaction_id TEXT,
    delivery_type TEXT DEFAULT 'delivery',
    status TEXT DEFAULT 'pending',
    branch_id INTEGER,
    promo_code TEXT,
    discount_amount INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    price_at_time INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS cart_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    UNIQUE(user_id, product_id)
);

CREATE TABLE IF NOT EXISTS promo_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    discount_percent INTEGER NOT NULL,
    max_uses INTEGER DEFAULT 100,
    used_count INTEGER DEFAULT 0,
    min_order_amount INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS order_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    rating INTEGER NOT NULL,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

POSTGRES_TABLES = """
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    full_name VARCHAR(255),
    phone_number VARCHAR(64),
    language VARCHAR(10) DEFAULT 'uz',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name_uz VARCHAR(255) NOT NULL,
    name_ru VARCHAR(255),
    name_en VARCHAR(255),
    is_active INT DEFAULT 1,
    sort_order INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    category_id INT,
    name VARCHAR(255) NOT NULL,
    name_ru VARCHAR(255),
    name_en VARCHAR(255),
    price INT NOT NULL,
    description TEXT,
    image_url TEXT,
    is_active INT DEFAULT 1,
    discount_price INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS branches (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    admin_chat_id BIGINT NOT NULL,
    max_delivery_km DOUBLE PRECISION DEFAULT 15.0,
    is_active INT DEFAULT 1
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    total_amount INT NOT NULL,
    delivery_address TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    phone_number VARCHAR(64),
    payment_method VARCHAR(32) DEFAULT 'cash',
    payment_status VARCHAR(32) DEFAULT 'unpaid',
    transaction_id VARCHAR(128),
    delivery_type VARCHAR(32) DEFAULT 'delivery',
    status VARCHAR(32) DEFAULT 'pending',
    branch_id INT,
    promo_code VARCHAR(64),
    discount_amount INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    price_at_time INT NOT NULL
);

CREATE TABLE IF NOT EXISTS cart_items (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    UNIQUE(user_id, product_id)
);

CREATE TABLE IF NOT EXISTS promo_codes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(64) UNIQUE NOT NULL,
    discount_percent INT NOT NULL,
    max_uses INT DEFAULT 100,
    used_count INT DEFAULT 0,
    min_order_amount INT DEFAULT 0,
    is_active INT DEFAULT 1
);

CREATE TABLE IF NOT EXISTS order_ratings (
    id SERIAL PRIMARY KEY,
    order_id INT NOT NULL,
    user_id BIGINT NOT NULL,
    rating INT NOT NULL,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

async def init_models():
    """Jadvallarni bazada yaratish yoki migratsiya qilish."""
    statements = POSTGRES_TABLES if IS_POSTGRES else SQLITE_TABLES
    for stmt in statements.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            await execute(stmt)

    if not IS_POSTGRES:
        try:
            from database.connection import fetch_all
            prod_cols = [c["name"] for c in await fetch_all("PRAGMA table_info(products)")]
            if prod_cols and "category_id" not in prod_cols:
                await execute("ALTER TABLE products ADD COLUMN category_id INTEGER DEFAULT 1")
            if prod_cols and "discount_price" not in prod_cols:
                await execute("ALTER TABLE products ADD COLUMN discount_price INTEGER DEFAULT 0")
            if prod_cols and "image_url" not in prod_cols:
                await execute("ALTER TABLE products ADD COLUMN image_url TEXT")
                await execute("UPDATE products SET image_url = image WHERE image_url IS NULL")
            if prod_cols and "is_active" not in prod_cols:
                await execute("ALTER TABLE products ADD COLUMN is_active INTEGER DEFAULT 1")
                if "is_available" in prod_cols:
                    await execute("UPDATE products SET is_active = is_available")
            if prod_cols and "name_ru" not in prod_cols:
                await execute("ALTER TABLE products ADD COLUMN name_ru TEXT")
            if prod_cols and "name_en" not in prod_cols:
                await execute("ALTER TABLE products ADD COLUMN name_en TEXT")

            order_cols = [c["name"] for c in await fetch_all("PRAGMA table_info(orders)")]
            if order_cols and "total_amount" not in order_cols:
                await execute("ALTER TABLE orders ADD COLUMN total_amount INTEGER DEFAULT 0")
                if "final_total" in order_cols:
                    await execute("UPDATE orders SET total_amount = final_total")
            if order_cols and "delivery_address" not in order_cols:
                await execute("ALTER TABLE orders ADD COLUMN delivery_address TEXT")
                if "address" in order_cols:
                    await execute("UPDATE orders SET delivery_address = address")
            if order_cols and "phone_number" not in order_cols:
                await execute("ALTER TABLE orders ADD COLUMN phone_number TEXT")
                if "phone" in order_cols:
                    await execute("UPDATE orders SET phone_number = phone")
            if order_cols and "latitude" not in order_cols:
                await execute("ALTER TABLE orders ADD COLUMN latitude REAL")
                if "lat" in order_cols:
                    await execute("UPDATE orders SET latitude = lat")
            if order_cols and "longitude" not in order_cols:
                await execute("ALTER TABLE orders ADD COLUMN longitude REAL")
                if "lon" in order_cols:
                    await execute("UPDATE orders SET longitude = lon")
            if order_cols and "transaction_id" not in order_cols:
                await execute("ALTER TABLE orders ADD COLUMN transaction_id TEXT")
        except Exception:
            pass
