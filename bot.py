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
from database import create_tables, add_user, get_deadlines, add_task, edit_task, delete_task
 

load_dotenv()
pool = None
BOT_TOKEN = os.getenv("BOT_TOKEN")
storage = MemoryStorage()
bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=storage)


class FSM(StatesGroup):
    waiting_for_title = State()
    waiting_for_date = State()
    waiting_for_answer = State()
    waiting_for_edit_choice = State()
    waiting_for_title_choice = State()
    waiting_for_deadline_choice = State()
    waiting_for_delete = State()

@dp.message(Command("cancel"), ~StateFilter(default_state))
async def cancel_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Действие отменено.\n\nНапиши /add, чтобы начать заново.")

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

/edit - Изменить задачу
Меняет название или дату задачи.

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
        await message.answer("📋 У тебя пока нет задач.\n\nНапиши /add, чтобы добавить новую задачу.")
        return
    
    text = "📋 Твои дедлайны:\n\n"
    for i, row in enumerate(deadlines, 1):
        text += f"{i}. {row['title']} — {row['deadline_at'].strftime('%d.%m.%Y %H:%M')}\n"
    
    await message.answer(text)


@dp.message(Command("add"), StateFilter(default_state))
async def add_command(message: Message, state: FSMContext):
    await message.answer("📋 Введи название задачи.\n\nНапример: Дописать курсовую работу.")
    await state.set_state(FSM.waiting_for_title)


@dp.message(StateFilter(FSM.waiting_for_title), F.text)
async def good_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Отлично! Теперь введи дату дедлайна.\n\nПример: число.месяц.год 14:30")
    await state.set_state(FSM.waiting_for_date)


@dp.message(StateFilter(FSM.waiting_for_date))
async def get_date(message: Message, state: FSMContext):
    try:
        deadline = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        await state.update_data(deadline=deadline)
    except ValueError:
        await message.answer("❌ Неверный формат.\n\nВведи дату так: число.месяц.год 14:30")
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
    text=f"📌 {data['title']} - {deadline.strftime('%d.%m.%Y %H:%M')}\n\nВсё верно?",
    reply_markup=markup
    )

@dp.callback_query(StateFilter(FSM.waiting_for_date), F.data.in_(["yes", "no"]))
async def callback(callback: CallbackQuery, state: FSMContext):
    if callback.data == "yes":
        data = await state.get_data()
        async with pool.acquire() as conn:
            await add_task(conn, callback.from_user.id, data['title'], data['deadline'])
    
        await callback.message.delete()
        await callback.message.answer("✅ Задача добавлена!\n\nДля просмотра всех задач напиши /list")
        await state.clear()
    else:
        await callback.message.delete()
        await callback.message.answer("❌ Действие отменено.\n\nНапиши /add, чтобы начать заново.")
        await state.clear()

