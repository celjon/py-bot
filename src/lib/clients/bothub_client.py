import json
import logging
import asyncio
import aiohttp
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)


class BothubClient:
    """Клиент для взаимодействия с API BotHub"""

    def __init__(self, settings):
        """
        Инициализация клиента BotHub

        Args:
            settings: Настройки приложения
        """
        self.api_url = settings.BOTHUB_API_URL

        # Удаляем префикс '=' если он есть
        if self.api_url and self.api_url.startswith('='):
            self.api_url = self.api_url[1:]

        # Удаляем слеш в конце URL, если он есть
        if self.api_url and self.api_url.endswith('/'):
            self.api_url = self.api_url[:-1]

        logger.info(f"BothubClient инициализирован с URL: {self.api_url}")

        self.secret_key = settings.BOTHUB_SECRET_KEY
        self.request_query = "?request_from=telegram&platform=TELEGRAM"

    async def _make_request(
            self,
            path: str,
            method: str = "GET",
            headers: Dict[str, str] = None,
            data: Dict[str, Any] = None,
            as_json: bool = True,
            multipart: bool = False,
            timeout: int = 30,
            retry: int = 3
    ) -> Dict[str, Any]:
        """
        Выполняет HTTP-запрос к API BotHub

        Args:
            path: Путь к API-эндпоинту
            method: HTTP-метод (GET, POST, PATCH, PUT)
            headers: Заголовки запроса
            data: Данные запроса
            as_json: Отправлять ли данные как JSON
            multipart: Отправлять ли данные как multipart/form-data
            timeout: Тайм-аут запроса в секундах
            retry: Количество повторных попыток

        Returns:
            Dict[str, Any]: Ответ от API

        Raises:
            Exception: При ошибке выполнения запроса
        """
        if not self.api_url:
            raise Exception("URL API не указан. Проверьте настройку BOTHUB_API_URL в .env")

        # Формируем путь к API - удаляем префикс v2/ если он есть
        if path.startswith("v2/"):
            path = path[3:]

        # Формируем URL в стиле PHP-версии
        url = f"{self.api_url}/api/v2/{path}{self.request_query}"

        # Настраиваем заголовки
        default_headers = {}
        if as_json and method != "GET":
            default_headers["Content-type"] = "application/json"
        elif multipart and method != "GET":
            default_headers["Content-type"] = "multipart/form-data"

        merged_headers = {**default_headers, **(headers or {})}

        # Для GET-запросов добавляем параметры к URL
        request_url = url
        if method == "GET" and data:
            for key, value in data.items():
                request_url += f"&{key}={value}"

        logger.info(f"Выполнение запроса {method} {request_url}")
        if data:
            logger.info(f"Данные запроса: {data}")
        logger.info(f"Заголовки: {merged_headers}")

        attempt = 0
        last_error = None

        while attempt < retry:
            try:
                async with aiohttp.ClientSession() as session:
                    if method == "GET":
                        response = await session.get(request_url, headers=merged_headers, timeout=timeout)
                    elif method == "POST":
                        response = await session.post(
                            url,
                            headers=merged_headers,
                            json=data if as_json else None,
                            data=data if not as_json else None,
                            timeout=timeout
                        )
                    elif method == "PATCH":
                        response = await session.patch(
                            url,
                            headers=merged_headers,
                            json=data if as_json else None,
                            data=data if not as_json else None,
                            timeout=timeout
                        )
                    elif method == "PUT":
                        response = await session.put(
                            url,
                            headers=merged_headers,
                            json=data if as_json else None,
                            data=data if not as_json else None,
                            timeout=timeout
                        )
                    else:
                        raise ValueError(f"Неподдерживаемый HTTP-метод: {method}")

                    # Обработка ответа
                    status = response.status
                    body = await response.text()

                    try:
                        result = json.loads(body) if body else {}
                    except json.JSONDecodeError:
                        logger.error(f"Не удалось декодировать JSON: {body}")
                        result = {}

                    if not isinstance(result, dict):
                        result = {}

                    # Обработка ошибок
                    if status >= 300:
                        if not isinstance(result, dict) or "errors" in result:
                            error_msg = f"Неверный ответ от BotHub API: {body}"
                            logger.error(error_msg)
                            raise Exception(f"Error {status}: {error_msg}")

                    if isinstance(result, dict) and "error" in result:
                        if isinstance(result["error"], dict):
                            message_txt = result["error"].get("code") or result["error"].get("message") or str(
                                result["error"])
                        else:
                            message_txt = str(result["error"])

                        logger.error(f"API вернуло ошибку: {message_txt}, статус: {status}")
                        raise Exception(f"Error {status}: {message_txt}")

                    return result

            except aiohttp.ClientError as e:
                last_error = e
                attempt += 1
                if attempt >= retry:
                    logger.error(f"Ошибка при выполнении запроса после {retry} попыток: {str(e)}")
                    raise Exception(f"Ошибка клиента HTTP: {str(e)}")
                logger.warning(f"Ошибка при выполнении запроса (попытка {attempt}/{retry}): {str(e)}")
                await asyncio.sleep(1)  # Пауза перед повторной попыткой

            except Exception as e:
                last_error = e
                attempt += 1
                if attempt >= retry:
                    logger.error(f"Ошибка при выполнении запроса после {retry} попыток: {str(e)}")
                    raise Exception(f"Ошибка API BotHub: {str(e)}")
                logger.warning(f"Ошибка при выполнении запроса (попытка {attempt}/{retry}): {str(e)}")
                await asyncio.sleep(1)  # Пауза перед повторной попыткой

        # Этот код не должен выполняться, но на всякий случай
        if last_error:
            raise last_error
        else:
            raise Exception("Не удалось выполнить запрос к API после нескольких попыток")

    async def authorize(
            self,
            tg_id: Optional[str],
            name: str,
            id_: Optional[str] = None,
            invited_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Авторизация пользователя в BotHub

        Args:
            tg_id: ID пользователя в Telegram
            name: Имя пользователя
            id_: ID пользователя в BotHub
            invited_by: Реферальный код

        Returns:
            Dict[str, Any]: Информация о пользователе
        """
        data = {"name": name}
        if tg_id:
            data["tg_id"] = tg_id
        if id_:
            data["id"] = id_
        if invited_by:
            data["invitedBy"] = invited_by

        headers = {"botsecretkey": self.secret_key}

        try:
            return await self._make_request("auth/telegram", "POST", headers, data)
        except Exception as e:
            logger.error(f"Ошибка авторизации: {str(e)}")
            logger.error(f"Данные запроса: {data}")
            logger.error(f"Заголовки: {headers}")
            raise Exception(f"Ошибка авторизации BotHub: {str(e)}")

    # Далее идут методы для конкретных эндпоинтов API
    # Пример:
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Получение информации о пользователе

        Args:
            access_token: Токен доступа

        Returns:
            Dict[str, Any]: Информация о пользователе
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        return await self._make_request("auth/me", "GET", headers)

    async def create_new_group(self, access_token: str, name: str) -> Dict[str, Any]:
        """
        Создание новой группы

        Args:
            access_token: Токен доступа
            name: Название группы

        Returns:
            Dict[str, Any]: Информация о созданной группе
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {"name": name}
        return await self._make_request("group", "POST", headers, data)

    async def create_new_chat(
            self,
            access_token: str,
            group_id: str,
            name: str,
            model_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Создание нового чата

        Args:
            access_token: Токен доступа
            group_id: ID группы
            name: Название чата
            model_id: ID модели

        Returns:
            Dict[str, Any]: Информация о созданном чате
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {"name": name, "groupId": group_id}
        if model_id:
            data["modelId"] = model_id

        return await self._make_request("chat", "POST", headers, data)

    async def list_models(self, access_token: str) -> Any:
        """
        Получение списка доступных моделей

        Args:
            access_token: Токен доступа

        Returns:
            List[Dict[str, Any]]: Список моделей
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        return await self._make_request("model/list", "GET", headers)

    async def save_chat_settings(
            self,
            access_token: str,
            chat_id: str,
            model_id: str,
            max_tokens: Optional[int] = None,
            include_context: bool = True,
            system_prompt: str = "",
            temperature: float = 0.7,
            top_p: float = 1.0,
            presence_penalty: float = 0.0,
            frequency_penalty: float = 0.0
    ) -> Dict[str, Any]:
        """
        Сохранение настроек чата

        Args:
            access_token: Токен доступа
            chat_id: ID чата
            model_id: ID модели
            max_tokens: Максимальное количество токенов
            include_context: Включать ли контекст
            system_prompt: Системный промпт
            temperature: Температура
            top_p: Top-p параметр
            presence_penalty: Штраф за повторение
            frequency_penalty: Штраф за частоту

        Returns:
            Dict[str, Any]: Результат операции
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {
            "model": model_id,
            "include_context": include_context,
            "temperature": temperature,
            "top_p": top_p,
            "system_prompt": system_prompt,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty
        }

        if max_tokens:
            data["max_tokens"] = max_tokens

        return await self._make_request(f"chat/{chat_id}/settings", "PATCH", headers, data)

    async def save_system_prompt(
            self,
            access_token: str,
            chat_id: str,
            system_prompt: str
    ) -> Dict[str, Any]:
        """
        Сохранение системного промпта для чата

        Args:
            access_token: Токен доступа
            chat_id: ID чата
            system_prompt: Текст системного промпта

        Returns:
            Dict[str, Any]: Результат операции
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {"system_prompt": system_prompt}

        return await self._make_request(f"chat/{chat_id}/settings", "PATCH", headers, data)

    async def reset_context(self, access_token: str, chat_id: str) -> Dict[str, Any]:
        """
        Сброс контекста чата

        Args:
            access_token: Токен доступа
            chat_id: ID чата

        Returns:
            Dict[str, Any]: Результат операции
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        return await self._make_request(f"chat/{chat_id}/clear-context", "PUT", headers)

    async def send_message(
            self,
            access_token: str,
            chat_id: str,
            message: str,
            files: Optional[List[str]] = None,
            audio_files: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Отправка сообщения в чат

        Args:
            access_token: Токен доступа
            chat_id: ID чата
            message: Текст сообщения
            files: Список файлов
            audio_files: Список аудио-файлов

        Returns:
            Dict[str, Any]: Ответ от API с ответом модели
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {
            "chatId": chat_id,
            "message": message,
            "stream": False
        }

        # Если есть файлы, здесь должен быть код для их отправки
        # Для полноценной отправки файлов нужен более сложный код с multipart/form-data
        # Это можно будет дополнить, когда будет предоставлен PHP-код

        return await self._make_request("message/send", "POST", headers, data)

    async def get_web_search(self, access_token: str, chat_id: str) -> bool:
        """
        Проверка, включен ли веб-поиск для чата

        Args:
            access_token: Токен доступа
            chat_id: ID чата

        Returns:
            bool: Включен ли веб-поиск
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            response = await self._make_request(f"chat/{chat_id}/settings", "GET", headers)
            if "text" not in response:
                return False
            return response["text"].get("enable_web_search", False)
        except Exception as e:
            logger.error(f"Ошибка при получении статуса веб-поиска: {str(e)}")
            return False

    async def enable_web_search(self, access_token: str, chat_id: str, enabled: bool) -> Dict[str, Any]:
        """
        Включение/выключение веб-поиска для чата

        Args:
            access_token: Токен доступа
            chat_id: ID чата
            enabled: Включить или выключить

        Returns:
            Dict[str, Any]: Результат операции
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {"enable_web_search": enabled}
        return await self._make_request(f"chat/{chat_id}/settings", "PATCH", headers, data)

    async def update_parent_model(
            self,
            access_token: str,
            chat_id: str,
            parent_model_id: str
    ) -> Dict[str, Any]:
        """
        Обновление родительской модели чата

        Args:
            access_token: Токен доступа
            chat_id: ID чата
            parent_model_id: ID родительской модели

        Returns:
            Dict[str, Any]: Результат операции
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {"parent_model_id": parent_model_id}
        return await self._make_request(f"chat/{chat_id}/parent-model", "PATCH", headers, data)

    async def save_model(
            self,
            access_token: str,
            chat_id: str,
            model_id: str
    ) -> Dict[str, Any]:
        """
        Сохранение модели для чата

        Args:
            access_token: Токен доступа
            chat_id: ID чата
            model_id: ID модели

        Returns:
            Dict[str, Any]: Результат операции
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {"model_id": model_id}
        return await self._make_request(f"chat/{chat_id}/model", "PATCH", headers, data)

    async def generate_telegram_connection_token(self, access_token: str) -> Dict[str, Any]:
        """
        Генерация токена для подключения Telegram

        Args:
            access_token: Токен доступа

        Returns:
            Dict[str, Any]: Токен подключения
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        return await self._make_request("auth/telegram-connection-token", "GET", headers)

    async def whisper(self, access_token: str, file_path: str, method: str = "transcriptions") -> str:
        """
        Транскрибирование аудио-файла с помощью Whisper API

        Args:
            access_token: Токен доступа
            file_path: Путь к аудио-файлу
            method: Метод транскрибирования ('transcriptions' или 'translations')

        Returns:
            str: Транскрибированный текст
        """
        import os

        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        # Создаем form-data для отправки файла
        form_data = aiohttp.FormData()
        form_data.add_field('model', 'whisper-1')
        form_data.add_field(
            'file',
            open(file_path, 'rb'),
            filename=os.path.basename(file_path),
            content_type='audio/mpeg'
        )

        # Отправляем запрос напрямую с помощью aiohttp
        try:
            url = f"{self.api_url}/api/v2/openai/v1/audio/{method}{self.request_query}"
            logger.info(f"Отправка запроса на транскрибацию: {url}")

            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=form_data) as response:
                    if response.status >= 400:
                        error_text = await response.text()
                        logger.error(f"Ошибка при транскрибировании: HTTP {response.status}, {error_text}")
                        raise Exception(f"Ошибка при транскрибировании: HTTP {response.status}, {error_text}")

                    result = await response.json()

                    if "text" not in result:
                        logger.error(f"В ответе отсутствует текст: {result}")
                        raise Exception("Ошибка при получении текста из аудио")

                    logger.info(f"Транскрибация успешна, получен текст: {result['text'][:50]}...")
                    return result["text"]
        finally:
            # Удаляем файл после использования
            try:
                os.remove(file_path)
                logger.info(f"Временный файл удален: {file_path}")
            except Exception as e:
                logger.warning(f"Не удалось удалить временный файл: {e}")
