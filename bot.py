import os
import json
import re
from datetime import datetime
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

# Вариант 1: вставь токен напрямую
TOKEN = "8618097739:AAEkgPPoH5LAXOxv2-sKZdK8rnfwf5x2CrI"

ADMIN_CHAT_ID = 194614510
DATA_FILE = "trip_users.json"
MOSCOW_TZ = ZoneInfo("Europe/Moscow")

EVENT = {
    "title": "Поездка в Казань на забег",
    "dates": "1–4 мая",
    "price": 29000,
    "max_slots": 12,
    "payment_phone": "8 925 826-57-45",
    "payment_banks": "Сбербанк / Т-Банк",
    "payment_link": "https://messenger.online.sberbank.ru/sl/WfKkX7QCNGEQOXLOH",
}

if not TOKEN or "СЮДА_ВСТАВЬ" in TOKEN:
    raise RuntimeError("Укажи новый токен бота в переменной TOKEN.")

# ================== TEXTS ==================

def places_left():
    confirmed = len([u for u in users if u.get("active", True)])
    return max(EVENT["max_slots"] - confirmed, 0)

def start_text():
    return (
        f"🏃 {EVENT['title']}\n\n"
        f"Даты: {EVENT['dates']}\n"
        f"Стоимость: {EVENT['price']} ₽\n"
        f"Осталось мест: {places_left()}\n\n"
        "В стоимость уже включено:\n"
        "— дорога туда-обратно\n"
        "— проживание\n"
        "— завтрак\n"
        "— подготовка к забегу\n"
        "— платная дорога\n"
        "— страховой сбор\n\n"
        "По отдельности такая поездка выйдет дороже.\n\n"
        "Нажми кнопку ниже, чтобы зарегистрироваться."
    )

TERMS_TEXT = (
    "Условия участия\n\n"
    "Стоимость поездки: 29 000 ₽.\n\n"
    "В стоимость включено:\n"
    "— дорога туда-обратно\n"
    "— проживание\n"
    "— завтрак\n"
    "— подготовка к забегу\n"
    "— платная дорога\n"
    "— страховой сбор\n\n"
    "Страховой сбор уже включён в общую стоимость, потому что мы берём на себя "
    "риски, связанные с арендой минивэна и дома.\n\n"
    "Это не отдельная скрытая доплата — всё уже включено.\n"
    "Если собирать поездку отдельно, оплачивать дорогу, жильё и организацию самостоятельно, "
    "выйдет дороже.\n\n"
    "Продолжая регистрацию, ты соглашаешься с этими условиями."
)

INFO_TEXT = (
    "Что входит в стоимость\n\n"
    "Цена участия: 29 000 ₽\n\n"
    "Включено:\n"
    "— дорога туда-обратно\n"
    "— проживание\n"
    "— завтрак\n"
    "— подготовка к забегу\n"
    "— платная дорога\n"
    "— страховой сбор\n\n"
    "Страховой сбор включён, потому что организатор берёт на себя риски за минивэн и дом.\n\n"
    "Для участника это удобная фиксированная цена без скрытых расходов.\n"
    "По отдельности поездка обойдётся дороже."
)

PAY_TEXT = (
    "Оплата участия\n\n"
    "Стоимость: 29 000 ₽\n\n"
    "В сумму уже входит:\n"
    "— дорога туда-обратно\n"
    "— проживание\n"
    "— завтрак\n"
    "— подготовка к забегу\n"
    "— платная дорога\n"
    "— страховой сбор\n\n"
    "Страховой сбор включён, так как мы берём риски за минивэн и дом.\n"
    "По отдельности такая поездка выйдет дороже.\n\n"
    "Оплата по номеру:\n"
    "8 925 826-57-45\n"
    "Сбербанк / Т-Банк\n\n"
    "Ссылка для оплаты:\n"
    "https://messenger.online.sberbank.ru/sl/7yOSdYz0k38b6kC9G\n\n"
    "После оплаты отправь в бот чек: фото или файл."
)

SUCCESS_PAYMENT_TEXT = (
    "Оплата подтверждена.\n\n"
    "Ты успешно зарегистрирован в поездку в Казань.\n"
    "Позже отправим детали по выезду, проживанию и программе."
)

# ================== STORAGE ==================

def load_users():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

users = load_users()

# ================== HELPERS ==================

def find_user(user_id: int):
    for u in users:
        if u["id"] == user_id:
            return u
    return None

def active_users():
    return [u for u in users if u.get("active", True)]

