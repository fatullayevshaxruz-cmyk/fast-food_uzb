"""
Sanitization & Input Validation (Anti-SQLi & Anti-XSS)
"""
import re
import html
from typing import Optional

def sanitize_text(text: Optional[str], max_length: int = 500) -> str:
    """Matnni XSS va xavfli belgilardan tozalaydi."""
    if not text:
        return ""
    # Script va style bloklarini butunlay olib tashlash
    cleaned = re.sub(r'<(script|style)[^>]*?>.*?</\1>', '', str(text), flags=re.DOTALL | re.IGNORECASE)
    # Qolgan barcha HTML teglarni tozalash
    cleaned = re.sub(r'<[^>]*?>', '', cleaned)
    # HTML xavfsiz entitylarga o'tkazish
    cleaned = html.escape(cleaned.strip())
    # Boshqaruv belgilarini tozalash (null bytes, carriage returns)
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)
    return cleaned[:max_length]

def sanitize_phone(phone: Optional[str]) -> str:
    """Telefon raqamini O'zbekiston standart formatiga (+998XXXXXXXXX) keltiradi."""
    if not phone:
        return ""
    digits = re.sub(r'\D', '', str(phone))
    if len(digits) == 9:
        return f"+998{digits}"
    elif len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"
    elif len(digits) > 9:
        return f"+{digits}"
    return phone.strip()

def is_safe_code(code: Optional[str]) -> bool:
    """Promokod yoki ID kod faqat harf va raqamlardan iboratligini tekshiradi."""
    if not code:
        return False
    return bool(re.match(r'^[A-Za-z0-9_-]{2,32}$', str(code).strip()))
