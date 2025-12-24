# handlers.py
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, MessageHandler, filters
from supabase import create_client
from datetime import datetime, timezone, timedelta
import os
from utils import has_active_access, days_left

BOT_TOKEN = os.environ["BOT_TOKEN"]
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

# === Генерация Reply-клавиатуры ===
def get_main_keyboard(tg_id: int):
    buttons = [
        [KeyboardButton("Подключить пересыл")],
        [KeyboardButton("Личный кабинет")]
    ]
    if tg_id == ADMIN_TG_ID:
        buttons.append([KeyboardButton("Админ")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=False)

# === Handlers ===

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

    await update.message.reply_text(
        text,
        reply_markup=get_main_keyboard(tg_id)
    )

# --- Подключить пересыл ---
async def setup_relay_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Обрабатываем текстовое сообщение
    tg_id = update.effective_user.id
    db_user = get_user(tg_id)

    if not has_active_access(db_user):
        text = "❌ У вас нет активной подписки. Сначала оформите доступ в «Личном кабинете»."
    else:
        text = "📬 Отправьте ссылку на исходный канал/чат (откуда пересылать)."

    await update.message.reply_text(text, reply_markup=get_main_keyboard(tg_id))

# --- Личный кабинет ---
async def cabinet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    db_user = get_user(tg_id)

    if not db_user:
        await update.message.reply_text("❌ Ошибка: пользователь не найден.", reply_markup=get_main_keyboard(tg_id))
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
        await update.message.reply_text(
            text,
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton("Да")],
                [KeyboardButton("Назад")]
            ], resize_keyboard=True)
        )
        return

    await update.message.reply_text(text, reply_markup=get_main_keyboard(tg_id))

# --- Запрос подписки ---
async def request_subscription_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_id = user.id
    username = user.username

    if not username:
        await update.message.reply_text(
            "⚠️ У вас не установлен username в Telegram.\n"
            "Пожалуйста, установите его в настройках Telegram и нажмите /start снова.",
            reply_markup=get_main_keyboard(tg_id)
        )
        return

    set_awaiting_payment(tg_id, True)

    await context.bot.send_message(
        chat_id=OWNER_TG_ID,
        text=f"🔔 Пользователь @{username} (ID: {tg_id}) хочет купить подписку.\n"
             f"Свяжитесь с ним в ЛС для оплаты."
    )

    await update.message.reply_text(
        "✅ Отлично! Владелец скоро свяжется с вами в личных сообщениях для оформления подписки.",
        reply_markup=get_main_keyboard(tg_id)
    )

# --- Админка ---
async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = get_all_users()
    if not users:
        await update.message.reply_text("Нет пользователей.", reply_markup=get_main_keyboard(update.effective_user.id))
        return

    text = "👥 Список пользователей:\n\n"
    for u in users:
        name = f"@{u['username']}" if u['username'] else f"ID: {u['tg_id']}"
        status = "🟢" if u.get("is_active", False) else "🔴"
        text += f"{status} {name}\n"

    await update.message.reply_text(text, reply_markup=get_main_keyboard(update.effective_user.id))

# --- Действия админа ---
async def admin_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Здесь можно реализовать логику, но пока просто сообщаем
    await update.message.reply_text("✅ Действие выполнено", reply_markup=get_main_keyboard(update.effective_user.id))

# --- Назад к старту ---
async def back_to_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start_handler(update, context)
