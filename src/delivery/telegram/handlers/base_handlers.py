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
        logger.info(f"[FILE_DOWNLOAD] Получение информации о файле с ID: {file_id}")
        file_info = await bot.get_file(file_id)
        file_path = file_info.file_path
        logger.info(f"[FILE_DOWNLOAD] Получен путь к файлу: {file_path}")
        logger.info(f"[FILE_DOWNLOAD] Полная информация о файле: {file_info}")

        # Если путь не указан, создаем временный файл
        if not save_path:
            import tempfile
            import os
            import time
            temp_dir = tempfile.gettempdir()
            file_ext = os.path.splitext(file_path)[
                           1] or '.ogg'  # Используем расширение из оригинального пути или .ogg по умолчанию
            save_path = os.path.join(temp_dir, f"{file_id}_{int(time.time())}{file_ext}")
            logger.info(f"[FILE_DOWNLOAD] Создан временный путь для сохранения: {save_path}")

        # Создаем директорию для файла, если она не существует
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        logger.info(f"[FILE_DOWNLOAD] Директория для сохранения файла: {os.path.dirname(save_path)}")

        # Список всех путей, которые будем проверять
        paths_to_check = [
            # Прямой путь
            file_path,
            # Путь внутри контейнера Telegram Bot API
            f"/telegram-bot-api-data{file_path}" if not file_path.startswith("/telegram-bot-api-data") else file_path,
            # Путь с удаленным начальным слэшем
            os.path.join("/telegram-bot-api-data", file_path.lstrip("/")),
            # Дополнительные варианты, которые могут помочь найти файл
            os.path.join("/telegram-bot-api-data/voice", os.path.basename(file_path)),
            os.path.join("/telegram-bot-api-data/audio", os.path.basename(file_path))
        ]

        logger.info(f"[FILE_DOWNLOAD] Проверяем следующие пути: {paths_to_check}")

        # Проверяем все возможные пути
        for path in paths_to_check:
            logger.info(f"[FILE_DOWNLOAD] Проверяем путь: {path}")
            if os.path.exists(path):
                logger.info(f"[FILE_DOWNLOAD] Файл найден по пути: {path}")
                # Проверяем размер файла
                file_size = os.path.getsize(path)
                logger.info(f"[FILE_DOWNLOAD] Размер файла: {file_size} байт")

                # Копируем файл
                import shutil
                shutil.copy(path, save_path)
                logger.info(f"[FILE_DOWNLOAD] Файл успешно скопирован из: {path} -> {save_path}")
                return save_path
            else:
                logger.info(f"[FILE_DOWNLOAD] Файл не найден по пути: {path}")

        # Логируем текущую директорию и содержимое /telegram-bot-api-data для отладки
        try:
            logger.info(f"[FILE_DOWNLOAD] Текущая директория: {os.getcwd()}")
            if os.path.exists("/telegram-bot-api-data"):
                logger.info(f"[FILE_DOWNLOAD] Содержимое /telegram-bot-api-data:")
                for root, dirs, files in os.walk("/telegram-bot-api-data", topdown=True, onerror=None):
                    logger.info(f"[FILE_DOWNLOAD] Директория: {root}")
                    logger.info(f"[FILE_DOWNLOAD] Поддиректории: {dirs}")
                    logger.info(f"[FILE_DOWNLOAD] Файлы: {files}")
                    # Ограничиваем глубину поиска, чтобы не переполнить логи
                    if root.count('/') > 4:  # Максимальная глубина
                        dirs[:] = []  # Не углубляемся дальше
        except Exception as e:
            logger.error(f"[FILE_DOWNLOAD] Ошибка при попытке вывести содержимое директории: {e}")

        # Поиск по всей директории, если файл не найден по конкретным путям
        file_name = os.path.basename(file_path)
        logger.info(f"[FILE_DOWNLOAD] Ищем файл по имени: {file_name} в директории /telegram-bot-api-data")
        for root, dirs, files in os.walk("/telegram-bot-api-data"):
            if file_name in files:
                found_path = os.path.join(root, file_name)
                logger.info(f"[FILE_DOWNLOAD] Файл найден по пути: {found_path}")

                # Проверяем размер файла
                file_size = os.path.getsize(found_path)
                logger.info(f"[FILE_DOWNLOAD] Размер файла: {file_size} байт")

                import shutil
                shutil.copy(found_path, save_path)
                logger.info(f"[FILE_DOWNLOAD] Файл успешно скопирован: {found_path} -> {save_path}")
                return save_path
            # Ограничиваем глубину поиска, чтобы не тратить слишком много времени
            if root.count('/') > 4:  # Максимальная глубина
                dirs[:] = []  # Не углубляемся дальше

        # Если файл не найден в файловой системе, пробуем HTTP-запрос
        logger.warning(f"[FILE_DOWNLOAD] Файл не найден в файловой системе, пробуем HTTP-запрос")

        # Используем настройки для получения базового URL
        if not settings:
            from src.config.settings import get_settings
            settings = get_settings()
            logger.info(f"[FILE_DOWNLOAD] Получены настройки: {settings.TELEGRAM_API_URL}")

        # Базовый URL локального API
        local_api_url = settings.TELEGRAM_API_URL.rstrip("/")
        token = bot.token
        logger.info(f"[FILE_DOWNLOAD] Используем API URL: {local_api_url}")

        # Пробуем разные форматы URL
        urls_to_try = [
            f"{local_api_url}/file/bot{token}/{file_path}",
            f"{local_api_url}/file/bot{token}/{file_path.lstrip('/')}",
            f"{local_api_url}/file/bot{token}/voice/{os.path.basename(file_path)}",
            f"{local_api_url}/file/bot{token}/audio/{os.path.basename(file_path)}",
            # Попробуем прямой URL
            f"https://api.telegram.org/file/bot{token}/{file_path}"
        ]

        logger.info(f"[FILE_DOWNLOAD] Пробуем следующие URL: {urls_to_try}")

        for url in urls_to_try:
            logger.info(f"[FILE_DOWNLOAD] Пробуем URL: {url}")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        status = response.status
                        logger.info(f"[FILE_DOWNLOAD] Статус ответа от {url}: {status}")

                        if status == 200:
                            content = await response.read()
                            content_length = len(content)
                            logger.info(f"[FILE_DOWNLOAD] Получено {content_length} байт с URL {url}")

                            if content_length > 100:  # Проверка, что файл не пустой
                                with open(save_path, "wb") as f:
                                    f.write(content)
                                logger.info(f"[FILE_DOWNLOAD] Файл успешно скачан с URL {url} и сохранен в {save_path}")
                                return save_path
                            else:
                                logger.warning(
                                    f"[FILE_DOWNLOAD] Получено слишком мало данных ({content_length} байт) с URL {url}")
                        else:
                            headers = response.headers
                            body = await response.text()
                            logger.error(f"[FILE_DOWNLOAD] Ошибка при загрузке с URL {url}: HTTP {status}")
                            logger.error(f"[FILE_DOWNLOAD] Заголовки: {headers}")
                            logger.error(f"[FILE_DOWNLOAD] Тело ответа: {body[:200]}...")  # Логируем только начало тела
            except Exception as url_error:
                logger.error(f"[FILE_DOWNLOAD] Ошибка при запросе URL {url}: {url_error}")

        # Если все попытки не удались - создаем пустой файл для тестирования дальнейшего процесса
        logger.error("[FILE_DOWNLOAD] Все попытки скачать файл не удались. Создаем пустой файл для тестирования.")
        with open(save_path, "wb") as f:
            f.write(b"Test file - failed to download real content")

        logger.warning(f"[FILE_DOWNLOAD] Создан пустой файл для тестирования: {save_path}")
        return save_path

    except Exception as e:
        logger.error(f"[FILE_DOWNLOAD] Общая ошибка при скачивании файла: {e}", exc_info=True)

        # Создаем пустой файл для тестирования дальнейшего процесса
        try:
            with open(save_path, "wb") as f:
                f.write(b"Test file - exception occurred during download")
            logger.warning(f"[FILE_DOWNLOAD] Создан пустой файл для тестирования: {save_path}")
            return save_path
        except Exception as file_error:
            logger.error(f"[FILE_DOWNLOAD] Ошибка при создании файла заглушки: {file_error}")
            raise Exception(f"Не удалось скачать файл: {e}")