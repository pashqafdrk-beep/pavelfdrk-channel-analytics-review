# Интервью Василия Якеменко: расшифровки

Список видео: `videos.txt`. Найден поиском 24.09.2026, может быть неполным.
Ролики-реакции и разборы (Кац, Мартынов, «Посмотрел это за вас») сюда не включены: там Якеменко не говорит сам.

Не на YouTube:
- Второе интервью, канал «Достойный», RUTUBE: https://rutube.ru/video/6da90b447067f95510c9dbccc0f3d9c7/
- Интервью Ксении Собчак, телеканал «Дождь», 2012: https://tvrain.tv/teleshow/sobchak_zhivem/vasiliy_yakemenko_s_zhenami_takaya_problema_oni_segodnya_idut_za_toboy_a_zavtra_idut_za_kem_to_drugi-297143/

Запуск:
```
pip install -U yt-dlp openai-whisper   # и ffmpeg
./transcribe.sh
```
Результат: `transcripts/<id>.txt` (название, канал, дата, ссылка, текст).

Не проверено, есть ли в ролике сам Якеменко (не включено в `videos.txt`):
- «Министр раскололся. Что рассказал чиновник Амирану Сардарову»: https://www.youtube.com/watch?v=vRpSu2iJhxU
