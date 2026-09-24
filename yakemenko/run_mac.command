#!/bin/bash
cd "$(dirname "$0")"
echo "Устанавливаю нужные программы..."
python3 -m pip install -U yt-dlp faster-whisper
command -v ffmpeg >/dev/null || brew install ffmpeg
python3 yakemenko.py "$@"
echo
echo "Откройте файл ВСЕ_РАСШИФРОВКИ.txt в этой папке."
open . 2>/dev/null
