"""HTTP-сервер мини-приложения: статика + API. Только стандартная библиотека Python."""
import datetime
import json
import mimetypes
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from auth import admin_user
from config import Config
from db import TEXT_KEYS, Database
from topics import TOPICS
import youtube

MAX_BODY = 64 * 1024
PUBLIC_EVENTS = {"open", "video_click", "book_click", "test_done"}


def public_video(v):
    return {k: v[k] for k in ("id", "title", "published", "duration", "thumbnail", "format", "topic", "pinned")}


class App:
    def __init__(self, config, db=None, fetch=None):
        self.config = config
        self.db = db or Database(config.db_path)
        self.fetch = fetch
        self.refresh_lock = threading.Lock()

    def refresh(self):
        if not self.refresh_lock.acquire(blocking=False):
            return {"ok": False, "error": "Обновление уже идёт"}
        try:
            kwargs = {"fetch": self.fetch} if self.fetch else {}
            count = youtube.refresh(self.db, self.config, **kwargs)
            self.db.set_meta("last_refresh", datetime.datetime.now().isoformat(timespec="minutes"))
            return {"ok": True, "count": count}
        except Exception as exc:  # сеть, квота, неверный ключ
            return {"ok": False, "error": str(exc)}
        finally:
            self.refresh_lock.release()

    # Публичные маршруты
    def public(self, method, path, body):
        if method == "GET" and path == "/api/content":
            return 200, {
                "topics": TOPICS,
                "videos": [public_video(v) for v in self.db.videos()],
                "books": [{k: b[k] for k in ("id", "title", "description", "series", "cover", "link")}
                          for b in self.db.books()],
                "texts": self.db.texts(),
            }
        if method == "POST" and path == "/api/event":
            event = body.get("event")
            item = str(body.get("item", ""))[:64]
            if event not in PUBLIC_EVENTS:
                return 400, {"error": "Неизвестное событие"}
            if event == "video_click" and not self.db.video_exists(item):
                return 400, {"error": "Нет такого видео"}
            if event != "video_click" and event != "book_click":
                item = ""
            self.db.count_event(event, item)
            return 200, {"ok": True}
        return None

    # Админ-маршруты: доступ только после проверки подписи и ID
    def admin(self, method, path, body, init_data):
        user = admin_user(init_data, self.config.bot_token, self.config.admin_ids)
        if user is None:
            return 403, {"error": "Нет доступа"}
        if method == "GET" and path == "/api/admin/me":
            return 200, {"ok": True, "name": user.get("first_name", "")}
        if method == "GET" and path == "/api/admin/videos":
            return 200, {"topics": TOPICS, "videos": self.db.videos(include_hidden=True)}
        if method == "POST" and path == "/api/admin/video":
            topic = body.get("topic")
            if topic is not None and topic not in TOPICS:
                return 400, {"error": "Неизвестная тема"}
            n = self.db.update_video(str(body.get("id", "")), body.get("hidden"), body.get("pinned"), topic)
            return (200, {"ok": True}) if n else (404, {"error": "Не найдено"})
        if method == "GET" and path == "/api/admin/books":
            return 200, {"books": self.db.books(include_hidden=True), "texts": self.db.texts()}
        if method == "POST" and path == "/api/admin/book":
            fields = {k: v for k, v in body.items() if k != "id"}
            for key in ("link", "cover"):
                if fields.get(key) and not str(fields[key]).startswith("https://"):
                    return 400, {"error": "Ссылка должна начинаться с https://"}
            n = self.db.update_book(int(body.get("id", 0)), fields)
            return (200, {"ok": True}) if n else (404, {"error": "Не найдено"})
        if method == "POST" and path == "/api/admin/text":
            key, value = body.get("key"), str(body.get("value", ""))[:5000]
            if key not in TEXT_KEYS:
                return 400, {"error": "Неизвестное поле"}
            if key.endswith(("_url", "_photo")) and value and not value.startswith("https://"):
                return 400, {"error": "Ссылка должна начинаться с https://"}
            self.db.set_text(key, value)
            return 200, {"ok": True}
        if method == "POST" and path == "/api/admin/refresh":
            return 200, self.refresh()
        if method == "GET" and path == "/api/admin/stats":
            stats = self.db.stats()
            stats["last_refresh"] = self.db.get_meta("last_refresh", "ещё не было")
            return 200, stats
        return 404, {"error": "Не найдено"}

    def handle(self, method, path, body, init_data):
        if path.startswith("/api/admin/"):
            return self.admin(method, path, body, init_data)
        result = self.public(method, path, body)
        return result or (404, {"error": "Не найдено"})


def make_handler(app):
    web_root = Path(app.config.web_dir).resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = "miniapp"

        def log_message(self, fmt, *args):
            pass  # не пишем в журнал адреса и запросы пользователей

        def _send(self, status, data, ctype="application/json; charset=utf-8"):
            payload = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            if ctype.startswith("application/json"):
                self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def _api(self, method):
            path = urlparse(self.path).path
            body = {}
            if method == "POST":
                length = int(self.headers.get("Content-Length") or 0)
                if length > MAX_BODY:
                    return self._send(413, {"error": "Слишком большой запрос"})
                try:
                    body = json.loads(self.rfile.read(length) or b"{}")
                except ValueError:
                    return self._send(400, {"error": "Неверный JSON"})
                if not isinstance(body, dict):
                    return self._send(400, {"error": "Неверный JSON"})
            init_data = self.headers.get("X-Telegram-Init-Data", "")
            try:
                status, data = app.handle(method, path, body, init_data)
            except (TypeError, ValueError):
                status, data = 400, {"error": "Неверные данные"}
            self._send(status, data)

        def _static(self):
            rel = urlparse(self.path).path.lstrip("/") or "index.html"
            target = (web_root / rel).resolve()
            if web_root not in target.parents and target != web_root:
                return self._send(404, {"error": "Не найдено"})
            if target.is_dir():
                target = target / "index.html"
            if not target.is_file():
                return self._send(404, {"error": "Не найдено"})
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype.endswith("javascript"):
                ctype += "; charset=utf-8"
            self._send(200, target.read_bytes(), ctype)

        def do_GET(self):
            if urlparse(self.path).path.startswith("/api/"):
                return self._api("GET")
            self._static()

        def do_POST(self):
            if urlparse(self.path).path.startswith("/api/"):
                return self._api("POST")
            self._send(405, {"error": "Метод не поддерживается"})

    return Handler


def serve(config):
    app = App(config)
    server = ThreadingHTTPServer((config.host, config.port), make_handler(app))
    print(f"Мини-приложение: http://{config.host}:{config.port}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    cfg = Config()
    if len(sys.argv) > 1 and sys.argv[1] == "refresh":
        result = App(cfg).refresh()
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0 if result["ok"] else 1)
    serve(cfg)
