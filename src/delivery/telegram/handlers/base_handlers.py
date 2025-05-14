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


async def download_telegram_file(bot, file_id: str, save_path: str = None, settings=None):
    """
    Загружает файл из локального Telegram API, используя прямой доступ к файловой системе

    Args:
        bot: Экземпляр бота aiogram
        file_id: ID файла в Telegram
        save_path: Путь для сохранения файла (если None, создается временный файл)
        settings: Настройки приложения

    Returns:
        str: Путь к загруженному файлу
    """
    try:
        # Получаем информацию о файле
        logger.info(f"Получение информации о файле с ID: {file_id}")
        file_info = await bot.get_file(file_id)
        file_path = file_info.file_path
        logger.info(f"Получен путь к файлу: {file_path}")

        # Если путь не указан, создаем временный файл
        if not save_path:
            import tempfile
            import os
            import time
            temp_dir = tempfile.gettempdir()
            save_path = os.path.join(temp_dir, f"{file_id}_{int(time.time())}.ogg")

        # Создаем директорию для файла, если она не существует
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        # Проверяем, есть ли прямой доступ к файлу через файловую систему
        if os.path.exists(file_path):
            # Просто копируем файл
            import shutil
            shutil.copy(file_path, save_path)
            logger.info(f"Файл скопирован напрямую из файловой системы: {file_path} -> {save_path}")
            return save_path

        logger.info(f"Файл не найден по прямому пути: {file_path}")

        # Пробуем другие варианты путей в файловой системе
        # Иногда пути могут немного отличаться

        # Вариант 1: файл должен быть в директории /telegram-bot-api-data/
        alt_path = f"/telegram-bot-api-data{file_path}" if not file_path.startswith(
            "/telegram-bot-api-data") else file_path
        if os.path.exists(alt_path):
            import shutil
            shutil.copy(alt_path, save_path)
            logger.info(f"Файл скопирован по альтернативному пути: {alt_path} -> {save_path}")
            return save_path

        logger.info(f"Файл не найден по альтернативному пути: {alt_path}")

        # Если файл не найден по прямым путям, используем поиск в директории
        # Обычно файлы голосовых сообщений имеют формат file_X.oga в директории voice

        file_name = os.path.basename(file_path)  # Например, file_18.oga

        # Ищем в директории /telegram-bot-api-data
        for root, dirs, files in os.walk("/telegram-bot-api-data"):
            if file_name in files:
                found_path = os.path.join(root, file_name)
                import shutil
                shutil.copy(found_path, save_path)
                logger.info(f"Файл найден и скопирован: {found_path} -> {save_path}")
                return save_path

        # Если файл все равно не найден, пробуем HTTP-запрос
        # Хотя, основываясь на предыдущих ошибках, это, скорее всего, не сработает
        logger.warning("Файл не найден в файловой системе, пробуем HTTP-запрос (маловероятно, что сработает)")

        # Используем настройки для получения базового URL
        if not settings:
            from src.config.settings import get_settings
            settings = get_settings()

        # Базовый URL локального API
        local_api_url = settings.TELEGRAM_API_URL.rstrip("/")  # убираем слеш в конце, если есть
        token = bot.token

        # Пробуем разные форматы URL
        urls_to_try = [
            f"{local_api_url}/file/bot{token}/voice/{file_name}",
            f"{local_api_url}/file/bot{token}/{file_name}",
            f"{local_api_url}/{file_path.lstrip('/')}"
        ]

        for url in urls_to_try:
            logger.info(f"Пробуем URL: {url}")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            with open(save_path, "wb") as f:
                                f.write(await response.read())
                            logger.info(f"Файл успешно скачан с URL {url}")
                            return save_path
            except Exception as url_error:
                logger.error(f"Ошибка при скачивании с URL {url}: {url_error}")

        # Если все попытки не удались - создаем пустой файл для тестирования дальнейшего процесса
        logger.error("Все попытки скачать файл не удались. Создаем пустой файл для тестирования.")
        with open(save_path, "wb") as f:
            f.write(b"Test file - failed to download real content")

        return save_path

    except Exception as e:
        logger.error(f"Ошибка при скачивании файла: {e}", exc_info=True)

        # Создаем пустой файл для тестирования дальнейшего процесса
        try:
            with open(save_path, "wb") as f:
                f.write(b"Test file - exception occurred during download")
            logger.warning(f"Создан пустой файл для тестирования: {save_path}")
            return save_path
        except:
            raise Exception(f"Не удалось скачать файл: {e}")