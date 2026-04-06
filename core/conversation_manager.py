from config import MAX_HISTORY_LENGTH

class ConversationManager:
    def __init__(self):
        self.messages = []
        self.max_history = MAX_HISTORY_LENGTH * 2  # 每轮对话包含user和assistant两条

    def add_user_message(self, content):
        """添加用户消息"""
        self.messages.append({"role": "user", "content": content})
        self._trim_history()

    def add_assistant_message(self, content):
        """添加助手回复"""
        self.messages.append({"role": "assistant", "content": content})
        self._trim_history()

    def _trim_history(self):
        """裁剪历史记录，保留最近的max_history条"""
        if len(self.messages) > self.max_history:
            self.messages = self.messages[-self.max_history:]

    def clear_history(self):
        """清空对话历史"""
        self.messages = []

    def get_conversation(self):
        """获取完整对话历史"""
        return self.messages.copy()

    def get_last_message(self):
        """获取最后一条消息"""
        if self.messages:
            return self.messages[-1]
        return None
