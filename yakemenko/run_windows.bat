@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Устанавливаю нужные программы...
python -m pip install -U yt-dlp faster-whisper

python yakemenko.py %*
echo.
echo Откройте файл ВСЕ_РАСШИФРОВКИ.txt в этой папке.
pause
