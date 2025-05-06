import logging
from typing import List, Dict, Any, Optional, Tuple
from src.domain.entity.user import User
from src.domain.entity.chat import Chat
from src.adapter.repository.chat_repository import ChatRepository
from src.adapter.gateway.bothub_gateway import BothubGateway

logger = logging.getLogger(__name__)


class ChatService:
    """Сервис для работы с чатами"""

    # Эмодзи-кнопки для стандартных чатов
    CHAT_BUTTONS = {'1️⃣': 1, '2️⃣': 2, '3️⃣': 3, '4️⃣': 4, '📝': 5}

    def __init__(self, repository: ChatRepository, gateway: BothubGateway):
        self.repository = repository
        self.gateway = gateway

    async def get_or_create_chat(self, user: User) -> Chat:
        """
        Получение или создание чата для пользователя

        Args:
            user: Пользователь

        Returns:
            Chat: Чат пользователя
        """
        chat = await self.repository.find_by_user_id_and_chat_index(
            user.id,
            user.current_chat_index
        )

        if not chat:
            chat = Chat(
                id=0,  # Временный ID, будет заменен после сохранения
                user_id=user.id,
                chat_index=user.current_chat_index,
                name=self._get_default_chat_name(user.current_chat_index)
            )

            # Специальная настройка для пятого чата (📝)
            if user.current_chat_index == 5:
                chat.context_remember = False
                chat.system_prompt = "Ты помощник, который помогает писать и редактировать тексты. Пожалуйста, помоги мне написать текст, исправить ошибки и улучшить стиль."

            chat_id = await self.repository.save(chat)
            chat.id = chat_id

        return chat

    def _get_default_chat_name(self, chat_index: int) -> Optional[str]:
        """
        Получить имя для стандартного чата

        Args:
            chat_index: Индекс чата

        Returns:
            Optional[str]: Имя чата или None
        """
        for emoji, index in self.CHAT_BUTTONS.items():
            if index == chat_index:
                return emoji
        return None

    def get_chat_buttons(self, current_chat_index: int) -> List[str]:
        """
        Получить список кнопок чатов с маркером текущего чата

        Args:
            current_chat_index: Текущий индекс чата

        Returns:
            List[str]: Список кнопок чатов
        """
        chat_buttons = []
        for key, value in self.CHAT_BUTTONS.items():
            if value == current_chat_index:
                chat_buttons.append(key + '✅')
            else:
                chat_buttons.append(key)
        return chat_buttons

    async def create_new_chat(self, user: User, name: Optional[str] = None) -> Chat:
        """
        Создание нового пользовательского чата

        Args:
            user: Пользователь
            name: Название чата (опционально)

        Returns:
            Chat: Созданный чат
        """
        # Получаем последний индекс чата
        last_chat_index = await self.repository.get_last_chat_index(user.id)

        # Новый индекс будет на 1 больше последнего
        new_chat_index = last_chat_index + 1

        # Создаем новый чат
        chat = Chat(
            id=0,  # Временный ID, будет заменен после сохранения
            user_id=user.id,
            chat_index=new_chat_index,
            name=name,
            context_remember=True,
            links_parse=False,
            formula_to_image=False,
            answer_to_voice=False
        )

        # Сохраняем в базу данных
        chat_id = await self.repository.save(chat)
        chat.id = chat_id

        # Обновляем текущий индекс чата пользователя
        user.current_chat_index = new_chat_index

        return chat

    async def switch_chat(self, user: User, chat_index: int) -> Optional[Chat]:
        """
        Переключение на другой чат

        Args:
            user: Пользователь
            chat_index: Индекс чата для переключения

        Returns:
            Optional[Chat]: Выбранный чат или None, если чат не существует
        """
        # Проверяем, что чат существует или это стандартный чат (1-5)
        if chat_index <= 5:
            user.current_chat_index = chat_index
            return await self.get_or_create_chat(user)
        else:
            chat = await self.repository.find_by_user_id_and_chat_index(user.id, chat_index)
            if chat:
                user.current_chat_index = chat_index
                return chat
            return None

    async def get_chat_list(self, user: User, page: int = 1, items_per_page: int = 5) -> Tuple[List[Chat], int]:
        """
        Получение списка чатов пользователя с пагинацией

        Args:
            user: Пользователь
            page: Номер страницы
            items_per_page: Количество элементов на странице

        Returns:
            Tuple[List[Chat], int]: Список чатов и общее количество страниц
        """
        chats = await self.repository.get_paginated_chats(user.id, page, items_per_page)
        total_pages = await self.repository.get_total_pages(user.id, items_per_page)

        return chats, total_pages

    def parse_chat_button(self, button_text: str) -> Optional[int]:
        """
        Парсинг текста кнопки чата для получения индекса

        Args:
            button_text: Текст кнопки

        Returns:
            Optional[int]: Индекс чата или None
        """
        # Удаляем маркер выбранного чата, если он есть
        button_text = button_text.replace('✅', '')

        # Проверяем, есть ли такая кнопка в списке стандартных
        return self.CHAT_BUTTONS.get(button_text)

    async def reset_context(self, user: User, chat: Chat) -> None:
        """
        Сброс контекста чата

        Args:
            user: Пользователь
            chat: Чат
        """
        try:
            # Сбрасываем контекст на сервере BotHub
            await self.gateway.reset_context(user, chat)

            # Сбрасываем локальный счетчик контекста
            chat.reset_context_counter()

            # Сохраняем изменения
            await self.repository.update(chat)

            logger.info(f"Контекст сброшен для чата {chat.chat_index} пользователя {user.id}")
        except Exception as e:
            logger.error(f"Ошибка при сбросе контекста: {e}", exc_info=True)
            raise e

    async def update_chat_settings(self, chat: Chat,
                                   context_remember: Optional[bool] = None,
                                   links_parse: Optional[bool] = None,
                                   formula_to_image: Optional[bool] = None,
                                   answer_to_voice: Optional[bool] = None,
                                   name: Optional[str] = None,
                                   system_prompt: Optional[str] = None) -> None:
        """
        Обновление настроек чата

        Args:
            chat: Чат
            context_remember: Запоминать ли контекст
            links_parse: Парсить ли ссылки
            formula_to_image: Конвертировать ли формулы в изображения
            answer_to_voice: Отвечать ли голосом
            name: Имя чата
            system_prompt: Системный промпт
        """
        # Обновляем только те поля, которые не None
        if context_remember is not None:
            chat.context_remember = context_remember
            # Если изменился режим контекста, сбрасываем счетчик
            if not context_remember:
                chat.reset_context_counter()

        if links_parse is not None:
            chat.links_parse = links_parse

        if formula_to_image is not None:
            chat.formula_to_image = formula_to_image

        if answer_to_voice is not None:
            chat.answer_to_voice = answer_to_voice

        if name is not None:
            chat.name = name

        if system_prompt is not None:
            chat.system_prompt = system_prompt

        # Сохраняем изменения
        await self.repository.update(chat)