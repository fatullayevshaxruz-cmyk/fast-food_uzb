"""
Ko'p tillilik (Internationalization - i18n) tizimi.
O'zbek, Rus va Ingliz tillarini to'liq qo'llab-quvvatlaydi.
"""

MESSAGES = {
    # Savat va ish vaqti
    "cart_empty": {
        "uz": "🛒 Savatingiz bo'sh! Iltimos, avval mahsulot tanlang.",
        "ru": "🛒 Ваша корзина пуста! Пожалуйста, сначала выберите товары.",
        "en": "🛒 Your cart is empty! Please select items first."
    },
    "closed_alert": {
        "uz": "⚠️ Hozir bizning ish vaqtimiz emas!\nIsh vaqti: {start}:00 dan {end}:00 gacha (Toshkent vaqti).",
        "ru": "⚠️ В данный момент мы закрыты!\nЧасы работы: с {start}:00 до {end}:00 (по Ташкенту).",
        "en": "⚠️ We are currently closed!\nWorking hours: from {start}:00 to {end}:00 (Tashkent time)."
    },
    "min_order_error": {
        "uz": "⚠️ Yetkazib berish uchun minimal buyurtma summasi: {min_amount:,} so'm.\n"
              "Sizning savatingiz: {current_amount:,} so'm.\n"
              "Yetkazib berishni davom ettirish uchun yana {diff:,} so'mlik mahsulot qo'shing.",
        "ru": "⚠️ Минимальная сумма заказа для доставки: {min_amount:,} сум.\n"
              "В вашей корзине: {current_amount:,} сум.\n"
              "Пожалуйста, добавьте товаров ещё на {diff:,} сум.",
        "en": "⚠️ Minimum order amount for delivery: {min_amount:,} UZS.\n"
              "Your current cart: {current_amount:,} UZS.\n"
              "Please add {diff:,} UZS more to proceed with delivery."
    },

    # Yetkazish turi
    "choose_delivery_type": {
        "uz": "🚚 Buyurtmani qanday qabul qilishni xohlaysiz?",
        "ru": "🚚 Как вы хотите получить заказ?",
        "en": "🚚 How would you like to receive your order?"
    },
    "btn_eat_in": {
        "uz": "🍽 Shu yerda (Restoranda)",
        "ru": "🍽 В заведении",
        "en": "🍽 Dine-in"
    },
    "btn_delivery": {
        "uz": "🛵 Yetkazib berish",
        "ru": "🛵 Доставка",
        "en": "🛵 Delivery"
    },
    "btn_cancel": {
        "uz": "❌ Bekor qilish",
        "ru": "❌ Отмена",
        "en": "❌ Cancel"
    },
    "btn_skip": {
        "uz": "➡️ O'tkazib yuborish",
        "ru": "➡️ Пропустить",
        "en": "➡️ Skip"
    },

    # Stol raqami
    "ask_table_number": {
        "uz": "🍽 Iltimos, o'tirgan stolingiz raqamini kiriting (masalan: 5):",
        "ru": "🍽 Пожалуйста, введите номер вашего стола (например: 5):",
        "en": "🍽 Please enter your table number (e.g. 5):"
    },
    "invalid_table_number": {
        "uz": "⚠️ Noto'g'ri stol raqami! Iltimos, faqat musbat butun son kiriting (masalan: 1, 2, 12).",
        "ru": "⚠️ Неверный номер стола! Пожалуйста, введите положительное целое число (например: 1, 2, 12).",
        "en": "⚠️ Invalid table number! Please enter a positive integer (e.g. 1, 2, 12)."
    },

    # Lokatsiya
    "ask_location": {
        "uz": "📍 Yetkazib berish manzilini yuboring.\n\n"
              "Quyidagi tugma orqali GPS joylashuvingizni yuborishingiz yoki xaritadan tanlashingiz mumkin:",
        "ru": "📍 Отправьте адрес доставки.\n\n"
              "Вы можете отправить свое местоположение по GPS или выбрать на карте:",
        "en": "📍 Please send your delivery location.\n\n"
              "You can share your GPS location using the button below or choose on map:"
    },
    "btn_send_location": {
        "uz": "📍 Joylashuvni jo'natish (GPS)",
        "ru": "📍 Отправить локацию (GPS)",
        "en": "📍 Send Location (GPS)"
    },
    "btn_open_map": {
        "uz": "🗺 Xaritadan tanlash",
        "ru": "🗺 Выбрать на карте",
        "en": "🗺 Choose on Map"
    },
    "location_out_of_uzb": {
        "uz": "⚠️ Kechirasiz, siz yuborgan manzil O'zbekiston hududidan tashqarida joylashgan!\n"
              "Iltimos, O'zbekiston hududidagi to'g'ri koordinatani yuboring.",
        "ru": "⚠️ Извините, указанное местоположение находится за пределами Узбекистана!\n"
              "Пожалуйста, отправьте корректные координаты в Узбекистане.",
        "en": "⚠️ Sorry, the specified location is outside of Uzbekistan!\n"
              "Please provide a valid location within Uzbekistan."
    },
    "location_too_far": {
        "uz": "⚠️ Kechirasiz, siz belgilagan manzil eng yaqin filialimizdan ({branch}) {distance:.1f} km uzoqlikda.\n"
              "Yetkazib berish xizmati maksimal {max_radius:.0f} km masofagacha amal qiladi.",
        "ru": "⚠️ К сожалению, ваше местоположение находится в {distance:.1f} км от ближайшего филиала ({branch}).\n"
              "Зона доставки ограничена {max_radius:.0f} км.",
        "en": "⚠️ Sorry, your location is {distance:.1f} km away from our nearest branch ({branch}).\n"
              "Our maximum delivery radius is {max_radius:.0f} km."
    },
    "location_confirmed": {
        "uz": "✅ Manzil qabul qilindi:\n📍 {address}\n🏢 Eng yaqin filial: {branch} ({distance:.1f} km)",
        "ru": "✅ Адрес принят:\n📍 {address}\n🏢 Ближайший филиал: {branch} ({distance:.1f} км)",
        "en": "✅ Address confirmed:\n📍 {address}\n🏢 Nearest branch: {branch} ({distance:.1f} km)"
    },

    # Telefon
    "ask_phone": {
        "uz": "📞 Iltimos, bog'lanish uchun telefon raqamingizni yuboring yoki yozing (+998901234567):",
        "ru": "📞 Пожалуйста, отправьте или введите ваш номер телефона (+998901234567):",
        "en": "📞 Please send or type your contact phone number (+998901234567):"
    },
    "btn_send_phone": {
        "uz": "📞 Telefon raqamni yuborish",
        "ru": "📞 Отправить номер телефона",
        "en": "📞 Send Phone Number"
    },
    "invalid_phone": {
        "uz": "⚠️ Telefon raqam noto'g'ri formatda!\n"
              "Iltimos, namunadagidek kiriting: +998901234567 yoki pastdagi tugmani bosing.",
        "ru": "⚠️ Неверный формат номера!\n"
              "Пожалуйста, введите как в примере: +998901234567 или воспользуйтесь кнопкой.",
        "en": "⚠️ Invalid phone format!\n"
              "Please enter like: +998901234567 or use the button below."
    },

    # Izoh
    "ask_note": {
        "uz": "📝 Buyurtmaga biror izoh yoki qo'shimcha istaklaringiz bormi?\n"
              "(Masalan: \"Piyozsiz bo'lsin\", \"Eshik kodi: 123\")\n"
              "Agar bo'lmasa, «O'tkazib yuborish» tugmasini bosing.",
        "ru": "📝 Есть ли пожелания к заказу?\n"
              "(Например: \"Без лука\", \"Код домофона: 123\")\n"
              "Если пожеланий нет, нажмите «Пропустить».",
        "en": "📝 Any special requests or notes for the order?\n"
              "(e.g. \"No onions\", \"Door code: 123\")\n"
              "If none, click «Skip»."
    },

    # Promokod
    "ask_promo": {
        "uz": "🎟 Sizda promokod bormi?\n"
              "Promokodni kiriting yoki «O'tkazib yuborish» tugmasini bosing.",
        "ru": "🎟 У вас есть промокод?\n"
              "Введите промокод или нажмите «Пропустить».",
        "en": "🎟 Do you have a promo code?\n"
              "Enter the promo code or click «Skip»."
    },
    "promo_success": {
        "uz": "🎉 Promokod qabul qilindi! Chegirma: {discount_percent}%\nTejalgan summa: {saved_amount:,} so'm.",
        "ru": "🎉 Промокод применен! Скидка: {discount_percent}%\nСэкономлено: {saved_amount:,} сум.",
        "en": "🎉 Promo code applied! Discount: {discount_percent}%\nYou saved: {saved_amount:,} UZS."
    },
    "promo_invalid": {
        "uz": "⚠️ Promokod noto'g'ri, muddati o'tgan yoki limit tugagan!\n"
              "Qaytadan urinib ko'ring yoki «O'tkazib yuborish» tugmasini bosing.",
        "ru": "⚠️ Промокод недействителен, истек или исчерпан лимит!\n"
              "Попробуйте снова или нажмите «Пропустить».",
        "en": "⚠️ Promo code is invalid, expired, or limit reached!\n"
              "Try again or click «Skip»."
    },

    # Bekor qilish va xatoliklar
    "order_cancelled": {
        "uz": "❌ Buyurtma bekor qilindi.",
        "ru": "❌ Заказ отменен.",
        "en": "❌ Order cancelled."
    },
    "main_menu": {
        "uz": "Asosiy menyuga qaytdingiz. Buyurtma berish uchun mahsulotlarni tanlang.",
        "ru": "Вы вернулись в главное меню. Выберите товары для заказа.",
        "en": "Returned to main menu. Select items to make an order."
    },

    # To'lov
    "ask_payment": {
        "uz": "💳 To'lov turini tanlang:",
        "ru": "💳 Выберите способ оплаты:",
        "en": "💳 Select payment method:"
    },
    "pay_cash": {
        "uz": "💵 Naqd pul",
        "ru": "💵 Наличные",
        "en": "💵 Cash"
    },
    "pay_click": {
        "uz": "🔵 Click",
        "ru": "🔵 Click",
        "en": "🔵 Click"
    },
    "pay_payme": {
        "uz": "🟢 Payme",
        "ru": "🟢 Payme",
        "en": "🟢 Payme"
    },

    # Yakuniy chek
    "receipt_title": {
        "uz": "✅ <b>Buyurtmangiz muvaffaqiyatli qabul qilindi!</b>\n🆔 <b>Buyurtma raqami:</b> #{order_id}\n\n",
        "ru": "✅ <b>Ваш заказ успешно принят!</b>\n🆔 <b>Номер заказа:</b> #{order_id}\n\n",
        "en": "✅ <b>Your order has been placed!</b>\n🆔 <b>Order ID:</b> #{order_id}\n\n"
    },
    "receipt_items_header": {
        "uz": "🛒 <b>Tarkib:</b>\n",
        "ru": "🛒 <b>Состав заказа:</b>\n",
        "en": "🛒 <b>Order Items:</b>\n"
    },
    "receipt_summary": {
        "uz": "\n━━━━━━━━━━━━━━━━━━━━\n"
              "📦 Mahsulotlar: {items_total:,} so'm\n"
              "🏷 Chegirma: -{discount:,} so'm\n"
              "🛵 Yetkazib berish: {delivery_fee:,} so'm\n"
              "💰 <b>Jami to'lov:</b> <b>{final_total:,} so'm</b>\n"
              "━━━━━━━━━━━━━━━━━━━━\n"
              "📌 <b>Holat:</b> {delivery_type_text}\n"
              "📍 <b>Manzil:</b> {address}\n"
              "📞 <b>Telefon:</b> {phone}\n"
              "📝 <b>Izoh:</b> {note}\n"
              "💳 <b>To'lov turi:</b> {payment_method}\n\n"
              "Operatorlarimiz tez orada siz bilan bog'lanishadi! Rahmat! 😊",
        "ru": "\n━━━━━━━━━━━━━━━━━━━━\n"
              "📦 Товары: {items_total:,} сум\n"
              "🏷 Скидка: -{discount:,} сум\n"
              "🛵 Доставка: {delivery_fee:,} сум\n"
              "💰 <b>Итого к оплате:</b> <b>{final_total:,} сум</b>\n"
              "━━━━━━━━━━━━━━━━━━━━\n"
              "📌 <b>Тип:</b> {delivery_type_text}\n"
              "📍 <b>Адрес:</b> {address}\n"
              "📞 <b>Телефон:</b> {phone}\n"
              "📝 <b>Комментарий:</b> {note}\n"
              "💳 <b>Способ оплаты:</b> {payment_method}\n\n"
              "Наши операторы свяжутся с вами в ближайшее время! Спасибо! 😊",
        "en": "\n━━━━━━━━━━━━━━━━━━━━\n"
              "📦 Items: {items_total:,} UZS\n"
              "🏷 Discount: -{discount:,} UZS\n"
              "🛵 Delivery: {delivery_fee:,} UZS\n"
              "💰 <b>Grand Total:</b> <b>{final_total:,} UZS</b>\n"
              "━━━━━━━━━━━━━━━━━━━━\n"
              "📌 <b>Type:</b> {delivery_type_text}\n"
              "📍 <b>Address:</b> {address}\n"
              "📞 <b>Phone:</b> {phone}\n"
              "📝 <b>Note:</b> {note}\n"
              "💳 <b>Payment:</b> {payment_method}\n\n"
              "Our team will contact you shortly! Thank you! 😊"
    }
}


def get_text(key: str, lang: str = "uz", **kwargs) -> str:
    """Tildagi matnni formatlab qaytaradi."""
    if lang not in ("uz", "ru", "en"):
        lang = "uz"
    
    phrase = MESSAGES.get(key, {}).get(lang)
    if phrase is None:
        phrase = MESSAGES.get(key, {}).get("uz", f"[{key}]")
    
    if kwargs:
        try:
            return phrase.format(**kwargs)
        except Exception:
            return phrase
    return phrase

