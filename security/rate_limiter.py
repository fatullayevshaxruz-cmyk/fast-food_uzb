"""
Anti-Flood, Rate Limiting & Replay Protection
"""
import time
from typing import Dict, Any
from aiogram import types
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.dispatcher.handler import CancelHandler

class AntiFloodMiddleware(BaseMiddleware):
    """
    Aiogram uchun Anti-Flood Middleware.
    Foydalanuvchilarning tez-tez tugma bosishini va spam jo'natishini cheklaydi (0.5s limit).
    """
    def __init__(self, limit: float = 0.5):
        super(AntiFloodMiddleware, self).__init__()
        self.limit = limit
        self.last_time: Dict[int, float] = {}

    async def on_process_message(self, message: types.Message, data: dict):
        user_id = message.from_user.id
        now = time.time()
        last = self.last_time.get(user_id, 0)
        
        if now - last < self.limit:
            # Spam aniqlandi - so'rov rad etiladi
            raise CancelHandler()
        
        self.last_time[user_id] = now

    async def on_process_callback_query(self, call: types.CallbackQuery, data: dict):
        user_id = call.from_user.id
        now = time.time()
        last = self.last_time.get(user_id, 0)
        
        if now - last < 0.3:  # Callbacklar uchun 0.3s
            try:
                await call.answer("Iltimos, shoshilmang...", show_alert=False)
            except Exception:
                pass
            raise CancelHandler()
            
        self.last_time[user_id] = now


class DoubleSpendGuard:
    """
    Replay & Double-Spend Protection:
    Bitta tranzaksiya yoki bir xil buyurtmani 15 soniya ichida qayta yuborishning oldini oladi.
    """
    def __init__(self, ttl_seconds: int = 15):
        self.ttl = ttl_seconds
        self.cache: Dict[str, float] = {}

    def is_duplicate(self, key: str) -> bool:
        now = time.time()
        self._cleanup(now)
        
        if key in self.cache:
            return True
        
        self.cache[key] = now
        return False

    def _cleanup(self, now: float):
        keys_to_remove = [k for k, timestamp in self.cache.items() if now - timestamp > self.ttl]
        for k in keys_to_remove:
            self.cache.pop(k, None)

double_spend_guard = DoubleSpendGuard(ttl_seconds=15)
