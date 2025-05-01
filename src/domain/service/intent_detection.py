from enum import Enum

class IntentType(Enum):
    CHAT = "chat"
    WEB_SEARCH = "web_search"
    IMAGE_GENERATION = "image_generation"

class IntentDetectionService:
    def detect_intent(self, text: str) -> tuple[IntentType, dict]:
        return IntentType.CHAT, {}