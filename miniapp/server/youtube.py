"""Загрузка видео канала через YouTube Data API v3 (только чтение публичных данных)."""
import json
import re
import urllib.parse
import urllib.request

from topics import classify

API = "https://www.googleapis.com/youtube/v3/"
SHORTS_MAX_SECONDS = 180  # с октября 2024 Shorts могут быть до 3 минут


def parse_duration(value):
    """ISO 8601 (PT1H2M3S) в секунды."""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def _get(path, params, fetch):
    url = API + path + "?" + urllib.parse.urlencode(params)
    return fetch(url)


def _fetch_json(url):
    with urllib.request.urlopen(url, timeout=20) as resp:
        return json.loads(resp.read().decode())


def to_row(item):
    snippet = item["snippet"]
    duration = parse_duration(item["contentDetails"].get("duration"))
    thumbs = snippet.get("thumbnails", {})
    thumb = (thumbs.get("medium") or thumbs.get("high") or thumbs.get("default") or {}).get("url", "")
    return {
        "id": item["id"],
        "title": snippet["title"],
        "published": snippet["publishedAt"][:10],
        "duration": duration,
        "thumbnail": thumb,
        "format": "shorts" if 0 < duration <= SHORTS_MAX_SECONDS else "video",
        "topic": classify(snippet["title"]),
    }


def fetch_channel_videos(api_key, handle, fetch=_fetch_json, limit=500):
    channel = _get("channels", {"part": "contentDetails", "forHandle": handle, "key": api_key}, fetch)
    items = channel.get("items") or []
    if not items:
        raise RuntimeError(f"Канал @{handle} не найден")
    uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    ids, token = [], None
    while len(ids) < limit:
        params = {"part": "contentDetails", "playlistId": uploads, "maxResults": 50, "key": api_key}
        if token:
            params["pageToken"] = token
        page = _get("playlistItems", params, fetch)
        ids += [it["contentDetails"]["videoId"] for it in page.get("items", [])]
        token = page.get("nextPageToken")
        if not token:
            break

    rows = []
    for i in range(0, len(ids), 50):
        batch = _get("videos", {"part": "snippet,contentDetails", "id": ",".join(ids[i:i + 50]),
                                "key": api_key}, fetch)
        rows += [to_row(it) for it in batch.get("items", [])
                 if it["snippet"].get("liveBroadcastContent", "none") == "none"]
    return rows


def refresh(db, config, fetch=_fetch_json):
    rows = fetch_channel_videos(config.youtube_api_key, config.youtube_handle, fetch)
    for row in rows:
        db.upsert_video(row)
    return len(rows)
