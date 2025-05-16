from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from src.domain.entity.user import User
from src.domain.entity.chat import Chat

def get_main_keyboard(user: User, chat: Chat = None) -> ReplyKeyboardMarkup:
    """Создает основную клавиатуру только с необходимыми кнопками"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔄 Новый чат"), KeyboardButton(text="⚙️ Сменить модель")],
            [KeyboardButton(text="🔗 Привязать аккаунт")]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_chat_buttons(current_chat_index: int):
    """Возвращает кнопки чатов с маркером текущего чата"""
    buttons = []
    chat_emojis = {"1️⃣": 1, "2️⃣": 2, "3️⃣": 3, "4️⃣": 4, "📝": 5}

    for emoji, index in chat_emojis.items():
        if index == current_chat_index:
            buttons.append(KeyboardButton(text=f"{emoji}✅"))
        else:
            buttons.append(KeyboardButton(text=emoji))

    return buttons