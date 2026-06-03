from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import asyncpg
import asyncio
from dotenv import load_dotenv
import os
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state, State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime
from database import create_tables, add_user, get_deadlines, add_task
 

load_dotenv()
pool = None
BOT_TOKEN = os.getenv("BOT_TOKEN")
storage = MemoryStorage()
bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=storage)


class FSM(StatesGroup):
    waiting_for_title = State()
    waiting_for_date = State()


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


@dp.message(Command("add"), StateFilter(default_state))
async def add_command(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Введите название задачи. Например: Дописать курсовую работу.")
    await state.set_state(FSM.waiting_for_title)


@dp.message(StateFilter(FSM.waiting_for_title), F.text)
async def good_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Отлично! Теперь введите дату дедлайна. Пример: число.месяц.год 14:30")
    await state.set_state(FSM.waiting_for_date)


@dp.message(StateFilter(FSM.waiting_for_date))
async def get_date(message: Message, state: FSMContext):
    try:
        deadline = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        await state.update_data(deadline=deadline)
    except ValueError:
        await message.answer("Неверный формат. Введите дату так: число.месяц.год 14:30")
        return
    first_button = InlineKeyboardButton(
        text = "Да, сохранить",
        callback_data= "yes"
    )
    second_button = InlineKeyboardButton(
        text = "Нет, начать заново",
        callback_data= "no"
    )
    keyboard: list[list[InlineKeyboardButton]] = [
        [first_button, second_button]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    data = await state.get_data()
    await message.answer(
    text=f"📌 {data['title']} - {deadline.strftime('%d.%m.%Y %H:%M')}\nВсё верно?",
    reply_markup=markup
    )

@dp.callback_query(StateFilter(FSM.waiting_for_date), F.data.in_(["yes", "no"]))
async def callback(callback: CallbackQuery, state: FSMContext):
    if callback.data == "yes":
        data = await state.get_data()
        async with pool.acquire() as conn:
            await add_task(conn, callback.from_user.id, data['title'], data['deadline'])
    
        await callback.message.delete()
        await callback.message.answer("✅ Задача добавлена!\n\n Для просмотра всех задач напишите /list")
        await state.clear()
    else:
        await callback.message.delete()
        await callback.message.answer("❌ Действие отменено.\n\n Напишите /add, чтобы начать заново.")
        await state.clear()


@dp.message(Command("cancel"), ~StateFilter(default_state))
async def cancel_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Действие отменено.\n\n Напишите /add, чтобы начать заново.")


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