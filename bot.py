# bot.py
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from telegram import Update
from handlers import (
    start_handler, cabinet_handler, request_subscription_handler,
    admin_panel_handler, admin_action_handler, back_to_start_handler
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Переменные
BOT_TOKEN = os.environ["BOT_TOKEN"]
PORT = int(os.environ.get("PORT", "10000"))
RENDER_EXTERNAL_URL = os.environ["RENDER_EXTERNAL_URL"]
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = RENDER_EXTERNAL_URL + WEBHOOK_PATH

# Инициализация Telegram Application (без запуска)
application = Application.builder().token(BOT_TOKEN).build()

# Регистрация обработчиков
application.add_handler(CommandHandler("start", start_handler))
application.add_handler(CallbackQueryHandler(cabinet_handler, pattern="^cabinet$"))
application.add_handler(CallbackQueryHandler(request_subscription_handler, pattern="^request_subscription$"))
application.add_handler(CallbackQueryHandler(admin_panel_handler, pattern="^admin_panel$"))
application.add_handler(CallbackQueryHandler(admin_action_handler, pattern=r"^admin_(grant|revoke)_\d+$"))
application.add_handler(CallbackQueryHandler(back_to_start_handler, pattern="^back_to_start$"))

# Lifespan — замена on_event
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.info(f"Setting webhook to {WEBHOOK_URL}")
    await application.bot.set_webhook(url=WEBHOOK_URL)
    logging.info("✅ Webhook set successfully")
    yield
    # Shutdown (опционально)
    await application.bot.delete_webhook(drop_pending_updates=True)
    logging.info("🧹 Webhook deleted on shutdown")

# FastAPI app с lifespan
app = FastAPI(lifespan=lifespan)

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    json_data = await request.json()
    update = Update.de_json(json_data, application.bot)
    await application.process_update(update)
    return {"ok": True}

@app.get("/")
async def health_check():
    return {"status": "ok", "webhook": WEBHOOK_URL}
