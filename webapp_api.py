"""
Web App Mini App REST API & Payment Handlers (aiohttp)
To'liq Checkout REST API, Click Shop-API va Payme JSON-RPC 2.0 Webhooklari.
"""
import logging
from aiohttp import web
from config import MAX_DELIVERY_RADIUS_KM
from database.crud import (
    get_active_branches,
    check_promo_code,
    mark_promo_used,
    get_product_by_id,
    create_order,
    save_or_update_user,
    clear_cart,
    mark_order_paid,
    get_order_payment_status,
    get_user_orders,
    get_order_by_id
)
from utils.geo import (
    is_within_uzbekistan,
    find_nearest_branch,
    calculate_delivery_fee,
    reverse_geocode
)
from utils.notifications import notify_admins_new_order
from security.sanitization import sanitize_phone, sanitize_text
from security.payment_guard import (
    generate_click_link,
    generate_payme_link,
    handle_click_request,
    handle_payme_request
)

logger = logging.getLogger(__name__)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization"
}

def register_webapp_routes(app: web.Application, bot, static_dir):
    """Barcha WebApp API yo'nalishlarini ro'yxatga oladi."""

    async def options_handler(request):
        return web.Response(headers=CORS_HEADERS)

    # Statik sahifalar
    async def index_handler(request):
        return web.FileResponse(static_dir / "index.html")

    async def map_handler(request):
        return web.FileResponse(static_dir / "map.html")

    async def terms_handler(request):
        terms_html = """<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Ommaviy Oferta & Yetkazib Berish Shartlari</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 20px; line-height: 1.6; color: #222; background: #f9f9f9; }
    .card { background: #fff; padding: 24px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.06); max-width: 600px; margin: 0 auto; }
    h1 { font-size: 20px; color: #111; margin-bottom: 12px; }
    h2 { font-size: 16px; margin-top: 18px; color: #FF4B2B; }
    p, li { font-size: 14px; color: #444; }
    .back { display: inline-block; margin-top: 20px; padding: 10px 18px; background: #FF4B2B; color: #fff; text-decoration: none; border-radius: 8px; font-weight: 600; }
  </style>
</head>
<body>
  <div class="card">
    <h1>📜 Ommaviy Oferta va Xizmat Ko'rsatish Qoidalari</h1>
    <p>Ushbu hujjat FastFood Express xizmatidan foydalanish shartlari va qoidalarini belgilaydi.</p>
    
    <h2>1. Buyurtma va Yetkazib Berish</h2>
    <p>Buyurtmalar soat 09:00 dan 23:00 gacha qabul qilinadi. Yetkazib berish radiusi filiallardan 15 km gacha bo'lgan hududlarni qamrab oladi. O'rtacha yetkazish vaqti: 25-45 daqiqa.</p>

    <h2>2. To'lov Usullari</h2>
    <p>To'lovlar naqd pulda kuryerga yoki Click va Payme to'lov tizimlari orqali xavfsiz tarzda amalga oshiriladi.</p>

    <h2>3. Buyurtmani Bekor Qilish va Pulni Qaytarish (Refund Policy)</h2>
    <p>Mijoz buyurtma berilganidan keyin 60 soniya ichida uni bekor qilishi mumkin. Agar to'lov o'tkazilgan bo'lsa va taom hali tayyorlanmagan bo'lsa, to'lov 24 soat ichida to'liq qaytariladi.</p>

    <h2>4. Maxfiylik va Xavfsizlik</h2>
    <p>Foydalanuvchi ma'lumotlari (telefon raqami, manzili) faqat buyurtmani yetkazib berish maqsadida ishlatiladi va uchinchi shaxslarga berilmaydi.</p>
    
    <a href="/" class="back">← Menyuga qaytish</a>
  </div>
</body>
</html>"""
        return web.Response(text=terms_html, content_type="text/html")

    # API: Filiallar
    async def api_branches_handler(request):
        branches = await get_active_branches()
        return web.json_response({"ok": True, "branches": branches}, headers=CORS_HEADERS)

    # API: Promokodni tekshirish
    async def api_promo_handler(request):
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "Invalid JSON"}, headers=CORS_HEADERS)

        code = (data.get("code") or "").strip().upper()
        amount = int(data.get("amount") or 0)

        is_valid, promo_data, reason = await check_promo_code(code, amount)
        if not is_valid or not promo_data:
            return web.json_response({"ok": False, "error": reason}, headers=CORS_HEADERS)

        discount_percent = promo_data.get("discount_percent", 0)
        discount_amount = int((amount * discount_percent) / 100)
        return web.json_response({
            "ok": True,
            "code": code,
            "discount_percent": discount_percent,
            "discount_amount": discount_amount
        }, headers=CORS_HEADERS)

    # API: Geo / Yetkazish narxi
    async def api_calculate_delivery_handler(request):
        try:
            data = await request.json()
            lat = float(data.get("lat"))
            lon = float(data.get("lon"))
        except Exception:
            return web.json_response({"ok": False, "error": "Noto'g'ri koordinata"}, headers=CORS_HEADERS)

        if not is_within_uzbekistan(lat, lon):
            return web.json_response({"ok": False, "error": "Belgilangan nuqta O'zbekiston hududidan tashqarida!"}, headers=CORS_HEADERS)

        branches = await get_active_branches()
        nearest_branch, distance_km = find_nearest_branch(lat, lon, branches)

        if distance_km > MAX_DELIVERY_RADIUS_KM:
            return web.json_response({
                "ok": False,
                "error": f"Yetkazib berish zonasi cheklangan ({MAX_DELIVERY_RADIUS_KM:.0f} km). Siz {distance_km:.1f} km uzoqlikdasiz."
            }, headers=CORS_HEADERS)

        fee = calculate_delivery_fee(distance_km)
        address = await reverse_geocode(lat, lon)

        return web.json_response({
            "ok": True,
            "address": address,
            "distance_km": round(distance_km, 1),
            "delivery_fee": fee,
            "branch_id": nearest_branch.get("id"),
            "branch_name": nearest_branch.get("name")
        }, headers=CORS_HEADERS)

    # API: Buyurtma yaratish
    async def api_order_create_handler(request):
        try:
            data = await request.json()
        except Exception as e:
            return web.json_response({"ok": False, "error": f"Invalid JSON: {e}"}, headers=CORS_HEADERS)

        user_id = data.get("user_id") or (data.get("user") or {}).get("id")
        if not user_id:
            return web.json_response({"ok": False, "error": "Foydalanuvchi ma'lumotlari topilmadi!"}, headers=CORS_HEADERS)

        user_id = int(user_id)
        phone = sanitize_phone(data.get("phone") or "")
        if not phone:
            return web.json_response({"ok": False, "error": "Telefon raqamingizni kiriting (+998901234567)"}, headers=CORS_HEADERS)

        await save_or_update_user(user_id, phone=phone, full_name=(data.get("user") or {}).get("first_name", ""))

        raw_items = data.get("items", [])
        if not raw_items:
            return web.json_response({"ok": False, "error": "Savatingiz bo'sh!"}, headers=CORS_HEADERS)

        # Narxlar tekshiruvi (Anti-Tamper)
        verified_items = []
        items_total = 0
        for item in raw_items:
            p_id = item.get("id") or item.get("product_id")
            qty = max(1, int(item.get("quantity") or item.get("count", 1)))
            p_data = await get_product_by_id(p_id)
            if p_data and p_data.get("is_active", 1) == 1:
                real_price = p_data.get("discount_price") if p_data.get("discount_price") and p_data["discount_price"] > 0 else p_data["price"]
                item_sum = real_price * qty
                items_total += item_sum
                verified_items.append({
                    "product_id": p_id,
                    "name": p_data["name"],
                    "price": real_price,
                    "quantity": qty,
                    "total_price": item_sum
                })

        if not verified_items:
            return web.json_response({"ok": False, "error": "Tanlangan mahsulotlar mavjud emas!"}, headers=CORS_HEADERS)

        delivery_type = data.get("delivery_type", "delivery")
        lat = data.get("lat")
        lon = data.get("lon")
        table_number = sanitize_text(str(data.get("table_number") or ""))
        address = sanitize_text(data.get("address", ""))
        branch_id = data.get("branch_id")
        branch_name = data.get("branch_name")
        distance_km = data.get("distance_km")

        if delivery_type == "eat_in":
            delivery_fee = 0
            if not table_number:
                return web.json_response({"ok": False, "error": "Stol raqami kiritilmadi!"}, headers=CORS_HEADERS)
            address = f"Stol raqami: #{table_number}"
            branch_name = branch_name or "Restoran zali"
        else:
            if not lat or not lon:
                return web.json_response({"ok": False, "error": "Yetkazib berish manzili topilmadi!"}, headers=CORS_HEADERS)
            lat = float(lat)
            lon = float(lon)
            branches = await get_active_branches()
            nearest_branch, calc_dist = find_nearest_branch(lat, lon, branches)
            if calc_dist > MAX_DELIVERY_RADIUS_KM:
                return web.json_response({"ok": False, "error": "Manzil 15 km yetkazib berish zonasidan tashqarida!"}, headers=CORS_HEADERS)
            distance_km = calc_dist
            branch_id = nearest_branch.get("id")
            branch_name = nearest_branch.get("name")
            delivery_fee = calculate_delivery_fee(distance_km)
            if not address or len(address) < 3:
                address = await reverse_geocode(lat, lon)

        promo_code = data.get("promo_code")
        discount_amount = 0
        if promo_code:
            is_valid, p_dict, _ = await check_promo_code(promo_code, items_total)
            if is_valid and p_dict:
                discount_amount = int((items_total * p_dict["discount_percent"]) / 100)
                await mark_promo_used(p_dict["id"])

        final_total = max(0, items_total - discount_amount) + delivery_fee
        payment_method = data.get("payment_method", "cash")
        payment_status = "cash" if payment_method == "cash" else "unpaid"

        order_id = await create_order(
            user_id=user_id,
            total_amount=final_total,
            phone_number=phone,
            items=verified_items,
            delivery_type=delivery_type,
            delivery_address=address,
            latitude=lat if delivery_type == "delivery" else None,
            longitude=lon if delivery_type == "delivery" else None,
            payment_method=payment_method,
            payment_status=payment_status,
            branch_id=branch_id,
            promo_code=promo_code,
            discount_amount=discount_amount
        )

        await clear_cart(user_id)

        # NAQD PUL: Zudlik bilan filial/oshxona kanaliga chiqarish
        if payment_method == "cash":
            try:
                order_full_data = {
                    "delivery_type": delivery_type,
                    "table_number": table_number,
                    "branch_name": branch_name,
                    "address": address,
                    "distance_km": distance_km,
                    "lat": lat,
                    "lon": lon,
                    "phone": phone,
                    "full_name": (data.get("user") or {}).get("first_name", "Mijoz"),
                    "user_id": user_id,
                    "note": sanitize_text(data.get("note", "")),
                    "items_total": items_total,
                    "discount_amount": discount_amount,
                    "promo_code": promo_code,
                    "delivery_fee": delivery_fee,
                    "final_total": final_total,
                    "payment_method": "cash"
                }
                await notify_admins_new_order(bot, order_full_data, verified_items, order_id)
            except Exception as ex:
                logger.error(f"Error notifying channel for cash order #{order_id}: {ex}")

            try:
                await bot.send_message(
                    user_id,
                    f"✅ <b>Buyurtmangiz #{order_id} qabul qilindi!</b>\n"
                    f"To'lov turi: 💵 Naqd pul\n"
                    f"Jami summa: <b>{final_total:,} so'm</b>\n"
                    f"Operatorlarimiz tez orada siz bilan bog'lanishadi!",
                    parse_mode="HTML"
                )
            except Exception:
                pass

            return web.json_response({
                "ok": True,
                "order_id": order_id,
                "payment_status": "cash",
                "final_total": final_total
            }, headers=CORS_HEADERS)

        # CLICK / PAYME: To'lov havolasi beriladi, OSHXONA KANALIGA HOZIRCHA YUBORILMAYDI
        else:
            payment_url = ""
            if payment_method == "click":
                payment_url = generate_click_link(order_id, final_total)
            elif payment_method == "payme":
                payment_url = generate_payme_link(order_id, final_total)

            return web.json_response({
                "ok": True,
                "order_id": order_id,
                "payment_status": "unpaid",
                "payment_url": payment_url,
                "final_total": final_total
            }, headers=CORS_HEADERS)

    # API: To'lov holati polling (/api/order/payment-status)
    async def api_order_payment_status_handler(request):
        order_id_str = request.query.get("order_id")
        if not order_id_str or not order_id_str.isdigit():
            return web.json_response({"ok": False, "error": "order_id required"}, headers=CORS_HEADERS)

        order_id = int(order_id_str)
        status_info = await get_order_payment_status(order_id)
        if not status_info:
            return web.json_response({"ok": False, "error": "Order not found"}, headers=CORS_HEADERS)

        return web.json_response({
            "ok": True,
            "order_id": order_id,
            "payment_status": status_info.get("payment_status"),
            "status": status_info.get("status")
        }, headers=CORS_HEADERS)

    # API: Test simulyatsiyasi (/api/order/pay-simulate)
    async def api_pay_simulate_handler(request):
        try:
            data = await request.json()
            order_id = int(data.get("order_id"))
        except Exception:
            return web.json_response({"ok": False, "error": "Invalid order_id"}, headers=CORS_HEADERS)

        order = await get_order_by_id(order_id)
        if not order:
            return web.json_response({"ok": False, "error": "Order not found"}, headers=CORS_HEADERS)

        await mark_order_paid(order_id, transaction_id=f"SIM_{order_id}")

        # Qat'iy qoida: To'lov paid bo'ldi ➔ Endi oshxona kanaliga xabar uzatiladi!
        try:
            order_full_data = {
                "delivery_type": order.get("delivery_type"),
                "table_number": "",
                "branch_name": "Bosh filial",
                "address": order.get("delivery_address"),
                "distance_km": 0,
                "lat": order.get("latitude"),
                "lon": order.get("longitude"),
                "phone": order.get("phone_number"),
                "full_name": "Mijoz",
                "user_id": order.get("user_id"),
                "note": "",
                "items_total": order.get("total_amount"),
                "discount_amount": order.get("discount_amount", 0),
                "promo_code": order.get("promo_code"),
                "delivery_fee": 0,
                "final_total": order.get("total_amount"),
                "payment_method": order.get("payment_method")
            }
            await notify_admins_new_order(bot, order_full_data, order.get("items", []), order_id)
        except Exception as ex:
            logger.error(f"Simulate payment notify error: {ex}")

        try:
            await bot.send_message(
                order["user_id"],
                f"💳 <b>To'lovingiz muvaffaqiyatli qabul qilindi!</b>\n"
                f"Buyurtma #{order_id} oshxonaga topshirildi. Tez orada yetkazib beramiz! 🚀",
                parse_mode="HTML"
            )
        except Exception:
            pass

        return web.json_response({"ok": True, "order_id": order_id, "payment_status": "paid"}, headers=CORS_HEADERS)

    # API: Foydalanuvchi buyurtmalari (/api/user/orders)
    async def api_user_orders_handler(request):
        user_id_str = request.query.get("user_id")
        if not user_id_str or not user_id_str.isdigit():
            return web.json_response({"ok": False, "orders": []}, headers=CORS_HEADERS)
        orders = await get_user_orders(int(user_id_str), limit=15)
        return web.json_response({"ok": True, "orders": orders}, headers=CORS_HEADERS)

    # Webhook: Click Shop-API
    async def click_webhook_handler(request):
        client_ip = request.remote or ""
        try:
            if request.content_type == "application/json":
                data = await request.json()
            else:
                post_data = await request.post()
                data = dict(post_data)
        except Exception:
            data = {}
        resp = await handle_click_request(data, client_ip)
        
        # Agar to'lov muvaffaqiyatli yakunlansa, oshxonaga xabar
        if resp.get("error") == 0 and str(data.get("action")) == "1":
            try:
                order_id = int(data.get("merchant_trans_id", 0))
                order = await get_order_by_id(order_id)
                if order:
                    order_data = {
                        "delivery_type": order.get("delivery_type"),
                        "address": order.get("delivery_address"),
                        "phone": order.get("phone_number"),
                        "user_id": order.get("user_id"),
                        "final_total": order.get("total_amount"),
                        "payment_method": "click"
                    }
                    await notify_admins_new_order(bot, order_data, order.get("items", []), order_id)
            except Exception as e:
                logger.error(f"Click complete notify error: {e}")

        return web.json_response(resp)

    # Webhook: Payme JSON-RPC 2.0
    async def payme_webhook_handler(request):
        client_ip = request.remote or ""
        auth_header = request.headers.get("Authorization")
        try:
            data = await request.json()
        except Exception:
            data = {}
        resp = await handle_payme_request(data, auth_header, client_ip)
        
        # Agar PerformTransaction muvaffaqiyatli bo'lsa, oshxonaga xabar
        if data.get("method") == "PerformTransaction" and "result" in resp:
            try:
                trans_id = (data.get("params") or {}).get("id")
                # Xotiradagi tranzaksiyadan order_id ni olish
                from security.payment_guard import payme_transactions
                t_info = payme_transactions.get(trans_id)
                if t_info:
                    order_id = t_info["order_id"]
                    order = await get_order_by_id(order_id)
                    if order:
                        order_data = {
                            "delivery_type": order.get("delivery_type"),
                            "address": order.get("delivery_address"),
                            "phone": order.get("phone_number"),
                            "user_id": order.get("user_id"),
                            "final_total": order.get("total_amount"),
                            "payment_method": "payme"
                        }
                        await notify_admins_new_order(bot, order_data, order.get("items", []), order_id)
            except Exception as e:
                logger.error(f"Payme perform notify error: {e}")

        return web.json_response(resp)

    # Marshrutlarni ulash
    app.router.add_get("/", index_handler)
    app.router.add_get("/terms", terms_handler)
    app.router.add_get("/map.html", map_handler)
    app.router.add_options("/{tail:.*}", options_handler)

    app.router.add_get("/api/branches", api_branches_handler)
    app.router.add_post("/api/promo", api_promo_handler)
    app.router.add_post("/api/order/calculate", api_calculate_delivery_handler)
    app.router.add_post("/api/order/create", api_order_create_handler)
    app.router.add_get("/api/order/payment-status", api_order_payment_status_handler)
    app.router.add_post("/api/order/pay-simulate", api_pay_simulate_handler)
    app.router.add_get("/api/user/orders", api_user_orders_handler)

    # To'lov webhooklari
    app.router.add_post("/payment/click", click_webhook_handler)
    app.router.add_post("/payment/payme", payme_webhook_handler)

