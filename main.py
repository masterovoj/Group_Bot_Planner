import asyncio
import logging
import os
from dotenv import find_dotenv, load_dotenv
from datetime import datetime, time, timedelta
import calendar
from typing import Optional
from itertools import groupby

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart, StateFilter, or_f
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ChatMemberUpdated,
    CallbackQuery
)
from sqlalchemy import (
    select,
    update,
    ForeignKeyConstraint,
    PrimaryKeyConstraint
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Mapped, mapped_column, selectinload
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

def parse_time(text: str) -> Optional[time]:
    """Парсит время из строки. Ожидает формат HH:MM."""
    try:
        return datetime.strptime(text, "%H:%M").time()
    except ValueError:
        return None

# --- Календарь ---
# Класс для колбэков календаря
class SimpleCalendarCallback(CallbackData, prefix="simple_calendar"):
    act: str
    year: int
    month: int
    day: int

# Класс для создания inline-календаря
class SimpleCalendar:
    async def start_calendar(
        self,
        year: int = datetime.now().year,
        month: int = datetime.now().month
    ) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        # Кнопка "ignore" для отображения названия месяца и года
        builder.button(
            text=f"{datetime(year, month, 1).strftime('%B %Y')}",
            callback_data=SimpleCalendarCallback(act="ignore", year=year, month=month, day=0).pack()
        )
        # Кнопки для навигации по месяцам
        builder.row(
            InlineKeyboardButton(text='<<', callback_data=SimpleCalendarCallback(act='prev-month', year=year, month=month, day=0).pack()),
            InlineKeyboardButton(text='>>', callback_data=SimpleCalendarCallback(act='next-month', year=year, month=month, day=0).pack())
        )
        # Дни недели
        week_days = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
        for day in week_days:
            builder.button(text=day, callback_data=SimpleCalendarCallback(act="ignore", year=year, month=month, day=0).pack())

        # Кнопки с датами
        month_calendar = calendar.monthcalendar(year, month)
        for week in month_calendar:
            for day in week:
                if day == 0:
                    builder.button(text=" ", callback_data=SimpleCalendarCallback(act="ignore", year=year, month=month, day=0).pack())
                else:
                    builder.button(
                        text=str(day),
                        callback_data=SimpleCalendarCallback(act="day", year=year, month=month, day=day).pack()
                    )
        builder.adjust(1, 2, 7) 
        return builder.as_markup()

    async def process_selection(self, query: CallbackQuery, data: SimpleCalendarCallback) -> tuple:
        if data.act == "ignore":
            await query.answer(cache_time=60)
            return False, None
        
        if data.act == "day":
            await query.message.delete_reply_markup()
            return True, datetime(data.year, data.month, data.day)

        if data.act == "prev-month":
            prev_month = datetime(data.year, data.month, 1) - timedelta(days=1)
            await query.message.edit_reply_markup(
                reply_markup=await self.start_calendar(int(prev_month.year), int(prev_month.month))
            )
            return False, None

        if data.act == "next-month":
            next_month = datetime(data.year, data.month, 28) + timedelta(days=4)
            await query.message.edit_reply_markup(
                reply_markup=await self.start_calendar(int(next_month.year), int(next_month.month))
            )
            return False, None
        
        return False, None

# --- Настройки ---
# Используйте переменную окружения для токена, если она есть, иначе - заглушку.
# Для реального использования рекомендуется устанавливать переменную окружения.

# загружаем данные из файла переменных окружения .env
load_dotenv(find_dotenv())

API_TOKEN = os.getenv('TOKEN')
DB_NAME = "tasks_main.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_NAME}"

# --- Логирование ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Модели SQLAlchemy ---
Base = declarative_base()

class User(Base):
    """Модель пользователя."""
    __tablename__ = 'users_tbl'
    user_id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[Optional[str]]
    full_name: Mapped[str]
    status: Mapped[str]  # 'administrator', 'creator', 'member', 'left', 'kicked'
    first_seen: Mapped[datetime]
    last_seen: Mapped[datetime]

    tasks: Mapped[list["Task"]] = relationship(back_populates="user")

    __table_args__ = (
        PrimaryKeyConstraint('user_id', 'chat_id'),
    )

    def __repr__(self):
        return f"<User(user_id={self.user_id}, chat_id={self.chat_id}, name='{self.full_name}')>"


class Task(Base):
    """Модель задачи."""
    __tablename__ = 'tasks_tbl'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int]
    chat_id: Mapped[int]
    start_datetime: Mapped[datetime]
    end_datetime: Mapped[datetime]
    description: Mapped[str]
    is_completed: Mapped[bool] = mapped_column(default=False)

    user: Mapped["User"] = relationship(back_populates="tasks")

    __table_args__ = (
        ForeignKeyConstraint(['user_id', 'chat_id'], ['users_tbl.user_id', 'users_tbl.chat_id']),
    )

    def __repr__(self):
        return f"<Task(id={self.id}, description='{self.description[:20]}...')>"


