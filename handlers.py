# handlers.py
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from supabase import create_client
from datetime import datetime, timezone, timedelta
import os
from utils import has_active_access

# === Настройки ===
ADMIN_TG_ID = int(os.environ["ADMIN_TG_ID"])
OWNER_TG_ID = int(os.environ["OWNER_TG_ID"])
SUBSCRIPTION_PRICE = os.getenv("SUBSCRIPTION_PRICE", "150₽/месяц")
TABLE_NAME = os.getenv("USERS_TABLE", "users")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

def get_user(tg_id: int):
    res = supabase.table(TABLE_NAME).select("*").eq("tg_id", tg_id).execute()
    return res.data[0] if res.data else None

def init_user(tg_id: int, username: str = None):
    now = datetime.now(timezone.utc)
    existing = get_user(tg_id)
    if not existing:
        supabase.table(TABLE_NAME).insert({
            "tg_id": tg_id,
            "username": username,
            "trial_start": now.isoformat(),
            "is_active": True,
            "awaiting_payment": False
        }).execute()
    elif username and existing.get("username") != username:
        supabase.table(TABLE_NAME).update({"username": username}).eq("tg_id", tg_id).execute()

def set_awaiting_payment(tg_id: int, status: bool):
    supabase.table(TABLE_NAME).update({"awaiting_payment": status}).eq("tg_id", tg_id).execute()

def grant_access(tg_id: int):
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=int(os.getenv("SUBSCRIPTION_DAYS", "30")))
    supabase.table(TABLE_NAME).update({
        "is_active": True,
        "subscription_end": end.isoformat(),
        "awaiting_payment": False
    }).eq("tg_id", tg_id).execute()

def revoke_access(tg_id: int):
    supabase.table(TABLE_NAME).update({
        "is_active": False,
        "subscription_end": None
    }).eq("tg_id", tg_id).execute()

def get_all_users():
    return supabase.table(TABLE_NAME).select("*").execute().data

def get_main_keyboard(tg_id: int):
    buttons = [
        [KeyboardButton("Подключить пересыл")],
        [KeyboardButton("Личный кабинет")]
    ]
    if tg_id == ADMIN_TG_ID:
        buttons.append([KeyboardButton("Админ")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

# === Основные обработчики ===

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id
    username = user.username
    init_user(tg_id, username)

    text = (
        "🔒 Бот не собирает персональные данные.\n"
        "Используются только технические данные Telegram (ID и username).\n\n"
        "👋 Привет! Это бот для пересылки сообщений...\n"
        f"Подписка: {SUBSCRIPTION_PRICE}"
    )
    await update.message.reply_text(text, reply_markup=get_main_keyboard(tg_id))

async def setup_relay_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    db_user = get_user(tg_id)
    if not has_active_access(db_user):
        await update.message.reply_text(
            "❌ Нет активной подписки. Оформите в «Личном кабинете».",
            reply_markup=get_main_keyboard(tg_id)
        )
        return
    context.user_data["awaiting_source"] = True
    await update.message.reply_text(
        "📬 Отправьте ссылку на исходный канал/чат.",
        reply_markup=get_main_keyboard(tg_id)
    )

async def handle_source_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_source"):
        text = update.message.text.strip()
        # Игнорируем кнопки
        if text in {"Подключить пересыл", "Личный кабинет", "Админ", "Да", "Назад"}:
            return False
        context.user_data["awaiting_source"] = False
        await update.message.reply_text(
            f"✅ Ссылка получена: {text}",
            reply_markup=get_main_keyboard(update.effective_user.id)
        )
        return True
    return False

async def cabinet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    db_user = get_user(tg_id)
    if not db_user:
        await update.message.reply_text("❌ Ошибка.", reply_markup=get_main_keyboard(tg_id))
        return
    if db_user["awaiting_payment"]:
        text = "⏳ Запрос подписки отправлен."
    elif has_active_access(db_user):
        from utils import days_left
        text = f"✅ Подписка активна. Осталось дней: {days_left(db_user)}"
    else:
        text = f"❌ Пробный период окончен.\nСтоимость: {SUBSCRIPTION_PRICE}"
        await update.message.reply_text(
            text,
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton("Да")],
                [KeyboardButton("Назад")]
            ], resize_keyboard=True)
        )
        return
    await update.message.reply_text(text, reply_markup=get_main_keyboard(tg_id))

async def request_subscription_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id
    username = user.username
    if not username:
        await update.message.reply_text(
            "⚠️ Установите username в Telegram и нажмите /start.",
            reply_markup=get_main_keyboard(tg_id)
        )
        return
    set_awaiting_payment(tg_id, True)
    await context.bot.send_message(
        chat_id=OWNER_TG_ID,
        text=f"🔔 Пользователь @{username} (ID: {tg_id}) хочет купить подписку."
    )
    await update.message.reply_text(
        "✅ Владелец скоро свяжется с вами.",
        reply_markup=get_main_keyboard(tg_id)
    )

async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_users()
    if not users:
        await update.message.reply_text("Нет пользователей.", reply_markup=get_main_keyboard(update.effective_user.id))
        return
    text = "👥 Пользователи:\n\n"
    for u in users:
        name = f"@{u['username']}" if u['username'] else f"ID: {u['tg_id']}"
        status = "🟢" if u.get("is_active") else "🔴"
        text += f"{status} {name}\n"
    await update.message.reply_text(text, reply_markup=get_main_keyboard(update.effective_user.id))

async def back_to_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_handler(update, context)
