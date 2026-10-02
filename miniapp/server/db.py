"""База SQLite: видео, книги, тексты, счётчики статистики."""
import datetime
import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  published TEXT NOT NULL,
  duration INTEGER NOT NULL DEFAULT 0,
  thumbnail TEXT NOT NULL DEFAULT '',
  format TEXT NOT NULL DEFAULT 'video',
  topic TEXT NOT NULL,
  topic_manual INTEGER NOT NULL DEFAULT 0,
  hidden INTEGER NOT NULL DEFAULT 0,
  pinned INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS books (
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  cover TEXT NOT NULL DEFAULT '',
  link TEXT NOT NULL DEFAULT '',
  position INTEGER NOT NULL DEFAULT 0,
  hidden INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS texts (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stats_daily (
  day TEXT NOT NULL,
  event TEXT NOT NULL,
  item TEXT NOT NULL DEFAULT '',
  count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (day, event, item)
);
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""

# Заглушки: настоящие описания, ссылки и тексты заполняются в админке.
DEFAULT_BOOKS = [
    ("Три уровня тревоги", "Описание книги появится здесь.", 1),
    ("Жить чужой жизнью", "Описание книги появится здесь.", 2),
]
DEFAULT_TEXTS = {
    "about_name": "Павел Федоренко",
    "about_role": "Психолог",
    "about_text": "Здесь будет рассказ об авторе.",
    "about_photo": "",
    "youtube_url": "https://www.youtube.com/@pavelfdrk",
    "telegram_url": "",
}
TEXT_KEYS = set(DEFAULT_TEXTS)


class Database:
    def __init__(self, path):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock, self.conn:
            self.conn.executescript(SCHEMA)
            if not self.conn.execute("SELECT 1 FROM books LIMIT 1").fetchone():
                self.conn.executemany(
                    "INSERT INTO books (title, description, position) VALUES (?, ?, ?)", DEFAULT_BOOKS
                )
            self.conn.executemany(
                "INSERT OR IGNORE INTO texts (key, value) VALUES (?, ?)", DEFAULT_TEXTS.items()
            )

    def _all(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def _run(self, sql, args=()):
        with self.lock, self.conn:
            return self.conn.execute(sql, args).rowcount

    # Видео
    def videos(self, include_hidden=False):
        where = "" if include_hidden else "WHERE hidden = 0"
        return self._all(f"SELECT * FROM videos {where} ORDER BY pinned DESC, published DESC")

    def video_exists(self, video_id):
        return bool(self._all("SELECT 1 FROM videos WHERE id = ?", (video_id,)))

    def upsert_video(self, v):
        """Новые данные с YouTube. Ручная тема, скрытие и закрепление сохраняются."""
        self._run(
            """INSERT INTO videos (id, title, published, duration, thumbnail, format, topic)
               VALUES (:id, :title, :published, :duration, :thumbnail, :format, :topic)
               ON CONFLICT(id) DO UPDATE SET
                 title = excluded.title, published = excluded.published,
                 duration = excluded.duration, thumbnail = excluded.thumbnail,
                 format = excluded.format,
                 topic = CASE WHEN videos.topic_manual THEN videos.topic ELSE excluded.topic END""",
            v,
        )

    def update_video(self, video_id, hidden=None, pinned=None, topic=None):
        sets, args = [], []
        if hidden is not None:
            sets.append("hidden = ?"); args.append(int(bool(hidden)))
        if pinned is not None:
            sets.append("pinned = ?"); args.append(int(bool(pinned)))
        if topic is not None:
            sets.append("topic = ?, topic_manual = 1"); args.append(topic)
        if not sets:
            return 0
        return self._run(f"UPDATE videos SET {', '.join(sets)} WHERE id = ?", (*args, video_id))

    # Книги
    def books(self, include_hidden=False):
        where = "" if include_hidden else "WHERE hidden = 0"
        return self._all(f"SELECT * FROM books {where} ORDER BY position, id")

    def update_book(self, book_id, fields):
        allowed = {"title", "description", "cover", "link", "position", "hidden"}
        fields = {k: v for k, v in fields.items() if k in allowed}
        if not fields:
            return 0
        sets = ", ".join(f"{k} = ?" for k in fields)
        return self._run(f"UPDATE books SET {sets} WHERE id = ?", (*fields.values(), book_id))

    # Тексты
    def texts(self):
        return {r["key"]: r["value"] for r in self._all("SELECT key, value FROM texts")}

    def set_text(self, key, value):
        return self._run("UPDATE texts SET value = ? WHERE key = ?", (value, key))

    # Служебное
    def get_meta(self, key, default=""):
        rows = self._all("SELECT value FROM meta WHERE key = ?", (key,))
        return rows[0]["value"] if rows else default

    def set_meta(self, key, value):
        self._run("INSERT INTO meta (key, value) VALUES (?, ?) "
                  "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))

    # Статистика: только счётчики по дням, без данных о людях
    def count_event(self, event, item="", day=None):
        day = day or datetime.date.today().isoformat()
        self._run(
            """INSERT INTO stats_daily (day, event, item, count) VALUES (?, ?, ?, 1)
               ON CONFLICT(day, event, item) DO UPDATE SET count = count + 1""",
            (day, event, item),
        )

    def stats(self, days=30):
        since = (datetime.date.today() - datetime.timedelta(days=days - 1)).isoformat()
        by_day = self._all(
            "SELECT day, event, SUM(count) AS count FROM stats_daily WHERE day >= ? "
            "GROUP BY day, event ORDER BY day", (since,))
        top_videos = self._all(
            "SELECT s.item AS id, v.title, SUM(s.count) AS count FROM stats_daily s "
            "LEFT JOIN videos v ON v.id = s.item WHERE s.event = 'video_click' AND s.day >= ? "
            "GROUP BY s.item ORDER BY count DESC LIMIT 10", (since,))
        return {"days": days, "by_day": by_day, "top_videos": top_videos}