# --- Настройка базы данных ---
engine = create_async_engine(DATABASE_URL) #, echo=True)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db():
    """Инициализация базы данных и создание таблиц."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logging.info("База данных инициализирована.")


# --- Инициализация бота ---
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# --- Управление пользователями ---

async def add_or_update_user(session: AsyncSession, user_id: int, chat_id: int, username: Optional[str], full_name: str, status: Optional[str] = None):
    """
    Добавляет или обновляет пользователя в базе данных.
    Если status=None, существующий статус не будет изменен.
    Для новых пользователей статус по умолчанию 'member'.
    """
    now = datetime.now()
    stmt = select(User).where(User.user_id == user_id, User.chat_id == chat_id)
    result = await session.execute(stmt)
    db_user = result.scalar_one_or_none()

    if db_user:
        db_user.username = username
        db_user.full_name = full_name
        if status:  # Обновляем статус, только если он явно передан
            db_user.status = status
        db_user.last_seen = now
        logging.info(f"Updated user {user_id} in chat {chat_id}.")
    else:
        new_user = User(
            user_id=user_id,
            chat_id=chat_id,
            username=username,
            full_name=full_name,
            status=status or 'member',  # Для новых пользователей статус 'member'
            first_seen=now,
            last_seen=now,
        )
        session.add(new_user)
        logging.info(f"Added new user {user_id} in chat {chat_id}.")
    await session.commit()


async def is_admin(bot: Bot, user_id: int, chat_id: int) -> bool:
    """Проверяет, является ли пользователь админом, запрашивая свежий список админов чата."""
    try:
        admins = await bot.get_chat_administrators(chat_id=chat_id)
        admin_ids = {admin.user.id for admin in admins}
        return user_id in admin_ids
    except Exception as e:
        logging.error(f"Не удалось получить список администраторов для чата {chat_id}: {e}")
        return False


# --- Клавиатуры ---
user_main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Мои задачи")]
    ],
    resize_keyboard=True
)

admin_main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Новая задача")],
        [KeyboardButton(text="Просмотр задач пользователей")],
        [KeyboardButton(text="Мои задачи")]
    ],
    resize_keyboard=True
)


# --- Основные обработчики команд ---

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start."""
    user_id = message.from_user.id
    
    # Если команда в группе, регистрируем/обновляем и даем инструкцию
    if message.chat.type != 'private':
        async with async_session() as session:
            await add_or_update_user(session, user_id, message.chat.id, message.from_user.username, message.from_user.full_name)
        
        bot_info = await bot.get_me()
        await message.reply(
            f"Добро пожаловать, {message.from_user.full_name}!\n"
            f"Вы зарегистрированы в чате '{message.chat.title}'. "
            f"Для управления задачами, пожалуйста, напишите мне в личные сообщения: @{bot_info.username}"
        )
        return

    # Если команда в ЛС, проверяем статус админа во всех чатах
    admin_groups = []
    async with async_session() as session:
        # Получаем все уникальные chat_id, где есть пользователи
        stmt = select(User.chat_id).distinct()
        chat_ids = (await session.execute(stmt)).scalars().all()
        
        for chat_id in chat_ids:
            if await is_admin(bot, user_id, chat_id):
                try:
                    chat_info = await bot.get_chat(chat_id)
                    admin_groups.append({'id': chat_id, 'title': chat_info.title})
                except Exception:
                    admin_groups.append({'id': chat_id, 'title': f"ID: {chat_id}"})

    if admin_groups:
        if len(admin_groups) == 1:
            group = admin_groups[0]
            await state.update_data(admin_context_chat_id=group['id'], admin_context_chat_title=group['title'])
            await message.answer(
                f"Добро пожаловать! Вы администратор в чате «<b>{group['title']}</b>».\n"
                "Он автоматически выбран для управления в текущей сессии. Используйте клавиатуру ниже.",
                reply_markup=admin_main_kb,
                parse_mode="HTML"
            )
        else:
            builder = InlineKeyboardBuilder()
            for group in admin_groups:
                builder.button(text=group['title'], callback_data=f"set_admin_ctx|{group['id']}")
            builder.adjust(1)
            await message.answer(
                "Добро пожаловать! Вы администрируете несколько чатов.\n"
                "Пожалуйста, выберите основной чат для управления в этой сессии:",
                reply_markup=builder.as_markup()
            )
            await message.answer("После выбора чата вы сможете использовать эти команды:", reply_markup=admin_main_kb)
    else:
        await message.answer(
            "Добро пожаловать! Используйте клавиатуру для управления вашими задачами.",
            reply_markup=user_main_kb
        )


@dp.callback_query(F.data.startswith("set_admin_ctx|"))
async def set_admin_chat_context_handler(callback: CallbackQuery, state: FSMContext):
    """Сохраняет выбранный админом чат в состояние FSM."""
    chat_id = int(callback.data.split("|")[1])
    try:
        chat_info = await bot.get_chat(chat_id)
        chat_title = chat_info.title
    except Exception as e:
        logging.error(f"Не удалось получить информацию о чате {chat_id}: {e}")
        chat_title = f"ID: {chat_id}"

    await state.update_data(admin_context_chat_id=chat_id, admin_context_chat_title=chat_title)

    await callback.message.edit_text(
        f"Отлично! Чат для управления на эту сессию: <b>{chat_title}</b>.\n\n"
        "Теперь вы можете использовать кнопки «Новая задача» и «Просмотр задач пользователей».",
        parse_mode="HTML"
    )
    await callback.answer()


@dp.message(Command("admin"), F.chat.type.in_(['group', 'supergroup']))
async def cmd_admin(message: Message, state: FSMContext):
    """Обработчик команды /admin в группе. Устанавливает/меняет контекст для админа."""
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not await is_admin(bot, user_id, chat_id):
        await message.reply("Эту команду могут использовать только администраторы.")
        return

    # Ключ для хранения данных в контексте ЛС с админом
    user_pm_key = StorageKey(bot_id=bot.id, user_id=user_id, chat_id=user_id)
    
    # Сохраняем ID и название чата в хранилище FSM для ЛС
    await state.storage.set_data(
        key=user_pm_key, 
        data={'admin_context_chat_id': chat_id, 'admin_context_chat_title': message.chat.title}
    )

    try:
        # Отправляем админскую клавиатуру в ЛС
        await bot.send_message(
            chat_id=user_id,
            text=f"Вы переключились в режим администрирования чата: <b>{message.chat.title}</b>.\n\nИспользуйте клавиатуру ниже для управления.",
            reply_markup=admin_main_kb,
            parse_mode="HTML"
        )
        await message.reply("Панель управления отправлена вам в личные сообщения.")
    except Exception as e:
        logging.error(f"Не удалось отправить ЛС админу {user_id}: {e}")
        await message.reply(f"Не могу отправить вам панель управления. Пожалуйста, начните диалог со мной (@{(await bot.get_me()).username}) и повторите команду.")


