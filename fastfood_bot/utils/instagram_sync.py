"""
📸 Instagram → Mini App sinxronizatsiyasi (@kafe_fastfood)

Faol Stories va oxirgi Reels mediyalarini olib, lokal `webapp/media/stories/`
papkasiga keshlaydi va `/api/promo-stories` orqali Mini App ga beradi.

Manbalar (ustuvorlik tartibida):
  1. Rasmiy Instagram Graph API  — INSTAGRAM_ACCESS_TOKEN + INSTAGRAM_BUSINESS_ID
     (Stories + Reels, eng barqaror va xavfsiz usul)
  2. instagrapi                  — INSTAGRAM_LOGIN + INSTAGRAM_PASSWORD (+ `pip install instagrapi`)
     (Stories + Reels; sessiya data/ig_session.json da saqlanadi)
  3. Ochiq profil (fallback)     — hech qanday kalit kerak emas, faqat oxirgi postlar/Reels
  4. Hech narsa bo'lmasa          — admin qo'shgan zaxira bannerlar story sifatida ko'rsatiladi

Instagram bloklamasligi uchun yangilanish har INSTAGRAM_SYNC_INTERVAL (standart 1800s = 30 daqiqa)
da bir marta bajariladi.
"""
import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

log = logging.getLogger(__name__)

# ── Yo'llar ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_DIR = BASE_DIR / "webapp" / "media" / "stories"
MEDIA_URL_PREFIX = "/webapp/media/stories"
DATA_DIR = BASE_DIR / "data"
CACHE_FILE = DATA_DIR / "promo_stories_cache.json"
BANNERS_FILE = DATA_DIR / "promo_banners.json"
SHOWCASE_CUSTOM_FILE = DATA_DIR / "showcase_items.json"
SESSION_FILE = DATA_DIR / "ig_session.json"

# ── Sozlamalar (.env) ───────────────────────────────────────────────────
IG_TARGET = (os.getenv("INSTAGRAM_TARGET") or "kafe_fastfood").strip().lstrip("@")
SYNC_INTERVAL = max(600, int(os.getenv("INSTAGRAM_SYNC_INTERVAL", "1800") or 1800))
GRAPH_TOKEN = (os.getenv("INSTAGRAM_ACCESS_TOKEN") or "").strip()
GRAPH_USER_ID = (os.getenv("INSTAGRAM_BUSINESS_ID") or "").strip()
GRAPH_VERSION = (os.getenv("INSTAGRAM_GRAPH_VERSION") or "v19.0").strip()
IG_LOGIN = (os.getenv("INSTAGRAM_LOGIN") or "").strip()
IG_PASSWORD = (os.getenv("INSTAGRAM_PASSWORD") or "").strip()

MAX_STORIES = 10
MAX_REELS = 8
MAX_FILE_BYTES = 40 * 1024 * 1024  # 40 MB
STORY_TTL = 24 * 3600
HTTP_TIMEOUT = aiohttp.ClientTimeout(total=45)
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)

SHOWCASE_URL_PREFIX = "/webapp/media/showcase"

