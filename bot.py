# bot.py
import os
import logging
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    ContentType,
    Message
)
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import asyncio

from supabase import create_client

# Логирование
logging.basicConfig(level=logging.INFO)

# === Конфигурация ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not all([BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY]):
    raise ValueError("Missing environment variables: BOT_TOKEN, SUPABASE_URL, or SUPABASE_KEY")

# === Инициализация ===
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
router = Router()
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

ADMIN_ID = 6782041245

def get_main_menu(user_id: int) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="🖥️ Личный кабинет"), KeyboardButton(text="🛡️ Помощь")],
        [KeyboardButton(text="👥 Реферальная программа")]
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="🔧 Админ панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

async def get_user_info(user_id: int):
    res = supabase.table('users').select('*').eq('id', user_id).execute()
    if res.data:
        return res.data[0]
    else:
        new_user = {
            'id': user_id,
            'username': 'unknown',
            'free_solutions': 3,
        }
        supabase.table('users').insert(new_user).execute()
        return new_user

async def update_user_solutions(user_id: int, delta: int):
    user = await get_user_info(user_id)
    new_count = max(0, user['free_solutions'] + delta)
    supabase.table('users').update({'free_solutions': new_count}).eq('id', user_id).execute()

async def add_referral(referrer_id: int, referred_id: int):
    supabase.table('referrals').insert({
        'referrer_id': referrer_id,
        'referred_id': referred_id
    }).execute()
    await update_user_solutions(referrer_id, 5)

async def get_referral_count(user_id: int) -> int:
    res = supabase.table('referrals').select('*').eq('referrer_id', user_id).execute()
    return len(res.data) if res.data else 0

# === Обработчики ===

@router.message(Command("start"))
async def start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"
    supabase.table('users').update({'username': username}).eq('id', user_id).execute()

    existing = supabase.table('users').select('id').eq('id', user_id).limit(1).execute()
    if not existing.
        supabase.table('users').insert({
            'id': user_id,
            'username': username,
            'free_solutions': 3
        }).execute()

    args = message.text.split()
    if len(args) > 1:
        ref_id = args[1]
        if ref_id.isdigit() and int(ref_id) != user_id:
            try:
                await add_referral(int(ref_id), user_id)
            except Exception as e:
                logging.error(f"Referral error: {e}")

    disclaimer = (
        "🎓 Привет! Я — помощник по решению задач по математике, физике и химии.\n\n"
        "❗ ВАЖНО: этот бот предназначен ТОЛЬКО для самопроверки и обучения.\n"
        "❌ Не используйте его на контрольных, экзаменах или тестах.\n\n"
        "⚠️ Ни бот, ни владелец НЕ НЕСУТ НИКАКОЙ ОТВЕТСТВЕННОСТИ за последствия использования или неправильное применение этого инструмента.\n"
        "✅ Продолжая, вы подтверждаете, что принимаете эти условия и используете бота на свой страх и риск.\n\n"
        "Для начала пришлите текст задания — я решу его бесплатно!"
    )
    await message.answer(disclaimer, reply_markup=get_main_menu(user_id))

@router.message(lambda msg: msg.text == "🛡️ Помощь")
async def help_command(message: Message):
    await message.answer("Пришли мне **текст задания** — я решу его за тебя! 🧠\n📸 Обработка фото временно недоступна.")

@router.message(lambda msg: msg.content_type == ContentType.PHOTO)
async def handle_photo(message: Message):
    await message.answer("📸 Обработка фото временно недоступна.\nПожалуйста, отправьте **текст задания**.")

@router.message(lambda msg: msg.text == "🖥️ Личный кабинет")
async def profile(message: Message):
    user_id = message.from_user.id
    user = await get_user_info(user_id)
    your_bot_username = "your_bot_username"  # ← ЗАМЕНИТЕ НА НАСТОЯЩЕЕ ИМЯ БОТА
    ref_link = f"https://t.me/{your_bot_username}?start={user_id}"
    await message.answer(
        f"👤 Твой профиль:\n"
        f"✅ Осталось решений: <b>{user['free_solutions']}</b>\n"
        f"🔗 Реферальная ссылка: <code>{ref_link}</code>\n"
        f"👥 Приглашено друзей: {await get_referral_count(user_id)}"
    )

@router.message(lambda msg: msg.text == "👥 Реферальная программа")
async def referral(message: Message):
    user_id = message.from_user.id
    your_bot_username = "your_bot_username"  # ← ЗАМЕНИТЕ!
    ref_link = f"https://t.me/{your_bot_username}?start={user_id}"
    await message.answer(
        f"📌 Поделись ссылкой и получи <b>+5 решений</b> за каждого друга!\n\n"
        f"🔗 Твоя ссылка: <code>{ref_link}</code>\n\n"
        f"💡 Как работает: друг переходит по ссылке → запускает бота → ты получаешь +5 решений."
    )

@router.message(lambda msg: msg.text == "💰 Доп. задания")
async def buy_subscription(message: Message):
    await message.answer(
        "Для приобретения подписки нажми «Да» 👇\n\n"
        "❗ Убедись, что у тебя есть юзернейм (@username), чтобы администратор мог связаться с тобой.",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="✅ Да, хочу подписку")]],
            resize_keyboard=True
        )
    )

@router.message(lambda msg: msg.text == "✅ Да, хочу подписку")
async def confirm_buy(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "нет юзернейма"
    await bot.send_message(
        ADMIN_ID,
        f"🔔 Запрос на подписку от @{username} (ID: {user_id})\n"
        "Нажми /unlock_user для разблокировки."
    )
    await message.answer("Запрос отправлен администратору. Ожидайте ответа.")

@router.message(lambda msg: msg.text == "🔧 Админ панель")
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "🔧 Админ-панель активна.\n"
        "/unlock_user <user_id> — выдать 10 решений\n"
        "/stats — статистика"
    )

@router.message(Command("unlock_user"))
async def unlock_user(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer("Использование: /unlock_user <user_id>")
            return
        user_id = int(parts[1])
        await update_user_solutions(user_id, 10)
        await message.answer(f"✅ Пользователь {user_id} получил 10 решений.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("stats"))
async def stats(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    total = supabase.table('users').select('*', count='exact').execute().count
    with_bonus = supabase.table('users').select('*', count='exact').gt('free_solutions', 3).execute().count
    await message.answer(f"📊 Статистика:\nВсего пользователей: {total}\nС бонусами/подпиской: {with_bonus}")

# === Запуск ===

async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
