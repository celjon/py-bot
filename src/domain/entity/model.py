# src/domain/entity/model.py
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class Model:
    """Сущность модели ИИ (аналог PHP Entity/Model.php)"""
    id: str
    label: Optional[str] = None
    max_tokens: Optional[int] = None
    features: Optional[List[str]] = field(default_factory=list)

    def __post_init__(self):
        if self.features is None:
            self.features = []

    def has_feature(self, feature: str) -> bool:
        """Проверить наличие функции у модели"""
        return feature in (self.features or [])

    def is_text_model(self) -> bool:
        """Проверить, является ли модель текстовой"""
        return self.has_feature("TEXT_TO_TEXT")

    def is_image_generation_model(self) -> bool:
        """Проверить, является ли модель для генерации изображений"""
        return self.has_feature("TEXT_TO_IMAGE")

    def is_image_analysis_model(self) -> bool:
        """Проверить, может ли модель анализировать изображения"""
        return self.has_feature("IMAGE_TO_TEXT")

    def get_display_name(self) -> str:
        """Получить отображаемое имя модели"""
        return self.label or self.id

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь"""
        return {
            'id': self.id,
            'label': self.label,
            'max_tokens': self.max_tokens,
            'features': self.features
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Model':
        """Создание объекта из словаря"""
        return cls(
            id=data['id'],
            label=data.get('label'),
            max_tokens=data.get('max_tokens'),
            features=data.get('features', [])
        )