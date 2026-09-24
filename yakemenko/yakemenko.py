#!/usr/bin/env python3
"""
Находит на YouTube все интервью и подкасты с Василием Якеменко
и делает по каждому текстовую расшифровку.

Что делает программа:
  1. Ищет видео по набору запросов на YouTube и добавляет ролики из videos.txt
     (там можно указывать отдельные видео, плейлисты и каналы).
  2. Отбирает ролики, где в названии или описании есть «Якеменко».
     Отсеивает шортсы, ролики про Бориса Якеменко и разборы других блогеров.
  3. Сохраняет список в found.csv.
  4. Для каждого видео берёт русские субтитры YouTube. Если их нет,
     скачивает звук и расшифровывает его через faster-whisper.
  5. Кладёт тексты в папку transcripts/ с отметками времени.

Установка (один раз):
  pip install -U yt-dlp faster-whisper
  и ffmpeg (Windows: winget install ffmpeg; macOS: brew install ffmpeg)

Запуск:
  python yakemenko.py                 # найти и расшифровать всё
  python yakemenko.py --only-search   # только найти и показать список
  python yakemenko.py --cookies-from-browser chrome   # если YouTube просит войти
"""
import argparse
import csv
import re
import sys
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    sys.exit("Не установлен yt-dlp. Выполните: pip install -U yt-dlp faster-whisper")

HERE = Path(__file__).resolve().parent

QUERIES = [
    "Василий Якеменко интервью",
    "Василий Якеменко подкаст",
    "Василий Якеменко разговор",
    "Якеменко экс-министр",
    "Якеменко Наши Росмолодежь интервью",
    "Василий Якеменко",
    "Василий Якименко интервью",
]

NAME = re.compile(r"як[еи]менк", re.I)
BROTHER = re.compile(r"борис", re.I)
# Признаки чужих разборов: там Якеменко почти не говорит сам.
REACTION = re.compile(
    r"разбор|посмотрел|реакци|обсудим|манипуляц|демагог|реагиру|что сказал|что рассказал", re.I
)


def ydl(opts, args):
    base = {"quiet": True, "no_warnings": True, "ignoreerrors": True}
    if args.cookies_from_browser:
        base["cookiesfrombrowser"] = (args.cookies_from_browser,)
    if args.cookies:
        base["cookiefile"] = args.cookies
    base.update(opts)
    return yt_dlp.YoutubeDL(base)


def flat_entries(url, args):
    with ydl({"extract_flat": "in_playlist"}, args) as y:
        info = y.extract_info(url, download=False)
    if not info:
        return []
    entries = info.get("entries")
    if entries is None:
        return [info]
    out = []
    for e in entries:
        if not e:
            continue
        if e.get("_type") == "playlist" or e.get("ie_key") == "YoutubeTab":
            out += flat_entries(e["url"], args)  # вкладки канала, вложенные плейлисты
        else:
            out.append(e)
    return out


def classify(e):
    title = e.get("title") or ""
    desc = e.get("description") or ""
    text = f"{title}\n{desc}"
    if not NAME.search(text):
        return "нет упоминания"
    if BROTHER.search(title) and "василий" not in title.lower():
        return "Борис Якеменко"
    dur = e.get("duration") or 0
    if dur and dur < args_global.min_minutes * 60:
        return "короткое"
    if REACTION.search(title):
        return "разбор/реакция"
    return "интервью"


