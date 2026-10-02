"""Проверка данных запуска Telegram Mini App (initData).

Алгоритм из документации Telegram:
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
секрет = HMAC-SHA256(ключ "WebAppData", токен бота);
hash = HMAC-SHA256(секрет, строки "ключ=значение" без hash, по алфавиту, через \\n).
"""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

MAX_AGE_SECONDS = 24 * 60 * 60


def validate_init_data(init_data, bot_token, max_age=MAX_AGE_SECONDS, now=None):
    """Возвращает словарь пользователя, если подпись верна и данные свежие. Иначе None."""
    if not init_data or not bot_token:
        return None
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return None
    fields = {}
    for key, value in pairs:
        if key in fields:
            return None
        fields[key] = value
    received_hash = fields.pop("hash", None)
    if not received_hash:
        return None

    check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        return None

    try:
        auth_date = int(fields.get("auth_date", ""))
    except ValueError:
        return None
    now = time.time() if now is None else now
    if auth_date > now + 60 or now - auth_date > max_age:
        return None

    try:
        user = json.loads(fields.get("user", ""))
    except ValueError:
        return None
    if not isinstance(user, dict) or not isinstance(user.get("id"), int):
        return None
    return user


def admin_user(init_data, bot_token, admin_ids, now=None):
    """Сначала подпись, потом ID. Возвращает пользователя-админа или None."""
    user = validate_init_data(init_data, bot_token, now=now)
    if user is None or user["id"] not in admin_ids:
        return None
    return user