# Admin hech narsa qo'shmagan bo'lsa ko'rsatiladigan standart menyu bannerlari (Direct-to-Cart qo'llab-quvvatlanadi)
DEFAULT_BANNERS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "title": "Katta Aksiya! 2 ta Burger oling",
        "subtitle": "Ikkinchi Chizburger uchun 50% chegirma!",
        "badge": "AKSIYA 🔥",
        "tag": "HOT DEAL",
        "image": f"{SHOWCASE_URL_PREFIX}/banner_burgers.jpg",
        "color": "linear-gradient(135deg,#991B1B 0%,#E50914 100%)",
        "button_text": "Buyurtma berish",
        "price": 57000,
        "old_price": 76000,
        "link": "category:1",
        "product": {
            "id": 901,
            "name": "Katta Aksiya: 2 ta Chizburger (50% chegirma)",
            "price": 57000,
            "old_price": 76000,
            "image_url": f"{SHOWCASE_URL_PREFIX}/banner_burgers.jpg",
            "description": "2 dona shirali go'shtli Kafeyimiz Chizburgeri. Ikkinchisi uchun maxsus 50% chegirma hisoblangan!",
        },
    },
    {
        "id": 2,
        "title": "Maxsus Kafe Kombo 🥤🍟",
        "subtitle": "Burger + Kartoshka Fri + Cola bor-yo'g'i 45,000 so'm",
        "badge": "Top Taklif ✨",
        "tag": "COMBO SET",
        "image": f"{SHOWCASE_URL_PREFIX}/banner_combo.jpg",
        "color": "linear-gradient(135deg,#7F1D1D 0%,#EA580C 100%)",
        "button_text": "Buyurtma berish",
        "price": 45000,
        "old_price": 60000,
        "link": "category:5",
        "product": {
            "id": 902,
            "name": "Maxsus Kafe Kombo (Burger + Fri + Cola)",
            "price": 45000,
            "old_price": 60000,
            "image_url": f"{SHOWCASE_URL_PREFIX}/banner_combo.jpg",
            "description": "Klassik mazali burger, oltinrang qarsildoq fri va muzdek Coca-Cola 0.5L kombo to'plami.",
        },
    },
    {
        "id": 3,
        "title": "Tezkor Dostavka Set ⚡",
        "subtitle": "2x Tandir Lavash + 2x Coca-Cola 0.5L — qaynoq yetkazish!",
        "badge": "DOSTAVKA ⚡",
        "tag": "FAST DELIVERY",
        "image": f"{SHOWCASE_URL_PREFIX}/banner_lavash.jpg",
        "color": "linear-gradient(135deg,#78350F 0%,#D97706 100%)",
        "button_text": "Buyurtma berish",
        "price": 68000,
        "old_price": 82000,
        "link": "category:2",
        "product": {
            "id": 903,
            "name": "Tezkor Dostavka Set (2x Lavash + 2x Cola)",
            "price": 68000,
            "old_price": 82000,
            "image_url": f"{SHOWCASE_URL_PREFIX}/banner_lavash.jpg",
            "description": "Issig'ida 2 ta mol go'shtli tandir lavash va 2 ta muzdek Coca-Cola 0.5L to'plami.",
        },
    },
    {
        "id": 4,
        "title": "Qarsildoq Snack Box 🍟",
        "subtitle": "Nuggets (6 dona) + Katta Fri + 2 ta maxsus sous",
        "badge": "AKSIYA 🔥",
        "tag": "SNACK BOX",
        "image": f"{SHOWCASE_URL_PREFIX}/banner_snacks.jpg",
        "color": "linear-gradient(135deg,#1E1B4B 0%,#4F46E5 100%)",
        "button_text": "Buyurtma berish",
        "price": 28000,
        "old_price": 36000,
        "link": "category:4",
        "product": {
            "id": 904,
            "name": "Qarsildoq Snack Box (Nuggets + Fri + Sous)",
            "price": 28000,
            "old_price": 36000,
            "image_url": f"{SHOWCASE_URL_PREFIX}/banner_snacks.jpg",
            "description": "6 dona oltinrang nuggets, qarsildoq kartoshka fri va 2 xil firma sousi.",
        },
    },
]

