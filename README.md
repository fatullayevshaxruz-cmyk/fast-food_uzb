# 🍔 FastFood Express - Telegram Bot & Web App

Fast-food va restoran buyurtmalarini qabul qilishga mo'ljallangan professional Telegram Bot va interaktiv Web App (Mini App).

## 🚀 Asosiy imkoniyatlar

1. **Zamonaviy Web App (Mini App):**
   - Taomlarning yuqori sifatli fotosuratlari va to'liq tarkibi
   - Kategoriyalar (Burgerlar, Lavash, Pizza, Gazaklar, Ichimliklar) va tezkor qidiruv
   - Interaktiv son hisoblagich va Telegram Haptic feedback
   - Suzuvchi savat va pastdan chiquvchi zamonaviy Savat modali (Bottom Drawer)
   - Jonli promokod hisob-kitobi (masalan: `FAST10`)

2. **FSM (Finite State Machine) Buyurtma tizimi:**
   - **Ish vaqti tekshiruvi:** Toshkent vaqti bo'yicha (09:00 - 23:00)
   - **Xizmat turi:**
     - 🍽 **Shu yerda (Zalda):** Stol raqamini kiritish, yetkazish narxi 0 so'm
     - 🛵 **Yetkazib berish:** Minimal summa (30,000 so'm) va masofa tekshiruvi
   - **Geo-Routing va Xavfsizlik:**
     - O'zbekiston chegarasi tekshiruvi
     - OpenStreetMap Nominatim orqali Reverse Geocoding (aniq manzil)
     - Eng yaqin filialni aniqlash va 15 km zona nazorati
     - Masofaga qarab yetkazish narxini 1000 so'mga yaxlitlab hisoblash
   - **Smart-avtotoldirish:** Foydalanuvchi telefon raqami bazada bo'lsa qayta so'ramaydi
   - **Ko'p tillilik:** O'zbek, Rus va Ingliz tillari

3. **Asinxron Bildirishnomalar:**
   - Oshxona/Filial kanaliga to'liq chek va buyurtma ma'lumotlari
   - Kuryer kanaliga yetkazish manzili, masofasi, telefoni va GPS lokatsiyasi

## 🛠 O'rnatish va Ishga tushirish

1. **Kutubxonalarni o'rnatish:**
```bash
pip install -r requirements.txt
```

2. **Konfiguratsiya:**
`.env.example` faylidan nusxa olib `.env` faylini yarating va kerakli token va kanal ID larini kiriting:
```bash
cp .env.example .env
```

3. **Ishga tushirish:**
```bash
python main.py
```

Web App statik serveri `http://localhost:8080/` portida avtomatik ishga tushadi.

