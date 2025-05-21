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
        try:
            response = await self._make_request("v2/model/list", "GET", headers)
            return response
        except Exception as e:
            logger.error(f"Ошибка при получении списка моделей: {str(e)}")
            return []

    async def generate_telegram_connection_token(self, access_token: str) -> Dict[str, Any]:
        """Генерация токена подключения Telegram к аккаунту для Python-бота"""
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            # Используем правильный эндпоинт для Python-бота
            response = await self._make_request("v2/auth/telegram-connection-token-python", "GET", headers)

            # Логируем полный ответ для отладки
            logger.info(f"Ответ сервера на запрос токена подключения: {response}")

            # Проверяем различные возможные форматы ответа
            if "telegramConnectionToken" in response:
                token = response["telegramConnectionToken"]
                logger.info(f"Найден токен в поле 'telegramConnectionToken': {token[:50] if token else 'ПУСТОЙ'}...")
                return response
            elif "token" in response:
                # Возможно токен в поле 'token'
                token = response["token"]
                logger.info(f"Найден токен в поле 'token': {token[:50] if token else 'ПУСТОЙ'}...")
                # Нормализуем ответ
                return {"telegramConnectionToken": token}
            elif "data" in response and isinstance(response["data"], dict):
                # Возможно токен в поле data
                data = response["data"]
                if "telegramConnectionToken" in data:
                    token = data["telegramConnectionToken"]
                    logger.info(f"Найден токен в data.telegramConnectionToken: {token[:50] if token else 'ПУСТОЙ'}...")
                    return {"telegramConnectionToken": token}
                elif "token" in data:
                    token = data["token"]
                    logger.info(f"Найден токен в data.token: {token[:50] if token else 'ПУСТОЙ'}...")
                    return {"telegramConnectionToken": token}

            # Если токен не найден, логируем проблему
            logger.error(f"Токен подключения не найден в ответе сервера: {response}")

            return response
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

    async def get_web_search(self, access_token: str, chat_id: str) -> bool:
        """
        Получение статуса веб-поиска для чата

        Args:
            access_token: Токен доступа
            chat_id: ID чата

        Returns:
            bool: Включен ли веб-поиск
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            response = await self._make_request(f"v2/chat/{chat_id}/settings", "GET", headers)
            if "text" not in response:
                return False
            return response["text"].get("enable_web_search", False)
        except Exception as e:
            logger.error(f"Ошибка при получении статуса веб-поиска: {str(e)}")
            return False

    async def enable_web_search(self, access_token: str, chat_id: str, enabled: bool) -> Dict[str, Any]:
        """
        Включение/выключение веб-поиска

        Args:
            access_token: Токен доступа
            chat_id: ID чата
            enabled: Включить или выключить

        Returns:
            Dict[str, Any]: Ответ от API
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {"enable_web_search": enabled}
        return await self._make_request(f"v2/chat/{chat_id}/settings", "PATCH", headers, data)

    async def send_message(
            self,
            access_token: str,
            chat_id: str,
            message: str,
            files: List[str] = None
    ) -> Dict[str, Any]:
        """Отправка сообщения в BotHub API"""
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {
            "chatId": chat_id,
            "message": message,
            "stream": False
        }

        logger.info(f"📨 Отправка сообщения: '{message[:50]}...' в чат {chat_id}")

        try:
            response = await self._make_request("v2/message/send", "POST", headers, data, timeout=60)
            logger.info(f"📨 Получен ответ от сервера для сообщения")

            # Детальное логирование ответа в зависимости от его содержимого
            if "content" in response:
                logger.info(f"📨 Ответ содержит контент: '{response['content'][:50]}...'")

            if "images" in response and response["images"]:
                logger.info(f"📨 Ответ содержит {len(response['images'])} изображений")
                for i, img in enumerate(response["images"]):
                    status = img.get("status", "UNKNOWN")
                    img_id = img.get("original_id", "NO_ID")
                    logger.info(f"📨 Изображение {i + 1}: статус={status}, ID={img_id}")

            if "attachments" in response:
                logger.info(f"📨 Ответ содержит {len(response['attachments'])} вложений")

            if "transaction" in response and "amount" in response["transaction"]:
                logger.info(f"📨 Ответ содержит информацию о токенах: {response['transaction']['amount']}")

            result = {"response": {}}

            # Обрабатываем контент
            if "content" in response:
                result["response"]["content"] = response["content"]
            else:
                result["response"]["content"] = "Извините, не удалось получить ответ от сервера"

            # Обрабатываем вложения
            if "images" in response and response["images"]:
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
            logger.error(f"📨 Ошибка при отправке сообщения: {str(e)}")

            # Улучшенное логирование ошибок
            error_message = str(e)
            if "NOT_ENOUGH_TOKENS" in error_message:
                logger.error(f"📨 Недостаточно токенов для запроса")
                return {
                    "response": {
                        "content": "Недостаточно токенов для выполнения запроса. Пожалуйста, пополните баланс или привяжите аккаунт с достаточным количеством токенов."
                    },
                    "error": "NOT_ENOUGH_TOKENS"
                }
            elif "MODEL_NOT_FOUND" in error_message:
                logger.error(f"📨 Модель не найдена")
                return {
                    "response": {
                        "content": "Выбранная модель недоступна. Пожалуйста, выберите другую модель."
                    },
                    "error": "MODEL_NOT_FOUND"
                }
            else:
                logger.error(f"📨 Общая ошибка: {error_message}")
                return {
                    "response": {
                        "content": f"Извините, произошла ошибка при обработке запроса: {str(e)}"
                    },
                    "error": "GENERAL_ERROR"
                }

    async def save_system_prompt(self, access_token: str, chat_id: str, system_prompt: str) -> Dict[str, Any]:
        """
        Сохранение системного промпта для чата

        Args:
            access_token: Токен доступа
            chat_id: ID чата
            system_prompt: Текст системного промпта

        Returns:
            Dict[str, Any]: Ответ от API
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {"system_prompt": system_prompt}

        try:
            return await self._make_request(f"v2/chat/{chat_id}/settings", "PATCH", headers, data)
        except Exception as e:
            logger.error(f"Ошибка при сохранении системного промпта: {str(e)}")
            raise Exception(f"Не удалось сохранить системный промпт: {str(e)}")

    async def create_referral_program(self, access_token: str, template_id: str) -> Dict[str, Any]:
        """Создание реферальной программы"""
        headers = {"Authorization": f"Bearer {access_token}"}
        return await self._make_request("v2/referral", "POST", headers, {"templateId": template_id})

    async def update_parent_model(self, access_token: str, chat_id: str, parent_model_id: str) -> Dict[str, Any]:
        """Обновление родительской модели чата"""
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {"parentModelId": parent_model_id}

        return await self._make_request(f"v2/chat/{chat_id}/parent-model", "PATCH", headers, data)

    async def save_model(self, access_token: str, chat_id: str, model_id: str) -> Dict[str, Any]:
        """Сохранение модели для чата"""
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {"model": model_id}

        return await self._make_request(f"v2/chat/{chat_id}/settings", "PATCH", headers, data)

    async def whisper(self, access_token: str, file_path: str, method: str = "transcriptions") -> str:
        """
        Транскрибирование голосового сообщения через BotHub API

        Args:
            access_token: Токен доступа
            file_path: Путь к аудиофайлу
            method: Метод транскрибирования ('transcriptions' или 'translations')

        Returns:
            str: Транскрибированный текст
        """
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            # Создаем форму для отправки файла
            form = aiohttp.FormData()
            form.add_field('model', 'whisper-1')
            form.add_field('file', open(file_path, 'rb'))

            # Отправляем запрос
            async with aiohttp.ClientSession() as session:
                async with session.post(
                        f"{self.api_url}/api/v2/openai/v1/audio/{method}{self.request_query}",
                        headers=headers,
                        data=form
                ) as response:
                    if response.status >= 400:
                        error_text = await response.text()
                        raise Exception(f"Ошибка при транскрибировании: HTTP {response.status}, {error_text}")

                    result = await response.json()

                    if "text" not in result:
                        raise Exception("Ошибка при получении текста из аудио")

                    return result["text"]
        except Exception as e:
            logger.error(f"Ошибка при транскрибировании аудио: {e}", exc_info=True)
            raise Exception(f"Не удалось транскрибировать аудио: {str(e)}")