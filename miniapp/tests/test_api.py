"""Проверка через настоящий HTTP-сервер: админ-функции работают только с правильной подписью."""
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

from helpers import ADMIN_ID, BOT_TOKEN, OTHER_ID, init_data
from app import App, make_handler
from config import Config
from db import Database
from youtube import parse_duration

ADMIN_ROUTES = [
    ("GET", "/api/admin/me", None),
    ("GET", "/api/admin/videos", None),
    ("POST", "/api/admin/video", {"id": "v1", "hidden": True}),
    ("GET", "/api/admin/books", None),
    ("POST", "/api/admin/book", {"id": 1, "title": "Взлом"}),
    ("POST", "/api/admin/text", {"key": "about_text", "value": "Взлом"}),
    ("POST", "/api/admin/refresh", {}),
    ("GET", "/api/admin/stats", None),
]


def fake_youtube(url):
    if "/channels?" in url:
        return {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]}
    if "/playlistItems?" in url:
        return {"items": [{"contentDetails": {"videoId": "v1"}}, {"contentDetails": {"videoId": "v2"}}]}
    return {"items": [
        {"id": "v1", "snippet": {"title": "Что делать при панической атаке", "publishedAt": "2026-09-01T10:00:00Z",
                                 "thumbnails": {"medium": {"url": "https://i.ytimg.com/vi/v1/mqdefault.jpg"}}},
         "contentDetails": {"duration": "PT14M5S"}},
        {"id": "v2", "snippet": {"title": "Откуда берётся тревога", "publishedAt": "2026-09-10T10:00:00Z", "thumbnails": {}},
         "contentDetails": {"duration": "PT45S"}},
    ]}


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        web = Path(cls.tmp.name) / "web"
        web.mkdir()
        (web / "index.html").write_text("ok")
        cfg = Config({"BOT_TOKEN": BOT_TOKEN, "ADMIN_IDS": str(ADMIN_ID), "YOUTUBE_API_KEY": "k",
                      "WEB_DIR": str(web), "DB_PATH": ":memory:"})
        cls.app = App(cfg, db=Database(":memory:"), fetch=fake_youtube)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.app))
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.app.refresh()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    def call(self, method, path, body=None, init=None):
        data = None if method == "GET" else json.dumps(body or {}).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if init is not None:
            req.add_header("X-Telegram-Init-Data", init)
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read() or b"{}")

    def assert_all_admin_routes(self, init, expected):
        for method, path, body in ADMIN_ROUTES:
            with self.subTest(path=path):
                status, _ = self.call(method, path, body, init)
                self.assertEqual(status, expected)

    # Защита админки
    def test_no_init_data_forbidden(self):
        self.assert_all_admin_routes(None, 403)

    def test_forged_hash_forbidden(self):
        fields = dict(parse_qsl(init_data()))
        fields["hash"] = "f" * 64
        self.assert_all_admin_routes(urlencode(fields), 403)

    def test_signed_with_other_token_forbidden(self):
        self.assert_all_admin_routes(init_data(token="999:attacker"), 403)

    def test_user_id_swapped_after_signing_forbidden(self):
        fields = dict(parse_qsl(init_data(user_id=OTHER_ID)))
        fields["user"] = fields["user"].replace(str(OTHER_ID), str(ADMIN_ID))
        self.assert_all_admin_routes(urlencode(fields), 403)

    def test_valid_signature_but_not_admin_forbidden(self):
        self.assert_all_admin_routes(init_data(user_id=OTHER_ID), 403)

    def test_expired_admin_forbidden(self):
        self.assert_all_admin_routes(init_data(auth_date=time.time() - 3 * 86400), 403)

    def test_forbidden_requests_change_nothing(self):
        before = self.app.db.texts()["about_text"]
        self.call("POST", "/api/admin/text", {"key": "about_text", "value": "Взлом"}, init_data(user_id=OTHER_ID))
        self.assertEqual(self.app.db.texts()["about_text"], before)

    def test_admin_with_valid_signature_allowed(self):
        status, data = self.call("GET", "/api/admin/me", init=init_data())
        self.assertEqual((status, data["ok"]), (200, True))

    # Работа админки
    def test_admin_hides_and_retopics_video(self):
        status, _ = self.call("POST", "/api/admin/video", {"id": "v2", "hidden": True}, init_data())
        self.assertEqual(status, 200)
        _, content = self.call("GET", "/api/content")
        self.assertNotIn("v2", [v["id"] for v in content["videos"]])
        self.call("POST", "/api/admin/video", {"id": "v2", "hidden": False, "topic": "Невроз"}, init_data())
        self.app.refresh()  # повторная загрузка не затирает ручную тему
        _, content = self.call("GET", "/api/content")
        self.assertEqual(next(v for v in content["videos"] if v["id"] == "v2")["topic"], "Невроз")

    def test_admin_rejects_unknown_topic_and_bad_links(self):
        self.assertEqual(self.call("POST", "/api/admin/video", {"id": "v1", "topic": "Кот"}, init_data())[0], 400)
        self.assertEqual(self.call("POST", "/api/admin/book", {"id": 1, "link": "javascript:alert(1)"}, init_data())[0], 400)
        self.assertEqual(self.call("POST", "/api/admin/text", {"key": "telegram_url", "value": "http://x"}, init_data())[0], 400)
        self.assertEqual(self.call("POST", "/api/admin/text", {"key": "secret", "value": "x"}, init_data())[0], 400)

    # Публичная часть
    def test_content_and_formats(self):
        status, content = self.call("GET", "/api/content")
        self.assertEqual(status, 200)
        by_id = {v["id"]: v for v in content["videos"]}
        self.assertEqual(by_id["v1"]["format"], "video")
        self.assertEqual(by_id["v1"]["topic"], "Панические атаки")
        self.assertEqual(by_id["v2"]["format"], "shorts")
        books = content["books"]
        self.assertEqual(len(books), 9)
        self.assertEqual(books[0]["title"], "Три уровня тревоги")
        self.assertEqual(books[1]["series"], "Серия «Тревожные расстройства»")
        self.assertTrue(all(b["description"] for b in books))
        self.assertNotIn("hidden", by_id["v1"])

    def test_events_counted_without_personal_data(self):
        self.assertEqual(self.call("POST", "/api/event", {"event": "video_click", "item": "v1"})[0], 200)
        self.assertEqual(self.call("POST", "/api/event", {"event": "video_click", "item": "nope"})[0], 400)
        self.assertEqual(self.call("POST", "/api/event", {"event": "drop_table"})[0], 400)
        self.call("POST", "/api/event", {"event": "test_done", "item": "answers=3,3,3"})
        _, stats = self.call("GET", "/api/admin/stats", init=init_data())
        self.assertIn("v1", [v["id"] for v in stats["top_videos"]])
        items = [r[0] for r in self.app.db.conn.execute("SELECT item FROM stats_daily WHERE event='test_done'")]
        self.assertEqual(items, [""])

    def test_static_path_traversal_blocked(self):
        self.assertEqual(self.call("GET", "/../../etc/passwd")[0], 404)
        self.assertEqual(self.call("GET", "/%2e%2e/%2e%2e/etc/passwd")[0], 404)


class DurationTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_duration("PT45S"), 45)
        self.assertEqual(parse_duration("PT1H2M3S"), 3723)
        self.assertEqual(parse_duration("P0D"), 0)
        self.assertEqual(parse_duration("bad"), 0)


if __name__ == "__main__":
    unittest.main()
