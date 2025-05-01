class Chat:
    def __init__(self, id: int, user_id: int, chat_index: int, context_counter: int = 0):
        self.id = id
        self.user_id = user_id
        self.chat_index = chat_index
        self.context_counter = context_counter