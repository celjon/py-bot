import os
import time
from src.lib.utils.file_utils import download_file
from typing import Dict, Any, Optional, List, Tuple
from src.lib.clients.bothub_client import BothubClient
from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class BothubGateway:
    """Адаптер для взаимодействия с BotHub API"""

    def __init__(self, bothub_client: BothubClient):
        self.client = bothub_client

    async def get_access_token(self, user: User) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
        """
        Получение/обновление токена доступа

        Returns:
            Tuple[str, Optional[str], Optional[str], Optional[str]]:
                (access_token, group_id, chat_id, model_id)
        """
        if user.bothub_access_token:
            # Проверка срока действия токена (по умолчанию - 24 часа)
            token_lifetime = 86390  # 24 * 60 * 60 - 10 секунд
            current_time = datetime.now()

            if (user.bothub_access_token_created_at and
                    (current_time - user.bothub_access_token_created_at).total_seconds() < token_lifetime):
                logger.debug(f"Using existing token for user {user.id}")
                return (user.bothub_access_token, user.bothub_group_id,
                        None, None)

        logger.info(f"Getting new access token for user {user.id}")
        response = await self.client.authorize(
            user.telegram_id,
            user.first_name or user.username or "Telegram User",
            user.bothub_id,
            user.referral_code
        )

        # Обновляем информацию о пользователе
        user.bothub_access_token = response["accessToken"]
        user.bothub_access_token_created_at = datetime.now()

        if not user.bothub_id:
            user.bothub_id = response["user"]["id"]

        # Проверяем наличие групп и чатов у пользователя
        group_id = None
        chat_id = None
        model_id = None

        if "groups" in response["user"] and response["user"]["groups"]:
            groups = response["user"]["groups"]
            group_id = groups[0]["id"]
            user.bothub_group_id = group_id

            if groups[0]["chats"]:
                chats = groups[0]["chats"]
                chat_id = chats[0]["id"]

                if "settings" in chats[0] and "model" in chats[0]["settings"]:
                    model_id = chats[0]["settings"]["model"]

        return user.bothub_access_token, group_id, chat_id, model_id

    async def get_available_models(self, access_token: str) -> List[Dict[str, Any]]:
        """Получение списка доступных моделей"""
        models_response = await self.client.list_models(access_token)
        return models_response

    def is_gpt_model(self, model: Dict[str, Any]) -> bool:
        """Проверка, является ли модель GPT-моделью"""
        return "TEXT_TO_TEXT" in model.get("features", [])

    async def get_default_model(self, access_token: str) -> dict:
        """Выбор модели по умолчанию, как в PHP-боте"""
        models = await self.client.list_models(access_token)
        # Ищем дефолтную модель, которая поддерживает генерацию текста
        for model in models:
            if (model.get("is_default", True) or model.get("is_allowed", True)) and "TEXT_TO_TEXT" in model.get(
                    "features", []):
                return model
        # Если дефолтную не нашли, возвращаем первую доступную для текста
        for model in models:
            if "TEXT_TO_TEXT" in model.get("features", []):
                return model
        raise Exception("No suitable GPT model found")

    async def create_new_chat(self, user: User, chat: Chat, is_image_generation: bool = False) -> None:
        """Создание нового чата"""
        access_token, group_id, _, _ = await self.get_access_token(user)

        if not group_id:
            logger.info(f"Creating new group for user {user.id}")
            group_response = await self.client.create_new_group(access_token, "Telegram")
            group_id = group_response["id"]
            user.bothub_group_id = group_id

        try:
            # Определяем модель в зависимости от типа чата
            if is_image_generation:
                model_id = user.image_generation_model or "dall-e"
                response = await self.client.create_new_chat(
                    access_token,
                    group_id,
                    f"Telegram chat {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    model_id
                )
            else:
                # Получаем список моделей и находим дефолтную модель
                models = await self.get_available_models(access_token)
                default_model = None
                for model in models:
                    if (model.get("is_default", False) or model.get("is_allowed",
                                                                    False)) and "TEXT_TO_TEXT" in model.get("features",
                                                                                                            []):
                        default_model = model
                        break

                if not default_model:
                    raise Exception("Default model not found")

                # Сначала создаем чат с родительской моделью
                parent_id = default_model.get("parent_id")
                response = await self.client.create_new_chat(
                    access_token,
                    group_id,
                    f"Telegram chat {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    parent_id
                )

                # Затем устанавливаем конкретную модель в настройках чата
                chat_id = response["id"]
                model_id = default_model.get("id")
                await self.client.save_chat_settings(
                    access_token,
                    chat_id,
                    model_id,
                    None,  # max_tokens
                    chat.context_remember,
                    chat.system_prompt
                )

            chat.bothub_chat_id = response["id"]
            chat.bothub_chat_model = model_id

        except Exception as e:
            logger.error(f"Error creating chat: {str(e)}")
            if "MODEL_NOT_FOUND" in str(e):
                # Пробуем создать чат с моделью по умолчанию
                models = await self.client.list_models(access_token)
                logger.warning(f"Available models: {[m.get('id') for m in models]}")
                # Берем первую доступную модель TEXT_TO_TEXT
                for model in models:
                    if "TEXT_TO_TEXT" in model.get("features", []) and model.get("is_allowed", False):
                        model_id = model.get("id")
                        parent_id = model.get("parent_id", model_id)
                        logger.info(f"Trying with model {parent_id} -> {model_id}")
                        response = await self.client.create_new_chat(
                            access_token,
                            group_id,
                            f"Telegram chat {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                            parent_id
                        )
                        chat.bothub_chat_id = response["id"]
                        chat.bothub_chat_model = model_id
                        return
                raise

    async def save_chat_settings(self, user: User, chat: Chat) -> None:
        """Сохранение настроек чата"""
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)
            return

        access_token, _, _, _ = await self.get_access_token(user)

        # Определяем максимальное количество токенов в зависимости от модели
        max_tokens = None
        if "gpt-4" in chat.bothub_chat_model:
            max_tokens = 4000
        elif "gpt-3.5" in chat.bothub_chat_model:
            max_tokens = 2000

        await self.client.save_chat_settings(
            access_token,
            chat.bothub_chat_id,
            chat.bothub_chat_model,
            max_tokens,
            chat.context_remember,
            chat.system_prompt
        )

    async def reset_context(self, user: User, chat: Chat) -> None:
        """Сброс контекста чата"""
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)
            return

        access_token, _, _, _ = await self.get_access_token(user)
        await self.client.reset_context(access_token, chat.bothub_chat_id)
        chat.reset_context_counter()

    async def get_web_search(self, user: User, chat: Chat) -> bool:
        """Проверка статуса веб-поиска"""
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)
            return False

        access_token, _, _, _ = await self.get_access_token(user)
        return await self.client.get_web_search(access_token, chat.bothub_chat_id)

    async def enable_web_search(self, user: User, chat: Chat, value: bool) -> None:
        """Включение/выключение веб-поиска"""
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)
            return

        access_token, _, _, _ = await self.get_access_token(user)
        await self.client.enable_web_search(access_token, chat.bothub_chat_id, value)

    async def transcribe_voice(self, user: User, chat: Chat, file_url: str) -> str:
        """Транскрибирование голосового сообщения"""
        access_token, _, _, _ = await self.get_access_token(user)

        try:
            # Скачиваем файл во временный каталог
            temp_file = await download_file(file_url, f"voice_{user.id}_{int(time.time())}.ogg")

            # Отправляем на транскрибирование
            result = await self.client.transcribe(access_token, temp_file)

            # Удаляем временный файл
            if os.path.exists(temp_file):
                os.remove(temp_file)

            return result.get("text", "")
        except Exception as e:
            logger.error(f"Error in BotHub transcription: {e}", exc_info=True)
            if os.path.exists(temp_file):
                os.remove(temp_file)
            # Пока просто возвращаем заглушку
            return "Это текст голосового сообщения (заглушка)"

    async def send_message(self, user: User, chat: Chat, message: str, files: List = None) -> Dict[str, Any]:
        """Отправка сообщения"""
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)

        access_token, _, _, _ = await self.get_access_token(user)

        try:
            response = await self.client.send_message(access_token, chat.bothub_chat_id, message, files)

            # Обновляем счетчик контекста, если надо запоминать его
            if chat.context_remember:
                chat.increment_context_counter()

            return response
        except Exception as e:
            # Если чат не найден, создаем новый
            if "CHAT_NOT_FOUND" in str(e):
                logger.warning(f"Chat not found, creating new one for user {user.id}")
                await self.create_new_chat(user, chat)
                return await self.client.send_message(access_token, chat.bothub_chat_id, message, files)
            raise