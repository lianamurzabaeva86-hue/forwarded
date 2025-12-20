# bot.py
import os
import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from handlers import (
    start_handler, cabinet_handler, request_subscription_handler,
    admin_panel_handler, admin_action_handler, back_to_start_handler
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

def main():
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CallbackQueryHandler(cabinet_handler, pattern="^cabinet$"))
    app.add_handler(CallbackQueryHandler(request_subscription_handler, pattern="^request_subscription$"))
    app.add_handler(CallbackQueryHandler(admin_panel_handler, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_action_handler, pattern=r"^admin_(grant|revoke)_\d+$"))
    app.add_handler(CallbackQueryHandler(back_to_start_handler, pattern="^back_to_start$"))

    logging.info("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
