import logging
import json
from aiogram.types import Message
from src.domain.entity.user import User
from src.domain.entity.chat import Chat
import aiohttp
logger = logging.getLogger(__name__)

async def get_or_create_user(message: Message, user_repository):
    """Получение или создание пользователя из сообщения Telegram"""
    telegram_id = str(message.from_user.id)
    user = await user_repository.find_by_telegram_id(telegram_id)

    if not user:
        user = User(
            id=0,  # Временный ID, будет заменён после сохранения
            telegram_id=telegram_id,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            username=message.from_user.username,
            language_code=message.from_user.language_code,
            current_chat_index=1,
            current_chat_list_page=1
        )
        user_id = await user_repository.save(user)
        user.id = user_id

    return user

async def get_or_create_chat(user: User, chat_repository):
    """Получение или создание чата для пользователя"""
    chat = await chat_repository.find_by_user_id_and_chat_index(user.id, user.current_chat_index)

    if not chat:
        chat = Chat(
            id=0,  # Временный ID, будет заменен после сохранения
            user_id=user.id,
            chat_index=user.current_chat_index,
            context_remember=True,
            context_counter=0,
            links_parse=False,
            formula_to_image=False,
            answer_to_voice=False
        )

        # Специальная настройка для пятого чата (📝)
        if user.current_chat_index == 5:
            chat.context_remember = False
            chat.system_prompt = "Ты помощник, который помогает писать и редактировать тексты."

        chat_id = await chat_repository.save(chat)
        chat.id = chat_id

    return chat

async def send_long_message(message: Message, content: str, parse_mode: str = "Markdown"):
    """Отправляет длинное сообщение, разбивая его на части, если необходимо."""
    max_length = 3900 if parse_mode == "Markdown" else 4096

    if len(content) <= max_length:
        await message.answer(content, parse_mode=parse_mode)
        return

    parts = []
    while content:
        if len(content) <= max_length:
            parts.append(content)
            content = ""
        else:
            last_newline = content[:max_length].rfind("\n")
            if last_newline == -1:
                last_newline = max_length
            parts.append(content[:last_newline])
            content = content[last_newline:]

    for part in parts:
        await message.answer(part, parse_mode=parse_mode)


async def download_file_custom(token, file_path, api_url):
    """
    Скачивание файла из Telegram API

    Args:
        token: Токен бота
        file_path: Путь к файлу от API
        api_url: URL API сервера

    Returns:
        bytes: Содержимое файла
    """
    import aiohttp

    # Формируем правильный URL файла
    # Заменяем двойные слеши на одинарные
    file_url = f"{api_url}/file/bot{token}/{file_path}"
    file_url = file_url.replace("//", "/")
    file_url = file_url.replace(":/", "://")  # Восстанавливаем протокол

    async with aiohttp.ClientSession() as session:
        async with session.get(file_url) as response:
            if response.status != 200:
                raise Exception(f"Ошибка при скачивании файла: {response.status}")

            return await response.read()


# Исправленная функция для скачивания файла
async def download_voice_file(bot, file_id, temp_file_path):
    try:
        # Получаем информацию о файле
        file_info = await bot.get_file(file_id)

        # Получаем настройки
        from src.config.settings import get_settings
        settings = get_settings()

        # Формируем корректный URL для скачивания
        api_url = settings.TELEGRAM_API_URL.rstrip('/')
        file_path = file_info.file_path.lstrip('/')
        file_url = f"{api_url}/file/bot{bot.token}/{file_path}"

        # Скачиваем файл
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                if response.status != 200:
                    raise Exception(f"Не удалось скачать файл: HTTP {response.status}")

                # Сохраняем содержимое файла
                with open(temp_file_path, "wb") as f:
                    f.write(await response.read())

        return temp_file_path
    except Exception as e:
        logger.error(f"Ошибка при скачивании файла: {e}", exc_info=True)
        raise