#!/bin/bash
# Одна команда для Mac: скачать программу, установить и запустить.
# Использование: curl -sL <ссылка на этот файл> | bash
# Или только нужные видео: curl -sL <ссылка> | bash -s -- "https://youtu.be/..."
set -e
RAW="https://raw.githubusercontent.com/pashqafdrk-beep/pavelfdrk-channel-analytics-review/claude/yakemenko-interview-transcripts-o97e92/yakemenko"
DIR="$HOME/Desktop/Якеменко"
mkdir -p "$DIR" && cd "$DIR"
curl -sL "$RAW/yakemenko.py" -o yakemenko.py
curl -sL "$RAW/videos.txt" -o videos.txt
if ! command -v python3 >/dev/null; then
  echo "Нет Python. Установите с https://www.python.org/downloads/ и повторите команду."; exit 1
fi
echo "Устанавливаю (первый раз несколько минут)..."
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q -U pip yt-dlp faster-whisper
.venv/bin/python yakemenko.py "$@"
open "$DIR"
