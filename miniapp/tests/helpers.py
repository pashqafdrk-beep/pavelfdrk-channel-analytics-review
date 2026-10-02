import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

BOT_TOKEN = "123456:TEST-token-only-for-tests"
ADMIN_ID = 111
OTHER_ID = 222


def sign(fields, token=BOT_TOKEN):
    """Собирает initData так же, как это делает Telegram."""
    check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": digest})


def init_data(user_id=ADMIN_ID, auth_date=None, token=BOT_TOKEN):
    return sign({
        "auth_date": str(int(time.time() if auth_date is None else auth_date)),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps({"id": user_id, "first_name": "Павел"}, ensure_ascii=False),
    }, token)
