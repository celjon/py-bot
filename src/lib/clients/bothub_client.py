import aiohttp
import json
from typing import Dict, Any, Optional, List
from src.config.settings import Settings


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
            timeout: int = 10
    ) -> Dict[str, Any]:
        """Базовый метод для выполнения запросов к API"""
        url = f"{self.api_url}/api/{path}{self.request_query}"
        default_headers = {"Content-type": "application/json"} if as_json else {}
        headers = {**default_headers, **(headers or {})}

        async with aiohttp.ClientSession() as session:
            if method == "GET":
                async with session.get(url, headers=headers, timeout=timeout) as response:
                    if response.status >= 400:
                        error_text = await response.text()
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
                        raise Exception(f"Error {response.status}: {error_text}")
                    return await response.json()
            else:
                raise ValueError(f"Unsupported method: {method}")

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
            # Добавим логирование для отладки
            print(f"Authorization error: {str(e)}")
            print(f"Request data: {data}")
            print(f"Headers: {headers}")
            raise Exception(f"BotHub авторизация не удалась. Проверьте BOTHUB_SECRET_KEY. Ошибка: {str(e)}")

    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Получение информации о пользователе"""
        headers = {"Authorization": f"Bearer {access_token}"}
        return await self._make_request("v2/auth/me", "GET", headers)

    async def create_new_chat(self, access_token: str, group_id: str, name: str, model_id: Optional[str] = None) -> \
    Dict[str, Any]:
        """Создание нового чата"""
        data = {"name": name}
        if group_id:
            data["groupId"] = group_id
        if model_id:
            data["modelId"] = model_id

        print(f"Creating chat with data: {data}")

        headers = {"Authorization": f"Bearer {access_token}"}
        return await self._make_request("v2/chat", "POST", headers, data)

    async def get_web_search(self, access_token: str, chat_id: str) -> bool:
        """Проверка статуса веб-поиска"""
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            response = await self._make_request(f"v2/chat/{chat_id}/settings", "GET", headers)
            return response.get("text", {}).get("enable_web_search", False)
        except Exception:
            return False

    async def enable_web_search(
            self,
            access_token: str,
            chat_id: str,
            value: bool
    ) -> Dict[str, Any]:
        """Включение/выключение веб-поиска"""
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {"enable_web_search": value}
        return await self._make_request(f"v2/chat/{chat_id}/settings", "PATCH", headers, data)

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

        # TODO: Реализовать загрузку файлов

        return await self._make_request("v2/message/send", "POST", headers, data)

    # Добавьте другие методы по мере необходимости
    async def list_models(self, access_token: str) -> Dict[str, Any]:
        """Получение списка доступных моделей"""
        headers = {"Authorization": f"Bearer {access_token}"}
        models = await self._make_request("v2/model/list", "GET", headers)
        print(f"Available models: {[model.get('id') for model in models]}")
        return models

    async def create_new_group(self, access_token: str, name: str) -> Dict[str, Any]:
        """Создание новой группы"""
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {"name": name}
        return await self._make_request("v2/group", "POST", headers, data)

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

    async def update_chat_model(self, access_token: str, chat_id: str, model_id: str) -> Dict[str, Any]:
        """Обновление модели чата"""
        headers = {"Authorization": f"Bearer {access_token}"}
        data = {"modelId": model_id}
        return await self._make_request(f"v2/chat/{chat_id}", "PATCH", headers, data)