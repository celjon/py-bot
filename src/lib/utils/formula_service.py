import re
import os
import tempfile
from PIL import Image


class FormulaService:
    """Сервис для работы с формулами"""

    LATEX_CHARSET = r'[a-zA-Z0-9,\|\'\.\(\)\[\]\+\-\*\^\/\{\}\\_\=\\\pi ]'

    @staticmethod
    def parse_formula(text: str) -> Optional[str]:
        """
        Извлечение формулы из текста

        Args:
            text: Текст с формулой

        Returns:
            Optional[str]: Извлеченная формула или None
        """
        text = text.strip("*\\ \n")
        text = text.replace('\\\\', '\\')
        text = text.replace('\\_', '_')
        text = text.replace('\\*', '*')

        # Проверяем, что текст содержит формулу между $ и $
        pattern = f'^\${FormulaService.LATEX_CHARSET}+\$$'
        if not re.match(pattern, text):
            return None

        return text.strip("$ ")

    @staticmethod
    def format_formulas(text: str) -> str:
        """
        Приводит формулы в тексте к единому формату

        Args:
            text: Исходный текст

        Returns:
            str: Текст с отформатированными формулами
        """
        # Заменяем короткие формулы на обычный текст
        text = re.sub(r'\\\\\((' + FormulaService.LATEX_CHARSET + r'{1,4})\\\\\)', r'\1', text)

        # Заменяем формулы на стандартный формат
        text = re.sub(
            r'(\\\\\(|\\\\\[|\$\$|\$)\s*(' + FormulaService.LATEX_CHARSET + r'{5,})\s*(\\\\\)|\\\\\]|\$\$|\$)',
            r"\n$\2$\n",
            text
        )

        return text