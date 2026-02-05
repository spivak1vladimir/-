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

TOKEN = "8570155371:AAEgDOsPnnEZm-EGYqDNVdeopQWd1UYrgzY"
ADMIN_CHAT_ID = 194614510
DATA_FILE = "registered_users.json"
MOSCOW_TZ = ZoneInfo("Europe/Moscow")

HALL = {
    "prana": {
        "title": "Йога · зал «Прана»",
        "max_slots": 12,
        "price": 800,
        "start": datetime(2026, 2, 7, 19, 00, tzinfo=MOSCOW_TZ),
        "users": []
    }
}

# ================== TEXTS ==================

START_TEXT = (
    "Йога · Spivak Run\n\n"
    "Зал «Прана»\n"
    "Йога-центр diwali столярный пер.,2, Москва\n\n"
    "https://yandex.ru/maps/-/CPEZV2ph\n\n"
    "Дата: 7 февраля\n"
    "Сбор: 18:45\n"
    "Начало занятия: 19:00\n\n"
    "Нажми кнопку ниже для записи:"
)

REMINDER_24H = "Напоминание\nЗанятие йогой состоится завтра в 19:00."
REMINDER_4H = "Напоминание\nЗанятие йогой начнётся через 4 часа."

# ================== STORAGE ==================

def load():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(HALL["prana"]["users"], f, ensure_ascii=False, indent=2)

HALL["prana"]["users"] = load()

# ================== HELPERS ==================

def paid_sorted():
    users = HALL["prana"]["users"]
    paid = [u for u in users if u["paid"]]
    unpaid = [u for u in users if not u["paid"]]
    return paid, unpaid

def status_and_position(user):
    paid, unpaid = paid_sorted()
    if user["paid"] and user in paid[:HALL["prana"]["max_slots"]]:
        return "Основной состав", paid.index(user) + 1
    if user["paid"]:
        return "Лист ожидания", paid.index(user) + 1
    return "Лист ожидания", unpaid.index(user) + 1

# ================== KEYBOARDS ==================

def start_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Записаться на занятие", callback_data="join")]
    ])

def user_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Оплатить", callback_data="pay")],
        [InlineKeyboardButton("Отменить участие", callback_data="cancel")],
        [InlineKeyboardButton("Информация о занятии", callback_data="info")],
        [InlineKeyboardButton("Обсудим йогу в чате", url="https://t.me/chat_spivak_run")]
    ])


def admin_user_kb(idx):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Подтвердить оплату", callback_data=f"adm_pay_{idx}")],
        [InlineKeyboardButton("Написать участнику", callback_data=f"adm_msg_{idx}")],
        [InlineKeyboardButton("Удалить", callback_data=f"adm_del_{idx}")]
    ])

def admin_message_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Написать всем", callback_data="msg_all")]
    ])

# ================== USER ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(START_TEXT, reply_markup=start_kb())

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    user = q.from_user
    users = HALL["prana"]["users"]

    if any(u["id"] == user.id for u in users):
        await q.message.reply_text("Ты уже записан.")
        return

    users.append({
        "id": user.id,
        "first_name": user.first_name,
        "username": user.username,
        "paid": False
    })
    save()

    await q.message.reply_text(
        "Для подтверждения участия необходимо произвести оплату.",
        reply_markup=user_kb()
    )

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id

    for u in HALL["prana"]["users"]:
        if u["id"] == uid:
            status, pos = status_and_position(u)
            await q.message.reply_text(
                f"Имя: {u['first_name']}\n"
                f"Username: @{u['username']}\n"
                f"ID: {u['id']}\n"
                f"Зал: Прана\n"
                f"Стоимость: {HALL['prana']['price']} ₽\n"
                f"Статус: {status}\n"
                f"Позиция: {pos}\n\n"
                "После оплаты отправь сюда чек (фото или файл)."
            )
            return

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user

    for idx, u in enumerate(HALL["prana"]["users"]):
        if u["id"] == user.id:
            await context.bot.forward_message(
                ADMIN_CHAT_ID,
                update.message.chat_id,
                update.message.message_id
            )
            await context.bot.send_message(
                ADMIN_CHAT_ID,
                f"Чек от {u['first_name']} (зал «Прана»)",
                reply_markup=admin_user_kb(idx)
            )
            return

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    users = HALL["prana"]["users"]

    for u in users:
        if u["id"] == uid:
            users.remove(u)
            save()
            await q.message.reply_text("Участие отменено.")
            return

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    text = START_TEXT + "\n\nУчастники:\n"
    paid, unpaid = paid_sorted()

    for u in paid[:HALL["prana"]["max_slots"]]:
        username = f"@{u['username']}" if u.get("username") else "без username"
        text += f"• {u['first_name']} ({username}) — основной\n"

    for u in paid[HALL["prana"]["max_slots"]:] + unpaid:
        username = f"@{u['username']}" if u.get("username") else "без username"
        text += f"• {u['first_name']} — ожидание\n"

    await q.message.reply_text(text)

# ================== ADMIN ==================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    text = "АДМИНКА · ЙОГА\n\n"
    for i, u in enumerate(HALL["prana"]["users"]):
        status, _ = status_and_position(u)
        paid = "оплачено" if u["paid"] else "не оплачено"
        text += f"{i+1}. {u['first_name']} — {paid} — {status}\n"

    await update.message.reply_text(text)

async def admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return
    await update.message.reply_text("Рассылка:", reply_markup=admin_message_kb())

async def admin_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    _, _, idx = q.data.split("_")
    user = HALL["prana"]["users"][int(idx)]
    user["paid"] = True
    save()

    await context.bot.send_message(user["id"], "Оплата подтверждена. Ты записан на занятие.")
    await q.edit_message_text("Оплата подтверждена.")

async def admin_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    _, _, idx = q.data.split("_")
    user = HALL["prana"]["users"].pop(int(idx))
    save()

    await context.bot.send_message(user["id"], "Ты удалён из списка.")
    await q.edit_message_text("Участник удалён.")

# ================== ADMIN MESSAGES ==================

async def admin_msg_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["admin_msg_mode"] = "all"
    await q.message.reply_text("Напиши сообщение для всех участников:")

async def admin_msg_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, _, idx = q.data.split("_")
    context.user_data["admin_msg_mode"] = ("user", int(idx))

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
        for u in HALL["prana"]["users"]:
            await context.bot.send_message(u["id"], text)

    elif isinstance(mode, tuple) and mode[0] == "user":
        _, idx = mode
        u = HALL["prana"]["users"][idx]
        await context.bot.send_message(u["id"], text)

    context.user_data.pop("admin_msg_mode")
    await update.message.reply_text("Сообщение отправлено.")

# ================== MAIN ==================

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("admin_message", admin_message))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text_sender))

    app.add_handler(CallbackQueryHandler(join, pattern="^join$"))
    app.add_handler(CallbackQueryHandler(pay, pattern="^pay$"))
    app.add_handler(CallbackQueryHandler(cancel, pattern="^cancel$"))
    app.add_handler(CallbackQueryHandler(info, pattern="^info$"))

    app.add_handler(CallbackQueryHandler(admin_msg_all, pattern="^msg_all$"))
    app.add_handler(CallbackQueryHandler(admin_msg_user, pattern="^adm_msg_"))
    app.add_handler(CallbackQueryHandler(admin_pay, pattern="^adm_pay_"))
    app.add_handler(CallbackQueryHandler(admin_del, pattern="^adm_del_"))


    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, receive_receipt))

    app.run_polling()

if __name__ == "__main__":
    main()