# Menyu bo'limlariga mos 5 xil dizayndagi Story posterlar + 5 ta Reels videolar
DEFAULT_SHOWCASE_ITEMS: List[Dict[str, Any]] = [
    {
        "id": "story_burgers",
        "kind": "story",
        "type": "image",
        "url": f"{SHOWCASE_URL_PREFIX}/story_burgers.jpg",
        "thumbnail": f"{SHOWCASE_URL_PREFIX}/story_burgers.jpg",
        "caption": "🍔 Shirali Grill Burgerlar",
        "subtitle": "Double Cheese, BBQ & Kafeyimiz Big Burgeri — 35 000 so'mdan",
        "badge": "🔥 Xit",
        "theme_color": "#E50914",
        "category_id": 1,
        "cta_label": "🍔 Burgerlar bo'limini ochish",
        "permalink": "",
        "taken_at": 0,
    },
    {
        "id": "reel_burgers",
        "kind": "reel",
        "type": "video",
        "url": f"{SHOWCASE_URL_PREFIX}/reel_burgers.mp4",
        "thumbnail": f"{SHOWCASE_URL_PREFIX}/reel_burgers_thumb.jpg",
        "caption": "🎬 Burgerlar Reels — Issiq Grill",
        "subtitle": "Cheese Burger, Double Cheese & Big Burger",
        "badge": "🍔 Burgerlar",
        "theme_color": "#E50914",
        "category_id": 1,
        "cta_label": "🍔 Burgerlarni tanlash",
        "permalink": "",
        "taken_at": 0,
    },
    {
        "id": "story_lavash",
        "kind": "story",
        "type": "image",
        "url": f"{SHOWCASE_URL_PREFIX}/story_lavash.jpg",
        "thumbnail": f"{SHOWCASE_URL_PREFIX}/story_lavash.jpg",
        "caption": "🌯 Tandir Lavash & Doner",
        "subtitle": "Mol va tovuq go'shtli tandir lavash — 32 000 so'mdan",
        "badge": "✨ Tandir",
        "theme_color": "#D97706",
        "category_id": 2,
        "cta_label": "🌯 Lavash & Doner bo'limi",
        "permalink": "",
        "taken_at": 0,
    },
    {
        "id": "reel_lavash",
        "kind": "reel",
        "type": "video",
        "url": f"{SHOWCASE_URL_PREFIX}/reel_lavash.mp4",
        "thumbnail": f"{SHOWCASE_URL_PREFIX}/reel_lavash_thumb.jpg",
        "caption": "🎬 Lavash & Doner Reels",
        "subtitle": "Mol go'shtli Lavash, Tovuqli va Mix Doner",
        "badge": "🌯 Lavash",
        "theme_color": "#D97706",
        "category_id": 2,
        "cta_label": "🌯 Lavashlarni ko'rish",
        "permalink": "",
        "taken_at": 0,
    },
    {
        "id": "story_combo",
        "kind": "story",
        "type": "image",
        "url": f"{SHOWCASE_URL_PREFIX}/story_combo.jpg",
        "thumbnail": f"{SHOWCASE_URL_PREFIX}/story_combo.jpg",
        "caption": "🎁 VIP Kombo To'plamlar",
        "subtitle": "KAFE10 promokodi bilan −10% chegirma!",
        "badge": "🎁 -10%",
        "theme_color": "#B91C1C",
        "category_id": 5,
        "cta_label": "🎁 Kombo to'plamlarni ochish",
        "permalink": "",
        "taken_at": 0,
    },
    {
        "id": "reel_combo",
        "kind": "reel",
        "type": "video",
        "url": f"{SHOWCASE_URL_PREFIX}/reel_combo.mp4",
        "thumbnail": f"{SHOWCASE_URL_PREFIX}/reel_combo_thumb.jpg",
        "caption": "🎬 Kombo To'plamlar Reels",
        "subtitle": "Kafe Kombo, Double Kombo va Oilaviy Kombo",
        "badge": "🎁 Kombo",
        "theme_color": "#B91C1C",
        "category_id": 5,
        "cta_label": "🎁 Komboga o'tish",
        "permalink": "",
        "taken_at": 0,
    },
    {
        "id": "story_snacks",
        "kind": "story",
        "type": "image",
        "url": f"{SHOWCASE_URL_PREFIX}/story_snacks.jpg",
        "thumbnail": f"{SHOWCASE_URL_PREFIX}/story_snacks.jpg",
        "caption": "🍟 Qarsildoq Gazaklar",
        "subtitle": "Kartoshka Fri, Tovuq Nuggets va maxsus souslar",
        "badge": "⚡ Top",
        "theme_color": "#4F46E5",
        "category_id": 4,
        "cta_label": "🍟 Gazaklar bo'limini ochish",
        "permalink": "",
        "taken_at": 0,
    },
    {
        "id": "reel_snacks",
        "kind": "reel",
        "type": "video",
        "url": f"{SHOWCASE_URL_PREFIX}/reel_snacks.mp4",
        "thumbnail": f"{SHOWCASE_URL_PREFIX}/reel_snacks_thumb.jpg",
        "caption": "🎬 Gazaklar & Fri Reels",
        "subtitle": "Kartoshka Fri, Nuggets 6 dona va Souslar",
        "badge": "🍟 Gazak",
        "theme_color": "#4F46E5",
        "category_id": 4,
        "cta_label": "🍟 Gazaklarni tanlash",
        "permalink": "",
        "taken_at": 0,
    },
    {
        "id": "story_drinks",
        "kind": "story",
        "type": "image",
        "url": f"{SHOWCASE_URL_PREFIX}/story_drinks.jpg",
        "thumbnail": f"{SHOWCASE_URL_PREFIX}/story_drinks.jpg",
        "caption": "🥤 Muzdek Ichimliklar",
        "subtitle": "Coca-Cola, Fanta, Sprite, suv va issiq choy",
        "badge": "❄️ Muzdek",
        "theme_color": "#0891B2",
        "category_id": 3,
        "cta_label": "🥤 Ichimliklarni ochish",
        "permalink": "",
        "taken_at": 0,
    },
    {
        "id": "reel_drinks",
        "kind": "reel",
        "type": "video",
        "url": f"{SHOWCASE_URL_PREFIX}/reel_drinks.mp4",
        "thumbnail": f"{SHOWCASE_URL_PREFIX}/reel_drinks_thumb.jpg",
        "caption": "🎬 Ichimliklar Reels — Ice Cold",
        "subtitle": "Muzdek gazli ichimliklar 3 000 so'mdan",
        "badge": "🥤 Ichimlik",
        "theme_color": "#0891B2",
        "category_id": 3,
        "cta_label": "🥤 Ichimlik buyurtma berish",
        "permalink": "",
        "taken_at": 0,
    },
]

