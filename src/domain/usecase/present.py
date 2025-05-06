from src.domain.entity.user import User
from src.domain.entity.present import Present
from src.adapter.repository.present_repository import PresentRepository
from src.adapter.gateway.bothub_gateway import BothubGateway
from typing import Dict, Any, List, Optional, Tuple
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PresentUseCase:
    """Юзкейс для работы с подарками токенов"""

    def __init__(self, repository: PresentRepository, gateway: BothubGateway, bot=None):
        self.repository = repository
        self.gateway = gateway
        self.bot = bot  # бот для отправки уведомлений

    async def add_present(self, user: User, tokens: int) -> Present:
        """
        Добавление подарка токенов пользователю

        Args:
            user: Пользователь
            tokens: Количество токенов

        Returns:
            Present: Созданный подарок
        """
        logger.info(f"Добавление подарка {tokens} токенов пользователю {user.id}")

        # Создаем новый подарок
        present = Present(
            id=0,  # Временный ID, будет заменен после сохранения
            user_id=user.id,
            tokens=tokens,
            notified=False,
            parsed_at=datetime.now()
        )

        # Сохраняем в базу данных
        present_id = await self.repository.save(present)
        present.id = present_id

        # Если у пользователя есть Telegram ID, отправляем уведомление
        if user.telegram_id and self.bot:
            await self.notify_present(present)

        return present

    async def notify_present(self, present: Present) -> None:
        """
        Отправка уведомления пользователю о подарке токенов

        Args:
            present: Подарок токенов
        """
        if present.notified:
            return

        try:
            # Получаем пользователя
            from src.adapter.repository.user_repository import UserRepository
            user_repository = UserRepository(self.repository.db_path)
            user = await user_repository.find_by_id(present.user_id)

            if not user or not user.telegram_id:
                logger.warning(f"Не удалось отправить уведомление о подарке: пользователь {present.user_id} не найден или не имеет Telegram ID")
                return

            # Отправляем уведомление
            if self.bot:
                await self.bot.send_message(
                    chat_id=user.telegram_id,
                    text=f"🎁 Вам подарили {present.tokens} токенов!",
                    parse_mode="Markdown"
                )

            # Отмечаем подарок как уведомленный
            present.notified = True
            present.notified_at = datetime.now()
            await self.repository.update(present)

            logger.info(f"Отправлено уведомление пользователю {present.user_id} о подарке {present.tokens} токенов")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления о подарке: {e}", exc_info=True)

    async def send_notifications(self, user: User) -> None:
        """
        Отправка всех неотправленных уведомлений о подарках пользователю

        Args:
            user: Пользователь
        """
        if not user.telegram_id or not self.bot:
            return

        # Получаем все неуведомленные подарки пользователя
        presents = await self.repository.find_unnotified_by_user_id(user.id)

        for present in presents:
            await self.notify_present(present)

    async def send_present(self, from_user: User, to_user_id_or_email: str, tokens: int) -> Dict[str, Any]:
        """
        Отправка подарка токенов другому пользователю

        Args:
            from_user: Отправитель
            to_user_id_or_email: ID или email получателя
            tokens: Количество токенов

        Returns:
            Dict[str, Any]: Результат операции
        """
        logger.info(f"Отправка подарка {tokens} токенов от {from_user.id} пользователю {to_user_id_or_email}")

        try:
            # Проверяем, является ли получатель email или username
            import re
            is_email = bool(re.match(r"[^@]+@[^@]+\.[^@]+", to_user_id_or_email))
            is_username = to_user_id_or_email.startswith('@')

            # Получаем токен доступа отправителя
            access_token = await self.gateway.get_access_token(from_user)

            # Отправляем запрос на подарок токенов через BotHub API
            # В реальной имплементации здесь нужно использовать метод API BotHub для отправки подарка
            # Пока просто имитируем успешную отправку

            # Формируем результат
            result = {
                "success": True,
                "from_user_id": from_user.id,
                "to_user": to_user_id_or_email,
                "tokens": tokens,
                "is_email": is_email
            }

            # В реальной имплементации здесь можно создать запись о подарке и в базе данных

            return result
        except Exception as e:
            logger.error(f"Ошибка при отправке подарка: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    async def verify_present_format(self, text: str) -> Tuple[bool, str]:
        """
        Проверка формата получателя подарка

        Args:
            text: Текст (email или username)

        Returns:
            Tuple[bool, str]: Результат проверки и сообщение об ошибке
        """
        import re

        # Проверка на email
        if re.match(r"[^@]+@[^@]+\.[^@]+", text):
            return True, ""

        # Проверка на username
        if text.startswith('@') and len(text) > 1:
            return True, ""

        # Проверка на username без @
        if re.match(r"^[a-zA-Z0-9_]+$", text):
            # Добавляем @ если его нет
            return True, "@" + text if not text.startswith('@') else text

        return False, "Неверный формат. Введите email или username в Telegram (например, @username)."