# --- Форматирование вывода задач ---
async def format_task_message(task: Task, for_admin: bool) -> tuple[str, InlineKeyboardMarkup]:
    """Форматирует сообщение о задаче и создает для него клавиатуру."""
    status_emoji = "✅" if task.is_completed else "❌"
    status_text = "Выполнена" if task.is_completed else "Не выполнена"
    
    now = datetime.now()
    if not task.is_completed and task.end_datetime < now:
        status_emoji = "⚠️"
        status_text += " (Просрочена)"

    # Используем user.full_name, если связь загружена
    user_full_name = task.user.full_name if task.user else "Неизвестный"

    text = (
        f"<b>Задача №{task.id}</b>\n"
        f"Исполнитель: {user_full_name}\n"
        f"Описание: {task.description}\n"
        f"Начало: {task.start_datetime.strftime('%d.%m.%Y %H:%M')}\n"
        f"Окончание: {task.end_datetime.strftime('%d.%m.%Y %H:%M')}\n"
        f"Статус: {status_emoji} {status_text}"
    )

    builder = InlineKeyboardBuilder()
    if for_admin:
        if not task.is_completed:
            builder.button(text="✅ Отметить выполненной", callback_data=f"usr_complete_task|{task.id}")
        builder.button(text="✏️ Редактировать", callback_data=f"adm_edit_task|{task.id}")
        builder.button(text="🗑 Удалить", callback_data=f"adm_delete_task|{task.id}")
        builder.button(text="💬 Написать сообщение", callback_data=f"adm_sendmsg_task|{task.id}")
    else: # для пользователя
        if not task.is_completed:
            builder.button(text="✅ Отметить выполненной", callback_data=f"usr_complete_task|{task.id}")
        builder.button(text="✏️ Редактировать", callback_data=f"usr_edit_task|{task.id}")
    
    builder.adjust(1)
    return text, builder.as_markup()


# --- FSM для создания задачи (теперь работает в ЛС) ---
class TaskCreation(StatesGroup):
    waiting_for_user = State()
    waiting_for_start_date = State()
    waiting_for_start_time = State()
    waiting_for_end_date = State()
    waiting_for_end_time = State()
    waiting_for_description = State()
    waiting_for_confirmation = State()


@dp.message(
    or_f(Command("newtask"), F.text == "Новая задача"),
    F.chat.type == 'private'
)
async def new_task_start_pm(message: Message, state: FSMContext):
    """Начало создания задачи в ЛС."""
    user_id = message.from_user.id
    
    # Получаем данные из хранилища для этого пользователя
    user_data = await state.get_data()
    group_chat_id = user_data.get('admin_context_chat_id')

    if not group_chat_id:
        await message.reply("Сначала выберите группу для управления, отправив в нее команду /admin.")
        return

    if not await is_admin(bot, user_id, group_chat_id):
        await message.reply("Вы не являетесь администратором в выбранной группе. Отправьте /admin в нужный чат для обновления статуса.")
        return

    async with async_session() as session:
        stmt = select(User).where(User.chat_id == group_chat_id)
        users = (await session.execute(stmt)).scalars().all()

    if not users:
        await message.reply("В выбранной группе нет зарегистрированных пользователей. Попросите их написать любое сообщение в чате.")
        return

    builder = InlineKeyboardBuilder()
    for user in users:
        builder.button(text=user.full_name, callback_data=f"assign_user_{user.user_id}")
    builder.adjust(1)
    
    # Начинаем FSM и сохраняем в него ID группы
    await state.set_state(TaskCreation.waiting_for_user)
    await state.update_data(group_chat_id=group_chat_id)
    
    await message.answer(
        "Шаг 1/7: Выберите исполнителя для новой задачи:",
        reply_markup=builder.as_markup()
    )


@dp.callback_query(StateFilter(TaskCreation.waiting_for_user), F.data.startswith("assign_user_"))
async def new_task_user_selected(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[2])
    
    user_data = await state.get_data()
    group_chat_id = user_data.get('group_chat_id')

    if not group_chat_id:
        await callback.message.edit_text("Произошла ошибка: контекст группы утерян. Начните заново с команды /newtask.")
        await state.clear()
        return

    async with async_session() as session:
        stmt = select(User).where(User.user_id == user_id, User.chat_id == group_chat_id)
        user = (await session.execute(stmt)).scalar_one_or_none()

    if not user:
        await callback.answer("Пользователь не найден!", show_alert=True)
        await callback.message.delete()
        await state.clear()
        return
    
    # Добавляем в состояние user_id и user_name, не удаляя group_chat_id
    await state.update_data(user_id=user.user_id, user_name=user.full_name)
    await callback.message.edit_text(
        f"Исполнитель: {user.full_name}.\n\n"
        "Шаг 2/7: Выберите дату **начала** задачи.",
        reply_markup=await SimpleCalendar().start_calendar()
    )
    await state.set_state(TaskCreation.waiting_for_start_date)