def search(args):
    found = {}
    sources = [f"ytsearch{args.per_query}:{q}" for q in QUERIES]
    seeds = HERE / "videos.txt"
    if seeds.exists():
        seeds_list = [l.strip() for l in seeds.read_text(encoding="utf-8").splitlines()
                      if l.strip() and not l.startswith("#")]
    else:
        seeds_list = []
    for src in sources + seeds_list:
        print(f"Поиск: {src}")
        for e in flat_entries(src, args):
            vid = e.get("id")
            if not vid or vid in found:
                continue
            e["_seed"] = src in seeds_list
            found[vid] = e

    rows = []
    for vid, e in found.items():
        kind = classify(e)
        if e["_seed"] and kind in ("нет упоминания",):
            kind = "интервью"  # ручной список и канал КиноКлуба берём как есть
        rows.append({
            "id": vid,
            "title": e.get("title") or "",
            "channel": e.get("channel") or e.get("uploader") or "",
            "minutes": round((e.get("duration") or 0) / 60),
            "views": e.get("view_count") or "",
            "kind": kind,
            "url": f"https://www.youtube.com/watch?v={vid}",
        })
    rows = [r for r in rows if r["kind"] != "нет упоминания"]
    rows.sort(key=lambda r: (r["kind"] != "интервью", r["title"]))
    with open(HERE / "found.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["id"], delimiter=";")
        w.writeheader()
        w.writerows(rows)
    md = ["# Найденные видео с Василием Якеменко", "",
          f"Всего: {len(rows)}. Интервью и подкасты: {sum(r['kind'] == 'интервью' for r in rows)}.", "",
          "| Тип | Мин | Название | Канал |", "|---|---|---|---|"]
    for r in rows:
        t = r["title"].replace("|", "/")
        md.append(f"| {r['kind']} | {r['minutes']} | [{t}]({r['url']}) | {r['channel'].replace('|', '/')} |")
    (HERE / "found.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return rows


def ts(sec):
    sec = int(sec)
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def vtt_to_segments(path):
    """Субтитры VTT -> [(секунды, текст)] без повторов автосубтитров."""
    segs, last, start = [], None, 0.0
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"(\d+):(\d+):([\d.]+) -->", line)
        if m:
            start = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
            continue
        if not line.strip() or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        text = re.sub(r"<[^>]+>", "", line).strip()
        if text and text != last:
            segs.append((start, text))
            last = text
    return segs


def paragraphs(segs, every=60):
    out, buf, t0 = [], [], None
    for t, text in segs:
        if t0 is None:
            t0 = t
        buf.append(text)
        if t - t0 >= every and text.rstrip().endswith((".", "?", "!", "…")) or t - t0 >= every * 2:
            out.append(f"[{ts(t0)}] " + " ".join(buf))
            buf, t0 = [], None
    if buf:
        out.append(f"[{ts(t0)}] " + " ".join(buf))
    return out


_whisper = None


def whisper_segments(audio, args):
    global _whisper
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("Для видео без субтитров нужен faster-whisper: pip install -U faster-whisper")
    if _whisper is None:
        print(f"  Загружаю модель Whisper «{args.model}» (первый раз долго)…")
        _whisper = WhisperModel(args.model, device="auto", compute_type="auto")
    segs, _ = _whisper.transcribe(str(audio), language="ru", vad_filter=True)
    return [(s.start, s.text.strip()) for s in segs]


def safe(name):
    return re.sub(r'[\\/:*?"<>|\n]+', " ", name).strip()[:80]


def transcribe(row, args):
    out_dir = HERE / "transcripts"
    tmp = HERE / "tmp"
    out_dir.mkdir(exist_ok=True)
    tmp.mkdir(exist_ok=True)
    vid = row["id"]
    done = list(out_dir.glob(f"*{vid}*.txt"))
    if done:
        print(f"  уже есть: {done[0].name}")
        return

    info, client_opts = None, {}
    for clients in (None, ["tv_simply"], ["web_safari"], ["mweb"], ["android_vr"]):
        client_opts = {"extractor_args": {"youtube": {"player_client": clients}}} if clients else {}
        try:
            with ydl({"ignoreerrors": False, **client_opts}, args) as y:
                info = y.extract_info(row["url"], download=False)
            break
        except Exception as ex:
            print(f"  [{clients or 'обычный'}] {str(ex).splitlines()[0][:200]}")
    if not info:
        print("  не удалось открыть видео, пропускаю")
        return
    date = info.get("upload_date") or "00000000"
    date = f"{date[:4]}-{date[4:6]}-{date[6:]}"

    segs, source = [], ""
    if not args.whisper_always:
        with ydl({"skip_download": True, "writesubtitles": True, "writeautomaticsub": True,
                  "subtitleslangs": ["ru", "ru-orig", "ru.*"], "subtitlesformat": "vtt",
                  "outtmpl": str(tmp / "%(id)s"), **client_opts}, args) as y:
            y.download([row["url"]])
        subs = sorted(tmp.glob(f"{vid}*.vtt"))
        manual = any(k.startswith("ru") for k in (info.get("subtitles") or {}))
        if subs:
            segs = vtt_to_segments(subs[0])
            source = "ручные субтитры YouTube" if manual else "автосубтитры YouTube"
        for p in subs:
            p.unlink()

    if not segs:
        print("  субтитров нет, расшифровываю звук через Whisper…")
        # Звук берём как есть: faster-whisper сам читает m4a/webm, отдельный ffmpeg не нужен
        with ydl({"format": "bestaudio[ext=m4a]/bestaudio/best", "outtmpl": str(tmp / "%(id)s.%(ext)s"),
                  **client_opts}, args) as y:
            y.download([row["url"]])
        audio = next(tmp.glob(f"{vid}.*"), None)
        if not audio:
            print("  не удалось скачать звук, пропускаю")
            return
        segs = whisper_segments(audio, args)
        source = f"Whisper ({args.model})"
        audio.unlink()

    name = out_dir / f"{date}_{vid}_{safe(info.get('title', vid))}.txt"
    header = [
        info.get("title", ""),
        f"Канал: {info.get('channel') or info.get('uploader') or ''}",
        f"Дата: {date}",
        f"Длительность: {ts(info.get('duration') or 0)}",
        f"Ссылка: {row['url']}",
        f"Источник текста: {source}",
        "",
    ]
    name.write_text("\n".join(header + paragraphs(segs)) + "\n", encoding="utf-8")
    print(f"  готово: {name.name}")


def main():
    global args_global
    p = argparse.ArgumentParser(description="Поиск и расшифровка интервью Василия Якеменко")
    p.add_argument("--only-search", action="store_true", help="только найти видео, без расшифровки")
    p.add_argument("--include-reactions", action="store_true", help="расшифровать и разборы других блогеров")
    p.add_argument("--per-query", type=int, default=50, help="сколько результатов брать на каждый запрос")
    p.add_argument("--min-minutes", type=int, default=10, help="отсеять ролики короче (минут)")
    p.add_argument("--model", default="medium", help="модель Whisper: small, medium, large-v3")
    p.add_argument("--whisper-always", action="store_true", help="не брать субтитры YouTube, всё через Whisper")
    p.add_argument("--cookies", help="файл cookies.txt (формат Netscape) для входа в YouTube")
    p.add_argument("--cookies-from-browser", help="chrome, firefox, edge… если YouTube требует вход")
    args_global = args = p.parse_args()

    rows = search(args)
    take = [r for r in rows if r["kind"] == "интервью" or (args.include_reactions and r["kind"] == "разбор/реакция")]
    print(f"\nНайдено с упоминанием Якеменко: {len(rows)}. К расшифровке: {len(take)}.")
    print("Полный список с пометками: found.csv\n")
    for r in rows:
        print(f"  [{r['kind']}] {r['minutes']:>4} мин | {r['title']} | {r['channel']}")
    if args.only_search:
        return
    for i, r in enumerate(take, 1):
        print(f"\n({i}/{len(take)}) {r['title']}")
        try:
            transcribe(r, args)
        except Exception as ex:  # одно сломанное видео не должно останавливать остальные
            print(f"  ошибка: {ex}")
    combine()


def combine():
    """Склеивает все расшифровки в один файл."""
    files = sorted((HERE / "transcripts").glob("*.txt"))
    if not files:
        print("\nРасшифровок нет. Посмотрите ошибки выше.")
        return
    total = HERE / "ВСЕ_РАСШИФРОВКИ.txt"
    sep = "\n\n" + "=" * 80 + "\n\n"
    total.write_text(sep.join(f.read_text(encoding="utf-8") for f in files), encoding="utf-8")
    print(f"\nГотово. Отдельные тексты: transcripts/ ({len(files)} шт.)")
    print(f"Всё одним файлом: {total}")


if __name__ == "__main__":
    main()
