"""
Dual-Engine Database Connection: PostgreSQL (asyncpg) + SQLite (aiosqlite)
Agar DATABASE_URL mavjud va unga ulanib bo'lsa PostgreSQL ishlatiladi,
aks holda avtomatik tarzda lokal SQLite (aiosqlite) rejimiga o'tadi.
"""
import os
import logging
from typing import Any, List, Optional, Tuple, Dict
from config import DATABASE_URL, DATABASE_PATH

logger = logging.getLogger(__name__)

IS_POSTGRES = False
pg_pool = None

async def init_connection():
    """Baza ulanishini ishga tushiradi."""
    global IS_POSTGRES, pg_pool
    if DATABASE_URL and (DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")):
        try:
            import asyncpg
            pg_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
            IS_POSTGRES = True
            logger.info("✅ PostgreSQL (asyncpg) bazasiga muvaffaqiyatli ulandi.")
            return
        except Exception as e:
            logger.warning(f"⚠️ PostgreSQL ulanishida xatolik: {e}. SQLite rejimiga o'tilmoqda.")
            IS_POSTGRES = False
            pg_pool = None
    else:
        IS_POSTGRES = False
        logger.info(f"ℹ️ SQLite (aiosqlite) bazasi ishlatilmoqda: {DATABASE_PATH}")

async def close_connection():
    """Baza ulanishini yopadi."""
    global pg_pool
    if pg_pool:
        await pg_pool.close()
        pg_pool = None

def _convert_query(query: str) -> str:
    """SQLite '?' parametrlarini PostgreSQL '$1, $2...' formatiga o'tkazadi."""
    if not IS_POSTGRES:
        return query
    parts = query.split("?")
    if len(parts) == 1:
        return query
    new_q = []
    for i, part in enumerate(parts[:-1]):
        new_q.append(part)
        new_q.append(f"${i+1}")
    new_q.append(parts[-1])
    return "".join(new_q)

async def execute(query: str, params: Tuple = ()) -> None:
    """INSERT, UPDATE, DELETE so'rovlarini bajarish."""
    if IS_POSTGRES and pg_pool:
        q = _convert_query(query)
        async with pg_pool.acquire() as conn:
            await conn.execute(q, *params)
    else:
        import aiosqlite
        async with aiosqlite.connect(DATABASE_PATH) as db:
            await db.execute(query, params)
            await db.commit()

async def execute_insert(query: str, params: Tuple = ()) -> int:
    """INSERT qilib yaratilgan oxirgi qator ID sini qaytaradi."""
    if IS_POSTGRES and pg_pool:
        q = _convert_query(query)
        # PostgreSQL da id ni qaytarish uchun RETURNING id qo'shamiz agar bo'lmasa
        if "RETURNING" not in q.upper():
            q = f"{q} RETURNING id"
        async with pg_pool.acquire() as conn:
            row = await conn.fetchrow(q, *params)
            return row["id"] if row else 0
    else:
        import aiosqlite
        async with aiosqlite.connect(DATABASE_PATH) as db:
            cursor = await db.execute(query, params)
            await db.commit()
            return cursor.lastrowid

async def fetch_one(query: str, params: Tuple = ()) -> Optional[Dict[str, Any]]:
    """Yagona qatorni dict formatida qaytaradi."""
    if IS_POSTGRES and pg_pool:
        q = _convert_query(query)
        async with pg_pool.acquire() as conn:
            row = await conn.fetchrow(q, *params)
            return dict(row) if row else None
    else:
        import aiosqlite
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

async def fetch_all(query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
    """Barcha qatorlarni dict ro'yxati formatida qaytaradi."""
    if IS_POSTGRES and pg_pool:
        q = _convert_query(query)
        async with pg_pool.acquire() as conn:
            rows = await conn.fetch(q, *params)
            return [dict(r) for r in rows]
    else:
        import aiosqlite
        async with aiosqlite.connect(DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]
