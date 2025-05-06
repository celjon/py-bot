from enum import Enum, auto

class CallbackType(Enum):
    """Типы callback-запросов"""
    MODEL_SELECTION = "model"
    UNAVAILABLE_MODEL = "unavail"
    CONTEXT_ON = "ctx_on"
    CONTEXT_OFF = "ctx_off"
    CANCEL = "cancel"
    CHAT_SELECTION = "chat"
    WEB_SEARCH = "search"
    TOOL_SELECTION = "tool"
    MIDJOURNEY_BUTTON = "mj_btn"