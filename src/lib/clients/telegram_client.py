# src/lib/clients/telegram_client.py
import logging
import aiohttp
import json
from typing import Dict, Any, Optional, Union, List

logger = logging.getLogger(__name__)


class TelegramClient:
    """Клиент для работы с Telegram Bot API"""

    def __init__(self, token: str, api_url: Optional[str] = None):
        """
        Инициализация клиента

        Args:
            token: Токен бота
            api_url: URL Telegram Bot API (опционально)
        """
        self.token = token
        self.api_url = api_url or "https://api.telegram.org"
        self.base_url = f"{self.api_url}/bot{self.token}"

    async def send_message(
            self,
            chat_id: Union[int, str],
            text: str,
            parse_mode: str = "Markdown",
            reply_markup: Optional[Any] = None,
            disable_web_page_preview: bool = False
    ) -> Dict[str, Any]:
        """
        Отправка сообщения

        Args:
            chat_id: ID чата
            text: Текст сообщения
            parse_mode: Режим разметки
            reply_markup: Клавиатура
            disable_web_page_preview: Отключить предпросмотр ссылок

        Returns:
            Dict[str, Any]: Ответ от Telegram API
        """
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview
        }

        # Преобразуем клавиатуру в словарь, если она объект aiogram
        if reply_markup:
            if hasattr(reply_markup, "model_dump"):
                # Для Pydantic моделей (aiogram >= 3.x)
                data["reply_markup"] = reply_markup.model_dump()
            elif hasattr(reply_markup, "to_json"):
                # Для aiogram 2.x
                data["reply_markup"] = json.loads(reply_markup.to_json())
            elif hasattr(reply_markup, "to_dict"):
                # Альтернативный метод
                data["reply_markup"] = reply_markup.to_dict()
            else:
                # Если это уже словарь
                data["reply_markup"] = reply_markup

        return await self._make_request("sendMessage", data)

    async def send_photo(
            self,
            chat_id: Union[int, str],
            photo: str,
            caption: Optional[str] = None,
            parse_mode: str = "Markdown",
            reply_markup: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Отправка изображения

        Args:
            chat_id: ID чата
            photo: URL или file_id изображения
            caption: Подпись к изображению
            parse_mode: Режим разметки
            reply_markup: Клавиатура

        Returns:
            Dict[str, Any]: Ответ от Telegram API
        """
        data = {
            "chat_id": chat_id,
            "photo": photo,
            "parse_mode": parse_mode
        }

        if caption:
            data["caption"] = caption

        if reply_markup:
            # Преобразуем клавиатуру в словарь, если она объект aiogram
            if hasattr(reply_markup, "model_dump"):
                # Для Pydantic моделей (aiogram >= 3.x)
                data["reply_markup"] = reply_markup.model_dump()
            elif hasattr(reply_markup, "to_json"):
                # Для aiogram 2.x
                data["reply_markup"] = json.loads(reply_markup.to_json())
            elif hasattr(reply_markup, "to_dict"):
                # Альтернативный метод
                data["reply_markup"] = reply_markup.to_dict()
            else:
                # Если это уже словарь
                data["reply_markup"] = reply_markup

        return await self._make_request("sendPhoto", data)

    async def _make_request(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Выполнение запроса к Telegram API

        Args:
            method: Метод API
            data: Данные запроса

        Returns:
            Dict[str, Any]: Ответ от Telegram API
        """
        url = f"{self.base_url}/{method}"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                result = await response.json()

                if not result.get("ok"):
                    logger.error(f"Telegram API error: {result}")
                    error_code = result.get("error_code", 0)
                    error_description = result.get("description", "Unknown error")
                    raise Exception(f"Telegram API error {error_code}: {error_description}")

                return result.get("result", {})