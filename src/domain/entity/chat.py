from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class Chat(BaseModel):
    """Сущность чата"""
    id: int
    user_id: int
    chat_index: int = 1
    bothub_chat_id: Optional[str] = None
    bothub_chat_model: Optional[str] = None
    context_remember: bool = True
    context_counter: int = 0
    links_parse: bool = False
    formula_to_image: bool = False
    answer_to_voice: bool = False
    system_prompt: str = ""
    name: Optional[str] = None
    buffer: Optional[List[Dict[str, Any]]] = None