@dp.message(Command("edit"), StateFilter(default_state))
async def edit_command(message: Message, state: FSMContext):
    async with pool.acquire() as conn:
        deadlines = await get_deadlines(conn, message.from_user.id)
    
    if not deadlines:
        await message.answer("📋 У тебя пока нет задач.\n\nНапиши /add, чтобы добавить новую задачу.")
        return
    
    buttons = []
    for row in deadlines:
        buttons.append([InlineKeyboardButton(
            text=f"{row['title']} - {row['deadline_at'].strftime('%d.%m.%Y %H:%M')}",
            callback_data=f"edit_{row['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="Отменить", callback_data="cancel")])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выбери задачу, которую хочешь изменить:", reply_markup=markup)
    await state.set_state(FSM.waiting_for_answer)


@dp.callback_query(StateFilter(FSM.waiting_for_answer))
async def answer(callback: CallbackQuery, state: FSMContext):
    if callback.data == "cancel":
        await callback.message.delete()
        await callback.message.answer("❌ Действие отменено.")
        await state.clear()
        await callback.answer()
        return
    
    task_id = callback.data.split("_")[1]
    await state.update_data(task_id=task_id)
    
    buttons = [[
        InlineKeyboardButton(text="✏️ Название", callback_data="change_title"),
        InlineKeyboardButton(text="📅 Дату", callback_data="change_date"),
        InlineKeyboardButton(text="Отменить", callback_data="cancel")
    ]]

    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("Что хочешь изменить?", reply_markup=markup)
    await state.set_state(FSM.waiting_for_edit_choice)
    await callback.answer()


@dp.callback_query(StateFilter(FSM.waiting_for_edit_choice))
async def choice(callback: CallbackQuery, state: FSMContext):
    if callback.data == "cancel":
        await callback.message.delete()
        await callback.message.answer("❌ Действие отменено.")
        await state.clear()
        await callback.answer()

    if callback.data == "change_title":
        await callback.message.delete()
        await callback.message.answer("✏️ Напиши новое название для задачи.")
        await state.set_state(FSM.waiting_for_title_choice)
    else:
        await callback.message.delete()
        await callback.message.answer("✏️ Напиши новую дату для задачи.\n\n Пример: число.месяц.год 14:30")
        await state.set_state(FSM.waiting_for_deadline_choice)
    await callback.answer()


@dp.message(StateFilter(FSM.waiting_for_title_choice))
async def title_choice(message: Message, state: FSMContext):
    data = await state.get_data()
    async with pool.acquire() as conn:
        await edit_task(conn, int(data['task_id']), message.from_user.id, title = message.text)
    
    await message.answer("✅ Название обновлено!\n\nНапиши /list для просмотра списка задач.")
    await state.clear()


@dp.message(StateFilter(FSM.waiting_for_deadline_choice))
async def deadline_choice(message: Message, state: FSMContext):
    try:
        deadline = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
    except ValueError:
        await message.answer("❌ Неверный формат.\n\nВведи дату так: число.месяц.год 14:30")
        return
    
    data = await state.get_data()
    async with pool.acquire() as conn:
        await edit_task(conn, int(data['task_id']), message.from_user.id, deadline_at=deadline)

    await message.answer("✅ Дата обновлена!\n\nНапиши /list для просмотра списка задач.")
    await state.clear()


@dp.message(Command("delete"), StateFilter(default_state))
async def delete_command(message: Message, state: FSMContext):
    async with pool.acquire() as conn:
        deadlines = await get_deadlines(conn, message.from_user.id)
    
    if not deadlines:
        await message.answer("📋 У тебя пока нет задач.\n\nНапиши /add, чтобы добавить новую задачу.")
        return
    
    buttons = []
    for row in deadlines:
        buttons.append([InlineKeyboardButton(
            text=f"{row['title']} - {row['deadline_at'].strftime('%d.%m.%Y %H:%M')}",
            callback_data=f"delete_{row['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="Отменить", callback_data="cancel")])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выбери задачу, которую хочешь удалить:", reply_markup=markup)
    await state.set_state(FSM.waiting_for_delete)


@dp.callback_query(StateFilter(FSM.waiting_for_delete))
async def delete_callback(callback: CallbackQuery, state: FSMContext):
    if callback.data == "cancel":
        await callback.message.delete()
        await callback.message.answer("❌ Действие отменено.")
        await state.clear()
        await callback.answer()
        return
    
    task_id = int(callback.data.split("_")[1])
    async with pool.acquire() as conn:
        await delete_task(conn, task_id, callback.from_user.id)
    
    await callback.message.delete()
    await callback.message.answer("✅ Задача удалена!\n\nНапиши /list для просмотра списка задач.")
    await state.clear()
    await callback.answer()

 
@dp.message(StateFilter(default_state))
async def wrong_messages(message: Message):
    await message.answer("Для того чтобы пользоваться ботом, используй команды из списка.\n\nПосмотреть список команд - /help")


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