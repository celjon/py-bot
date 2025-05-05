# src/lib/clients/bothub_client.py

import aiohttp
import json
import logging
from typing import Dict, Any, Optional, List
from src.config.settings import Settings

logger = logging.getLogger(__name__)


class BothubClient:
    """Клиент для взаимодействия с BotHub API"""

    def __init__(self, settings: Settings):
        self.api_url = settings.BOTHUB_API_URL
        self.secret_key = settings.BOTHUB_SECRET_KEY
        self.request_query = "?request_from=telegram&platform=TELEGRAM"

    async def _make_request(
            self,
            path: str,
            method: str = "GET",
            headers: Dict[str, str] = None,
            data: Dict[str, Any] = None,
            as_json: bool = True,
            timeout: int = 30,
            retry: int = 3
    ) -> Dict[str, Any]:
        """Базовый метод для выполнения запросов к API с поддержкой повторных попыток"""
        url = f"{self.api_url}/api/{path}{self.request_query}"
        default_headers = {"Content-type": "application/json"} if as_json else {}
        headers = {**default_headers, **(headers or {})}

        attempt = 0
        last_error = None

        while attempt < retry:
            try:
                async with aiohttp.ClientSession() as session:
                    if method == "GET":
                        async with session.get(url, headers=headers, timeout=timeout) as response:
                            if response.status >= 400:
                                error_text = await response.text()
                                if response.status == 502:
                                    raise Exception(f"Сервер BotHub временно недоступен (502 Bad Gateway)")
                                raise Exception(f"Error {response.status}: {error_text}")
                            return await response.json()
                    elif method == "POST":
                        async with session.post(
                                url,
                                headers=headers,
                                json=data if as_json else None,
                                data=data if not as_json else None,
                                timeout=timeout
                        ) as response:
                            if response.status >= 400:
                                error_text = await response.text()
                                if response.status == 502:
                                    raise Exception(f"Сервер BotHub временно недоступен (502 Bad Gateway)")
                                raise Exception(f"Error {response.status}: {error_text}")
                            return await response.json()
                    elif method == "PATCH":
                        async with session.patch(
                                url,
                                headers=headers,
                                json=data if as_json else None,
                                timeout=timeout
                        ) as response:
                            if response.status >= 400:
                                error_text = await response.text()
                                if response.status == 502:
                                    raise Exception(f"Сервер BotHub временно недоступен (502 Bad Gateway)")
                                raise Exception(f"Error {response.status}: {error_text}")
                            return await response.json()
                    elif method == "PUT":
                        async with session.put(
                                url,
                                headers=headers,
                                json=data if as_json else None,
                                timeout=timeout
                        ) as response:
                            if response.status >= 400:
                                error_text = await response.text()
                                if response.status == 502:
                                    raise Exception(f"Сервер BotHub временно недоступен (502 Bad Gateway)")
                                raise Exception(f"Error {response.status}: {error_text}")
                            return await response.json()
                    else:
                        raise ValueError(f"Неподдерживаемый метод: {method}")
            except Exception as e:
                last_error = e
                attempt += 1
                if attempt >= retry:
                    logger.error(f"Ошибка при выполнении запроса после {retry} попыток: {str(e)}")
                    raise Exception(f"Ошибка API BotHub: {str(e)}")
                logger.warning(f"Ошибка при выполнении запроса (попытка {attempt}/{retry}): {str(e)}")

        raise last_error  # Этот код не должен выполняться, но на всякий случай

    async def authorize(
            self,
            tg_id: Optional[str],
            name: str,
            id_: Optional[str] = None,
            invited_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Авторизация пользователя"""
        data = {"name": name}
        if tg_id:
            data["tg_id"] = tg_id
        if id_:
            data["id"] = id_
        if invited_by:
            data["invitedBy"] = invited_by

        headers = {"botsecretkey": self.secret_key}

        try:
            return await self._make_request("v2/auth/telegram", "POST", headers, data)
        except Exception as e:
            logger.error(f"Ошибка авторизации: {str(e)}")
            logger.error(f"Данные запроса: {data}")
            logger.error(f"Заголовки: {headers}")
            raise Exception(f"Ошибка авторизации BotHub: {str(e)}")

    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Получение информации о пользователе"""
        headers = {"Authorization": f"Bearer {access_token}"}
        return await self._make_request("v2/auth/me", "GET", headers)

    async def create_new_group(self, access_token: str, name: str) -> Dict[str, Any]:
        """Создание новой группы"""
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {"name": name}
        return await self._make_request("v2/group", "POST", headers, data)

    async def create_new_chat(
            self, access_token: str, group_id: str, name: str, model_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Создание нового чата"""
        data = {"name": name}
        if group_id:
            data["groupId"] = group_id
        if model_id:
            data["modelId"] = model_id

        logger.info(f"Создание чата с данными: {data}")

        headers = {"Authorization": f"Bearer {access_token}"}
        return await self._make_request("v2/chat", "POST", headers, data)

    async def list_models(self, access_token: str) -> List[Dict[str, Any]]:
        """Получение списка моделей"""
        headers = {"Authorization": f"Bearer {access_token}"}
        return await self._make_request("v2/model/list", "GET", headers)

    async def generate_telegram_connection_token(self, access_token: str) -> Dict[str, Any]:
        """Генерация токена подключения Telegram к аккаунту"""
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            return await self._make_request("v2/auth/telegram-connection-token", "GET", headers)
        except Exception as e:
            logger.error(f"Ошибка при генерации токена подключения: {str(e)}")
            raise Exception(f"Не удалось создать токен подключения: {str(e)}")

    async def save_chat_settings(
            self,
            access_token: str,
            chat_id: str,
            model: str,
            max_tokens: Optional[int] = None,
            include_context: bool = True,
            system_prompt: str = "",
            temperature: float = 0.7,
            top_p: float = 1.0,
            presence_penalty: float = 0.0,
            frequency_penalty: float = 0.0
    ) -> Dict[str, Any]:
        """Сохранение настроек чата"""
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {
            "model": model,
            "include_context": include_context,
            "temperature": temperature,
            "top_p": top_p,
            "system_prompt": system_prompt,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty,
        }

        if max_tokens:
            data["max_tokens"] = max_tokens

        return await self._make_request(f"v2/chat/{chat_id}/settings", "PATCH", headers, data)

    async def reset_context(self, access_token: str, chat_id: str) -> Dict[str, Any]:
        """Сброс контекста чата"""
        headers = {"Authorization": f"Bearer {access_token}"}
        return await self._make_request(f"v2/chat/{chat_id}/clear-context", "PUT", headers)

    async def send_message(
            self,
            access_token: str,
            chat_id: str,
            message: str,
            files: List[Any] = None
    ) -> Dict[str, Any]:
        """Отправка сообщения"""
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {
            "chatId": chat_id,
            "message": message,
            "stream": False
        }

        try:
            response = await self._make_request("v2/message/send", "POST", headers, data, timeout=60)

            result = {}

            # Обрабатываем структуру ответа
            if "content" in response:
                result["response"] = {"content": response["content"]}
            else:
                result["response"] = {"content": "Извините, не удалось получить ответ от сервера"}

            # Обрабатываем вложения
            if "images" in response:
                result["response"]["attachments"] = []
                for image in response["images"]:
                    if image.get("original") and image.get("original_id") and image.get("status") == "DONE":
                        attachment = {
                            "file": image["original"],
                            "file_id": image["original_id"],
                            "buttons": image.get("buttons", [])
                        }
                        result["response"]["attachments"].append(attachment)
            elif "attachments" in response:
                result["response"]["attachments"] = response["attachments"]

            # Добавляем токены из транзакции
            if "transaction" in response and "amount" in response["transaction"]:
                result["tokens"] = int(response["transaction"]["amount"])

            return result
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения: {str(e)}")
            return {
                "response": {
                    "content": f"Извините, произошла ошибка при обработке запроса: {str(e)}"
                }
            }