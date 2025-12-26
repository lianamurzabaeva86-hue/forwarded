# bot.py
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import Update

# === Логирование ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# === Обработчик ошибок ===
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Произошла ошибка: {context.error}", exc_info=True)

# === Импорт обработчиков (ТОЛЬКО существующие функции) ===
from handlers import (
    start_handler,
    setup_source_handler,          # Обрабатывает кнопку "Подключить пересыл"
    cabinet_handler,
    request_subscription_handler,
    admin_panel_handler,
    back_to_start_handler,
    handle_source_link,            # Обрабатывает ввод исходной ссылки
    handle_target_link,            # Обрабатывает ввод целевой ссылки
    relay_message_handler,         # Пересылает сообщения из чатов
)

# === Переменные окружения ===
BOT_TOKEN = os.environ["BOT_TOKEN"]
RENDER_EXTERNAL_URL = os.environ["RENDER_EXTERNAL_URL"]
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = RENDER_EXTERNAL_URL + WEBHOOK_PATH

# === Telegram Application ===
application = Application.builder().token(BOT_TOKEN).build()
application.add_error_handler(error_handler)

# === РЕГИСТРАЦИЯ ОБРАБОТЧИКОВ (в правильном порядке) ===
application.add_handler(CommandHandler("start", start_handler))

# Кнопки из ReplyKeyboard
application.add_handler(MessageHandler(filters.Regex(r"^Подключить пересыл$"), setup_source_handler))
application.add_handler(MessageHandler(filters.Regex(r"^Личный кабинет$"), cabinet_handler))
application.add_handler(MessageHandler(filters.Regex(r"^Админ$"), admin_panel_handler))
application.add_handler(MessageHandler(filters.Regex(r"^Да$"), request_subscription_handler))
application.add_handler(MessageHandler(filters.Regex(r"^Назад$"), back_to_start_handler))

# Обработка состояний (ввод ссылок)
application.add_handler(MessageHandler(filters.TEXT, handle_source_link))
application.add_handler(MessageHandler(filters.TEXT, handle_target_link))

# Пересылка сообщений из групп/каналов
application.add_handler(MessageHandler(
    filters.ChatType.CHANNEL | filters.ChatType.GROUP,
    relay_message_handler
))

# === Lifespan (инициализация и завершение) ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Инициализация Telegram Application...")
    await application.initialize()
    logger.info("Установка webhook...")
    await application.bot.set_webhook(url=WEBHOOK_URL)
    logger.info(f"✅ Webhook установлен: {WEBHOOK_URL}")
    yield
    logger.info("Очистка webhook и завершение работы...")
    await application.bot.delete_webhook(drop_pending_updates=True)
    await application.shutdown()
    logger.info("🧹 Работа завершена")

# === FastAPI приложение ===
app = FastAPI(lifespan=lifespan)

# === Webhook endpoint ===
@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    try:
        json_data = await request.json()
        update = Update.de_json(json_data, application.bot)
        await application.process_update(update)
        logger.info(f"✅ Обновление обработано: {getattr(update, 'update_id', 'N/A')}")
        return {"ok": True}
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке webhook: {e}", exc_info=True)
        return {"ok": False}

# === Health check ===
@app.get("/")
@app.get("/healthz")
async def health_check():
    return {"status": "ok", "bot": "running", "webhook": WEBHOOK_PATH}