@dp.callback_query(SimpleCalendarCallback.filter(), StateFilter(TaskCreation.waiting_for_start_date, TaskCreation.waiting_for_end_date))
async def process_calendar_for_creation(callback_query: CallbackQuery, callback_data: SimpleCalendarCallback, state: FSMContext):
    selected, date = await SimpleCalendar().process_selection(callback_query, callback_data)
    if not selected:
        return

    current_state = await state.get_state()
    user_data = await state.get_data()

    if current_state == TaskCreation.waiting_for_start_date:
        await state.update_data(start_date=date)
        await callback_query.message.edit_text(
            f"Исполнитель: {user_data['user_name']}\n"
            f"Дата начала: {date.strftime('%d.%m.%Y')}\n\n"
            "Шаг 3/7: Введите время **начала** в формате HH:MM."
        )
        await state.set_state(TaskCreation.waiting_for_start_time)

    elif current_state == TaskCreation.waiting_for_end_date:
        start_dt = datetime.combine(user_data['start_date'].date(), user_data['start_time'])
        if date.date() < start_dt.date():
            await callback_query.answer("Дата окончания не может быть раньше даты начала!", show_alert=True)
            # Возвращаем календарь
            await callback_query.message.edit_reply_markup(reply_markup=await SimpleCalendar().start_calendar(year=date.year, month=date.month))
            return

        await state.update_data(end_date=date)
        await callback_query.message.edit_text(
            f"Исполнитель: {user_data['user_name']}\n"
            f"Начало: {start_dt.strftime('%d.%m.%Y %H:%M')}\n"
            f"Дата окончания: {date.strftime('%d.%m.%Y')}\n\n"
            "Шаг 5/7: Введите время **окончания** в формате HH:MM."
        )
        await state.set_state(TaskCreation.waiting_for_end_time)


@dp.message(StateFilter(TaskCreation.waiting_for_start_time))
async def new_task_start_time(message: Message, state: FSMContext):
    start_time = parse_time(message.text)
    if not start_time:
        await message.reply("Неверный формат времени. Пожалуйста, введите в формате HH:MM.")
        return

    await state.update_data(start_time=start_time)
    user_data = await state.get_data()
    start_dt = datetime.combine(user_data['start_date'].date(), start_time)
    
    await message.reply(
        f"Исполнитель: {user_data['user_name']}\n"
        f"Начало: {start_dt.strftime('%d.%m.%Y %H:%M')}\n\n"
        "Шаг 4/7: Теперь выберите дату **окончания** задачи.",
        reply_markup=await SimpleCalendar().start_calendar()
    )
    await state.set_state(TaskCreation.waiting_for_end_date)


@dp.message(StateFilter(TaskCreation.waiting_for_end_time))
async def new_task_end_time(message: Message, state: FSMContext):
    end_time = parse_time(message.text)
    if not end_time:
        await message.reply("Неверный формат времени. Пожалуйста, введите в формате HH:MM.")
        return
        
    user_data = await state.get_data()
    start_dt = datetime.combine(user_data['start_date'].date(), user_data['start_time'])
    end_dt = datetime.combine(user_data['end_date'].date(), end_time)

    if end_dt <= start_dt:
        await message.reply("Дата и время окончания должны быть позже даты и времени начала. Пожалуйста, введите время окончания еще раз.")
        return

    await state.update_data(end_time=end_time)
    
    await message.reply(
        f"Исполнитель: {user_data['user_name']}\n"
        f"Начало: {start_dt.strftime('%d.%m.%Y %H:%M')}\n"
        f"Окончание: {end_dt.strftime('%d.%m.%Y %H:%M')}\n\n"
        "Шаг 6/7: Введите **описание** задачи."
    )
    await state.set_state(TaskCreation.waiting_for_description)


