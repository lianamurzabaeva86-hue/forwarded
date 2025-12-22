# handlers.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from supabase import create_client
from datetime import datetime, timezone, timedelta
import os
from utils import has_active_access, days_left

# Переменные окружения
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_TG_ID = int(os.environ["ADMIN_TG_ID"])
OWNER_TG_ID = int(os.environ["OWNER_TG_ID"])
SUBSCRIPTION_PRICE = os.getenv("SUBSCRIPTION_PRICE", "150₽/месяц")

# Supabase
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
TABLE_NAME = os.getenv("USERS_TABLE", "users")  # можно задать имя таблицы

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

# --- Handlers ---
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id
    username = user.username
    init_user(tg_id, username)

    text = (
        "👋 Привет! Это бот для пересылки сообщений с одного канала/группы в другой.\n\n"
        "У вас активен **2-дневный бесплатный пробный период**.\n"
        f"После его окончания требуется подписка: {SUBSCRIPTION_PRICE}"
    )

    buttons = [
        [InlineKeyboardButton("Подключить пересыл", callback_data="setup_relay")],
        [InlineKeyboardButton("Личный кабинет", callback_data="cabinet")]
    ]

    if tg_id == ADMIN_TG_ID:
        buttons.append([InlineKeyboardButton("Админ", callback_data="admin_panel")])

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def cabinet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tg_id = query.from_user.id
    db_user = get_user(tg_id)

    if not db_user:
        await query.edit_message_text("❌ Ошибка: пользователь не найден.")
        return

    if db_user["awaiting_payment"]:
        text = "⏳ Вы запросили подписку. Владелец скоро свяжется с вами в личных сообщениях."
    elif has_active_access(db_user):
        days = days_left(db_user)
        text = f"✅ У вас активна подписка!\nОсталось дней: {days}"
    else:
        text = (
            "❌ Пробный период закончился.\n"
            f"Стоимость подписки: {SUBSCRIPTION_PRICE}\n"
            "Нажмите «Да», чтобы приобрести."
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Да", callback_data="request_subscription")]
            ])
        )
        return

    await query.edit_message_text(text)

async def request_subscription_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    tg_id = user.id
    username = user.username

    if not username:
        await query.edit_message_text(
            "⚠️ У вас не установлен username в Telegram.\n"
            "Пожалуйста, установите его в настройках Telegram и нажмите /start снова."
        )
        return

    set_awaiting_payment(tg_id, True)

    await context.bot.send_message(
        chat_id=OWNER_TG_ID,
        text=f"🔔 Пользователь @{username} (ID: {tg_id}) хочет купить подписку.\n"
             f"Свяжитесь с ним в ЛС для оплаты."
    )

    await query.edit_message_text(
        "✅ Отлично! Владелец скоро свяжется с вами в личных сообщениях для оформления подписки."
    )

async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    users = get_all_users()
    if not users:
        await query.edit_message_text("Нет пользователей.")
        return

    text = "👥 Список пользователей:\n\n"
    buttons = []

    for u in users:
        name = f"@{u['username']}" if u['username'] else f"ID: {u['tg_id']}"
        status = "🟢" if u.get("is_active", False) else "🔴"
        text += f"{status} {name}\n"
        action = "revoke" if u.get("is_active", False) else "grant"
        buttons.append([
            InlineKeyboardButton(
                f"{'Заблокировать' if u.get('is_active', False) else 'Разрешить'} ({name})",
                callback_data=f"admin_{action}_{u['tg_id']}"
            )
        ])

    buttons.append([InlineKeyboardButton("Назад", callback_data="back_to_start")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def admin_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, action, tg_id_str = query.data.split("_")
    tg_id = int(tg_id_str)

    if action == "grant":
        grant_access(tg_id)
        msg = "✅ Доступ разрешён на 30 дней."
    elif action == "revoke":
        revoke_access(tg_id)
        msg = "❌ Доступ отключён."

    await query.edit_message_text(msg)

async def back_to_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_handler(update, co
