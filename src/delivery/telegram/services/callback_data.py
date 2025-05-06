from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional
from .callback_types import CallbackType
import urllib.parse
import base64
import zlib


@dataclass
class CallbackData:
    """Данные для callback-запросов"""
    type: CallbackType
    data: Dict[str, str] = field(default_factory=dict)

    def encode(self) -> str:
        """
        Кодирует данные для callback в строку

        Returns:
            str: Строка для callback_data
        """
        # Если данных нет, возвращаем только тип
        if not self.data:
            return self.type.value

        # Формируем строку запроса для данных
        query_string = urllib.parse.urlencode(self.data)

        # Если длина callback_data может превысить лимит, используем сжатие
        result = f"{self.type.value}?{query_string}"
        if len(result) > 60:  # Оставляем запас, максимум 64 байта
            # Сжимаем данные и кодируем в base64
            compressed = zlib.compress(query_string.encode('utf-8'))
            b64_data = base64.urlsafe_b64encode(compressed).decode('ascii')
            result = f"{self.type.value}!{b64_data}"

        return result

    @classmethod
    def decode(cls, data: str) -> 'CallbackData':
        """
        Декодирует строку callback_data в объект CallbackData

        Args:
            data: Строка callback_data

        Returns:
            CallbackData: Объект с данными callback
        """
        # Проверяем формат данных
        if '?' in data:
            # Обычный формат query string
            type_str, query_string = data.split('?', 1)
            callback_type = CallbackType(type_str)
            parsed_data = dict(urllib.parse.parse_qsl(query_string))

        elif '!' in data:
            # Сжатый формат
            type_str, compressed_data = data.split('!', 1)
            callback_type = CallbackType(type_str)

            # Декодируем и распаковываем
            binary_data = base64.urlsafe_b64decode(compressed_data)
            query_string = zlib.decompress(binary_data).decode('utf-8')
            parsed_data = dict(urllib.parse.parse_qsl(query_string))

        else:
            # Только тип без данных
            callback_type = CallbackType(data)
            parsed_data = {}

        return cls(type=callback_type, data=parsed_data)