@dp.message(StateFilter(TaskCreation.waiting_for_description))
async def new_task_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    user_data = await state.get_data()

    start_dt = datetime.combine(user_data['start_date'].date(), user_data['start_time'])
    end_dt = datetime.combine(user_data['end_date'].date(), user_data['end_time'])
    
    text = (
        f"Пожалуйста, подтвердите создание задачи:\n\n"
        f"<b>Исполнитель:</b> {user_data['user_name']}\n"
        f"<b>Описание:</b> {message.text}\n"
        f"<b>Начало:</b> {start_dt.strftime('%d.%m.%Y %H:%M')}\n"
        f"<b>Окончание:</b> {end_dt.strftime('%d.%m.%Y %H:%M')}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="task_confirm")
    builder.button(text="❌ Отменить", callback_data="task_cancel")
    
    await message.reply(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.set_state(TaskCreation.waiting_for_confirmation)


@dp.callback_query(StateFilter(TaskCreation.waiting_for_confirmation), F.data.in_(['task_confirm', 'task_cancel']))
async def new_task_confirm(callback: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    group_chat_id = user_data.get('group_chat_id')
    admin_kb = admin_main_kb # В ЛС у админа всегда админская клавиатура

    if callback.data == 'task_cancel':
        await callback.message.edit_text("Создание задачи отменено.")
        await callback.message.answer("Выберите следующее действие:", reply_markup=admin_kb)
        await state.set_state(None)  # Завершаем FSM, но сохраняем данные (контекст админа)
        return

    await callback.message.edit_text("✅ Задача создана и отправляется исполнителю...")
    
    start_dt = datetime.combine(user_data['start_date'].date(), user_data['start_time'])
    end_dt = datetime.combine(user_data['end_date'].date(), user_data['end_time'])
    user_id = user_data['user_id']
    
    async with async_session() as session:
        stmt = select(User).where(User.user_id == user_id, User.chat_id == group_chat_id)
        assignee = (await session.execute(stmt)).scalar_one_or_none()

        if not assignee:
            await callback.message.answer("Ошибка: не удалось найти исполнителя в базе данных.")
            await state.clear()
            return

        new_task = Task(
            user_id=assignee.user_id,
            chat_id=group_chat_id,
            start_datetime=start_dt,
            end_datetime=end_dt,
            description=user_data['description'],
            is_completed=False
        )
        session.add(new_task)
        await session.commit()
        
        # Уведомление пользователю в ЛС
        try:
            group_info = await bot.get_chat(group_chat_id)
            task_notification_text = (
                f"🔔 **Новая задача!**\n\n"
                f"Вам назначена новая задача в чате '{group_info.title}'.\n\n"
                f"<b>Описание:</b> {new_task.description}\n"
                f"<b>Начало:</b> {new_task.start_datetime.strftime('%d.%m.%Y %H:%M')}\n"
                f"<b>Окончание:</b> {new_task.end_datetime.strftime('%d.%m.%Y %H:%M')}\n"
                f"<b>Задачу для вас создал:</b> {callback.from_user.full_name}"
            )
            await bot.send_message(assignee.user_id, task_notification_text, parse_mode="HTML")
            await callback.message.edit_text(f"✅ Задача для {assignee.full_name} успешно создана и отправлена в ЛС.")
        except Exception as e:
            logging.error(f"Не удалось отправить ЛС о новой задаче пользователю {assignee.user_id}: {e}")
            try:
                admin_id = callback.from_user.id
                await bot.send_message(
                    admin_id,
                    f"⚠️ Не удалось отправить уведомление о новой задаче пользователю {assignee.full_name} в личные сообщения. "
                    f"Возможно, он не запустил бота. Попросите его отправить команду /start боту (@{(await bot.get_me()).username})."
                )
            except Exception as admin_e:
                 logging.error(f"Не удалось отправить ЛС админу {callback.from_user.id} об ошибке: {admin_e}")
            
            await callback.message.edit_text(
                f"⚠️ Задача для {assignee.full_name} создана, но не удалось отправить уведомление в ЛС."
            )

    await callback.message.answer("Выберите следующее действие:", reply_markup=admin_kb)
    await state.set_state(None)  # Завершаем FSM, но сохраняем данные (контекст админа)


@dp.message(F.text == "Мои задачи", F.chat.type == 'private')
async def show_my_tasks_pm(message: Message):
    """Отображает задачи пользователя в ЛС, сгруппированные по чатам."""
    user_id = message.from_user.id
    async with async_session() as session:
        stmt = (
            select(Task)
            .options(selectinload(Task.user))
            .where(Task.user_id == user_id)
            .order_by(Task.chat_id, Task.end_datetime)
        )
        tasks = (await session.execute(stmt)).scalars().all()

    if not tasks:
        await message.answer("У вас нет назначенных задач.")
        return
        
    await message.answer("Ваши задачи:")
    
    tasks_by_chat = groupby(tasks, key=lambda task: task.chat_id)
    for chat_id_val, user_tasks in tasks_by_chat:
        try:
            chat_info = await bot.get_chat(chat_id_val)
            await message.answer(f"<b><u>Задачи в чате: {chat_info.title}</u></b>", parse_mode="HTML")
        except Exception:
            await message.answer(f"<b><u>Задачи в чате (ID: {chat_id_val})</u></b>", parse_mode="HTML")
        
        for task in user_tasks:
            text, keyboard = await format_task_message(task, for_admin=False)
            await message.answer(text, reply_markup=keyboard, parse_mode='HTML')


# --- Новая FSM для просмотра задач пользователя админом ---
class AdminViewTasks(StatesGroup):
    waiting_for_user = State()
    viewing_tasks = State()

@dp.message(F.text == "Просмотр задач пользователей", F.chat.type == 'private')
async def admin_choose_user_for_view(message: Message, state: FSMContext):
    """Шаг 1: выбор пользователя для просмотра задач (админ)."""
    user_id = message.from_user.id
    user_data = await state.get_data()
    chat_id = user_data.get('admin_context_chat_id')

    if not chat_id:
        await message.reply("Контекст группы не установлен. Отправьте команду /admin в нужный чат.")
        return

    if not await is_admin(bot, user_id, chat_id):
        await message.reply("Вы больше не администратор в этом чате. Отправьте /admin в нужный чат, чтобы обновить статус.")
        return

    async with async_session() as session:
        stmt = select(User).where(User.chat_id == chat_id)
        users = (await session.execute(stmt)).scalars().all()

    if not users:
        await message.reply("В выбранной группе нет зарегистрированных пользователей.")
        return

    builder = InlineKeyboardBuilder()
    for user in users:
        builder.button(text=user.full_name, callback_data=f"viewtasks_user_{user.user_id}")
    builder.adjust(1)

    await state.set_state(AdminViewTasks.waiting_for_user)
    await message.answer(
        "Выберите пользователя для просмотра его задач:",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(StateFilter(AdminViewTasks.waiting_for_user), F.data.startswith("viewtasks_user_"))
async def admin_view_selected_user_tasks(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[-1])
    user_data = await state.get_data()
    chat_id = user_data.get('admin_context_chat_id')

    async with async_session() as session:
        stmt = select(User).where(User.user_id == user_id, User.chat_id == chat_id)
        user = (await session.execute(stmt)).scalar_one_or_none()
        if not user:
            await callback.answer("Пользователь не найден!", show_alert=True)
            await callback.message.delete()
            await state.clear()
            return
        stmt_tasks = (
            select(Task)
            .options(selectinload(Task.user))
            .where(Task.user_id == user_id, Task.chat_id == chat_id)
            .order_by(Task.end_datetime)
        )
        tasks = (await session.execute(stmt_tasks)).scalars().all()

    await callback.message.edit_text(f"Задачи пользователя <b>{user.full_name}</b> (@{user.username or 'N/A'}):", parse_mode='HTML')
    if not tasks:
        await callback.message.answer("У пользователя нет задач.")
    else:
        for task in tasks:
            text, keyboard = await format_task_message(task, for_admin=True)
            await callback.message.answer(text, reply_markup=keyboard, parse_mode='HTML')
    await state.set_state(None)
    await callback.answer()


# --- Обработчики inline-кнопок задач (теперь вызываются из ЛС) ---

async def get_task_if_user_has_permission(callback: types.CallbackQuery, state: FSMContext) -> Optional[Task]:
    """Проверяет права доступа к задаче и возвращает ее, если они есть."""
    task_id = int(callback.data.split('|')[1])
    user_id = callback.from_user.id
    
    async with async_session() as session:
        # Загружаем задачу сразу с пользователем
        task = (await session.execute(select(Task).options(selectinload(Task.user)).where(Task.id == task_id))).scalar_one_or_none()
        if not task:
            await callback.answer("Задача не найдена!", show_alert=True)
            return None

        # Админ может все в чате, который у него в контексте
        user_data = await state.get_data()
        admin_chat_id = user_data.get('admin_context_chat_id')
        
        # Проверяем, является ли юзер админом в чате задачи И совпадает ли чат задачи с контекстом админа
        is_admin_in_task_chat = await is_admin(callback.message.bot, user_id, task.chat_id)
        
        if is_admin_in_task_chat and task.chat_id == admin_chat_id:
            return task
        
        # Владелец может
        if task.user_id == user_id:
            return task

    await callback.answer("У вас нет прав для этого действия, или ваш админ-контекст не совпадает с чатом задачи.", show_alert=True)
    return None


@dp.callback_query(F.data.startswith("usr_complete_task|"))
async def complete_task_handler(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Выполнена'."""
    task = await get_task_if_user_has_permission(callback, state)
    if not task:
        return
        
    async with async_session() as session:
        task.is_completed = True
        await session.merge(task)
        await session.commit()
    
    await callback.message.edit_text(f"Задача №{task.id} отмечена как выполненная.")
    await callback.answer()


@dp.callback_query(F.data.startswith("usr_delete_task|") | F.data.startswith("adm_delete_task|"))
async def delete_task_handler(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик удаления задачи."""
    task = await get_task_if_user_has_permission(callback, state)
    if not task:
        return

    async with async_session() as session:
        await session.delete(task)
        await session.commit()
        
    await callback.message.edit_text(f"Задача №{task.id} удалена.")
    await callback.answer()


@dp.callback_query(F.data.startswith("usr_edit_task|") | F.data.startswith("adm_edit_task|"))
async def edit_task_handler(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик начала редактирования задачи."""
    task = await get_task_if_user_has_permission(callback, state)
    if not task:
        return
    
    await state.set_state(TaskStates.editing_task_description)
    # Сохраняем и ID задачи, и ID чата для корректной проверки прав в конце
    await state.update_data(task_id=task.id, edit_task_chat_id=task.chat_id)

    await callback.message.edit_text(
        "Введите новое описание для задачи:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Описание", callback_data=f"edit_choice|{task.id}|desc")],
                [InlineKeyboardButton(text="Дату/время окончания", callback_data=f"edit_choice|{task.id}|end_dt")],
            ]
        )
    )
    await callback.answer()


class TaskStates(StatesGroup):
    editing_task_description = State()
    editing_task_end_date = State()
    editing_task_end_time = State()

@dp.callback_query(F.data.startswith("edit_choice|"))
async def process_edit_choice(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора поля для редактирования."""
    _, task_id, choice = callback.data.split("|")
    await state.update_data(edit_task_id=int(task_id))

    if choice == "desc":
        await state.set_state(TaskStates.editing_task_description)
        await callback.message.edit_text("Введите новое описание задачи.")
    elif choice == "end_dt":
        await state.set_state(TaskStates.editing_task_end_date)
        await callback.message.edit_text("Выберите новую дату окончания.", reply_markup=await SimpleCalendar().start_calendar())
    await callback.answer()

@dp.message(StateFilter(TaskStates.editing_task_description))
async def process_edit_description(message: Message, state: FSMContext):
    """Обновляет описание задачи в БД."""
    user_data = await state.get_data()
    task_id = user_data.get('task_id')
    chat_id_for_admin_check = user_data.get('edit_task_chat_id')

    async with async_session() as session:
        stmt = update(Task).where(Task.id == task_id).values(description=message.text)
        await session.execute(stmt)
        await session.commit()
    
    # Возвращаем правильную клавиатуру в зависимости от прав в чате задачи
    if not await is_admin(bot, message.from_user.id, chat_id_for_admin_check):
        # Если юзер не админ, возвращаем обычную клавиатуру
        await message.answer("Описание задачи обновлено!", reply_markup=user_main_kb)
    else:
        await message.answer("Описание задачи обновлено!", reply_markup=admin_main_kb)
    await state.set_state(None)  # Завершаем FSM, но сохраняем данные

@dp.callback_query(SimpleCalendarCallback.filter(), StateFilter(TaskStates.editing_task_end_date))
async def process_edit_date(callback_query: CallbackQuery, callback_data: SimpleCalendarCallback, state: FSMContext):
    """Обработка выбора новой даты окончания."""
    selected, new_date = await SimpleCalendar().process_selection(callback_query, callback_data)
    if selected:
        await state.update_data(end_date=new_date)
        await state.set_state(TaskStates.editing_task_end_time)
        await callback_query.message.edit_text(f"Новая дата: {new_date.strftime('%d.%m.%Y')}. Теперь введите время (HH:MM).")


@dp.message(StateFilter(TaskStates.editing_task_end_time))
async def process_edit_end_time(message: Message, state: FSMContext):
    """Обновляет время окончания задачи в БД."""
    user_data = await state.get_data()
    task_id = user_data.get('task_id')
    chat_id_for_admin_check = user_data.get('edit_task_chat_id')
    end_date = user_data.get('end_date')

    try:
        end_time = datetime.strptime(message.text, "%H:%M").time()
        new_datetime = datetime.combine(end_date, end_time)
        
        async with async_session() as session:
            stmt = update(Task).where(Task.id == task_id).values(end_datetime=new_datetime)
            await session.execute(stmt)
            await session.commit()
        
        # Возвращаем правильную клавиатуру в зависимости от прав
        if not await is_admin(bot, message.from_user.id, chat_id_for_admin_check):
            await message.answer("Дата окончания обновлена!", reply_markup=user_main_kb)
        else:
            await message.answer("Дата окончания обновлена!", reply_markup=admin_main_kb)
        await state.set_state(None)  # Завершаем FSM, но сохраняем данные
    except ValueError:
        await message.answer("Неверный формат времени. Введите HH:MM.")


# --- ОБРАБОТЧИКИ СОБЫТИЙ (В САМЫЙ КОНЕЦ ФАЙЛА!) ---
# Сначала должны идти специфические хендлеры (команды, FSM),
# а потом уже "общие" хендлеры, которые ловят любые сообщения.

@dp.chat_member(F.chat.type.in_({"group", "supergroup"}))
async def on_chat_member_update(event: ChatMemberUpdated):
    """Отслеживает изменения статуса участника чата."""
    user = event.new_chat_member.user
    chat_id = event.chat.id
    status = event.new_chat_member.status.name.lower()
    
    async with async_session() as session:
        await add_or_update_user(session, user.id, chat_id, user.username, user.full_name, status)
    
    logging.info(f"Chat member {user.id} status changed to {status} in chat {chat_id}.")


@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def on_any_message(message: Message):
    """Фиксирует/обновляет любого пользователя, написавшего сообщение. Должен быть последним message хендлером."""
    if not message.from_user or message.from_user.is_bot:
        return
        
    user = message.from_user
    chat_id = message.chat.id
    
    async with async_session() as session:
        # Статус не передаем, чтобы случайно не понизить админа.
        # Функция сама обработает, новый это юзер или старый.
        await add_or_update_user(session, user.id, chat_id, user.username, user.full_name)


# --- Фоновые задачи для уведомлений ---

def get_notification_keyboard(task: Task) -> InlineKeyboardMarkup:
    """Создает клавиатуру для сообщений-уведомлений."""
    builder = InlineKeyboardBuilder()
    if not task.is_completed:
        # Эта кнопка для всех, права проверятся в хендлере
        builder.button(text="✅ Отметить выполненной", callback_data=f"usr_complete_task|{task.id}")
    
    # Эти кнопки тоже для всех, права проверятся в хендлере
    builder.button(text="✏️ Редактировать", callback_data=f"adm_edit_task|{task.id}")
    builder.button(text="🗑 Удалить", callback_data=f"adm_delete_task|{task.id}")
    
    builder.adjust(1)
    return builder.as_markup()


async def check_overdue_tasks():
    """Проверяет просроченные задачи и отправляет уведомления."""
    while True:
        try:
            async with async_session() as session:
                now = datetime.now()
                stmt = (
                    select(Task)
                    .options(selectinload(Task.user))
                    .where(Task.end_datetime < now, Task.is_completed == False)
                )
                overdue_tasks = (await session.execute(stmt)).scalars().all()

                for task in overdue_tasks:
                    try:
                        if not task.user:
                            logging.warning(f"Пропуск уведомления для задачи {task.id}: пользователь {task.user_id} не найден в БД.")
                            continue

                        user_mention = f"<a href='tg://user?id={task.user.user_id}'>{task.user.full_name}</a>"
                        
                        text = (
                            f"⚠️ **Задача просрочена!** ⚠️\n\n"
                            f"<b>Задача №{task.id}</b>: {task.description}\n"
                            f"<b>Начало:</b> {task.start_datetime.strftime('%d.%m.%Y %H:%M')}\n"
                            f"<b>Срок был:</b> {task.end_datetime.strftime('%d.%m.%Y %H:%M')}"
                        )
                        keyboard = get_notification_keyboard(task)
                        
                        # Отправляем уведомление в ЛС
                        await bot.send_message(
                            chat_id=task.user.user_id,
                            text=text,
                            reply_markup=keyboard,
                            parse_mode='HTML'
                        )
                    except Exception as e:
                        logging.error(f"Не удалось отправить ЛС о просроченной задаче пользователю {task.user.user_id}: {e}")
        except Exception as e:
            logging.error(f"Ошибка в фоновой задаче check_overdue_tasks: {e}")
        
        await asyncio.sleep(60) # Для тестов можно поставить значение поменьше, например 60 секунд


async def notify_task_deadlines():
    """Уведомляет о задачах, срок которых скоро истечет (за час)."""
    while True:
        try:
            async with async_session() as session:
                now = datetime.now()
                hour_later = now + timedelta(hours=1)
                
                stmt = (
                    select(Task)
                    .options(selectinload(Task.user))
                    .where(
                        Task.end_datetime.between(now, hour_later),
                        Task.is_completed == False
                    )
                )
                upcoming_tasks = (await session.execute(stmt)).scalars().all()

                for task in upcoming_tasks:
                    try:
                        if not task.user:
                            logging.warning(f"Пропуск уведомления для задачи {task.id}: пользователь {task.user_id} не найден в БД.")
                            continue
                            
                        user_mention = f"<a href='tg://user?id={task.user.user_id}'>{task.user.full_name}</a>"
                        
                        text = (
                            f"🔥 **Скоро истекает срок задачи!** 🔥\n\n"
                            f"<b>Задача №{task.id}</b>: {task.description}\n"
                            f"<b>Начало:</b> {task.start_datetime.strftime('%d.%m.%Y %H:%M')}\n"
                            f"<b>Срок:</b> {task.end_datetime.strftime('%d.%m.%Y %H:%M')}"
                        )
                        keyboard = get_notification_keyboard(task)

                        # Отправляем уведомление в ЛС
                        await bot.send_message(
                            chat_id=task.user.user_id,
                            text=text,
                            reply_markup=keyboard,
                            parse_mode='HTML'
                        )
                    except Exception as e:
                        logging.error(f"Не удалось отправить ЛС о дедлайне пользователю {task.user.user_id}: {e}")
        except Exception as e:
            logging.error(f"Ошибка в фоновой задаче notify_task_deadlines: {e}")
            
        await asyncio.sleep(60) # Проверка каждую минуту


# --- ДОБАВЛЕНИЕ КНОПКИ 'Написать сообщение' ---
class AdminSendMessageFSM(StatesGroup):
    waiting_for_text = State()

# Модификация format_task_message
async def format_task_message(task: Task, for_admin: bool) -> tuple[str, InlineKeyboardMarkup]:
    status_emoji = "✅" if task.is_completed else "❌"
    status_text = "Выполнена" if task.is_completed else "Не выполнена"
    now = datetime.now()
    if not task.is_completed and task.end_datetime < now:
        status_emoji = "⚠️"
        status_text += " (Просрочена)"
    user_full_name = task.user.full_name if task.user else "Неизвестный"
    text = (
        f"<b>Задача №{task.id}</b>\n"
        f"Исполнитель: {user_full_name}\n"
        f"Описание: {task.description}\n"
        f"Начало: {task.start_datetime.strftime('%d.%m.%Y %H:%M')}\n"
        f"Окончание: {task.end_datetime.strftime('%d.%m.%Y %H:%M')}\n"
        f"Статус: {status_emoji} {status_text}"
    )
    builder = InlineKeyboardBuilder()
    if for_admin:
        if not task.is_completed:
            builder.button(text="✅ Отметить выполненной", callback_data=f"usr_complete_task|{task.id}")
        builder.button(text="✏️ Редактировать", callback_data=f"adm_edit_task|{task.id}")
        builder.button(text="🗑 Удалить", callback_data=f"adm_delete_task|{task.id}")
        builder.button(text="💬 Написать сообщение", callback_data=f"adm_sendmsg_task|{task.id}")
    else:
        if not task.is_completed:
            builder.button(text="✅ Отметить выполненной", callback_data=f"usr_complete_task|{task.id}")
        builder.button(text="✏️ Редактировать", callback_data=f"usr_edit_task|{task.id}")
    builder.adjust(1)
    return text, builder.as_markup()

# --- FSM: обработка нажатия 'Написать сообщение' ---
@dp.callback_query(F.data.startswith("adm_sendmsg_task|"))
async def admin_sendmsg_start(callback: CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split("|")[1])
    await state.update_data(sendmsg_task_id=task_id)
    await callback.message.answer("Введите сообщение, которое хотите отправить пользователю по этой задаче:")
    await state.set_state(AdminSendMessageFSM.waiting_for_text)
    await callback.answer()

@dp.message(StateFilter(AdminSendMessageFSM.waiting_for_text))
async def admin_sendmsg_process(message: Message, state: FSMContext):
    user_data = await state.get_data()
    task_id = user_data.get('sendmsg_task_id')
    admin_name = message.from_user.full_name
    text_to_send = message.text
    async with async_session() as session:
        task = (await session.execute(select(Task).options(selectinload(Task.user)).where(Task.id == task_id))).scalar_one_or_none()
        if not task or not task.user:
            await message.answer("Ошибка: не удалось найти задачу или пользователя.")
            await state.clear()
            return
        # Формируем цитату задачи
        task_quote = (
            f"<b>Цитата задачи №{task.id}</b>\n"
            f"Описание: {task.description}\n"
            f"Начало: {task.start_datetime.strftime('%d.%m.%Y %H:%M')}\n"
            f"Окончание: {task.end_datetime.strftime('%d.%m.%Y %H:%M')}"
        )
        msg = (
            f"<b>Вам сообщение от администратора:</b>\n"
            f"<b>Текст:</b> {text_to_send}\n\n"
            f"{task_quote}\n\n"
            f"<i>Отправитель: {admin_name}</i>"
        )
        try:
            await bot.send_message(task.user.user_id, msg, parse_mode="HTML")
            await message.answer("Сообщение успешно отправлено пользователю в личные сообщения!")
        except Exception as e:
            await message.answer(f"Не удалось отправить сообщение пользователю: {e}")
    await state.clear()


# --- Точка входа ---

async def main():
    """Главная функция запуска бота."""
    # Регистрация хендлеров в правильном порядке, если бы мы делали это не через декораторы
    # dp.message.register(...)
    # ...
    # Важно, что on_any_message регистрируется после всех команд и FSM
    
    await init_db()
    
    # Запускаем фоновые задачи
    asyncio.create_task(check_overdue_tasks())
    asyncio.create_task(notify_task_deadlines())

    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")