# ── Holat ───────────────────────────────────────────────────────────────
_state: Dict[str, Any] = {
    "stories": [],
    "reels": [],
    "source": None,
    "synced_at": 0,
    "error": None,
}
_lock: Optional[asyncio.Lock] = None
_task: Optional[asyncio.Task] = None


# ══════════════════════════════════════════════════════════════════════
# Fayl yordamchilari
# ══════════════════════════════════════════════════════════════════════
def _ensure_dirs() -> None:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning(f"JSON o'qishda xato ({path.name}): {e}")
    return default


def _write_json(path: Path, data) -> None:
    try:
        _ensure_dirs()
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception as e:
        log.warning(f"JSON yozishda xato ({path.name}): {e}")


def load_banners() -> List[Dict[str, Any]]:
    data = _read_json(BANNERS_FILE, [])
    return data if isinstance(data, list) else []


def save_banners(banners: List[Dict[str, Any]]) -> None:
    _write_json(BANNERS_FILE, banners)


def _showcase_item_valid(item: Dict[str, Any]) -> bool:
    url = str(item.get("url") or "")
    if url.startswith(SHOWCASE_URL_PREFIX):
        fname = url.rsplit("/", 1)[-1]
        return (BASE_DIR / "webapp" / "media" / "showcase" / fname).exists()
    if url.startswith(MEDIA_URL_PREFIX):
        fname = url.rsplit("/", 1)[-1]
        return (MEDIA_DIR / fname).exists()
    return bool(url)


def load_showcase_items() -> List[Dict[str, Any]]:
    """Admin tahrirlagan yoki standart Stories & Reels ro'yxatini qaytaradi."""
    if SHOWCASE_CUSTOM_FILE.exists():
        data = _read_json(SHOWCASE_CUSTOM_FILE, None)
        if isinstance(data, list):
            return [dict(item) for item in data if _showcase_item_valid(item)]
    return [dict(item) for item in DEFAULT_SHOWCASE_ITEMS if _showcase_item_valid(item)]


def save_showcase_items(items: List[Dict[str, Any]]) -> None:
    _write_json(SHOWCASE_CUSTOM_FILE, items)


def reset_showcase_items() -> List[Dict[str, Any]]:
    try:
        if SHOWCASE_CUSTOM_FILE.exists():
            SHOWCASE_CUSTOM_FILE.unlink()
    except Exception:
        pass
    return load_showcase_items()


def _load_cache() -> None:
    cached = _read_json(CACHE_FILE, {})
    if isinstance(cached, dict):
        for key in ("stories", "reels", "source", "synced_at"):
            if key in cached:
                _state[key] = cached[key]
    # Lokal fayli o'chib ketgan (masalan, Render qayta ishga tushgan) elementlarni olib tashlash
    for key in ("stories", "reels"):
        _state[key] = [i for i in _state.get(key) or [] if _local_exists(i.get("url"))]


def _save_cache() -> None:
    _write_json(CACHE_FILE, {k: _state[k] for k in ("stories", "reels", "source", "synced_at")})


def _local_exists(url: Optional[str]) -> bool:
    if not url or not url.startswith(MEDIA_URL_PREFIX):
        return False
    return (MEDIA_DIR / url.rsplit("/", 1)[-1]).exists()


def _safe_id(raw: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "", str(raw))[:64] or str(int(time.time() * 1000))


