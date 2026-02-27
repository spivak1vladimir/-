import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ================== CONFIG ==================

TOKEN = "8540000411:AAHlqjProM_Z5SLow4Xh749Ibho6mPxbRK8"
ADMIN_CHAT_ID = 194614510
MAX_SLOTS = 30
DATA_FILE = "registered_users.json"

MOSCOW_TZ = ZoneInfo("Europe/Moscow")

GAME_DATETIME = datetime(
    2026, 3, 9, 19, 0,
    tzinfo=MOSCOW_TZ
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

# ================== TEXTS ==================

TERMS_TEXT = (
  "Пожалуйста, ознакомься с правилами участия в киновечере в лофте:\n"
"— Если гость из листа ожидания произведёт оплату раньше, чем гость из основного списка, он будет переведён в основной список участников.\n"
"— Просьба производить оплату заранее, так как требуется предварительная оплата аренды лофта и организация фуршета.\n"
"— Формат встречи включает совместный просмотр фильма, фуршет и последующее обсуждение картины в открытом формате.\n"
"— Участник самостоятельно несёт ответственность за свою жизнь и здоровье.\n"
"— Участник несёт ответственность за сохранность личных вещей.\n"
"— Согласие на обработку персональных данных.\n"
"— Согласие на фото- и видеосъёмку во время мероприятия.\n\n"
"Условия оплаты и отмены участия:\n"
"— При отмене участия менее чем за 24 часа до начала киновечера оплата не возвращается.\n"
"— При отмене не позднее чем за 24 часа до начала мероприятия средства возвращаются.\n"
"— Допускается передача оплаченного места другому гостю при самостоятельном поиске замены.\n\n"
)

START_TEXT = (
    "Собираемся в лофте на кинопоказ:\n"
    "Цитрус Холл\n"
    "Садовническая ул., 78, стр. 5, Москва\n"
    "метро Павелецкая\n"
    "09 марта 2026\n"
    "Сбор: 18:40\n"
    "Начало просмотра: 19:00\n\n"
    "Ты присоединился на кинопаказ\n\n"
    + TERMS_TEXT +
    "Если согласен с условиями — нажми кнопку ниже."
)

BASE_INFO_TEXT = (
    "Киновечер от Ани Архипенко\n\n"
    "09 марта 2026\n"
    "Сбор: 18:40\n"
    "Начало просмотра: 19:00\n\n"
    "Адрес:\n"
    "Цитрус Холл\n"
    "метро Павелецкая\n"
    "Садовническая ул., 78, стр. 5, Москва\n"
    "https://yandex.ru/maps/-/CPeTRCMn\n\n"
)

PAYMENT_TEXT = (
    "Стоимость участия — 1300 ₽\n\n"
    "Оплата по номеру 8 925 826-57-45\n"
    "Сбербанк / Т-Банк\n\n"
    "Ссылка для оплаты:\n"
    "https://messenger.online.sberbank.ru/sl/rI5Wt9jmVbG90spq6\n\n"
    "После оплаты нажми кнопку ниже."
)

REMINDER_24H = "Напоминание\nКинопоказ состоится завтра в 22:00."
REMINDER_4H = "Напоминание\nКинопоказ начнётся через 4 часа."

# ================== STORAGE ==================

registered_users: list[dict] = []


def load_users_sync():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_users_sync(users):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


async def load_users():
    global registered_users
    registered_users = await asyncio.to_thread(load_users_sync)


async def save_users():
    await asyncio.to_thread(save_users_sync, registered_users)

# ================== HELPERS ==================

def build_admin_new_user_text(user, position):
    status = "основной состав" if position <= MAX_SLOTS else "лист ожидания"
    username = f"@{user.username}" if user.username else "—"

    return (
        "Новый игрок!\n\n"
        f"Имя: {user.first_name}\n"
        f"Username: {username}\n"
        f"ID: {user.id}\n"
        f"Статус: {status}\n"
        f"Позиция: {position}"
    )


def build_user_status_text(user, position):
    status = "основной состав" if position <= MAX_SLOTS else "лист ожидания"
    username = f"@{user.username}" if user.username else "—"

    return (
        "Регистрация принята \n\n"
        f"Имя: {user.first_name}\n"
        f"Username: {username}\n"
        f"ID: {user.id}\n"
        f"Статус: {status}\n"
        f"Позиция: {position}\n\n"
        "Используй кнопки ниже для управления участием 👇"
    )

def try_promote_paid_user():
    if len(registered_users) <= MAX_SLOTS:
        return

    # ищем неоплаченного в основном составе
    for i in range(MAX_SLOTS):
        if not registered_users[i].get("paid"):
            # ищем оплаченного в листе ожидания
            for j in range(MAX_SLOTS, len(registered_users)):
                if registered_users[j].get("paid"):
                    # меняем местами
                    registered_users[i], registered_users[j] = (
                        registered_users[j],
                        registered_users[i],
                    )
                    return


def build_participants_text():
    if not registered_users:
        return "Участников пока нет."

    text = "Участники:\n\n"

    # Основной состав
    text += " Основной состав:\n"
    for i, u in enumerate(registered_users[:MAX_SLOTS], 1):
        paid = " оплачено" if u.get("paid") else " не оплачено"
        arrived = " пришёл" if u.get("arrived") else "—"
        username = f"@{u['username']}" if u.get("username") else "—"
        text += f"{i}. {u['first_name']} ({username}) — {paid} — {arrived}\n"

    # Лист ожидания
    if len(registered_users) > MAX_SLOTS:
        text += "\n──────────────\n⏳ Лист ожидания:\n"
        for i, u in enumerate(registered_users[MAX_SLOTS:], MAX_SLOTS + 1):
            paid = " оплачено" if u.get("paid") else " не оплачено"
            username = f"@{u['username']}" if u.get("username") else "—"
            text += f"{i}. {u['first_name']} ({username}) — {paid}\n"

    return text


def build_info_text():
    return (
        BASE_INFO_TEXT
        + f"Количество участников: {len(registered_users)}\n\n"
        + build_participants_text()
    )


def participant_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Информация по кинопоказу", callback_data="info")],
        [InlineKeyboardButton("Оплатить", callback_data="paid")],
        [InlineKeyboardButton("Пришёл", callback_data="arrived_self")],
        [InlineKeyboardButton("Отменить участие", callback_data="cancel")],
    ])

