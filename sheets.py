"""
sheets.py — Google Sheets API v4 через обычный API-ключ.
Работает для таблиц с доступом «Все у кого есть ссылка».
Сервисный аккаунт не нужен.
"""

import csv
import io
import json
import logging
import os
import ssl
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from dotenv import load_dotenv
import certifi

load_dotenv()

logger = logging.getLogger(__name__)

SPREADSHEET_ID = os.environ.get(
    "SPREADSHEET_ID",
    "1DaCPZpf5PLRXfeDJ-PLfZaZLdLWXVIlQyReTeJDiO5E",
)
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

_cache: dict = {}
CACHE_TTL = timedelta(minutes=10)


def _fetch_range(tab_name: str) -> list:
    """Запрашивает данные через Sheets API v4."""
    if not GOOGLE_API_KEY:
        raise RuntimeError(
            "Не задан GOOGLE_API_KEY. Добавь его в .env файл.\n"
            "Получить ключ: console.cloud.google.com → APIs → Google Sheets API → Credentials → Create API Key"
        )

    range_encoded = urllib.parse.quote(tab_name)
    key_encoded   = urllib.parse.quote(GOOGLE_API_KEY)
    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}"
        f"/values/{range_encoded}?key={key_encoded}"
    )
    logger.info("Sheets API v4: %s", url)

    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    return data.get("values", [])


def get_discounts(tab_name: str) -> list:
    """
    Возвращает список словарей — по одному на строку.
    Ключи = значения первой (заголовочной) строки.
    """
    now = datetime.utcnow()
    cached = _cache.get(tab_name)
    if cached and (now - cached[1]) < CACHE_TTL:
        logger.info("Cache HIT: '%s'", tab_name)
        return cached[0]

    try:
        values = _fetch_range(tab_name)
    except Exception as e:
        logger.error("Sheets API error for '%s': %s", tab_name, e)
        raise RuntimeError("Ошибка загрузки «" + tab_name + "»: " + str(e)) from e

    if not values or len(values) < 2:
        _cache[tab_name] = ([], now)
        return []

    headers = [h.strip() for h in values[0]]
    rows = []
    for raw_row in values[1:]:
        # Дополняем строку пустыми ячейками если она короче заголовка
        row = raw_row + [""] * (len(headers) - len(raw_row))
        record = {headers[i]: row[i].strip() for i in range(len(headers))}
        if any(record.values()):   # пропускаем полностью пустые строки
            rows.append(record)

    _cache[tab_name] = (rows, now)
    logger.info("Loaded %d rows from '%s'", len(rows), tab_name)
    return rows


def invalidate_cache(tab_name=None):
    if tab_name:
        _cache.pop(tab_name, None)
    else:
        _cache.clear()
