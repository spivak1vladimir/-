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

TOKEN = ""
ADMIN_CHAT_ID = 194614510
DATA_FILE = "registered_users.json"
MOSCOW_TZ = ZoneInfo("Europe/Moscow")

COURTS = {
    "court10": {
        "title": "Корт 10 человек",
        "max_slots": 10,
        "price": 1400,
        "start": datetime(2026, 2, 5, 21, 30, tzinfo=MOSCOW_TZ),
        "users": []
    },
    "court4": {
        "title": "Корт 4 человека",
        "max_slots": 4,
        "price": 1600,
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

def paid_sorted(court_key):
    users = COURTS[court_key]["users"]
    paid = [u for u in users if u["paid"]]
    unpaid = [u for u in users if not u["paid"]]
    return paid, unpaid

def status_and_position(court_key, user):
    paid, unpaid = paid_sorted(court_key)
    if user["paid"] and user in paid[:COURTS[court_key]["max_slots"]]:
        return "Основной состав", paid.index(user) + 1
    if user["paid"]:
        return "Лист ожидания", paid.index(user) + 1
    return "Лист ожидания", unpaid.index(user) + 1

# ================== KEYBOARDS ==================

def courts_kb():
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
        [InlineKeyboardButton("Подтвердить оплату", callback_data=f"adm_pay_{court}_{idx}")],
        [InlineKeyboardButton("Написать участнику", callback_data=f"adm_msg_{court}_{idx}")],
        [InlineKeyboardButton("Удалить", callback_data=f"adm_del_{court}_{idx}")]
    ])

def admin_message_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Написать всем", callback_data="msg_all")],
        [InlineKeyboardButton("Написать корту", callback_data="msg_court")]
    ])

# ================== USER ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_TEXT, reply_markup=courts_kb())

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    court_key = q.data.replace("join_", "")
    user = q.from_user
    court = COURTS[court_key]["users"]

    if any(u["id"] == user.id for u in court):
        await q.message.reply_text("Ты уже зарегистрирован.")
        return

    court.append({
        "id": user.id,
        "first_name": user.first_name,
        "username": user.username,
        "paid": False,
        "court": court_key
    })
    save()

    await q.message.reply_text(
        "Для регистрации необходимо произвести оплату.",
        reply_markup=user_kb()
    )

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    for k, c in COURTS.items():
        for u in c["users"]:
            if u["id"] == uid:
                status, pos = status_and_position(k, u)
                
                price = COURTS[k]["price"]
                court_title = COURTS[k]["title"]
                
                await q.message.reply_text(
                    f"Имя: {u['first_name']}\n"
                    f"Username: @{u['username']}\n"
                    f"ID: {u['id']}\n"
                    f"Корт: {court_title}\n"
                    f"Стоимость: {price} ₽\n"
                    f"Статус: {status}\n"
                    f"Позиция: {pos}\n\n"
                    "Для подтверждения участия необходимо произвести оплату.\n\n"
                    "После оплаты нажми на скрепку и отправь в бот чек (фото или файл)."
                )
                return

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user

    for k, c in COURTS.items():
        for idx, u in enumerate(c["users"]):
            if u["id"] == user.id:
                await context.bot.forward_message(
                    ADMIN_CHAT_ID,
                    update.message.chat_id,
                    update.message.message_id
                )
                await context.bot.send_message(
                    ADMIN_CHAT_ID,
                    f"Чек от {u['first_name']} ({COURTS[k]['title']})",
                    reply_markup=admin_user_kb(k, idx)
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
    for k, c in COURTS.items():
        text += f"{c['title']}:\n"
        paid, unpaid = paid_sorted(k)
        for u in paid[:c["max_slots"]]:
            text += f"• {u['first_name']} (@{u['username']}) — основной\n"
        for u in paid[c["max_slots"]:] + unpaid:
            text += f"• {u['first_name']} (@{u['username']}) — ожидание\n"
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
            status, _ = status_and_position(k, u)
            paid = "оплачено" if u["paid"] else "не оплачено"
            text += f"{i+1}. {u['first_name']} — {paid} — {status}\n"
        text += "\n"

    await update.message.reply_text(text)

async def admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    await update.message.reply_text("Выбери действие:", reply_markup=admin_message_kb())

async def admin_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    _, _, court, idx = q.data.split("_")
    user = COURTS[court]["users"][int(idx)]
    user["paid"] = True
    save()

    await context.bot.send_message(user["id"], "Оплата подтверждена.")
    await q.edit_message_text("Оплата подтверждена.")

async def admin_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    _, _, court, idx = q.data.split("_")
    user = COURTS[court]["users"].pop(int(idx))
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

async def admin_msg_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["admin_msg_mode"] = "all"
    await q.message.reply_text("Напиши сообщение для всех участников:")


async def admin_msg_court(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["admin_msg_mode"] = "court"
    await q.message.reply_text("Напиши сообщение в формате:\ncourt10 ТЕКСТ")


async def admin_msg_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, _, court, idx = q.data.split("_")
    context.user_data["admin_msg_mode"] = ("user", court, int(idx))
    await q.message.reply_text("Напиши сообщение участнику:")

# ================== MAIN ==================

async def admin_text_sender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    mode = context.user_data.get("admin_msg_mode")
    if not mode:
        return

    text = update.message.text

    if mode == "all":
        for c in COURTS.values():
            for u in c["users"]:
                await context.bot.send_message(u["id"], text)

    elif mode == "court":
        court_key, msg = text.split(" ", 1)
        for u in COURTS[court_key]["users"]:
            await context.bot.send_message(u["id"], msg)

    elif isinstance(mode, tuple) and mode[0] == "user":
        _, court, idx = mode
        u = COURTS[court]["users"][idx]
        await context.bot.send_message(u["id"], text)

    context.user_data.pop("admin_msg_mode")
    await update.message.reply_text("Сообщение отправлено.")

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("admin_message", admin_message))

    app.add_handler(CallbackQueryHandler(admin_msg_all, pattern="^msg_all$"))
    app.add_handler(CallbackQueryHandler(admin_msg_court, pattern="^msg_court$"))
    app.add_handler(CallbackQueryHandler(admin_msg_user, pattern="^adm_msg_"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text_sender))

    app.add_handler(CallbackQueryHandler(join, pattern="^join_"))
    app.add_handler(CallbackQueryHandler(pay, pattern="^pay$"))
    app.add_handler(CallbackQueryHandler(cancel, pattern="^cancel$"))
    app.add_handler(CallbackQueryHandler(info, pattern="^info$"))

    app.add_handler(CallbackQueryHandler(admin_pay, pattern="^adm_pay_"))
    app.add_handler(CallbackQueryHandler(admin_del, pattern="^adm_del_"))

    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, receive_receipt))

    app.run_polling()

if __name__ == "__main__":
    main()
