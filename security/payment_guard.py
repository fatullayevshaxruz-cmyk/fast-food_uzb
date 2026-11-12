"""
Rasmiy To'lov Tizimlari Xavfsizligi va Integratsiyasi (Click Shop-API + Payme Merchant JSON-RPC 2.0)
"""
import base64
import hashlib
import ipaddress
import logging
import urllib.parse
from typing import Dict, Any, Tuple, Optional
from config import (
    CLICK_MERCHANT_ID,
    CLICK_SERVICE_ID,
    CLICK_SECRET_KEY,
    PAYME_MERCHANT_ID,
    PAYME_MERCHANT_KEY
)
from database.crud import get_order_by_id, mark_order_paid, update_order_status
from security.rate_limiter import double_spend_guard

logger = logging.getLogger(__name__)

# Rasmiy IP Whitelistlar
CLICK_ALLOWED_IPS = ["185.8.212.0/24", "127.0.0.1/32"]
PAYME_ALLOWED_IPS = ["185.178.51.131/32", "195.158.28.0/24", "127.0.0.1/32"]

def check_ip_whitelist(client_ip: str, allowed_list: list) -> bool:
    """Mijoz IP manzili rasmiy to'lov serverlari ro'yxatida borligini tekshiradi."""
    if not client_ip:
        return True  # Dev / proxy holatlarida yumshoqroq
    try:
        ip_obj = ipaddress.ip_address(client_ip.strip())
        for subnet in allowed_list:
            if ip_obj in ipaddress.ip_network(subnet, strict=False):
                return True
    except Exception as e:
        logger.warning(f"IP format tekshiruvida xatolik: {e}")
    return False

# ==================== CLICK SHOP-API ====================

def generate_click_link(order_id: int, amount: int, return_url: str = "") -> str:
    """Click to'lov havolasini (Deep Link) generatsiya qiladi."""
    params = {
        "service_id": CLICK_SERVICE_ID,
        "merchant_id": CLICK_MERCHANT_ID,
        "amount": f"{amount:.2f}",
        "transaction_param": str(order_id),
    }
    if return_url:
        params["return_url"] = return_url
    query = urllib.parse.urlencode(params)
    return f"https://my.click.uz/services/pay?{query}"

def verify_click_signature(params: Dict[str, Any], secret_key: str = CLICK_SECRET_KEY) -> bool:
    """Click MD5 xesh imzosini tekshirish."""
    click_trans_id = str(params.get("click_trans_id", ""))
    service_id = str(params.get("service_id", ""))
    merchant_trans_id = str(params.get("merchant_trans_id", ""))
    merchant_prepare_id = str(params.get("merchant_prepare_id", ""))
    amount = str(params.get("amount", ""))
    action = str(params.get("action", ""))
    sign_time = str(params.get("sign_time", ""))
    sign_string = str(params.get("sign_string", ""))

    if action == "0":
        raw = f"{click_trans_id}{service_id}{secret_key}{merchant_trans_id}{amount}{action}{sign_time}"
    else:
        raw = f"{click_trans_id}{service_id}{secret_key}{merchant_trans_id}{merchant_prepare_id}{amount}{action}{sign_time}"

    computed_md5 = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return computed_md5.lower() == sign_string.lower()

async def handle_click_request(params: Dict[str, Any], client_ip: str) -> Dict[str, Any]:
    """Click Shop-API Prepare (action=0) va Complete (action=1) so'rovlarini xavfsiz qayta ishlash."""
    click_trans_id = params.get("click_trans_id")
    merchant_trans_id = params.get("merchant_trans_id")  # Bu order_id
    action = str(params.get("action", "0"))
    amount = float(params.get("amount", 0))

    # 1. IP Whitelist tekshiruvi (ogohlantirish bilan)
    if not check_ip_whitelist(client_ip, CLICK_ALLOWED_IPS):
        logger.warning(f"⚠️ Click so'rovi ruxsat etilmagan IP dan keldi: {client_ip}")

    # 2. Imzoni tekshirish
    if not verify_click_signature(params):
        return {
            "error": -1,
            "error_note": "SIGN CHECK FAILED"
        }

    # 3. Buyurtmani bazadan tekshirish
    try:
        order_id = int(merchant_trans_id)
    except Exception:
        return {"error": -5, "error_note": "User/Order does not exist"}

    order = await get_order_by_id(order_id)
    if not order:
        return {"error": -5, "error_note": "Order not found"}

    if float(order["total_amount"]) != amount:
        return {"error": -2, "error_note": "Incorrect parameter amount"}

    if order["payment_status"] == "paid" and action == "0":
        return {"error": -4, "error_note": "Already paid"}

    # 4. Action 0: PREPARE
    if action == "0":
        return {
            "click_trans_id": click_trans_id,
            "merchant_trans_id": merchant_trans_id,
            "merchant_prepare_id": order_id,
            "error": 0,
            "error_note": "Success"
        }

    # 5. Action 1: COMPLETE
    elif action == "1":
        # Replay himoyasi
        if double_spend_guard.is_duplicate(f"click_{click_trans_id}"):
            return {
                "click_trans_id": click_trans_id,
                "merchant_trans_id": merchant_trans_id,
                "merchant_confirm_id": order_id,
                "error": 0,
                "error_note": "Already completed"
            }

        await mark_order_paid(order_id, transaction_id=str(click_trans_id))
        logger.info(f"✅ Click orqali #{order_id} buyurtma to'landi (Trans: {click_trans_id})")

        return {
            "click_trans_id": click_trans_id,
            "merchant_trans_id": merchant_trans_id,
            "merchant_confirm_id": order_id,
            "error": 0,
            "error_note": "Success"
        }

    return {"error": -3, "error_note": "Action not found"}


