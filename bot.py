from aiogram import Bot, Dispatcher
from aiogram.filters import Command
import asyncpg
import asyncio
from dotenv import load_dotenv
import os
from database import create_tables, add_user, get_deadlines
 
load_dotenv()
pool = None
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_command(message: Message):
    async with pool.acquire() as conn:
        await add_user(conn, message.from_user.id, message.from_user.username)
    await message.answer("""
    👋 Привет! Я Reminder Bot - помогу не забыть о важных дедлайнах.

🔥 Что я умею:
- Добавлять дедлайны 
- Отправлять уведомление с напоминанием
- Показывать список твоих задач

Напиши /help, чтобы увидеть все команды.
""")

@dp.message(Command("help"))
async def help_command(message: Message):
    await message.answer("""
📋 Список команд:

/start - Запуск бота

/add - Добавить новый дедлайн
Бот спросит название задачи и дату дедлайна.

/list - Показать все твои задачи
Выводит список активных дедлайнов.

/done - Отметить задачу выполненной
Задача удаляется из списка активных.

/delete - Удалить задачу
Удаляет задачу из списка.

/cancel - Отменить текущее действие
Используй, если хочешь прервать добавление задачи.
    """)

@dp.message(Command("list"))
async def list_command(message: Message):
    async with pool.acquire() as conn:
        deadlines = await get_deadlines(conn, message.from_user.id)
    
    if not deadlines:
        await message.answer("У тебя пока нет задач. Напиши /add, чтобы добавить новую задачу.")
        return
    
    text = "📋 Твои дедлайны:\n\n"
    for i, row in enumerate(deadlines, 1):
        text += f"{i}. {row['title']} — {row['deadline_at'].strftime('%d.%m.%Y %H:%M')}\n"
    
    await message.answer(text)


async def main():
    global pool
    pool = await asyncpg.create_pool(
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT"))
    )
    async with pool.acquire() as conn:
        await create_tables(conn)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 