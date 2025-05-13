import logging
import os
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


async def download_telegram_file(token: str, file_id: str, save_path: str = None):
    base_url = "http://telegram-bot-api:8081"
    logger.info(f"[download_telegram_file] Используемый base_url: {base_url}")
    logger.info(f"[download_telegram_file] Telegram token: {token}")
    logger.info(f"[download_telegram_file] file_id: {file_id}")

    async with aiohttp.ClientSession() as session:
        # Шаг 1: Получить путь к файлу
        get_file_url = f"{base_url}/bot{token}/getFile"
        logger.info(f"[download_telegram_file] URL для getFile: {get_file_url}")
        async with session.get(get_file_url, params={"file_id": file_id}) as response:
            logger.info(f"[download_telegram_file] Ответ от getFile: HTTP {response.status}")
            response_text = await response.text()
            if response.status != 200:
                logger.error(
                    f"[download_telegram_file] Ошибка при запросе getFile: HTTP {response.status}, {response_text}")
                raise Exception(f"Ошибка при запросе getFile: HTTP {response.status}, {response_text}")

            data = await response.json()
            if not data.get("ok"):
                logger.error(f"[download_telegram_file] Telegram API error: {data.get('description')}")
                raise Exception(f"Telegram API error: {data.get('description')}")

            file_path = data["result"]["file_path"]
            logger.info(f"[download_telegram_file] Получен file_path: {file_path}")

        # Шаг 2: Извлекаем правильную часть пути для скачивания
        # Предполагаем, что путь имеет формат /telegram-bot-api-data/TOKEN/voice/file_name.oga
        parts = file_path.split('/')

        # Определяем тип файла и имя файла
        if len(parts) >= 4:
            file_type = parts[-2]  # например, 'voice'
            file_name = parts[-1]  # например, 'file_15.oga'

            # Формируем URL с учетом того, как работает ваш локальный API
            download_url = f"{base_url}/file/bot{token}/{file_type}/{file_name}"
            logger.info(f"[download_telegram_file] URL для скачивания файла: {download_url}")

            async with session.get(download_url) as file_response:
                logger.info(f"[download_telegram_file] Ответ от скачивания файла: HTTP {file_response.status}")

                if file_response.status != 200:
                    # Если не сработало, пробуем без типа файла
                    simple_url = f"{base_url}/file/bot{token}/{file_name}"
                    logger.info(f"[download_telegram_file] Пробуем упрощенный URL: {simple_url}")

                    async with session.get(simple_url) as simple_response:
                        logger.info(f"[download_telegram_file] Ответ от упрощенного URL: HTTP {simple_response.status}")

                        if simple_response.status != 200:
                            error_text = await simple_response.text()
                            logger.error(
                                f"[download_telegram_file] Ошибка при скачивании файла: HTTP {simple_response.status}, {error_text}")
                            raise Exception(
                                f"Не удалось скачать файл. Пожалуйста, проверьте документацию вашего Telegram Bot API сервера.")

                        file_data = await simple_response.read()
                else:
                    file_data = await file_response.read()
        else:
            # Если путь не соответствует ожидаемому формату
            raise Exception(f"Неожиданный формат пути к файлу: {file_path}")

        # Сохраняем или возвращаем файл
        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(file_data)
            logger.info(f"[download_telegram_file] Файл сохранён по пути: {save_path}")
            return save_path

        logger.info(f"[download_telegram_file] Файл загружен в память, размер: {len(file_data)} байт")
        return file_data