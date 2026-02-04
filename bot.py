import os
import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

# ================== TEXTS ==================

TERMS_TEXT = (
    "Пожалуйста, ознакомься с условиями участия:\n"
    "— Если участник из листа ожидания произведёт оплату раньше, чем участник из основного состава, он будет переведён в основной состав.\n"
    "— Просьба производить оплату заранее.\n"
    "— Ответственность за здоровье и вещи несёт участник.\n"
    "— Согласие на обработку персональных данных.\n"
    "— Согласие на фото- и видеосъёмку.\n\n"
)

START_TEXT = (
    "Игра в волейбол Spivak Run\n\n"
    "Пляжный центр «Лето»\n"
    "проспект маршала жукова 4 строение 2\n\n"
    "https://yandex.ru/maps/-/CLh3JG0S\n\n"
    "Дата: 5 февраля\n"
    "Сбор: 21:20\n"
    "Начало игры: 21:30\n\n"
    "Выбери корт:"
)

REMINDER_24H = "Напоминание\nИгра состоится завтра в 21:30."
REMINDER_4H = "Напоминание\nИгра начнётся через 4 часа."

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

def recalc(court):
    paid = [u for u in court if u["paid"]]
    unpaid = [u for u in court if not u["paid"]]
    court[:] = paid + unpaid

def status_pos(court, user):
    idx = court.index(user)
    status = "Основной состав" if idx < COURTS[user["court"]]["max_slots"] else "Лист ожидания"
    return status, idx + 1

# ================== KEYBOARDS ==================

def start_kb():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(c["title"], callback_data=f"join_{k}")]
         for k, c in COURTS.items()]
    )

def user_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Оплатить", callback_data="pay")],
        [InlineKeyboardButton("Отменить участие", callback_data="cancel")],
        [InlineKeyboardButton("Информация по игре", callback_data="info")]
    ])

def admin_user_kb(court, idx):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Подтвердить оплату", callback_data=f"adm_pay_{court}_{idx}"),
            InlineKeyboardButton("Удалить", callback_data=f"adm_del_{court}_{idx}")
        ]
    ])

# ================== USER ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_TEXT, reply_markup=start_kb())

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    court_key = q.data.replace("join_", "")
    user = q.from_user

    court = COURTS[court_key]["users"]

    if any(u["id"] == user.id for u in court):
        await q.message.reply_text("Ты уже зарегистрирован.")
        return

    entry = {
        "id": user.id,
        "first_name": user.first_name,
        "username": user.username,
        "paid": False,
        "receipt": False,
        "court": court_key
    }

    court.append(entry)
    save()

    status, pos = status_pos(court, entry)

    await q.message.reply_text(
        f"Имя: {user.first_name}\n"
        f"Username: @{user.username}\n"
        f"ID: {user.id}\n"
        f"Статус: {status}\n"
        f"Позиция: {pos}\n\n"
        "Для регистрации необходимо произвести оплату.",
        reply_markup=user_kb()
    )

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    user = q.from_user
    for c in COURTS.values():
        for u in c["users"]:
            if u["id"] == user.id:
                status, pos = status_pos(c["users"], u)
                await q.message.reply_text(
                    f"Имя: {u['first_name']}\n"
                    f"Username: @{u['username']}\n"
                    f"ID: {u['id']}\n"
                    f"Статус: {status}\n"
                    f"Позиция: {pos}\n\n"
                    "Для подтверждения участия необходимо произвести оплату.\n\n"
                    "После оплаты нажми на скрепку и отправь в бот чек (фото или файл)."
                )
                return

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user

    for k, c in COURTS.items():
        for u in c["users"]:
            if u["id"] == user.id:
                u["receipt"] = True
                save()

                await context.bot.send_message(
                    ADMIN_CHAT_ID,
                    f"Чек от {u['first_name']} ({c['title']})",
                    reply_markup=admin_user_kb(k, c["users"].index(u))
                )
                await context.bot.forward_message(
                    ADMIN_CHAT_ID,
                    update.message.chat_id,
                    update.message.message_id
                )
                return

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

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    text = START_TEXT + "\n\n"
    for c in COURTS.values():
        text += f"{c['title']}:\n"
        for i, u in enumerate(c["users"], 1):
            paid = "оплачено" if u["paid"] else "не оплачено"
            text += f"{i}. {u['first_name']} (@{u['username']}) — {paid}\n"
        text += "\n"

    await q.message.reply_text(text)

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

async def admin_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    _, _, court, idx = q.data.split("_")
    idx = int(idx)

    user = COURTS[court]["users"][idx]
    user["paid"] = True
    recalc(COURTS[court]["users"])
    save()

    await context.bot.send_message(user["id"], "Оплата подтверждена.")
    await q.edit_message_text("Оплата подтверждена.")

async def admin_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    _, _, court, idx = q.data.split("_")
    idx = int(idx)

    user = COURTS[court]["users"].pop(idx)
    save()

    await context.bot.send_message(user["id"], "Ты удалён из списка.")
    await q.edit_message_text("Игрок удалён.")

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
    app.add_handler(CallbackQueryHandler(pay, pattern="^pay$"))
    app.add_handler(CallbackQueryHandler(cancel, pattern="^cancel$"))
    app.add_handler(CallbackQueryHandler(info, pattern="^info$"))

    app.add_handler(CallbackQueryHandler(admin_pay, pattern="^adm_pay_"))
    app.add_handler(CallbackQueryHandler(admin_del, pattern="^adm_del_"))

    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, receive_receipt))

    app.job_queue.run_repeating(reminders, 300)

    logging.info("BOT STARTED")
    app.run_polling()

if __name__ == "__main__":
    main()
