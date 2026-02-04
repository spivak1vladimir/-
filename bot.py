import os
import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================== CONFIG ==================

TOKEN = "7705759805:AAFx2IHX44ZPIRC3bCXCVqP23J9WeM0u7qc"
ADMIN_CHAT_ID = 194614510
DATA_FILE = "registered_users.json"

MOSCOW_TZ = ZoneInfo("Europe/Moscow")

COURTS = {
    "court10": {
        "title": "Корт 10 человек",
        "max_slots": 10,
        "price": 1400,
        "duration": "2 часа",
        "start": datetime(2026, 2, 5, 21, 30, tzinfo=MOSCOW_TZ),
        "users": []
    },
    "court4": {
        "title": "Корт 4 человека",
        "max_slots": 4,
        "price": 1600,
        "duration": "1 час",
        "start": datetime(2026, 2, 5, 21, 30, tzinfo=MOSCOW_TZ),
        "users": []
    }
}

LOCATION_TEXT = (
    "Пляжный центр «Лето»\n"
    "проспект маршала жукова 4 строение 2\n\n"
    "https://yandex.ru/maps/-/CLh3JG0S"
)

logging.basicConfig(level=logging.INFO)

# ================== TEXTS ==================

TERMS_TEXT = (
    "Пожалуйста, ознакомься с условиями участия:\n"
    "— Если участник из листа ожидания произведёт оплату раньше, чем участник из основного состава, он будет переведён в основной состав.\n"
    "— Просьба производить оплату заранее, так как требуется предварительная оплата аренды площадки.\n"
    "— Участник самостоятельно несёт ответственность за свою жизнь и здоровье.\n"
    "— Участник несёт ответственность за сохранность личных вещей.\n"
    "— Согласие на обработку персональных данных.\n"
    "— Согласие на фото- и видеосъёмку во время мероприятия.\n\n"
    "Условия оплаты и отмены участия:\n"
    "— При отмене участия менее чем за 24 часа до начала игры оплата не возвращается.\n"
    "— При отмене не позднее чем за 24 часа до игры средства возвращаются.\n"
    "— Допускается передача оплаченного места другому игроку при самостоятельном поиске замены.\n\n"
)

START_TEXT = (
    "Играем в волейбол Spivak Run\n\n"
    "Площадка:\n"
    "Пляжный центр «Лето»\n"
    "проспект маршала жукова 4 строение 2\n\n"
    "https://yandex.ru/maps/-/CLh3JG0S\n\n"
    "Дата: 5 февраля\n"
    "Сбор: 21:20\n"
    "Начало игры: 21:30\n\n"
    "Выбери корт для участия:"
)

REMINDER_24H = "Напоминание\nИгра состоится завтра в 21:30."
REMINDER_4H = "Напоминание\nИгра начнётся через 4 часа."

PAYMENT_TEXT = (
    "Для подтверждения участия необходимо произвести оплату.\n"
    "После оплаты отправь сюда чек (фото или файл)."
)

# ================== STORAGE ==================

def load():
    if not os.path.exists(DATA_FILE):
        return {k: [] for k in COURTS}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({k: COURTS[k]["users"] for k in COURTS}, f, ensure_ascii=False, indent=2)

data = load()
for k in COURTS:
    COURTS[k]["users"] = data.get(k, [])

# ================== HELPERS ==================

def position_and_status(court, user):
    paid_users = [u for u in court if u["paid"]]
    if user in paid_users[:len(court)]:
        return "Основной состав", paid_users.index(user) + 1
    return "Лист ожидания", court.index(user) + 1

def promote_logic(court):
    paid = [u for u in court if u["paid"]]
    unpaid = [u for u in court if not u["paid"]]
    court[:] = paid + unpaid

# ================== KEYBOARDS ==================

def start_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(c["title"], callback_data=f"join_{k}")]
        for k, c in COURTS.items()
    ] + [[InlineKeyboardButton("Информация по игре", callback_data="info")]])

def user_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Отменить участие", callback_data="cancel")],
        [InlineKeyboardButton("Информация по игре", callback_data="info")]
    ])

# ================== USER ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выбери корт:", reply_markup=start_kb())

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    court_key = q.data.replace("join_", "")
    court = COURTS[court_key]["users"]
    user = q.from_user

    if any(u["id"] == user.id for u in court):
        await q.message.reply_text("Ты уже зарегистрирован.")
        return

    entry = {
        "id": user.id,
        "first_name": user.first_name,
        "username": user.username,
        "paid": False,
        "receipt": False
    }

    court.append(entry)
    save()

    status, pos = position_and_status(court, entry)

    await q.message.reply_text(
        f"Имя: {user.first_name}\n"
        f"Username: @{user.username}\n"
        f"ID: {user.id}\n"
        f"Статус: {status}\n"
        f"Позиция: {pos}\n\n"
        "Для подтверждения участия необходимо произвести оплату.\n"
        "После оплаты отправь сюда чек (фото или файл).",
        reply_markup=user_kb()
    )

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user

    for court_key, c in COURTS.items():
        for u in c["users"]:
            if u["id"] == user.id and not u["receipt"]:
                u["receipt"] = True
                save()

                await context.bot.send_message(
                    ADMIN_CHAT_ID,
                    f"Чек от {u['first_name']} ({c['title']})"
                )
                await context.bot.forward_message(
                    ADMIN_CHAT_ID,
                    update.message.chat_id,
                    update.message.message_id
                )
                return

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    text = f"Игра в волейбол Spivak Run\n\n{LOCATION_TEXT}\n\n"
    for k, c in COURTS.items():
        text += f"{c['title']}:\n"
        for i, u in enumerate(c["users"], 1):
            paid = "оплачено" if u["paid"] else "не оплачено"
            text += f"{i}. {u['first_name']} (@{u['username']}) — {paid}\n"
        text += "\n"

    await q.message.reply_text(text)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    for c in COURTS.values():
        for u in c["users"]:
            if u["id"] == uid:
                c["users"].remove(u)
                save()
                await q.message.reply_text("Участие отменено.")
                return

# ================== ADMIN ==================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    text = "АДМИНКА\n\n"
    for k, c in COURTS.items():
        text += f"{c['title']}:\n"
        for i, u in enumerate(c["users"]):
            text += f"{i+1}. {u['first_name']} (@{u['username']})\n"
        text += "\n"

    await update.message.reply_text(text)

# ================== REMINDERS ==================

async def reminders(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(MOSCOW_TZ)
    for c in COURTS.values():
        delta = c["start"] - now
        for u in c["users"]:
            if not u["paid"]:
                continue
            if timedelta(hours=23, minutes=50) < delta < timedelta(hours=24, minutes=10):
                await context.bot.send_message(u["id"], REMINDER_24H)
            if timedelta(hours=3, minutes=50) < delta < timedelta(hours=4, minutes=10):
                await context.bot.send_message(u["id"], REMINDER_4H)

# ================== MAIN ==================

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))

    app.add_handler(CallbackQueryHandler(join, pattern="^join_"))
    app.add_handler(CallbackQueryHandler(info, pattern="^info$"))
    app.add_handler(CallbackQueryHandler(cancel, pattern="^cancel$"))

    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, receive_receipt))

    app.job_queue.run_repeating(reminders, 300)

    app.run_polling()

if __name__ == "__main__":
    main()
