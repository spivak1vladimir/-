import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.error import Forbidden

# ================= CONFIG =================
TOKEN = "ВАШ_TOKEN"  # <- вставьте токен вашего бота
ADMIN_CHAT_ID = 194614510
DATA_FILE = "registered_users.json"
AFISHA_FILE = "afisha.jpg"
MOSCOW_TZ = ZoneInfo("Europe/Moscow")

COURTS = {
    "court1": {"title": "Корт 8 человек", "max_slots": 8, "price": 1500,
               "start": datetime(2026, 3, 19, 21, 30, tzinfo=MOSCOW_TZ), "users": []},
    "court2": {"title": "Корт 8 человек", "max_slots": 8, "price": 1500,
               "start": datetime(2026, 3, 19, 21, 30, tzinfo=MOSCOW_TZ), "users": []},
    "court3": {"title": "Корт 8 человек (дополнительный корт)", "max_slots": 8, "price": 1500,
               "start": datetime(2026, 3, 19, 22, 0, tzinfo=MOSCOW_TZ), "users": []}
}
PRIMARY_COURT_KEY = "court1"

START_TEXT = (
    "Игра в волейбол Spivak Run\n\n"
    "Пляжный центр «Лето»\n"
    "проспект маршала жукова 4 строение 2\n\n"
    "https://yandex.ru/maps/-/CLh3JG0S\n\n"
    "Дата: 19 марта 2026\n"
    "Сбор: 21:20\n"
    "Начало игры: 21:30\n\n"
    "Выбери корт:"
)

# ================= STORAGE =================
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

# ================= HELPERS =================
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

# ================= KEYBOARDS =================
def courts_kb():
    primary = COURTS[PRIMARY_COURT_KEY]
    keys = [PRIMARY_COURT_KEY] if len(primary["users"]) < primary["max_slots"] else list(COURTS.keys())
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(COURTS[k]["title"], callback_data=f"join_{k}")] for k in keys]
    )

def user_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Оплатить", callback_data="pay")],
        [InlineKeyboardButton("Отменить участие", callback_data="cancel")],
        [InlineKeyboardButton("Информация по игре", callback_data="info")]
    ])

def admin_main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Обновить афишу", callback_data="update_afisha")],
        [InlineKeyboardButton("Управление участниками", callback_data="manage_courts")]
    ])

def admin_court_kb():
    rows = []
    for k in COURTS:
        rows.append([InlineKeyboardButton(COURTS[k]["title"], callback_data=f"manage_{k}")])
    return InlineKeyboardMarkup(rows)

def admin_court_manage_kb(court_key):
    rows = []
    for i, u in enumerate(COURTS[court_key]["users"]):
        name = u.get("first_name") or "Без имени"
        rows.append([
            InlineKeyboardButton(f"{i+1}. {name}", callback_data=f"adm_user_{court_key}_{i}_pay"),
            InlineKeyboardButton("Удалить", callback_data=f"adm_user_{court_key}_{i}_del")
        ])
    return InlineKeyboardMarkup(rows) if rows else None

# ================= USER HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if os.path.exists(AFISHA_FILE):
            with open(AFISHA_FILE, "rb") as f:
                await update.message.reply_photo(photo=f, caption=START_TEXT, reply_markup=courts_kb())
        else:
            await update.message.reply_text(START_TEXT, reply_markup=courts_kb())
    except:
        await update.message.reply_text(START_TEXT, reply_markup=courts_kb())

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    court_key = q.data.replace("join_", "")
    if court_key != PRIMARY_COURT_KEY and len(COURTS[PRIMARY_COURT_KEY]["users"]) < COURTS[PRIMARY_COURT_KEY]["max_slots"]:
        await q.message.reply_text("Сначала заполняем основной корт. Другие корты пока недоступны.")
        return
    user = q.from_user
    court = COURTS[court_key]["users"]
    if any(u["id"] == user.id for u in court):
        await q.message.reply_text("Ты уже зарегистрирован.")
        return
    court.append({"id": user.id, "first_name": user.first_name, "username": user.username, "paid": False, "court": court_key})
    save()
    await q.message.reply_text(f"Ты зарегистрирован на {COURTS[court_key]['title']}. Оплати и отправь чек.", reply_markup=user_kb())

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    removed = False
    for c in COURTS.values():
        for u in c["users"]:
            if u["id"] == uid:
                c["users"].remove(u)
                save()
                removed = True
                break
    await q.message.reply_text("Регистрация отменена." if removed else "Ты не был зарегистрирован.")

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    for k, c in COURTS.items():
        for u in c["users"]:
            if u["id"] == uid:
                status, pos = status_and_position(k, u)
                await q.message.reply_text(f"Корт: {c['title']}\nСтоимость: {c['price']} ₽\nСтатус: {status}\nПозиция: {pos}\n\nОплата: Сбербанк / Т-Банк\nНомер: 8 925 826-57-45\nСсылка: https://messenger.online.sberbank.ru/sl/7yOSdYz0k38b6kC9G\nПосле оплаты отправь чек (фото или файл).")
                return

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    text = "Информация по игре:\n\n"
    for k, c in COURTS.items():
        text += f"{c['title']}:\n"
        paid, unpaid = paid_sorted(k)
        if paid:
            for i, u in enumerate(paid[:c["max_slots"]], 1):
                username = f"@{u['username']}" if u.get("username") else "—"
                text += f"{i}. {u['first_name']} ({username}) — оплачено\n"
        if unpaid:
            for i, u in enumerate(unpaid, 1):
                username = f"@{u['username']}" if u.get("username") else "—"
                text += f"— {u['first_name']} ({username}) — не оплачено\n"
        if len(c["users"]) < c["max_slots"]:
            text += f"Набралось {len(c['users'])} игроков. Игра сокращённая, 1 час.\n"
        text += "\n"
    await q.message.reply_text(text)

