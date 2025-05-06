# src/domain/service/formula_service.py

import re
import os
import tempfile
import logging
from typing import Optional, List, Tuple
import aiohttp
import base64

logger = logging.getLogger(__name__)


class FormulaService:
    """Сервис для работы с математическими формулами и их конвертацией в изображения"""

    # Регулярное выражение для поиска LaTeX формул
    LATEX_PATTERN = r'(\$\$(.*?)\$\$|\$(.*?)\$|\\\[(.*?)\\\]|\\\((.*?)\\\))'
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

    @staticmethod
    def extract_formulas(text: str) -> List[Tuple[str, str, int, int]]:
        """
        Извлекает все формулы из текста с их позициями

        Args:
            text: Исходный текст

        Returns:
            List[Tuple[str, str, int, int]]: Список кортежей (оригинальная формула, содержимое формулы, начальная позиция, конечная позиция)
        """
        formulas = []
        for match in re.finditer(FormulaService.LATEX_PATTERN, text, re.DOTALL):
            start = match.start()
            end = match.end()
            original = match.group(0)

            # Извлекаем содержимое формулы
            content = None
            for group_idx in range(2, 6):
                if match.group(group_idx):
                    content = match.group(group_idx)
                    break

            if content:
                formulas.append((original, content, start, end))

        return formulas

    @staticmethod
    async def generate_formula_image(formula: str) -> Optional[str]:
        """
        Генерирует изображение для формулы через API сервиса

        Args:
            formula: Формула в формате LaTeX

        Returns:
            Optional[str]: Путь к сгенерированному изображению или None в случае ошибки
        """
        try:
            # Здесь можно использовать сторонний API для генерации изображений
            # В данном примере мы используем API сервиса mathpix.com (нужно добавить API ключи)
            # Альтернативно можно использовать локальную библиотеку matplotlib для генерации изображений

            # Создаем временный файл для изображения
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            temp_file_path = temp_file.name
            temp_file.close()

            # Для примера, предположим, что мы используем API MathJax-node-svc
            # (https://github.com/mathjax/MathJax-node-svc)
            async with aiohttp.ClientSession() as session:
                async with session.post(
                        "http://localhost:8080/equation",  # Локальный сервис MathJax
                        json={
                            "math": formula,
                            "format": "TeX",
                            "svg": True,
                            "ex": 12,
                            "width": 800,
                            "linebreaks": True
                        }
                ) as response:
                    if response.status == 200:
                        result = await response.json()

                        if "svg" in result:
                            # Сохраняем SVG в файл
                            svg_content = result["svg"]
                            with open(temp_file_path, "w") as f:
                                f.write(svg_content)

                            return temp_file_path

            # Если API не доступен, возвращаем None
            logger.warning(f"Не удалось сгенерировать изображение для формулы: {formula}")
            return None
        except Exception as e:
            logger.error(f"Ошибка при генерации изображения формулы: {e}")
            return None

    @staticmethod
    def replace_formulas_with_images(text: str, formulas_with_images: List[Tuple[str, str]]) -> str:
        """
        Заменяет формулы в тексте на ссылки на изображения

        Args:
            text: Исходный текст
            formulas_with_images: Список кортежей (оригинальная формула, путь к изображению)

        Returns:
            str: Текст с заменами
        """
        result = text
        for original, image_path in formulas_with_images:
            if image_path:
                # Заменяем формулу на тег изображения
                result = result.replace(original, f"![formula]({image_path})")

        return result