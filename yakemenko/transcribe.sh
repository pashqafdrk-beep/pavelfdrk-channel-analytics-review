#!/usr/bin/env bash
# Расшифровки интервью Якеменко.
# Шаг 1: берём субтитры YouTube (ручные или автоматические, русские).
# Шаг 2: если субтитров нет, скачиваем звук и расшифровываем через Whisper.
# Нужно: pip install -U yt-dlp openai-whisper ; и ffmpeg.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p transcripts audio
LIST=videos.txt

# Раскрываем плейлисты и убираем дубли
grep -v '^#' "$LIST" | grep -v '^$' \
  | xargs -n1 yt-dlp --flat-playlist --print "%(id)s" 2>/dev/null \
  | sort -u > ids.txt
echo "Видео к обработке: $(wc -l < ids.txt)"

while read -r id; do
  out="transcripts/$id.txt"
  [ -s "$out" ] && { echo "есть: $id"; continue; }
  url="https://www.youtube.com/watch?v=$id"
  title=$(yt-dlp --print "%(title)s | %(channel)s | %(upload_date)s" "$url" 2>/dev/null || echo "$id")

  yt-dlp --skip-download --write-subs --write-auto-subs --sub-langs "ru.*,ru" \
         --sub-format vtt -o "transcripts/%(id)s.%(ext)s" "$url" >/dev/null 2>&1 || true
  vtt=$(ls transcripts/"$id"*.vtt 2>/dev/null | head -1 || true)

  if [ -n "$vtt" ]; then
    # VTT -> чистый текст без тайм-кодов и повторов автосубтитров
    { echo "$title"; echo "$url"; echo "Источник: субтитры YouTube"; echo;
      grep -v -E '^(WEBVTT|Kind:|Language:|[0-9:.]+ -->|\s*$)' "$vtt" \
        | sed -E 's/<[^>]+>//g' | awk '!seen[$0]++'; } > "$out"
    rm -f transcripts/"$id"*.vtt
  else
    yt-dlp -x --audio-format mp3 -o "audio/%(id)s.%(ext)s" "$url"
    whisper "audio/$id.mp3" --language ru --model medium --output_format txt --output_dir audio
    { echo "$title"; echo "$url"; echo "Источник: Whisper medium"; echo;
      cat "audio/$id.txt"; } > "$out"
  fi
  echo "готово: $id"
done < ids.txt
