# handlers.py
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from supabase import create_client
import os

# === Настройки ===
ADMIN_TG_ID = int(os.environ["ADMIN_TG_ID"])
OWNER_TG_ID = int(os.environ["OWNER_TG_ID"])
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

def get_main_keyboard(tg_id: int):
    buttons = [[KeyboardButton("Подключить пересыл")]]
    if tg_id == ADMIN_TG_ID:
        buttons.append([KeyboardButton("Админ")])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Бот пересылки. Нажмите «Подключить пересыл».",
        reply_markup=get_main_keyboard(update.effective_user.id)
    )

async def setup_source_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = "awaiting_source"
    await update.message.reply_text("📤 Отправьте ссылку на исходный чат:")

async def handle_source_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") == "awaiting_source":
        context.user_data["source"] = update.message.text.strip()
        context.user_data["state"] = "awaiting_target"
        await update.message.reply_text("📥 Отправьте ссылку на целевой чат:")
        return True
    return False

async def handle_target_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("state") == "awaiting_target":
        source = context.user_data["source"]
        target = update.message.text.strip()
        tg_id = update.effective_user.id
        
        # Сохраняем в relay_config
        supabase.table("relay_config").upsert({
            "tg_id": tg_id,
            "source_link": source,
            "target_link": target,
            "active": True
        }).execute()
        
        context.user_data["state"] = None
        await update.message.reply_text(
            f"✅ Пересылка активна!\nИз: {source}\nВ: {target}"
        )
        return True
    return False