def is_valid_phone(phone: str):
    digits = re.sub(r"\D", "", phone)
    return len(digits) >= 10

# ================== KEYBOARDS ==================

def start_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(" Зарегистрироваться", callback_data="register")],
        [InlineKeyboardButton(" Что входит в стоимость", callback_data="info")],
        [InlineKeyboardButton(" Сколько осталось мест", callback_data="places")],
    ])

def terms_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Согласен, продолжить", callback_data="agree_terms")],
        [InlineKeyboardButton("Назад", callback_data="back_start")],
    ])

def user_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(" Оплатить", callback_data="pay")],
        [InlineKeyboardButton(" Моя анкета", callback_data="profile")],
        [InlineKeyboardButton(" Информация", callback_data="info")],
        [InlineKeyboardButton(" Отменить участие", callback_data="cancel")],
    ])

def admin_user_kb(user_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(" Подтвердить оплату", callback_data=f"adm_pay_{user_id}")],
        [InlineKeyboardButton(" Удалить участника", callback_data=f"adm_del_{user_id}")],
    ])

# ================== USER FLOW ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(start_text(), reply_markup=start_kb())

async def back_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data.clear()
    await q.message.reply_text(start_text(), reply_markup=start_kb())

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(INFO_TEXT)

async def places(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(
        f"Свободных мест осталось: {places_left()} из {EVENT['max_slots']}"
    )

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if places_left() <= 0:
        await q.message.reply_text("Свободных мест больше нет.")
        return

    await q.message.reply_text(TERMS_TEXT, reply_markup=terms_kb())

async def agree_terms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    tg_user = q.from_user
    existing = find_user(tg_user.id)

    if existing and existing.get("active", True):
        await q.message.reply_text(
            "Ты уже есть в списке участников.",
            reply_markup=user_kb()
        )
        return

    context.user_data["registration_step"] = "fio"
    await q.message.reply_text("Напиши ФИО полностью:")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    tg_user = update.effective_user
    step = context.user_data.get("registration_step")

    # Админский режим сообщений
    admin_mode = context.user_data.get("admin_msg_mode")
    if tg_user.id == ADMIN_CHAT_ID and admin_mode:
        await admin_text_sender(update, context)
        return

    if not step:
        return

    if step == "fio":
        context.user_data["fio"] = text
        context.user_data["registration_step"] = "phone"
        await update.message.reply_text("Напиши номер телефона:")

    elif step == "phone":
        if not is_valid_phone(text):
            await update.message.reply_text("Номер выглядит некорректно. Напиши телефон ещё раз.")
            return

        context.user_data["phone"] = text
        context.user_data["registration_step"] = "city"
        await update.message.reply_text("Напиши свой город:")

    elif step == "city":
        context.user_data["city"] = text

        existing = find_user(tg_user.id)
        if existing:
            existing["fio"] = context.user_data["fio"]
            existing["phone"] = context.user_data["phone"]
            existing["city"] = context.user_data["city"]
            existing["username"] = tg_user.username or ""
            existing["first_name"] = tg_user.first_name or ""
            existing["paid"] = existing.get("paid", False)
            existing["active"] = True
        else:
            users.append({
                "id": tg_user.id,
                "first_name": tg_user.first_name or "",
                "username": tg_user.username or "",
                "fio": context.user_data["fio"],
                "phone": context.user_data["phone"],
                "city": context.user_data["city"],
                "paid": False,
                "active": True,
                "created_at": datetime.now(MOSCOW_TZ).isoformat(),
            })

        save_users()
        context.user_data.pop("registration_step", None)

        await update.message.reply_text(
            "✅ Анкета заполнена.\n\n"
            "Теперь для подтверждения участия нужно внести оплату.",
            reply_markup=user_kb()
        )

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    user = find_user(q.from_user.id)
    if not user:
        await q.message.reply_text("Сначала зарегистрируйся через /start")
        return

    username = f"@{user['username']}" if user.get("username") else "—"
    paid = "оплачено" if user.get("paid") else "не оплачено"

    text = (
        "📝 Твоя анкета\n\n"
        f"ФИО: {user.get('fio', '—')}\n"
        f"Телефон: {user.get('phone', '—')}\n"
        f"Город: {user.get('city', '—')}\n"
        f"Username: {username}\n"
        f"Статус оплаты: {paid}"
    )
    await q.message.reply_text(text)

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    user = find_user(q.from_user.id)
    if not user:
        await q.message.reply_text("Сначала зарегистрируйся через /start")
        return

    await q.message.reply_text(PAY_TEXT)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    user = find_user(q.from_user.id)
    if not user or not user.get("active", True):
        await q.message.reply_text("Тебя нет в активном списке участников.")
        return

    user["active"] = False
    save_users()
    await q.message.reply_text("Твоя регистрация отменена.")

async def receive_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.message.from_user
    user = find_user(tg_user.id)

    if not user or not user.get("active", True):
        await update.message.reply_text("Сначала зарегистрируйся через /start")
        return

    await context.bot.forward_message(
        chat_id=ADMIN_CHAT_ID,
        from_chat_id=update.message.chat_id,
        message_id=update.message.message_id
    )

    username = f"@{user['username']}" if user.get("username") else "—"

    admin_text = (
        "📩 Новый чек на подтверждение\n\n"
        f"ФИО: {user.get('fio', '—')}\n"
        f"Телефон: {user.get('phone', '—')}\n"
        f"Город: {user.get('city', '—')}\n"
        f"Username: {username}\n"
        f"Telegram ID: {user['id']}\n"
        f"Поездка: {EVENT['title']}\n"
        f"Стоимость: {EVENT['price']} ₽"
    )

    await context.bot.send_message(
        ADMIN_CHAT_ID,
        admin_text,
        reply_markup=admin_user_kb(user["id"])
    )

    await update.message.reply_text(
        "Чек отправлен на проверку. После подтверждения оплаты ты получишь сообщение."
    )

# ================== ADMIN ==================

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    current_users = active_users()

    if not current_users:
        await update.message.reply_text("Пока нет зарегистрированных участников.")
        return

    lines = [
        f"📋 Участники поездки\n",
        f"Всего активных: {len(current_users)}",
        f"Свободных мест: {places_left()}",
        ""
    ]

    for i, u in enumerate(current_users, start=1):
        paid = "оплачено" if u.get("paid") else "не оплачено"
        username = f"@{u['username']}" if u.get("username") else "—"
        lines.append(
            f"{i}. {u.get('fio', u.get('first_name', 'Без имени'))}\n"
            f"   {username} | {u.get('phone', '—')} | {u.get('city', '—')} | {paid}"
        )

    await update.message.reply_text("\n".join(lines))

async def admin_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_CHAT_ID:
        return

    user_id = int(q.data.replace("adm_pay_", ""))
    user = find_user(user_id)

    if not user:
        await q.edit_message_text("Участник не найден.")
        return

    user["paid"] = True
    save_users()

    await context.bot.send_message(user_id, SUCCESS_PAYMENT_TEXT)
    await q.edit_message_text("Оплата подтверждена.")

async def admin_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_CHAT_ID:
        return

    user_id = int(q.data.replace("adm_del_", ""))
    user = find_user(user_id)

    if not user:
        await q.edit_message_text("Участник не найден.")
        return

    user["active"] = False
    save_users()

    await context.bot.send_message(user_id, "Твоя регистрация отменена администратором.")
    await q.edit_message_text("Участник удалён из активного списка.")

async def admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    context.user_data["admin_msg_mode"] = "all"
    await update.message.reply_text("Напиши сообщение для всех активных участников:")

async def admin_text_sender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    mode = context.user_data.get("admin_msg_mode")
    if mode != "all":
        return

    text = update.message.text
    for u in active_users():
        await context.bot.send_message(u["id"], text)

    context.user_data.pop("admin_msg_mode", None)
    await update.message.reply_text("Сообщение отправлено всем активным участникам.")

# ================== MAIN ==================

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("admin_message", admin_message))

    app.add_handler(CallbackQueryHandler(back_start, pattern="^back_start$"))
    app.add_handler(CallbackQueryHandler(info, pattern="^info$"))
    app.add_handler(CallbackQueryHandler(places, pattern="^places$"))
    app.add_handler(CallbackQueryHandler(register, pattern="^register$"))
    app.add_handler(CallbackQueryHandler(agree_terms, pattern="^agree_terms$"))
    app.add_handler(CallbackQueryHandler(profile, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(pay, pattern="^pay$"))
    app.add_handler(CallbackQueryHandler(cancel, pattern="^cancel$"))

    app.add_handler(CallbackQueryHandler(admin_pay, pattern="^adm_pay_"))
    app.add_handler(CallbackQueryHandler(admin_del, pattern="^adm_del_"))

    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, receive_receipt))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()

if __name__ == "__main__":
    main()