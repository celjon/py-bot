from src.domain.entity.user import User
from src.domain.entity.referral import ReferralTemplate, ReferralProgram
from src.adapter.gateway.bothub_gateway import BothubGateway
from src.config.settings import Settings
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class ReferralUseCase:
    """Юзкейс для работы с реферальной системой"""

    def __init__(self, gateway: BothubGateway, settings: Settings):
        self.gateway = gateway
        self.settings = settings

    async def list_referral_templates(self, user: User) -> List[ReferralTemplate]:
        """
        Получение списка доступных шаблонов реферальных программ

        Args:
            user: Пользователь

        Returns:
            List[ReferralTemplate]: Список шаблонов реферальных программ
        """
        logger.info(f"Получение списка шаблонов реферальных программ для пользователя {user.id}")
        try:
            # Получаем токен доступа
            access_token = await self.gateway.get_access_token(user)

            # Используем локаль пользователя или русский по умолчанию
            locale = user.language_code or "ru"

            # Получаем шаблоны через API BotHub
            templates_data = await self.gateway.client.list_referral_templates(access_token, locale)

            # Обрабатываем полученные данные
            templates = []
            for template_data in templates_data.get("data", []):
                template = ReferralTemplate(
                    id=template_data.get("id"),
                    name=template_data.get("name"),
                    currency=template_data.get("currency"),
                    encourage_percentage=template_data.get("encouragement_percentage"),
                    min_withdraw_amount=template_data.get("min_withdraw_amount"),
                    tokens=template_data.get("tokens"),
                    locale=template_data.get("locale", locale),
                    plan=template_data.get("plan"),
                    disabled=template_data.get("disabled", False),
                    private=template_data.get("private", False)
                )
                templates.append(template)

            return templates
        except Exception as e:
            logger.error(f"Ошибка при получении шаблонов реферальных программ: {e}", exc_info=True)
            raise Exception(f"Не удалось получить шаблоны реферальных программ: {e}")

    async def create_referral_program(self, user: User, template_id: str) -> ReferralProgram:
        """
        Создание реферальной программы

        Args:
            user: Пользователь
            template_id: ID шаблона реферальной программы

        Returns:
            ReferralProgram: Созданная реферальная программа
        """
        logger.info(f"Создание реферальной программы для пользователя {user.id} с шаблоном {template_id}")
        try:
            # Получаем токен доступа
            access_token = await self.gateway.get_access_token(user)

            # Создаем реферальную программу через API BotHub
            program_data = await self.gateway.client.create_referral_program(access_token, template_id)

            # Создаем объект реферальной программы из полученных данных
            program = ReferralProgram(
                id=program_data.get("id"),
                code=program_data.get("code"),
                owner_id=program_data.get("owner_id"),
                participants=len(program_data.get("participants", [])),
                balance=program_data.get("balance", 0),
                template_id=program_data.get("template_id"),
                name=program_data.get("name"),
                disabled=program_data.get("disabled", False),
                amount_spend_by_users=program_data.get("amount_spend_by_users", 0),
                last_withdrawed_at=program_data.get("last_withdrawed_at")
            )

            # Если в ответе есть шаблон, добавляем его
            if "template" in program_data:
                template_data = program_data["template"]
                program.template = ReferralTemplate(
                    id=template_data.get("id"),
                    name=template_data.get("name"),
                    currency=template_data.get("currency"),
                    encourage_percentage=template_data.get("encouragement_percentage"),
                    min_withdraw_amount=template_data.get("min_withdraw_amount"),
                    tokens=template_data.get("tokens"),
                    locale=template_data.get("locale", user.language_code or "ru"),
                    plan=template_data.get("plan"),
                    disabled=template_data.get("disabled", False),
                    private=template_data.get("private", False)
                )

            return program
        except Exception as e:
            logger.error(f"Ошибка при создании реферальной программы: {e}", exc_info=True)
            raise Exception(f"Не удалось создать реферальную программу: {e}")

    async def list_referral_programs(self, user: User) -> List[ReferralProgram]:
        """
        Получение списка реферальных программ пользователя

        Args:
            user: Пользователь

        Returns:
            List[ReferralProgram]: Список реферальных программ
        """
        logger.info(f"Получение списка реферальных программ для пользователя {user.id}")
        try:
            # Получаем токен доступа
            access_token = await self.gateway.get_access_token(user)

            # Получаем реферальные программы через API BotHub
            programs_data = await self.gateway.client.list_referral_programs(access_token)

            # Обрабатываем полученные данные
            programs = []
            for program_data in programs_data:
                program = ReferralProgram(
                    id=program_data.get("id"),
                    code=program_data.get("code"),
                    owner_id=program_data.get("owner_id"),
                    participants=len(program_data.get("participants", [])),
                    balance=program_data.get("balance", 0),
                    template_id=program_data.get("template_id"),
                    name=program_data.get("name"),
                    disabled=program_data.get("disabled", False),
                    amount_spend_by_users=program_data.get("amount_spend_by_users", 0),
                    last_withdrawed_at=program_data.get("last_withdrawed_at")
                )

                # Если в ответе есть шаблон, добавляем его
                if "template" in program_data:
                    template_data = program_data["template"]
                    program.template = ReferralTemplate(
                        id=template_data.get("id"),
                        name=template_data.get("name"),
                        currency=template_data.get("currency"),
                        encourage_percentage=template_data.get("encouragement_percentage"),
                        min_withdraw_amount=template_data.get("min_withdraw_amount"),
                        tokens=template_data.get("tokens"),
                        locale=template_data.get("locale", user.language_code or "ru"),
                        plan=template_data.get("plan"),
                        disabled=template_data.get("disabled", False),
                        private=template_data.get("private", False)
                    )

                programs.append(program)

            return programs
        except Exception as e:
            logger.error(f"Ошибка при получении реферальных программ: {e}", exc_info=True)
            raise Exception(f"Не удалось получить реферальные программы: {e}")

    def get_referral_links(self, program: ReferralProgram) -> Dict[str, str]:
        """
        Получение реферальных ссылок для программы

        Args:
            program: Реферальная программа

        Returns:
            Dict[str, str]: Словарь с реферальными ссылками
        """
        # Формируем веб-ссылку
        web_url = self.settings.BOTHUB_WEB_URL or "https://bothub.chat"
        web_link = f"{web_url}?invitedBy={program.code}"

        # Формируем телеграм-ссылку
        bot_name = self.settings.TELEGRAM_BOT_NAME or "BotHubBot"
        telegram_link = f"https://t.me/{bot_name}?start={program.code}"

        return {
            "web": web_link,
            "telegram": telegram_link,
            "code": program.code
        }