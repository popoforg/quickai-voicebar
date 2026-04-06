from pynput import keyboard
import time
from config import HOTKEY_MODIFIERS, HOTKEY_KEY

class HotkeyListener:
    def __init__(self, toggle_window_callback):
        self.toggle_window = toggle_window_callback
        self.pressed_keys = set()
        self.listener = None

        # 映射修饰键
        self.modifier_map = {
            'cmd': keyboard.Key.cmd,
            'shift': keyboard.Key.shift,
            'ctrl': keyboard.Key.ctrl,
            'alt': keyboard.Key.alt
        }

        self.required_modifiers = [self.modifier_map[mod] for mod in HOTKEY_MODIFIERS]
        self.target_key = HOTKEY_KEY.lower()

        # 双击Ctrl检测
        self.last_ctrl_press_time = 0
        self.double_click_threshold = 0.3  # 300ms以内按两次算双击

    def on_press(self, key):
        try:
            self.pressed_keys.add(key)

            # 检测双击Ctrl
            if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                current_time = time.time()
                if current_time - self.last_ctrl_press_time < self.double_click_threshold:
                    # 双击Ctrl，触发窗口切换
                    self.toggle_window()
                    self.last_ctrl_press_time = 0  # 重置，避免连续触发
                else:
                    self.last_ctrl_press_time = current_time
                return

            # 检查所有修饰键是否都按下
            modifiers_pressed = all(mod in self.pressed_keys for mod in self.required_modifiers)

            # 检查目标键是否按下
            if modifiers_pressed and hasattr(key, 'char') and key.char == self.target_key:
                self.toggle_window()
                # 防止重复触发
                self.pressed_keys.clear()

        except AttributeError:
            pass

    def on_release(self, key):
        try:
            self.pressed_keys.discard(key)
        except AttributeError:
            pass

    def start(self):
        """启动快捷键监听"""
        self.listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release,
            daemon=True
        )
        self.listener.start()
        print(f"全局快捷键已启动: {'+'.join(HOTKEY_MODIFIERS)}+{HOTKEY_KEY}")
        print("提示: 请在系统偏好设置 > 安全性与隐私 > 隐私 > 辅助功能 中为终端/Python授予权限")

    def stop(self):
        """停止快捷键监听"""
        if self.listener:
            self.listener.stop()