def _parse_ts(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, datetime):
        return int(value.timestamp())
    try:
        return int(datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%S%z").timestamp())
    except Exception:
        return 0


def _item(kind: str, media_id: Any, is_video: bool, media_url: Optional[str],
          thumb_url: Optional[str], permalink: str = "", caption: str = "",
          taken_at: Any = None) -> Optional[Dict[str, Any]]:
    media_url = str(media_url) if media_url else ""
    thumb_url = str(thumb_url) if thumb_url else ""
    if not media_url and not thumb_url:
        return None
    if is_video and not media_url:
        # Video havolasi yo'q (ochiq profilda bo'ladi) — muqovasini rasm sifatida ko'rsatamiz
        is_video, media_url = False, thumb_url
    return {
        "id": f"{kind}_{_safe_id(media_id)}",
        "kind": kind,  # story | reel
        "type": "video" if is_video else "image",
        "remote_url": media_url,
        "remote_thumb": thumb_url or (media_url if not is_video else ""),
        "permalink": permalink or "",
        "caption": (caption or "")[:280],
        "taken_at": _parse_ts(taken_at),
    }


# ══════════════════════════════════════════════════════════════════════
# 1. Rasmiy Instagram Graph API
# ══════════════════════════════════════════════════════════════════════
async def _fetch_graph(session: aiohttp.ClientSession) -> Tuple[List[dict], List[dict]]:
    base = f"https://graph.facebook.com/{GRAPH_VERSION}/{GRAPH_USER_ID}"
    stories, reels = [], []

    async with session.get(f"{base}/stories", params={
        "fields": "id,media_type,media_url,thumbnail_url,permalink,timestamp",
        "access_token": GRAPH_TOKEN,
    }) as r:
        data = await r.json(content_type=None)
        if r.status != 200:
            raise RuntimeError(f"Graph stories {r.status}: {data.get('error', {}).get('message')}")
        for m in (data.get("data") or [])[:MAX_STORIES]:
            it = _item("story", m.get("id"), m.get("media_type") == "VIDEO", m.get("media_url"),
                       m.get("thumbnail_url"), m.get("permalink"), "", m.get("timestamp"))
            if it:
                stories.append(it)

    async with session.get(f"{base}/media", params={
        "fields": "id,media_type,media_product_type,media_url,thumbnail_url,permalink,caption,timestamp",
        "limit": 25,
        "access_token": GRAPH_TOKEN,
    }) as r:
        data = await r.json(content_type=None)
        if r.status != 200:
            raise RuntimeError(f"Graph media {r.status}: {data.get('error', {}).get('message')}")
        media = data.get("data") or []
        only_reels = [m for m in media if m.get("media_product_type") == "REELS"]
        for m in (only_reels or [m for m in media if m.get("media_type") != "CAROUSEL_ALBUM"])[:MAX_REELS]:
            it = _item("reel", m.get("id"), m.get("media_type") == "VIDEO", m.get("media_url"),
                       m.get("thumbnail_url"), m.get("permalink"), m.get("caption"), m.get("timestamp"))
            if it:
                reels.append(it)
    return stories, reels


# ══════════════════════════════════════════════════════════════════════
# 2. instagrapi (ixtiyoriy)
# ══════════════════════════════════════════════════════════════════════
def _fetch_instagrapi_blocking() -> Tuple[List[dict], List[dict]]:
    from instagrapi import Client  # type: ignore  # ixtiyoriy bog'liqlik

    cl = Client()
    cl.delay_range = [2, 5]  # so'rovlar orasida tabiiy kechikish
    if SESSION_FILE.exists():
        try:
            cl.load_settings(str(SESSION_FILE))
        except Exception:
            pass
    cl.login(IG_LOGIN, IG_PASSWORD)
    cl.dump_settings(str(SESSION_FILE))

    uid = cl.user_id_from_username(IG_TARGET)
    stories, reels = [], []
    for s in cl.user_stories(uid)[:MAX_STORIES]:
        it = _item("story", s.pk, s.media_type == 2, s.video_url or s.thumbnail_url,
                   s.thumbnail_url, f"https://www.instagram.com/stories/{IG_TARGET}/{s.pk}/",
                   "", s.taken_at)
        if it:
            stories.append(it)
    for m in cl.user_clips(uid, amount=MAX_REELS):
        it = _item("reel", m.pk, m.media_type == 2, m.video_url or m.thumbnail_url,
                   m.thumbnail_url, f"https://www.instagram.com/reel/{m.code}/",
                   m.caption_text or "", m.taken_at)
        if it:
            reels.append(it)
    return stories, reels


# ══════════════════════════════════════════════════════════════════════
# 3. Ochiq profil (fallback, faqat postlar/Reels)
# ══════════════════════════════════════════════════════════════════════
async def _fetch_public(session: aiohttp.ClientSession) -> Tuple[List[dict], List[dict]]:
    url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={IG_TARGET}"
    headers = {"User-Agent": USER_AGENT, "x-ig-app-id": "936619743392459", "Accept": "application/json"}
    async with session.get(url, headers=headers) as r:
        if r.status != 200:
            raise RuntimeError(f"Public profile HTTP {r.status}")
        data = await r.json(content_type=None)

    user = (data.get("data") or {}).get("user") or {}
    edges = []
    for key in ("edge_felix_video_timeline", "edge_owner_to_timeline_media"):
        edges.extend(((user.get(key) or {}).get("edges")) or [])

    reels, seen = [], set()
    for e in edges:
        n = e.get("node") or {}
        if not n.get("id") or n["id"] in seen:
            continue
        seen.add(n["id"])
        cap_edges = ((n.get("edge_media_to_caption") or {}).get("edges")) or []
        caption = (cap_edges[0].get("node") or {}).get("text", "") if cap_edges else ""
        is_reel = n.get("product_type") == "clips" or n.get("is_video")
        it = _item("reel", n["id"], bool(n.get("is_video")), n.get("video_url"), n.get("display_url"),
                   f"https://www.instagram.com/{'reel' if is_reel else 'p'}/{n.get('shortcode', '')}/",
                   caption, n.get("taken_at_timestamp"))
        if it:
            reels.append(it)
        if len(reels) >= MAX_REELS:
            break
    return [], reels


# ══════════════════════════════════════════════════════════════════════
# Yuklab olish va lokal keshlash
# ══════════════════════════════════════════════════════════════════════
async def _download(session: aiohttp.ClientSession, url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        async with session.get(url, headers={"User-Agent": USER_AGENT}) as r:
            if r.status != 200:
                return False
            size = 0
            tmp = dest.with_suffix(dest.suffix + ".part")
            with open(tmp, "wb") as f:
                async for chunk in r.content.iter_chunked(64 * 1024):
                    size += len(chunk)
                    if size > MAX_FILE_BYTES:
                        f.close()
                        tmp.unlink(missing_ok=True)
                        return False
                    f.write(chunk)
            tmp.replace(dest)
            return True
    except Exception as e:
        log.warning(f"Media yuklab bo'lmadi ({dest.name}): {e}")
        return False


async def _localize(session: aiohttp.ClientSession, items: List[dict]) -> List[dict]:
    result = []
    for it in items:
        ext = "mp4" if it["type"] == "video" else "jpg"
        main_name = f"{it['id']}.{ext}"
        if not await _download(session, it["remote_url"], MEDIA_DIR / main_name):
            continue
        thumb = f"{MEDIA_URL_PREFIX}/{main_name}" if it["type"] == "image" else ""
        if it["type"] == "video" and it.get("remote_thumb"):
            thumb_name = f"{it['id']}_thumb.jpg"
            if await _download(session, it["remote_thumb"], MEDIA_DIR / thumb_name):
                thumb = f"{MEDIA_URL_PREFIX}/{thumb_name}"
        result.append({
            "id": it["id"],
            "kind": it["kind"],
            "type": it["type"],
            "url": f"{MEDIA_URL_PREFIX}/{main_name}",
            "thumbnail": thumb,
            "permalink": it["permalink"],
            "caption": it["caption"],
            "taken_at": it["taken_at"],
        })
    return result


def _cleanup_media(keep: List[dict]) -> None:
    keep_names = set()
    for it in keep:
        for key in ("url", "thumbnail"):
            if it.get(key):
                keep_names.add(it[key].rsplit("/", 1)[-1])
    for f in MEDIA_DIR.glob("*"):
        if f.is_file() and f.name not in keep_names and f.name != ".gitkeep":
            try:
                f.unlink()
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════════════
# Asosiy sinxronizatsiya
# ══════════════════════════════════════════════════════════════════════
async def sync_instagram(force: bool = False) -> Dict[str, Any]:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    async with _lock:
        if not force and time.time() - (_state.get("synced_at") or 0) < SYNC_INTERVAL:
            return _state
        _ensure_dirs()

        attempts = []
        if GRAPH_TOKEN and GRAPH_USER_ID:
            attempts.append("graph_api")
        if IG_LOGIN and IG_PASSWORD:
            attempts.append("instagrapi")
        attempts.append("public")

        errors = []
        async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as session:
            for source in attempts:
                try:
                    if source == "graph_api":
                        stories, reels = await _fetch_graph(session)
                    elif source == "instagrapi":
                        loop = asyncio.get_running_loop()
                        stories, reels = await loop.run_in_executor(None, _fetch_instagrapi_blocking)
                    else:
                        stories, reels = await _fetch_public(session)

                    if not stories and not reels:
                        errors.append(f"{source}: bo'sh")
                        continue

                    local_stories = await _localize(session, stories)
                    local_reels = await _localize(session, reels)
                    if not local_stories and not local_reels:
                        errors.append(f"{source}: media yuklanmadi")
                        continue

                    _state.update(stories=local_stories, reels=local_reels, source=source,
                                  synced_at=int(time.time()), error=None)
                    _cleanup_media(local_stories + local_reels)
                    _save_cache()
                    log.info(f"📸 Instagram sync OK ({source}): {len(local_stories)} story, {len(local_reels)} reels")
                    return _state
                except ImportError:
                    errors.append(f"{source}: instagrapi o'rnatilmagan")
                except Exception as e:
                    errors.append(f"{source}: {e}")

        # Hech bir manba ishlamadi — eski keshni saqlab qolamiz, keyingi urinishgacha kutamiz
        _state["synced_at"] = int(time.time())
        _state["error"] = "; ".join(errors)[:500]
        if (GRAPH_TOKEN and GRAPH_USER_ID) or (IG_LOGIN and IG_PASSWORD):
            log.warning(f"📸 Instagram sync muvaffaqiyatsiz: {_state['error']}")
        else:
            log.info("📸 Stories & Bannerlar: lokal zaxira bannerlar faol.")
        return _state


async def _sync_loop() -> None:
    await asyncio.sleep(15)  # bot to'liq ishga tushishini kutamiz
    while True:
        try:
            await sync_instagram(force=False)
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error(f"Instagram sync loop xatosi: {e}", exc_info=True)
        await asyncio.sleep(SYNC_INTERVAL)


async def start_background_sync(app=None) -> None:
    """aiohttp `on_startup` signali uchun."""
    global _task
    _ensure_dirs()
    _load_cache()
    if _task is None or _task.done():
        _task = asyncio.create_task(_sync_loop())


async def stop_background_sync(app=None) -> None:
    """aiohttp `on_cleanup` signali uchun."""
    global _task
    if _task and not _task.done():
        _task.cancel()
    _task = None


# ══════════════════════════════════════════════════════════════════════
# API javobi
# ══════════════════════════════════════════════════════════════════════
def get_promo_payload() -> Dict[str, Any]:
    banners = load_banners() or DEFAULT_BANNERS
    now = time.time()
    stories = [s for s in _state.get("stories") or []
               if not s.get("taken_at") or now - s["taken_at"] < STORY_TTL]
    reels = list(_state.get("reels") or [])
    live_items = stories + reels

    curated = load_showcase_items()

    if live_items:
        seen_ids = {i.get("id") for i in curated}
        items = curated + [l for l in live_items if l.get("id") not in seen_ids]
        fallback = False
    elif curated:
        items = curated
        fallback = True
    else:
        items = [{
            "id": f"promo_{b.get('id')}",
            "kind": "promo",
            "type": "image",
            "url": b.get("image") or "",
            "thumbnail": b.get("image") or "",
            "permalink": b.get("link") or "",
            "caption": b.get("title") or "",
            "subtitle": b.get("subtitle") or "",
            "color": b.get("color") or "",
            "taken_at": 0,
        } for b in banners]
        fallback = True

    return {
        "success": True,
        "banners": banners,
        "stories": items,
        "instagram": {
            "username": IG_TARGET,
            "profile_url": f"https://www.instagram.com/{IG_TARGET}/",
            "source": None if fallback else _state.get("source"),
            "synced_at": _state.get("synced_at") or 0,
            "fallback": fallback,
        },
    }
