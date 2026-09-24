#!/bin/bash
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null; then
  echo "Нет Python. Установите его с https://www.python.org/downloads/ и запустите снова."
  read -p "Нажмите Enter..."; exit 1
fi
echo "Готовлю программы (первый раз несколько минут)..."
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q -U pip yt-dlp faster-whisper
.venv/bin/python yakemenko.py --cookies-from-browser safari "$@" \
  || .venv/bin/python yakemenko.py "$@"
echo
echo "Готово. Откройте файл ВСЕ_РАСШИФРОВКИ.txt в этой папке."
open .
read -p "Нажмите Enter, чтобы закрыть окно..."
