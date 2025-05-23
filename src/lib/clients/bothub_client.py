import aiohttp
import json
import logging
import asyncio
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
            retry: int = 1  # Убираем автоматические повторы
    ) -> Dict[str, Any]:
        """Базовый метод для выполнения запросов к API"""
        url = f"{self.api_url}/api/{path}{self.request_query}"
        default_headers = {"Content-type": "application/json"} if as_json else {}
        headers = {**default_headers, **(headers or {})}

        try:
            async with aiohttp.ClientSession() as session:
                if method == "GET":
                    if data:
                        # Добавляем query параметры к URL
                        query_params = "&".join([f"{k}={v}" for k, v in data.items()])
                        url = f"{url}&{query_params}"

                    async with session.get(url, headers=headers, timeout=timeout) as response:
                        if response.status >= 400:
                            error_text = await response.text()
                            if response.status == 502:
                                raise Exception(f"Сервер BotHub временно недоступен (502 Bad Gateway)")
                            raise Exception(f"Error {response.status}: {error_text}")
                        return await response.json()

                elif method == "POST":
                    # Для multipart данных не используем JSON
                    if not as_json:
                        # Для файлов используем FormData
                        form_data = aiohttp.FormData()
                        for key, value in data.items():
                            form_data.add_field(key, value)

                        async with session.post(url, headers={h: v for h, v in headers.items() if
                                                              'content-type' not in h.lower()}, data=form_data,
                                                timeout=timeout) as response:
                            if response.status >= 400:
                                error_text = await response.text()
                                if response.status == 502:
                                    raise Exception(f"Сервер BotHub временно недоступен (502 Bad Gateway)")
                                raise Exception(f"Error {response.status}: {error_text}")
                            return await response.json()
                    else:
                        async with session.post(url, headers=headers, json=data, timeout=timeout) as response:
                            if response.status >= 400:
                                error_text = await response.text()
                                if response.status == 502:
                                    raise Exception(f"Сервер BotHub временно недоступен (502 Bad Gateway)")
                                raise Exception(f"Error {response.status}: {error_text}")
                            return await response.json()

                elif method == "PATCH":
                    async with session.patch(url, headers=headers, json=data, timeout=timeout) as response:
                        if response.status >= 400:
                            error_text = await response.text()
                            if response.status == 502:
                                raise Exception(f"Сервер BotHub временно недоступен (502 Bad Gateway)")
                            raise Exception(f"Error {response.status}: {error_text}")
                        return await response.json()

                elif method == "PUT":
                    async with session.put(url, headers=headers, json=data, timeout=timeout) as response:
                        if response.status >= 400:
                            error_text = await response.text()
                            if response.status == 502:
                                raise Exception(f"Сервер BotHub временно недоступен (502 Bad Gateway)")
                            raise Exception(f"Error {response.status}: {error_text}")
                        return await response.json()
                else:
                    raise ValueError(f"Неподдерживаемый метод: {method}")

        except Exception as e:
            logger.error(f"Ошибка при выполнении запроса: {str(e)}")
            raise Exception(f"Ошибка API BotHub: {str(e)}")

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

        headers = {"Authorization": f"Bearer {access_token}"}
        response = await self._make_request("v2/chat", "POST", headers, data)
        return response

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
        """Получение статуса веб-поиска для чата"""
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
        """Включение/выключение веб-поиска"""
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {"enable_web_search": enabled}
        return await self._make_request(f"v2/chat/{chat_id}/settings", "PATCH", headers, data)

    async def save_model(self, access_token: str, chat_id: str, model: str) -> Dict[str, Any]:
        """Сохранение модели для чата"""
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {"model": model}
        return await self._make_request(f"v2/chat/{chat_id}/settings", "PATCH", headers, data)

    async def update_parent_model(self, access_token: str, chat_id: str, parent_model_id: str) -> Dict[str, Any]:
        """Обновление родительской модели чата"""
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {"modelId": parent_model_id}
        return await self._make_request(f"v2/chat/{chat_id}", "PATCH", headers, data)

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

        # Добавляем файлы если они есть
        if files:
            for i, file in enumerate(files):
                if file:  # Проверяем что файл не None
                    data[f"files[{i}]"] = file

        try:
            response = await self._make_request("v2/message/send", "POST", headers, data,
                                                as_json=not bool(files), timeout=60)

            # Обрабатываем ответ по аналогии с PHP
            result = {"response": {}}

            if response.get("content"):
                result["response"]["content"] = response["content"]

            # Обработка изображений (как в PHP)
            if response.get("images"):
                result["response"]["attachments"] = []
                for image in response["images"]:
                    if (image.get("original") and image.get("original_id") and
                            image.get("status") == "DONE"):
                        attachment = {
                            "file": image["original"],
                            "file_id": image["original_id"],
                            "buttons": image.get("buttons", [])
                        }
                        result["response"]["attachments"].append(attachment)
            elif response.get("attachments"):
                result["response"]["attachments"] = response["attachments"]

            # Обработка токенов
            if response.get("transaction", {}).get("amount"):
                result["tokens"] = int(response["transaction"]["amount"])

            # Обработка ошибок
            error = response.get("job", {}).get("error")
            if error:
                if "MIDJOURNEY_ERROR" in error:
                    raise Exception(error.replace("Error (MIDJOURNEY_ERROR): ", ""))
                raise Exception(error)

            return result

        except Exception as e:
            error_message = str(e)

            if "FLOOD_ERROR" in error_message:
                import re
                timeout_match = re.search(r'(\d+\.?\d*)\s*seconds', error_message)
                wait_time = int(float(timeout_match.group(1))) if timeout_match else 60

                return {
                    "response": {
                        "content": f"Слишком много запросов. Пожалуйста, подождите {wait_time} секунд и попробуйте снова."
                    },
                    "error": "FLOOD_ERROR",
                    "wait_time": wait_time
                }
            elif "NOT_ENOUGH_TOKENS" in error_message:
                return {
                    "response": {
                        "content": "Недостаточно токенов для выполнения запроса. Пожалуйста, пополните баланс или привяжите аккаунт с достаточным количеством токенов."
                    },
                    "error": "NOT_ENOUGH_TOKENS"
                }
            else:
                return {
                    "response": {
                        "content": f"Извините, произошла ошибка при обработке запроса: {str(e)}"
                    },
                    "error": "GENERAL_ERROR"
                }

    async def save_system_prompt(self, access_token: str, chat_id: str, system_prompt: str) -> Dict[str, Any]:
        """Сохранение системного промпта для чата"""
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {"system_prompt": system_prompt}

        try:
            return await self._make_request(f"v2/chat/{chat_id}/settings", "PATCH", headers, data)
        except Exception as e:
            logger.error(f"Ошибка при сохранении системного промпта: {str(e)}")
            raise Exception(f"Не удалось сохранить системный промпт: {str(e)}")

    async def whisper(self, access_token: str, file_path: str, method: str = "transcriptions") -> str:
        """Транскрибирование голосового сообщения через BotHub API"""
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            # Подготавливаем данные для отправки файла
            data = {
                'model': 'whisper-1'
            }

            # Читаем файл
            with open(file_path, 'rb') as f:
                file_data = f.read()

            # Отправляем как multipart/form-data
            form_data = aiohttp.FormData()
            form_data.add_field('model', 'whisper-1')
            form_data.add_field('file', file_data, filename=file_path)

            # Отправляем запрос
            url = f"{self.api_url}/api/v2/openai/v1/audio/{method}{self.request_query}"
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=form_data) as response:
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

    # Остальные методы остаются без изменений
    async def create_referral_program(self, access_token: str, template_id: str) -> Dict[str, Any]:
        """Создание реферальной программы"""
        headers = {"Authorization": f"Bearer {access_token}"}
        return await self._make_request("v2/referral", "POST", headers, {"templateId": template_id})

    async def list_plans(self) -> List[Dict[str, Any]]:
        """Получение списка планов"""
        return await self._make_request("v2/plan/list", "GET")

    async def buy_plan(
            self,
            access_token: str,
            plan_id: str,
            provider: str,
            present_email: Optional[str] = None,
            present_user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Покупка плана"""
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {"provider": provider}
        if present_email:
            data["presentEmail"] = present_email
        elif present_user_id:
            data["presentUserId"] = present_user_id
        return await self._make_request(f"v2/plan/{plan_id}/buy", "POST", headers, data)