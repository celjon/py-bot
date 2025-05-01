from typing import Dict, Any, Optional, List
from src.lib.clients.bothub_client import BothubClient
from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from datetime import datetime


class BothubGateway:
    """Адаптер для взаимодействия с BotHub API"""

    def __init__(self, bothub_client: BothubClient):
        self.client = bothub_client

    async def get_access_token(self, user: User) -> str:
        """Получение/обновление токена доступа"""
        if user.bothub_access_token:
            # TODO: проверка срока действия токена
            return user.bothub_access_token

        response = await self.client.authorize(
            user.telegram_id,
            user.first_name or user.username or "Telegram User"
        )

        # Обновляем информацию о пользователе
        user.bothub_access_token = response["accessToken"]
        user.bothub_id = response["user"]["id"]

        # Проверяем наличие групп и чатов у пользователя
        if "groups" in response["user"] and response["user"]["groups"]:
            groups = response["user"]["groups"]
            if groups[0]["chats"]:
                chats = groups[0]["chats"]
                return user.bothub_access_token, groups[0]["id"], chats[0]["id"], chats[0]["settings"]["model"]
            else:
                return user.bothub_access_token, groups[0]["id"], None, None

        return user.bothub_access_token, None, None, None

    async def create_new_chat(self, user: User, chat: Chat) -> None:
        """Создание нового чата"""
        access_token, group_id, _, _ = await self.get_access_token(user)

        # Получаем список доступных моделей
        try:
            models = await self.client.list_models(access_token)
            default_models = [model for model in models if model.get('is_default')]

            if default_models:
                model_id = default_models[0].get('id')
                print(f"Using default model: {model_id}")
            else:
                # Если нет модели по умолчанию, используем первую доступную
                model_id = models[0].get('id') if models else None
                print(f"Using first available model: {model_id}")
        except Exception as e:
            print(f"Error getting models list: {str(e)}")
            # Указываем некоторые распространенные модели
            model_id = "gpt-3.5-turbo"
            print(f"Falling back to hardcoded model: {model_id}")

        response = await self.client.create_new_chat(
            access_token,
            group_id,
            f"Telegram chat {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            model_id
        )

        chat.bothub_chat_id = response["id"]
        chat.bothub_chat_model = response.get("model_id", model_id)

    async def get_web_search(self, user: User, chat: Chat) -> bool:
        """Проверка статуса веб-поиска"""
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)

        access_token, _, _, _ = await self.get_access_token(user)
        return await self.client.get_web_search(access_token, chat.bothub_chat_id)

    async def enable_web_search(self, user: User, chat: Chat, value: bool) -> None:
        """Включение/выключение веб-поиска"""
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)

        access_token, _, _, _ = await self.get_access_token(user)
        await self.client.enable_web_search(access_token, chat.bothub_chat_id, value)

    async def send_message(self, user: User, chat: Chat, message: str, files: List = None) -> Dict[str, Any]:
        """Отправка сообщения"""
        if not chat.bothub_chat_id:
            await self.create_new_chat(user, chat)

        access_token, _, _, _ = await self.get_access_token(user)
        return await self.client.send_message(access_token, chat.bothub_chat_id, message, files)

    # Добавьте другие методы по мере необходимости