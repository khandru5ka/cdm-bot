import logging
import asyncio
import sqlite3
import qrcode
import io
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()  # читает .env файл из текущей папки
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes,
)
from sheets import get_discounts

# ─── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHANNEL_1 = "@ne_detskii"
CHANNEL_2 = "@cdm_moscow"
DB_PATH   = "users.db"

CATEGORIES = {
    "stores":  "🏪 Магазины ЦДМ",
    "corners": "🍽 Корнеры НеДетского",
    "cafes":   "☕️ Кафе и рестораны",
}

SHEET_TABS = {
    "stores":  "Магазины ЦДМ",
    "corners": "Корнеры НеДетского",
    "cafes":   "Кафе и рестораны",
}

_NOT_MEMBER = {"left", "kicked"}

# ─── Database ──────────────────────────────────────────────────────────────────
def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """CREATE TABLE IF NOT EXISTS users (
               user_id       INTEGER PRIMARY KEY,
               username      TEXT,
               full_name     TEXT,
               registered_at TEXT
           )"""
    )
    con.commit()
    con.close()


def is_registered(user_id: int) -> bool:
    con = sqlite3.connect(DB_PATH)
    row = con.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,)).fetchone()
    con.close()
    return row is not None


def register_user(user):
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT OR IGNORE INTO users (user_id, username, full_name, registered_at) VALUES (?,?,?,?)",
        (user.id, user.username, user.full_name, datetime.utcnow().isoformat()),
    )
    con.commit()
    con.close()


# ─── Subscription check ────────────────────────────────────────────────────────
async def check_subscriptions(bot, user_id: int):
    """Возвращает (bool, bool) — подписан ли на каждый канал."""
    async def is_member(channel: str) -> bool:
        try:
            member = await bot.get_chat_member(channel, user_id)
            status = member.status
            if hasattr(status, "value"):
                status = status.value
            result = status not in _NOT_MEMBER
            logger.info("check_sub %s user=%s status=%s -> %s", channel, user_id, status, result)
            return result
        except Exception as e:
            logger.error("get_chat_member(%s, %s): %s", channel, user_id, e)
            return False

    return await asyncio.gather(is_member(CHANNEL_1), is_member(CHANNEL_2))


# ─── QR code ───────────────────────────────────────────────────────────────────
def generate_qr(user_id: int) -> io.BytesIO:
    payload = "CDM_DISCOUNT|uid=" + str(user_id) + "|ts=" + str(int(datetime.utcnow().timestamp()))
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


# ─── Keyboards ─────────────────────────────────────────────────────────────────
def main_menu_keyboard():
    buttons = [
        [InlineKeyboardButton(label, callback_data="cat:" + key)]
        for key, label in CATEGORIES.items()
    ]
    buttons.append([InlineKeyboardButton("🎟 Мой QR-код", callback_data="qr")])
    return InlineKeyboardMarkup(buttons)


def subscribe_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 НеДетский",  url="https://t.me/ne_detskii"),
            InlineKeyboardButton("📢 ЦДМ Москва", url="https://t.me/cdm_moscow"),
        ],
        [InlineKeyboardButton("✅ Я подписался — проверить", callback_data="check_sub")],
    ])


def back_keyboard():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")]]
    )


