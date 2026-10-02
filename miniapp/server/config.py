"""Настройки читаются только из переменных окружения.

На сервере их задаёт systemd из файла /etc/pavel-miniapp.env (см. deploy/).
В коде и репозитории секретов нет.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Config:
    def __init__(self, env=None):
        env = os.environ if env is None else env
        self.bot_token = env.get("BOT_TOKEN", "")
        self.admin_ids = {
            int(x) for x in env.get("ADMIN_IDS", "").replace(" ", "").split(",") if x.isdigit()
        }
        self.youtube_api_key = env.get("YOUTUBE_API_KEY", "")
        self.youtube_handle = env.get("YOUTUBE_HANDLE", "pavelfdrk")
        self.db_path = env.get("DB_PATH", str(ROOT / "data" / "miniapp.db"))
        self.web_dir = env.get("WEB_DIR", str(ROOT / "web"))
        self.host = env.get("HOST", "127.0.0.1")
        self.port = int(env.get("PORT", "8080"))
