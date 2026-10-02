# Мини-приложение Павла Федоренко

Видео с YouTube по темам канала, тест на тревогу GAD-7, книги, страница об авторе и админ-панель.
Сервер на Python 3 без сторонних библиотек, база SQLite, интерфейс на чистом HTML/CSS/JS.

```
server/   app.py (сервер и API), auth.py (проверка подписи Telegram), db.py, youtube.py, topics.py, config.py
web/      index.html, app.css, app.js, gad7.js, privacy.html
tests/    тесты
deploy/   systemd, nginx, пример файла настроек
```

## Перед запуском обязательно

1. **Текст теста GAD-7** в `web/gad7.js` сейчас черновой перевод. Замените 7 вопросов, вступление и варианты ответов официальным русским переводом с сайта phqscreeners.com. Баллы и пороги трогать не нужно.
2. В админке впишите ссылки «Купить», обложки, текст об авторе, фото и ссылку на Телеграм-канал. Девять книг с описаниями уже стоят: названия из базы «Книги» в Ноушене, описания из подзаголовков рукописей.

## Проверка на своём компьютере

```bash
cd miniapp
python3 -m unittest discover -s tests -t tests   # 30 тестов, в том числе защита админки
node --test tests/gad7.test.js                    # подсчёт баллов GAD-7
PORT=8080 python3 server/app.py                   # открыть http://127.0.0.1:8080/
```

Тесты `tests/test_api.py` и `tests/test_auth.py` доказывают: без правильной подписи Telegram, с чужим токеном, с подменённым ID, с просроченными данными или с подписью обычного пользователя каждый админ-маршрут отвечает 403 и ничего не меняет.

## Выкладка на VPS одной командой (Ubuntu/Debian)

Заранее: домен (или поддомен) направлен на IP сервера, токен бота, ваш Telegram ID, ключ YouTube.

```bash
git clone -b claude/trusting-brahmagupta-lmbc70 https://github.com/pashqafdrk-beep/pavelfdrk-channel-analytics-review.git
cd pavelfdrk-channel-analytics-review/miniapp
sudo bash deploy/install.sh
```

Скрипт поставит python3, nginx и certbot, спросит 4 значения (токен и ключ вводятся скрыто), настроит сервис, HTTPS и автообновление видео, загрузит видео и проверит адрес.
**Обновить код потом:** `git pull` в той же папке и снова `sudo bash deploy/install.sh`. Вопросы повторно не задаются, база не трогается.

## Выкладка вручную (запасной вариант)

Нужно: Python 3.10+, nginx, домен с HTTPS (Telegram открывает мини-приложения только по https).

```bash
# 1. Пользователь и файлы
sudo useradd --system --no-create-home miniapp
sudo mkdir -p /opt/pavel-miniapp
sudo cp -r server web /opt/pavel-miniapp/

# 2. Настройки (секреты только здесь)
sudo cp deploy/env.example /etc/pavel-miniapp.env
sudo nano /etc/pavel-miniapp.env          # вписать BOT_TOKEN, ADMIN_IDS, YOUTUBE_API_KEY
sudo chown root:miniapp /etc/pavel-miniapp.env
sudo chmod 640 /etc/pavel-miniapp.env

# 3. Сервис и автообновление раз в 6 часов
sudo cp deploy/pavel-miniapp.service deploy/pavel-miniapp-refresh.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pavel-miniapp pavel-miniapp-refresh.timer
sudo systemctl start pavel-miniapp-refresh   # первая загрузка видео сразу

# 4. nginx: вставить deploy/nginx.conf в server { } вашего домена
sudo nginx -t && sudo systemctl reload nginx
```

Проверка: `https://ваш-домен/app/` открывается в браузере, видео на месте.
Журнал: `journalctl -u pavel-miniapp -u pavel-miniapp-refresh`.

## Где взять значения для настроек

- **BOT_TOKEN.** В @BotFather: `/newbot`, он выдаст токен.
- **ADMIN_IDS.** Ваш числовой Telegram ID. Несколько админов через запятую.
- **YOUTUBE_API_KEY.** console.cloud.google.com → создать проект → включить «YouTube Data API v3» → «Учётные данные» → «Создать ключ API». Ограничьте ключ этим API.

## Подключение к боту

В @BotFather: `/mybots` → ваш бот → Bot Settings → Menu Button → адрес `https://ваш-домен/app/`.
Можно ещё зарегистрировать приложение командой `/newapp`, тогда появится прямая ссылка вида `t.me/бот/имя`.

## Как обновлять

- **Видео** подтягиваются сами раз в 6 часов. Вручную: админка → «Обновить с YouTube».
- **Тема видео** ставится по словам в названии (`server/topics.py`). Если ошиблась, поменяйте в админке. Ручной выбор больше не перезаписывается.
- **Скрыть или закрепить видео, книги, тексты** правятся в админке.
- **Код:** скопировать новые `server` и `web` в `/opt/pavel-miniapp/`, затем `sudo systemctl restart pavel-miniapp`.
- **Резервная копия:** файл `/var/lib/pavel-miniapp/miniapp.db`.

## Как устроена защита админки

1. Телеграм подписывает данные запуска (initData) токеном бота.
2. Браузер передаёт их в заголовке `X-Telegram-Init-Data`.
3. Сервер пересчитывает подпись по алгоритму Telegram (`server/auth.py`), проверяет, что данным не больше суток, и только потом сравнивает ID с `ADMIN_IDS`.
4. Кнопка «Админка» появляется, только когда сервер это подтвердил. Но даже если её показать вручную, сервер без подписи ответит 403.

## Личные данные

Приложение не собирает имя, телефон и почту. Ответы теста не уходят с телефона. Статистика хранит только счётчики по дням, без ID пользователей. Поэтому согласие на обработку данных не требуется. Описание в `web/privacy.html`.