# ─── Handlers ──────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_registered(user.id):
        await update.message.reply_text(
            "👋 С возвращением, " + user.first_name + "!\n\n"
            "Выбери категорию скидок или получи свой QR-код:",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await update.message.reply_text(
            "👋 Привет, " + user.first_name + "!\n\n"
            "Вы получили карту-доступ программе лояльности  в <b>друзья ЦДМ х НеДетский</b>.\n\n"         
            "Откройте мир особых привилегий для наших самых дорогих гостей.\n\n""
            "Сгенерируйте QR-код, предъявите его на кассе и получите индивидуальную скидку до 30%. Предложения будут обновляться.\n\n""
            "Для регистрации подпишись на наши каналы:",
            parse_mode="HTML",
            reply_markup=subscribe_keyboard(),
        )
        
async def cb_check_sub(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    ch1, ch2 = await check_subscriptions(ctx.bot, user.id)

    if ch1 and ch2:
        register_user(user)
        await query.edit_message_text(
            "✅ Отлично! Ты успешно зарегистрирован.\n\nВыбери категорию скидок:",
            reply_markup=main_menu_keyboard(),
        )
    else:
        missing = []
        if not ch1:
            missing.append("• " + CHANNEL_1)
        if not ch2:
            missing.append("• " + CHANNEL_2)
        await query.edit_message_text(
            "❌ Ты ещё не подписан на:\n" + "\n".join(missing) + "\n\n"
            "Подпишись и нажми кнопку снова 👇",
            reply_markup=subscribe_keyboard(),
        )


def _esc(text: str) -> str:
    """Экранирует спецсимволы HTML."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def cb_category(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # Отвечаем на callback НЕМЕДЛЕННО — иначе Telegram покажет "часики" и timeout
    await query.answer()

    if not is_registered(query.from_user.id):
        await query.edit_message_text("⚠️ Сначала нужно зарегистрироваться. Используй /start")
        return

    key   = query.data.split(":")[1]
    label = CATEGORIES.get(key, key)
    tab   = SHEET_TABS.get(key)
    chat_id = query.message.chat_id

    # Удаляем меню, отправляем "загрузка" — это быстро
    try:
        await query.delete_message()
    except Exception:
        pass

    loading_msg = await ctx.bot.send_message(
        chat_id=chat_id,
        text="⏳ Загружаю скидки: " + label + "…",
    )

    # Теперь грузим данные — сколько бы ни заняло
    try:
        rows = get_discounts(tab)
    except Exception as e:
        logger.error("Sheets error: %s", e)
        await loading_msg.edit_text(
            "😕 Не удалось загрузить данные.\n\n" + _esc(str(e)),
            parse_mode="HTML",
            reply_markup=back_keyboard(),
        )
        return

    if not rows:
        await loading_msg.edit_text(
            "<b>" + _esc(label) + "</b>\n\nСкидок пока нет. Заходи позже!",
            parse_mode="HTML",
            reply_markup=back_keyboard(),
        )
        return

    lines = ["<b>" + _esc(label) + "</b>", ""]
    for r in rows:
        name     = r.get("Название", "") or r.get("название", "") or "—"
        discount = r.get("Скидка",   "") or r.get("скидка",   "")
        promo    = r.get("Промокод", "") or r.get("промокод", "")
        desc     = r.get("Описание", "") or r.get("описание", "")

        if not name or name == "—":
            continue

        line = "🏷 <b>" + _esc(name) + "</b>"
        if discount:
            line += " — " + _esc(discount)
        if promo:
            line += "\n🔑 Промокод: <code>" + _esc(promo) + "</code>"
        if desc:
            line += "\n<i>" + _esc(desc) + "</i>"
        lines.append(line)

    text = "\n\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n\n…"

    await loading_msg.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=back_keyboard(),
    )


async def cb_qr(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_registered(query.from_user.id):
        await query.edit_message_text("⚠️ Сначала нужно зарегистрироваться. Используй /start")
        return

    buf = generate_qr(query.from_user.id)

    # Удаляем старое сообщение с меню, отправляем фото отдельным сообщением
    # Кнопка «Назад» в фото-сообщении отправит новое текстовое меню
    try:
        await query.delete_message()
    except Exception:
        pass

    await ctx.bot.send_photo(
        chat_id=query.message.chat_id,
        photo=buf,
        caption=(
            "🎟 <b>Твой персональный QR-код</b>\n\n"
            "Покажи его на кассе для получения скидки.\n"
            "<i>QR обновляется при каждом запросе.</i>"
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⬅️ Назад в меню", callback_data="back_from_qr")]]
        ),
    )


async def cb_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Назад из сообщения с результатами — удаляем его, отправляем меню заново."""
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    try:
        await query.delete_message()
    except Exception:
        pass
    await ctx.bot.send_message(
        chat_id=chat_id,
        text="Выбери категорию скидок или получи свой QR-код:",
        reply_markup=main_menu_keyboard(),
    )


async def cb_back_from_qr(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Назад из фото-сообщения QR — удаляем фото, отправляем новое меню."""
    query = update.callback_query
    await query.answer()
    try:
        await query.delete_message()
    except Exception:
        pass
    await ctx.bot.send_message(
        chat_id=query.message.chat_id,
        text="Выбери категорию скидок или получи свой QR-код:",
        reply_markup=main_menu_keyboard(),
    )


async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if is_registered(update.effective_user.id):
        await update.message.reply_text("Главное меню:", reply_markup=main_menu_keyboard())
    else:
        await update.message.reply_text("Сначала нужно зарегистрироваться. Используй /start")


async def cmd_debug(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Диагностика подписки и соединения с таблицей."""
    user = update.effective_user
    lines = ["🔍 <b>Диагностика</b> для <code>" + str(user.id) + "</code>", ""]

    for channel in (CHANNEL_1, CHANNEL_2):
        try:
            member = await ctx.bot.get_chat_member(channel, user.id)
            status = member.status
            if hasattr(status, "value"):
                status = status.value
            ok = status not in _NOT_MEMBER
            icon = "✅" if ok else "❌"
            lines.append(icon + " " + channel + " — статус: <code>" + status + "</code>")
        except Exception as e:
            lines.append("⚠️ " + channel + " — ошибка: <code>" + _esc(str(e)) + "</code>")

    lines.append("")
    lines.append("📋 В БД: <code>" + str(is_registered(user.id)) + "</code>")

    # Проверяем таблицу
    lines.append("")
    lines.append("📊 <b>Тест таблицы:</b>")
    for key, tab in SHEET_TABS.items():
        try:
            rows = get_discounts(tab)
            lines.append("✅ " + _esc(tab) + " — " + str(len(rows)) + " строк")
        except Exception as e:
            lines.append("❌ " + _esc(tab) + " — " + _esc(str(e)))

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


# ─── Entry point ───────────────────────────────────────────────────────────────
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu",  cmd_menu))
    app.add_handler(CommandHandler("debug", cmd_debug))
    app.add_handler(CallbackQueryHandler(cb_check_sub,    pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(cb_qr,           pattern="^qr$"))
    app.add_handler(CallbackQueryHandler(cb_back,         pattern="^back_to_menu$"))
    app.add_handler(CallbackQueryHandler(cb_back_from_qr, pattern="^back_from_qr$"))
    app.add_handler(CallbackQueryHandler(cb_category,     pattern="^cat:"))

    logger.info("Bot started.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
