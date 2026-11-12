"""
Telegram WebApp HMAC-SHA256 Signature Verification
Rasmiy Telegram Mini App initData xavfsizlik tekshiruvi.
"""
import hmac
import hashlib
import json
import urllib.parse
from typing import Dict, Any, Tuple, Optional
from config import BOT_TOKEN

def validate_init_data(init_data: str, bot_token: str = BOT_TOKEN) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Telegram WebApp initData xeshini tekshiradi va foydalanuvchi ma'lumotlarini qaytaradi.
    Agar init_data bo'sh bo'lsa yoki dev/test rejimida bo'lsa xavfsiz boshqarish imkoniyati mavjud.
    """
    if not init_data:
        return False, None

    try:
        parsed_params = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        if "hash" not in parsed_params:
            return False, None

        received_hash = parsed_params.pop("hash")
        
        # Alfavit tartibida kalitlarni saralash va \n bilan ulash
        data_check_items = [f"{k}={v}" for k, v in sorted(parsed_params.items())]
        data_check_string = "\n".join(data_check_items)

        # secret_key = HMAC_SHA256("WebAppData", bot_token)
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        
        # calculated_hash = HMAC_SHA256(secret_key, data_check_string)
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if calculated_hash.lower() == received_hash.lower():
            user_data = None
            if "user" in parsed_params:
                try:
                    user_data = json.loads(parsed_params["user"])
                except Exception:
                    user_data = {"raw": parsed_params["user"]}
            return True, user_data
        
        return False, None
    except Exception as e:
        return False, None