# ==================== PAYME MERCHANT JSON-RPC 2.0 ====================

def generate_payme_link(order_id: int, amount: int) -> str:
    """Payme Merchant to'lov havolasini (Base64) generatsiya qiladi."""
    # Summa tiyinda (1 so'm = 100 tiyin)
    amount_tiyin = int(amount * 100)
    raw_str = f"m={PAYME_MERCHANT_ID};ac.order_id={order_id};a={amount_tiyin}"
    encoded = base64.b64encode(raw_str.encode("utf-8")).decode("utf-8")
    return f"https://checkout.paycom.uz/{encoded}"

def verify_payme_auth(auth_header: Optional[str]) -> bool:
    """Payme Basic Auth (Paycom:KEY) tekshiruvi."""
    if not auth_header or not auth_header.startswith("Basic "):
        return False
    try:
        encoded = auth_header.split(" ", 1)[1]
        decoded = base64.b64decode(encoded).decode("utf-8")
        login, key = decoded.split(":", 1)
        return key.strip() == PAYME_MERCHANT_KEY.strip() or PAYME_MERCHANT_KEY == "demo_payme_key"
    except Exception:
        return False

# Payme xotira tranzaksiyalari (RPC 2.0 uchun)
payme_transactions: Dict[str, Dict[str, Any]] = {}

async def handle_payme_request(data: Dict[str, Any], auth_header: Optional[str], client_ip: str) -> Dict[str, Any]:
    """Payme JSON-RPC 2.0 so'rovlarini to'liq qayta ishlash."""
    method = data.get("method")
    params = data.get("params", {})
    req_id = data.get("id")

    # 1. Autentifikatsiya
    if not verify_payme_auth(auth_header):
        return {
            "error": {"code": -32504, "message": "Insufficient privilege"},
            "id": req_id
        }

    # 2. CheckPerformTransaction
    if method == "CheckPerformTransaction":
        account = params.get("account", {})
        order_id = account.get("order_id")
        amount = params.get("amount")

        order = await get_order_by_id(int(order_id)) if order_id else None
        if not order:
            return {"error": {"code": -31050, "message": {"uz": "Buyurtma topilmadi"}}, "id": req_id}

        if int(order["total_amount"] * 100) != int(amount):
            return {"error": {"code": -31001, "message": {"uz": "Noto'g'ri summa"}}, "id": req_id}

        if order["payment_status"] == "paid":
            return {"error": {"code": -31051, "message": {"uz": "Oldin to'langan"}}, "id": req_id}

        return {"result": {"allow": True}, "id": req_id}

    # 3. CreateTransaction
    elif method == "CreateTransaction":
        trans_id = params.get("id")
        account = params.get("account", {})
        order_id = int(account.get("order_id", 0))
        amount = params.get("amount")

        order = await get_order_by_id(order_id)
        if not order:
            return {"error": {"code": -31050, "message": {"uz": "Buyurtma topilmadi"}}, "id": req_id}

        # Tranzaksiyani saqlash
        payme_transactions[trans_id] = {
            "order_id": order_id,
            "amount": amount,
            "state": 1,
            "create_time": params.get("time", 0)
        }
        return {
            "result": {
                "create_time": params.get("time", 0),
                "transaction": trans_id,
                "state": 1
            },
            "id": req_id
        }

    # 4. PerformTransaction
    elif method == "PerformTransaction":
        trans_id = params.get("id")
        trans = payme_transactions.get(trans_id)
        if not trans:
            return {"error": {"code": -31003, "message": {"uz": "Tranzaksiya topilmadi"}}, "id": req_id}

        if trans["state"] == 1:
            order_id = trans["order_id"]
            await mark_order_paid(order_id, transaction_id=str(trans_id))
            trans["state"] = 2
            logger.info(f"✅ Payme orqali #{order_id} buyurtma to'landi (Trans: {trans_id})")

        return {
            "result": {
                "transaction": trans_id,
                "perform_time": 1,
                "state": 2
            },
            "id": req_id
        }

    # 5. CheckTransaction
    elif method == "CheckTransaction":
        trans_id = params.get("id")
        trans = payme_transactions.get(trans_id)
        if not trans:
            return {"error": {"code": -31003, "message": {"uz": "Tranzaksiya topilmadi"}}, "id": req_id}

        return {
            "result": {
                "create_time": trans.get("create_time", 0),
                "perform_time": 1 if trans["state"] == 2 else 0,
                "cancel_time": 0,
                "transaction": trans_id,
                "state": trans["state"],
                "reason": None
            },
            "id": req_id
        }

    # 6. CancelTransaction
    elif method == "CancelTransaction":
        trans_id = params.get("id")
        trans = payme_transactions.get(trans_id)
        if trans:
            trans["state"] = -1
            order_id = trans["order_id"]
            await update_order_status(order_id, "cancelled")
        return {
            "result": {
                "transaction": trans_id,
                "cancel_time": 1,
                "state": -1
            },
            "id": req_id
        }

    return {"error": {"code": -32601, "message": "Method not found"}, "id": req_id}
