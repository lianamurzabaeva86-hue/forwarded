# bot.py
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ContextTypes
from telegram import Update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def error_handler(update, context):
    logger.error(f"Ошибка: {context.error}", exc_info=True)

from handlers import (
    start_handler,
    setup_source_handler,
    setup_target_handler,
    cabinet_handler,
    request_subscription_handler,
    admin_panel_handler,
    back_to_start_handler,
    handle_source_link,
    handle_target_link,
    relay_message_handler,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
RENDER_EXTERNAL_URL = os.environ["RENDER_EXTERNAL_URL"]
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = RENDER_EXTERNAL_URL + WEBHOOK_PATH

application = Application.builder().token(BOT_TOKEN).build()
application.add_error_handler(error_handler)

# === Регистрация обработчиков ===
application.add_handler(CommandHandler("start", start_handler))

# Сначала — кнопки
application.add_handler(MessageHandler(filters.Regex(r"^Подключить пересыл$"), setup_source_handler))
application.add_handler(MessageHandler(filters.Regex(r"^Личный кабинет$"), cabinet_handler))
application.add_handler(MessageHandler(filters.Regex(r"^Админ$"), admin_panel_handler))
application.add_handler(MessageHandler(filters.Regex(r"^Да$"), request_subscription_handler))
application.add_handler(MessageHandler(filters.Regex(r"^Назад$"), back_to_start_handler))

# Потом — состояния
application.add_handler(MessageHandler(filters.TEXT, handle_source_link))
application.add_handler(MessageHandler(filters.TEXT, handle_target_link))

# Самый последний — пересылка сообщений
application.add_handler(MessageHandler(filters.ChatType.CHANNEL | filters.ChatType.GROUP, relay_message_handler))

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Инициализация...")
    await application.initialize()
    await application.bot.set_webhook(url=WEBHOOK_URL)
    logger.info(f"Webhook: {WEBHOOK_URL}")
    yield
    await application.bot.delete_webhook()
    await application.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    try:
        json_data = await request.json()
        update = Update.de_json(json_data, application.bot)
        await application.process_update(update)
        logger.info(f"✅ Обновление {getattr(update, 'update_id', 'N/A')}")
        return {"ok": True}
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
        return {"ok": False}

@app.get("/")
@app.get("/healthz")
async def health():
    return {"status": "ok"}
