import requests
import json
import threading
import config

class LLMClient:
    def __init__(self, stream_callback, complete_callback):
        self.stream_callback = stream_callback
        self.complete_callback = complete_callback
        self.is_streaming = False

    def chat(self, messages):
        """发送聊天请求，流式返回结果"""
        if self.is_streaming:
            return

        self.is_streaming = True
        thread = threading.Thread(
            target=self._stream_request,
            args=(messages,),
            daemon=True
        )
        thread.start()

    def _stream_request(self, messages):
        """流式请求处理"""
        full_response = ""
        try:
            headers = {
                "Content-Type": "application/json"
            }

            payload = {
                "model": config.LMSTUDIO_MODEL,
                "messages": messages,
                "stream": True,
                "temperature": config.LMSTUDIO_TEMPERATURE,
                "max_tokens": config.LMSTUDIO_MAX_TOKENS
            }

            response = requests.post(
                f"{config.LMSTUDIO_API_BASE}/chat/completions",
                headers=headers,
                json=payload,
                stream=True,
                timeout=60
            )

            response.raise_for_status()

            for line in response.iter_lines():
                if not self.is_streaming:
                    break

                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == '[DONE]':
                            break
                        try:
                            json_data = json.loads(data)
                            if 'choices' in json_data and len(json_data['choices']) > 0:
                                delta = json_data['choices'][0].get('delta', {})
                                content = delta.get('content', '')
                                if content:
                                    full_response += content
                                    self.stream_callback(content)
                        except json.JSONDecodeError:
                            continue

        except requests.exceptions.RequestException as e:
            error_msg = f"API请求错误: {str(e)}\n请确保LMStudio已经启动并开启了API服务"
            self.stream_callback(error_msg)
            full_response = error_msg
        finally:
            self.is_streaming = False
            self.complete_callback(full_response)

    def stop_stream(self):
        """停止流式输出"""
        self.is_streaming = False

    def get_available_models(self):
        """获取当前可用的模型列表"""
        try:
            response = requests.get(
                f"{config.LMSTUDIO_API_BASE}/models",
                timeout=2
            )
            response.raise_for_status()
            data = response.json()
            models = []
            for item in data.get("data", []):
                models.append(item.get("id"))
            return models
        except Exception as e:
            print(f"获取模型列表失败: {e}")
            return []
