#!/usr/bin/env bash
# Установка и обновление мини-приложения на сервере Ubuntu/Debian.
# Запуск из папки miniapp:  sudo bash deploy/install.sh
# Повторный запуск обновляет код и не трогает базу и настройки.
set -euo pipefail

APP_DIR=/opt/pavel-miniapp
ENV_FILE=/etc/pavel-miniapp.env
DATA_DIR=/var/lib/pavel-miniapp
NGINX_SITE=/etc/nginx/sites-available/pavel-miniapp
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

say() { printf '\n\033[1;33m▶ %s\033[0m\n' "$*"; }
fail() { printf '\n\033[1;31m✖ %s\033[0m\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || fail "Запустите через sudo: sudo bash deploy/install.sh"
[[ -f "$SRC_DIR/server/app.py" && -d "$SRC_DIR/web" ]] || fail "Не найдены папки server и web рядом со скриптом"
command -v apt-get >/dev/null || fail "Скрипт рассчитан на Ubuntu или Debian"

say "Ставлю пакеты: python3, nginx, certbot"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 nginx certbot python3-certbot-nginx curl >/dev/null

# Настройки: спрашиваем только при первой установке
if [[ -f "$ENV_FILE" ]]; then
  say "Файл настроек уже есть, оставляю как есть: $ENV_FILE"
  DOMAIN="$(grep -E '^DOMAIN=' "$ENV_FILE" | cut -d= -f2-)"
  [[ -n "$DOMAIN" ]] || read -rp "Домен (например, app.example.ru): " DOMAIN
else
  say "Нужны 4 значения. Они сохранятся только в $ENV_FILE на этом сервере."
  read -rp "Домен, уже направленный на этот сервер (например, app.example.ru): " DOMAIN
  read -rsp "Токен бота из @BotFather (ввод скрыт): " BOT_TOKEN; echo
  read -rp "Ваш Telegram ID (число; несколько через запятую): " ADMIN_IDS
  read -rsp "Ключ YouTube Data API (ввод скрыт): " YOUTUBE_API_KEY; echo
  [[ "$BOT_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]] || fail "Токен бота выглядит неверно"
  [[ "$ADMIN_IDS" =~ ^[0-9]+(,[0-9]+)*$ ]] || fail "Telegram ID должен быть числом"
  [[ -n "$YOUTUBE_API_KEY" ]] || fail "Ключ YouTube пустой"
  umask 077
  cat > "$ENV_FILE" <<EOF
DOMAIN=$DOMAIN
BOT_TOKEN=$BOT_TOKEN
ADMIN_IDS=$ADMIN_IDS
YOUTUBE_API_KEY=$YOUTUBE_API_KEY
YOUTUBE_HANDLE=pavelfdrk
DB_PATH=$DATA_DIR/miniapp.db
HOST=127.0.0.1
PORT=8080
EOF
  umask 022
  unset BOT_TOKEN YOUTUBE_API_KEY
fi
[[ "$DOMAIN" =~ ^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]] || fail "Домен выглядит неверно: $DOMAIN"

say "Пользователь и файлы приложения"
id miniapp >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin miniapp
chown root:miniapp "$ENV_FILE"
chmod 640 "$ENV_FILE"
mkdir -p "$APP_DIR"
rm -rf "$APP_DIR/server" "$APP_DIR/web"
cp -r "$SRC_DIR/server" "$SRC_DIR/web" "$APP_DIR/"
find "$APP_DIR" -name '__pycache__' -prune -exec rm -rf {} +
chown -R root:root "$APP_DIR"

say "Сервис и автообновление видео раз в 6 часов"
cp "$SRC_DIR/deploy/pavel-miniapp.service" \
   "$SRC_DIR/deploy/pavel-miniapp-refresh.service" \
   "$SRC_DIR/deploy/pavel-miniapp-refresh.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now pavel-miniapp.service pavel-miniapp-refresh.timer >/dev/null
systemctl restart pavel-miniapp.service

say "nginx для https://$DOMAIN/app/"
if [[ ! -f "$NGINX_SITE" ]]; then
  cat > "$NGINX_SITE" <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    location = /app { return 301 /app/; }
    location /app/ {
        proxy_pass http://127.0.0.1:8080/;
        proxy_set_header Host \$host;
        client_max_body_size 64k;
    }
}
EOF
  ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/pavel-miniapp
fi
nginx -t
systemctl reload nginx

if [[ ! -d "/etc/letsencrypt/live/$DOMAIN" ]]; then
  say "Получаю бесплатный сертификат HTTPS (Let's Encrypt)"
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect
fi

say "Первая загрузка видео с YouTube"
systemctl start pavel-miniapp-refresh.service || echo "Не получилось. Причина: journalctl -u pavel-miniapp-refresh"

say "Проверка"
sleep 1
if curl -fsS "https://$DOMAIN/app/api/content" -o /dev/null; then
  COUNT="$(curl -fsS "https://$DOMAIN/app/api/content" | python3 -c 'import json,sys;print(len(json.load(sys.stdin)["videos"]))')"
  printf '\n\033[1;32m✔ Готово. Приложение: https://%s/app/  Видео загружено: %s\033[0m\n' "$DOMAIN" "$COUNT"
  echo "Дальше: @BotFather → /mybots → ваш бот → Bot Settings → Menu Button → https://$DOMAIN/app/"
else
  fail "Адрес https://$DOMAIN/app/ не отвечает. Журнал: journalctl -u pavel-miniapp"
fi
