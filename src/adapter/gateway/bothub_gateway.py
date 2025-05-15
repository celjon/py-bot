# src/adapter/gateway/bothub_gateway.py
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import logging
from src.lib.clients.bothub_client import BothubClient
from src.domain.entity.user import User
from src.domain.entity.chat import Chat

logger = logging.getLogger(__name__)


class BothubGateway:
    """Адаптер для взаимодействия с BotHub API"""

    # Список доступных моделей в порядке приоритета
    AVAILABLE_MODELS = ["gpt-4.1-nano", "gpt-3.5-turbo", "claude-instant", "gemini-pro"]

    def __init__(self, bothub_client: BothubClient):
        self.client = bothub_client

    async def get_access_token(self, user: User) -> str:
        """
        Получение/обновление токена доступа

        Args:
            user: Пользователь

        Returns:
            str: Токен доступа
        """
        token_lifetime = 86390  # 24 * 60 * 60 - 10 seconds
        current_time = datetime.now()

        # Проверяем, есть ли у пользователя токен и не истек ли он
        if (user.bothub_access_token and user.bothub_access_token_created_at and
                (current_time - user.bothub_access_token_created_at).total_seconds() < token_lifetime):
            logger.debug(f"Использую существующий токен для пользователя {user.id}")
            return user.bothub_access_token

        # Получаем новый токен
        logger.info(f"Получаю новый токен доступа для пользователя {user.id}")
        response = await self.client.authorize(
            user.telegram_id,
            user.first_name or user.username or "Telegram User",
            user.bothub_id,
            user.referral_code
        )

        # Обновляем данные пользователя
        user.bothub_access_token = response["accessToken"]
        user.bothub_access_token_created_at = current_time

        if not user.bothub_id:
            user.bothub_id = response["user"]["id"]

            if "groups" in response["user"] and response["user"]["groups"]:
                user.bothub_group_id = response["user"]["groups"][0]["id"]

                if "chats" in response["user"]["groups"][0] and response["user"]["groups"][0]["chats"]:
                    chat_data = response["user"]["groups"][0]["chats"][0]
                    chat = Chat(
                        id=0,
                        user_id=user.id,
                        chat_index=user.current_chat_index,
                        bothub_chat_id=chat_data["id"],
                        name=chat_data.get("name")
                    )

                    if "settings" in chat_data and "model" in chat_data["settings"]:
                        chat.bothub_chat_model = chat_data["settings"]["model"]

        return user.bothub_access_token

    async def create_new_chat(self, user: User, chat: Chat, is_image_generation: bool = False) -> None:
        """
        Creating a new chat

        Args:
            user: User
            chat: Chat
            is_image_generation: Flag for image generation chat
        """
        logger.info(f"Creating new chat for user {user.id}")
        access_token = await self.get_access_token(user)

        # If no group, create a new one
        if not user.bothub_group_id:
            logger.info(f"Creating new group for user {user.id}")
            group_response = await self.client.create_new_group(access_token, "Telegram")
            user.bothub_group_id = group_response["id"]

        try:
            name = f"Telegram Chat {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            # Get available models first
            try:
                models = await self.client.list_models(access_token)

                if is_image_generation:
                    # For image generation
                    model_id = user.image_generation_model or "dall-e"
                    parent_id = model_id  # For image models, parent and model are typically the same

                    # Special handling for flux models
                    if "flux" in model_id:
                        response = await self.client.create_new_chat(
                            access_token,
                            user.bothub_group_id,
                            name,
                            "replicate-flux"  # Parent model for flux
                        )
                        await self.client.update_parent_model(access_token, response["id"], "replicate-flux")
                        await self.client.save_model(access_token, response["id"], model_id)
                        response["model_id"] = model_id
                    else:
                        response = await self.client.create_new_chat(
                            access_token,
                            user.bothub_group_id,
                            name,
                            model_id
                        )
                else:
                    # For text models
                    # Filter for text models that are default or allowed
                    text_models = [
                        model for model in models
                        if ("TEXT_TO_TEXT" in model.get("features", []) and
                            (model.get("is_default", False) or model.get("is_allowed", False)))
                    ]

                    # Find a suitable model
                    default_model = None
                    for model in text_models:
                        if model.get("is_default") and model.get("is_allowed", False):
                            default_model = model
                            break

                    # If no default model, take the first allowed one
                    if default_model is None:
                        for model in text_models:
                            if model.get("is_allowed", False):
                                default_model = model
                                break

                    # If still no model found, use a fallback
                    if default_model is None:
                        # Fallback to a basic model - using parent model ID
                        parent_id = "gpt"
                        model_id = "gpt-4.1-nano"
                    else:
                        model_id = default_model.get("id")
                        parent_id = default_model.get("parent_id") or model_id

                    logger.info(f"Creating chat with model: {model_id} (parent: {parent_id})")

                    # Create chat with parent model
                    response = await self.client.create_new_chat(
                        access_token,
                        user.bothub_group_id,
                        name,
                        parent_id
                    )

                    # Then set the actual model
                    if parent_id != model_id:
                        await self.client.save_chat_settings(
                            access_token,
                            response["id"],
                            model_id,
                            None,  # max_tokens
                            chat.context_remember,
                            chat.system_prompt
                        )

            except Exception as model_error:
                logger.error(f"Error getting models: {str(model_error)}")
                # Simpler fallback
                parent_id = "gpt"  # Use parent model ID
                model_id = "gpt-3.5-turbo"

                response = await self.client.create_new_chat(
                    access_token,
                    user.bothub_group_id,
                    name,
                    parent_id
                )

                # Then set the model we want
                await self.client.save_chat_settings(
                    access_token,
                    response["id"],
                    model_id,
                    None,  # max_tokens
                    chat.context_remember,
                    chat.system_prompt
                )

            # Update chat data
            chat.bothub_chat_id = response["id"]
            chat.bothub_chat_model = response.get("model_id", model_id)

            # Save system prompt if present
            if chat.system_prompt:
                await self.client.save_system_prompt(
                    access_token,
                    chat.bothub_chat_id,
                    chat.system_prompt
                )

        except Exception as e:
            # Handle errors
            if "404" in str(e) or "500" in str(e):
                # Create new group and try again
                group_response = await self.client.create_new_group(access_token, "Telegram")
                user.bothub_group_id = group_response["id"]

                # Create chat with simpler approach
                name = f"Telegram Chat {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                parent_id = "gpt"
                model_id = "gpt-3.5-turbo"

                response = await self.client.create_new_chat(
                    access_token,
                    user.bothub_group_id,
                    name,
                    parent_id
                )

                chat.bothub_chat_id = response["id"]
                chat.bothub_chat_model = model_id

                await self.client.save_chat_settings(
                    access_token,
                    response["id"],
                    model_id,
                    None,
                    chat.context_remember,
                    chat.system_prompt
                )
            else:
                raise


    async def send_message(self, user: User, chat: Chat, message: str, files: Optional[List[str]] = None) -> Dict[
        str, Any]:
        """
        Отправка сообщения

        Args:
            user: Пользователь
            chat: Чат
            message: Текст сообщения
            files: Список файлов (URL)

        Returns:
            Dict[str, Any]: Ответ от BotHub API
        """
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)

        access_token = await self.get_access_token(user)

        try:
            result = await self.client.send_message(
                access_token,
                chat.bothub_chat_id,
                message,
                files
            )
            return result
        except Exception as e:
            # Если чат не найден, создаем новый и пробуем снова
            if "CHAT_NOT_FOUND" in str(e):
                logger.warning(f"Чат не найден, создаю новый для пользователя {user.id}")
                await self.create_new_chat(user, chat)
                return await self.client.send_message(
                    access_token,
                    chat.bothub_chat_id,
                    message,
                    files
                )
            raise

    async def reset_context(self, user: User, chat: Chat) -> None:
        """
        Сброс контекста чата

        Args:
            user: Пользователь
            chat: Чат
        """
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)
            return

        access_token = await self.get_access_token(user)
        await self.client.reset_context(access_token, chat.bothub_chat_id)

    async def get_web_search(self, user: User, chat: Chat) -> bool:
        """
        Получение статуса веб-поиска для чата

        Args:
            user: Пользователь
            chat: Чат

        Returns:
            bool: Включен ли веб-поиск
        """
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)

        access_token = await self.get_access_token(user)
        return await self.client.get_web_search(access_token, chat.bothub_chat_id)

    async def enable_web_search(self, user: User, chat: Chat, enabled: bool) -> None:
        """
        Включение/выключение веб-поиска

        Args:
            user: Пользователь
            chat: Чат
            enabled: Включить или выключить
        """
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)

        access_token = await self.get_access_token(user)
        await self.client.enable_web_search(access_token, chat.bothub_chat_id, enabled)

    async def save_system_prompt(self, user: User, chat: Chat) -> None:
        """
        Сохранение системного промпта

        Args:
            user: Пользователь
            chat: Чат
        """
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)
            return

        access_token = await self.get_access_token(user)
        await self.client.save_system_prompt(access_token, chat.bothub_chat_id, chat.system_prompt)

    async def generate_telegram_connection_link(self, user: User, settings) -> str:
        """
        Генерация ссылки для подключения Telegram к аккаунту

        Args:
            user: Пользователь
            settings: Настройки приложения

        Returns:
            str: Ссылка для подключения
        """
        access_token = await self.get_access_token(user)
        response = await self.client.generate_telegram_connection_token(access_token)
        token = response.get("telegramConnectionToken", "")

        web_url = settings.BOTHUB_WEB_URL
        return f"{web_url}?telegram-connection-token={token}"

    async def transcribe_voice(self, user: User, chat: Chat, file_path: str) -> str:
        """
        Транскрибирование голосового сообщения

        Args:
            user: Пользователь
            chat: Чат
            file_path: Путь к аудиофайлу

        Returns:
            str: Транскрибированный текст
        """
        # Получаем токен доступа
        access_token = await self.get_access_token(user)

        try:
            # Проверяем существование файла перед отправкой
            import os
            if not os.path.exists(file_path):
                logger.error(f"[TRANSCRIBE] Файл не существует: {file_path}")
                return "Ошибка: файл не найден"

            file_size = os.path.getsize(file_path)
            if file_size < 100:
                logger.error(f"[TRANSCRIBE] Файл слишком маленький ({file_size} байт)")
                return "Ошибка: файл слишком маленький или поврежден"

            logger.info(
                f"[TRANSCRIBE] Отправка голосового сообщения на транскрибацию: {file_path}, размер: {file_size} байт")

            # Пробуем отправить запрос на транскрибацию
            try:
                # Сначала пробуем через специальный эндпоинт Whisper
                result = await self.client.whisper(access_token, file_path)
                logger.info(f"[TRANSCRIBE] Результат транскрибации через Whisper API: {result[:50]}...")
                return result
            except Exception as whisper_error:
                logger.error(f"[TRANSCRIBE] Ошибка при использовании Whisper API: {whisper_error}")

                # Если не удалось через Whisper API, пробуем через обычный чат с вложением аудио
                if not chat.bothub_chat_id:
                    await self.create_new_chat(user, chat)

                logger.info(f"[TRANSCRIBE] Пробуем отправить аудио в чат {chat.bothub_chat_id}")
                result = await self.client.send_message(
                    access_token,
                    chat.bothub_chat_id,
                    "Пожалуйста, транскрибируй это аудио:",
                    files=None,
                    audio_files=[file_path]
                )

                if "response" in result and "content" in result["response"]:
                    content = result["response"]["content"]
                    logger.info(f"[TRANSCRIBE] Результат через чат: {content[:50]}...")
                    return content
                else:
                    logger.error(f"[TRANSCRIBE] Неожиданный формат ответа: {result}")
                    return "Не удалось распознать голосовое сообщение через чат"

        except Exception as e:
            logger.error(f"[TRANSCRIBE] Ошибка при транскрибировании голосового сообщения: {e}", exc_info=True)
            return f"Не удалось распознать голосовое сообщение. Ошибка: {str(e)}"
