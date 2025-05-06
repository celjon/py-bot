from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from src.domain.entity.user import User
from src.domain.entity.chat import Chat

def get_main_keyboard(user: User, chat: Chat) -> ReplyKeyboardMarkup:
    """Создание основной клавиатуры бота"""
    chat_buttons = get_chat_buttons(user.current_chat_index)

    web_search_text = "🔍 Поиск в интернете"
    if hasattr(chat, 'web_search_enabled') and chat.web_search_enabled:
        web_search_text += " ✅"
    else:
        web_search_text += " ❌"

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔄 Новый чат"),
                KeyboardButton(text=web_search_text),
                KeyboardButton(text="🎨 Генерация изображений")
            ],
            [
                KeyboardButton(text="⚙️ Инструменты"),
                KeyboardButton(text="📋 Буфер")
            ] + chat_buttons
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