import logging
from aiogram import Bot
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


async def download_telegram_file(bot: Bot, token: str, file_id: str, save_path: str = None):
    api_server = bot.session.api
    get_file_url = api_server.api_url(token, "getFile")  # ✅ правильно!

    logger.info(f"Token: {token}")
    logger.info(f"API server base: {api_server.base}")
    logger.info(f"getFile URL: {get_file_url}")

    async with aiohttp.ClientSession() as session:
        async with session.post(get_file_url, json={"file_id": file_id}) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"HTTP {response.status}: {error_text}")
                raise Exception(f"Не удалось получить информацию о файле: HTTP {response.status}")

            file_info = await response.json()
            if not file_info.get("ok"):
                error = file_info.get("description", "Неизвестная ошибка")
                raise Exception(f"Ошибка API Telegram: {error}")

            file_path = file_info["result"]["file_path"]
            logger.info(f"Raw file_path from Telegram: {file_path}")
            download_url = api_server.file_url(token, file_path)
            logger.info(f"Download file URL: {download_url}")

            async with session.get(download_url) as download_response:
                if download_response.status != 200:
                    error_text = await download_response.text()
                    logger.error(f"HTTP {download_response.status}: {error_text}")
                    raise Exception(f"Не удалось скачать файл: HTTP {download_response.status}")

                file_content = await download_response.read()

                if save_path:
                    import os
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    with open(save_path, "wb") as f:
                        f.write(file_content)
                    logger.info(f"Файл сохранен: {save_path}")
                    return save_path

                return file_content