# ================= RECEIVE CHECKS =================
async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if user.id == ADMIN_CHAT_ID: return
    found = False
    for k, c in COURTS.items():
        for u in c["users"]:
            if u["id"] == user.id:
                found = True
                if update.message.photo or update.message.document:
                    try: await context.bot.forward_message(ADMIN_CHAT_ID, update.message.chat_id, update.message.message_id)
                    except: pass
                    await update.message.reply_text("Чек получен! Оплата будет подтверждена администратором.")
                else: await update.message.reply_text("Отправь фото или документ чека.")
                return
    if not found: await update.message.reply_text("Ты не зарегистрирован.")

# ================= ADMIN =================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID: return
    await update.message.reply_text("Выбери действие:", reply_markup=admin_main_kb())

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    if data == "update_afisha":
        context.user_data["upload_afisha_active"] = True
        await q.message.reply_text("Отправь фото афиши для обновления:")
    elif data == "manage_courts":
        await q.message.reply_text("Выбери корт для управления:", reply_markup=admin_court_kb())
    elif data.startswith("manage_"):
        court_key = data.replace("manage_", "")
        kb = admin_court_manage_kb(court_key)
        if kb: await q.message.reply_text(f"Управление {COURTS[court_key]['title']}:", reply_markup=kb)
        else: await q.message.reply_text("На этом корте нет участников.")
    elif data.startswith("adm_user_"):
        parts = data.split("_"); _, _, court, idx, action = parts; idx = int(idx)
        if court not in COURTS or idx >= len(COURTS[court]["users"]):
            await q.edit_message_text("Игрок не найден"); return
        user = COURTS[court]["users"][idx]
        if action == "del":
            COURTS[court]["users"].pop(idx)
            save()
            try: await context.bot.send_message(user["id"], "Ты удалён администратором."); except: pass
            await q.edit_message_text(f"{user['first_name']} удалён.")
        elif action == "pay":
            user["paid"] = True
            save()
            try: await context.bot.send_message(user["id"], "Оплата подтверждена."); except: pass
            await q.edit_message_text(f"{user['first_name']} оплата подтверждена.")

async def upload_afisha_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if user.id != ADMIN_CHAT_ID or not context.user_data.get("upload_afisha_active"): return
    if update.message.photo:
        try: photo = update.message.photo[-1]; file = await photo.get_file(); await file.download_to_drive(AFISHA_FILE)
        except: pass
        await update.message.reply_text("Афиша обновлена")
    else: await update.message.reply_text("Это не фото. Отправь фото.")
    context.user_data.pop("upload_afisha_active", None)

# ================= MAIN =================
async def main():
    app = Application.builder().token(TOKEN).build()
    # USER
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(join, pattern="^join_"))
    app.add_handler(CallbackQueryHandler(pay, pattern="^pay$"))
    app.add_handler(CallbackQueryHandler(cancel, pattern="^cancel$"))
    app.add_handler(CallbackQueryHandler(info, pattern="^info$"))
    # RECEIPTS
    app.add_handler(MessageHandler((filters.PHOTO | filters.Document.ALL) & ~filters.User(user_id=ADMIN_CHAT_ID), receive_receipt))
    # ADMIN
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^(update_afisha|manage_courts|manage_.*|adm_user_.*)$"))
    app.add_handler(MessageHandler(filters.PHOTO & filters.User(user_id=ADMIN_CHAT_ID), upload_afisha_handler))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