# ================== USER HANDLERS ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Принимаю", callback_data="register")],
        [InlineKeyboardButton("Информация по кинопоказу", callback_data="info")],
    ]
    await update.message.reply_text(START_TEXT, reply_markup=InlineKeyboardMarkup(keyboard))


async def info_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(build_info_text())


async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if any(u["id"] == user.id for u in registered_users):
        await query.edit_message_text("Ты уже зарегистрирован.")
        return

    user_data = {
        "id": user.id,
        "first_name": user.first_name,
        "username": user.username,
        "paid": False,
        "arrived": False,
    }

    registered_users.append(user_data)
    await save_users()

    position = len(registered_users)

    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=build_admin_new_user_text(user, position),
    )

    await context.bot.send_message(
        chat_id=user.id,
        text=build_user_status_text(user, position),
        reply_markup=participant_keyboard(),
    )

    if position <= MAX_SLOTS:
        await context.bot.send_message(
            chat_id=user.id,
            text=PAYMENT_TEXT,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Я оплатил", callback_data="paid")]
            ]),
        )

    await query.edit_message_text("Регистрация принята.")


async def paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    
    user_data = next((u for u in registered_users if u["id"] == user.id), None)
    if user_data:
        user_data["paid"] = True
        try_promote_paid_user()
        await save_users()

    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=f"Игрок {user.first_name} нажал кнопку «Я оплатил».",
    )

    await query.edit_message_text("Ожидается подтверждение оплаты администратором.")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    user_data = next((u for u in registered_users if u["id"] == user.id), None)
    if not user_data:
        await query.edit_message_text("Ты не зарегистрирован.")
        return

    registered_users.remove(user_data)
    await save_users()
    await promote_from_waiting_list(context)

    await query.edit_message_text("Ты отменил участие.")


