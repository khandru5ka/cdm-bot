# 🤖 Бот скидок ЦДМ & НеДетский

Telegram-бот для демонстрации скидок в ТЦ ЦДМ и фудхоле НеДетский.  
Данные о скидках берутся в реальном времени из Google Sheets.

---

## Функционал

| Функция | Описание |
|---|---|
| Регистрация | Проверка подписки на @ne_detskii и @cdm_moscow |
| QR-код | Персональный QR для предъявления на кассе |
| Скидки — Магазины ЦДМ | Список магазинов ЦДМ со скидками |
| Скидки — Корнеры НеДетского | Корнеры фудхола НеДетский |
| Скидки — Кафе и рестораны | Кафе и рестораны |
| Кэш таблицы | Данные кэшируются на 10 мин, не нагружая API |

---

## Быстрый старт

### 1. Создать бота в Telegram

1. Открой [@BotFather](https://t.me/BotFather)
2. Отправь `/newbot` и следуй инструкциям
3. Скопируй **токен** (вида `7xxxxxxxxx:AAxxxx…`)

### 2. Настроить Google Sheets API

1. Открой [Google Cloud Console](https://console.cloud.google.com/)
2. Создай новый проект (или выбери существующий)
3. Включи **Google Sheets API** и **Google Drive API**
4. Перейди в **IAM & Admin → Service Accounts → Create Service Account**
5. Назови аккаунт (например `cdm-bot`) и нажми **Create**
6. На вкладке **Keys** нажми **Add Key → JSON** — скачается файл
7. Переименуй файл в `service_account.json` и положи рядом с `bot.py`
8. Скопируй `client_email` из JSON-файла (вида `cdm-bot@project.iam.gserviceaccount.com`)
9. Открой [таблицу скидок](https://docs.google.com/spreadsheets/d/1DaCPZpf5PLRXfeDJ-PLfZaZLdLWXVIlQyReTeJDiO5E/edit) → **Поделиться** → вставь этот email с правами **Читатель**

### 3. Настроить таблицу

Таблица должна содержать **три листа** с точными названиями:

| Лист | Категория |
|---|---|
| `Магазины ЦДМ` | Магазины ЦДМ |
| `Корнеры НеДетского` | Корнеры фудхола |
| `Кафе и рестораны` | Кафе и рестораны |

Заголовки столбцов в каждом листе (первая строка):

| Название | Скидка | Промокод | Описание |
|---|---|---|---|
| Adidas | 15% | ADIDAS15 | На всю коллекцию |

Бот выводит все 4 поля. Незаполненные поля просто не показываются.

### 4. Установка

```bash
# Клонируй или скопируй файлы в папку
cd /opt/cdm_bot

# Создай виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Установи зависимости
pip install -r requirements.txt

# Создай файл с переменными окружения
cp .env.example .env
nano .env   # вставь BOT_TOKEN
```

### 5. Запуск (разработка)

```bash
source venv/bin/activate
BOT_TOKEN="7xxx:AAAxxx" python bot.py
```

### 6. Запуск на сервере (production)

```bash
# Скопируй systemd-сервис
sudo cp cdm_bot.service /etc/systemd/system/

# Отредактируй пути если нужно
sudo nano /etc/systemd/system/cdm_bot.service

# Активируй и запусти
sudo systemctl daemon-reload
sudo systemctl enable cdm_bot
sudo systemctl start cdm_bot

# Проверь статус
sudo systemctl status cdm_bot

# Логи в реальном времени
sudo journalctl -u cdm_bot -f
```

---

## Структура файлов

```
cdm_bot/
├── bot.py              # Основной файл бота
├── sheets.py           # Модуль Google Sheets
├── requirements.txt    # Зависимости Python
├── .env.example        # Шаблон переменных окружения
├── .env                # Твои секреты (не коммить в git!)
├── service_account.json # Ключ Google (не коммить в git!)
├── users.db            # SQLite база (создаётся автоматически)
└── cdm_bot.service     # Systemd unit-файл
```

---

## Обновление скидок

Достаточно отредактировать таблицу Google Sheets — бот подтянет изменения автоматически.  
Кэш обновляется каждые **10 минут**. Перезапускать бота не нужно.

---

## Требования к серверу

- Python 3.10+
- 128 MB RAM
- Доступ в интернет

Подходит любой VPS/облако: Hetzner, Timeweb Cloud, REG.RU и т.д.

---

## .gitignore (рекомендуется)

```
.env
service_account.json
users.db
venv/
__pycache__/
*.pyc
```
