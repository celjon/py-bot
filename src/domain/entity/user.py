class User:
    def __init__(
        self,
        id: int,
        telegram_id: str,
        first_name: str = None,
        last_name: str = None,
        username: str = None,
        language_code: str = None
    ):
        self.id = id
        self.telegram_id = telegram_id
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.language_code = language_code
        self.current_chat_index = 0