async def arrived_self(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    user_data = next((u for u in registered_users if u["id"] == user.id), None)
    if not user_data:
        await query.edit_message_text("Ты не зарегистрирован.")
        return

    user_data["arrived"] = True
    await save_users()

    await query.edit_message_text("Отлично  Ты отмечен как пришедший на кинопоказ.")

# ================== ADMIN ==================

async def promote_from_waiting_list(context: ContextTypes.DEFAULT_TYPE):
    if len(registered_users) < MAX_SLOTS:
        return

    user = registered_users[MAX_SLOTS - 1]
    if user.get("paid"):
        return

    await context.bot.send_message(
        chat_id=user["id"],
        text="Для тебя освободилось место в основном составе.\n\n" + PAYMENT_TEXT,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Я оплатил", callback_data="paid")]
        ]),
    )


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("Доступ запрещён.")
        return

    keyboard = []
    for i, u in enumerate(registered_users):
        row = [
            InlineKeyboardButton(f"Удалить {u['first_name']}", callback_data=f"del_{i}")
        ]
        if not u["paid"]:
            row.append(
                InlineKeyboardButton(f"Подтвердить оплату {u['first_name']}", callback_data=f"pay_{i}")
            )
        if not u["arrived"]:
            row.append(
                InlineKeyboardButton(f"Пришёл {u['first_name']}", callback_data=f"arr_{i}")
            )
        keyboard.append(row)

    await update.message.reply_text(
        build_participants_text(),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def admin_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split("_")[1])

    registered_users.pop(idx)
    await save_users()
    await promote_from_waiting_list(context)

    await query.edit_message_text("Участник удалён.")


async def admin_confirm_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split("_")[1])

    registered_users[idx]["paid"] = True
    try_promote_paid_user()
    await save_users()

    await context.bot.send_message(
        chat_id=registered_users[idx]["id"],
        text="Оплата подтверждена администратором.",
    )

    await query.edit_message_text("Оплата подтверждена.")


async def admin_arrived(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split("_")[1])

    registered_users[idx]["arrived"] = True
    await save_users()

    await query.edit_message_text("Отмечен как пришёл.")

async def admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Напиши текст сообщения:\n/admin_message Текст")
        return

    for u in registered_users:
        try:
            await context.bot.send_message(u["id"], text)
        except Exception:
            pass

    await update.message.reply_text("Сообщение отправлено всем участникам ")


# ================== REMINDERS ==================

async def reminder_24h(context: ContextTypes.DEFAULT_TYPE):
    for u in registered_users:
        await context.bot.send_message(u["id"], REMINDER_24H)


async def reminder_4h(context: ContextTypes.DEFAULT_TYPE):
    for u in registered_users:
        await context.bot.send_message(u["id"], REMINDER_4H)

# ================== MAIN ==================

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    loop.run_until_complete(load_users())

    app = Application.builder().token(TOKEN).build()

    app.job_queue.run_once(reminder_24h, when=GAME_DATETIME - timedelta(hours=24))
    app.job_queue.run_once(reminder_4h, when=GAME_DATETIME - timedelta(hours=4))

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("admin_message", admin_message))


    app.add_handler(CallbackQueryHandler(register, pattern="^register$"))
    app.add_handler(CallbackQueryHandler(paid, pattern="^paid$"))
    app.add_handler(CallbackQueryHandler(arrived_self, pattern="^arrived_self$"))
    app.add_handler(CallbackQueryHandler(cancel, pattern="^cancel$"))
    app.add_handler(CallbackQueryHandler(info_cb, pattern="^info$"))

    app.add_handler(CallbackQueryHandler(admin_delete, pattern="^del_"))
    app.add_handler(CallbackQueryHandler(admin_confirm_payment, pattern="^pay_"))
    app.add_handler(CallbackQueryHandler(admin_arrived, pattern="^arr_"))

    logging.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()