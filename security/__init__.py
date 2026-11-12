"""
Security package interface
"""
from security.webapp_auth import validate_init_data
from security.rate_limiter import AntiFloodMiddleware, double_spend_guard
from security.sanitization import sanitize_text, sanitize_phone, is_safe_code
from security.payment_guard import (
    generate_click_link,
    generate_payme_link,
    handle_click_request,
    handle_payme_request
)

