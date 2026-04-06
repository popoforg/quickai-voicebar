import threading
import time

from config import HOTKEY_KEY, HOTKEY_MODIFIERS
from core.speech_recognizer import app_log

try:
    import Quartz
except Exception:  # pragma: no cover - only used on non-macOS environments
    Quartz = None


class HotkeyListener:
    CTRL_KEYCODES = {59, 62}
    KEYCODE_MAP = {
        "a": 0,
        "s": 1,
        "d": 2,
        "f": 3,
        "h": 4,
        "g": 5,
        "z": 6,
        "x": 7,
        "c": 8,
        "v": 9,
        "b": 11,
        "q": 12,
        "w": 13,
        "e": 14,
        "r": 15,
        "y": 16,
        "t": 17,
        "1": 18,
        "2": 19,
        "3": 20,
        "4": 21,
        "6": 22,
        "5": 23,
        "=": 24,
        "9": 25,
        "7": 26,
        "-": 27,
        "8": 28,
        "0": 29,
        "]": 30,
        "o": 31,
        "u": 32,
        "[": 33,
        "i": 34,
        "p": 35,
        "l": 37,
        "j": 38,
        "'": 39,
        "k": 40,
        ";": 41,
        "\\": 42,
        ",": 43,
        "/": 44,
        "n": 45,
        "m": 46,
        ".": 47,
        "`": 50,
    }
    MODIFIER_FLAGS = {
        "ctrl": Quartz.kCGEventFlagMaskControl if Quartz else 0,
        "shift": Quartz.kCGEventFlagMaskShift if Quartz else 0,
        "alt": Quartz.kCGEventFlagMaskAlternate if Quartz else 0,
        "cmd": Quartz.kCGEventFlagMaskCommand if Quartz else 0,
    }

    def __init__(self, toggle_window_callback):
        self.toggle_window = toggle_window_callback
        self.listener_thread = None
        self.run_loop = None
        self.event_tap = None
        self.start_error = None
        self.last_ctrl_tap_time = 0.0
        self.ctrl_double_tap_threshold = 0.45
        self.last_toggle_time = 0.0
        self.toggle_cooldown = 0.2
        self.ctrl_is_down = False
        self.active_ctrl_keycodes = set()
        self.required_flags_mask = 0
        for modifier in HOTKEY_MODIFIERS:
            self.required_flags_mask |= self.MODIFIER_FLAGS.get(modifier, 0)
        self.target_key = HOTKEY_KEY.lower()
        self.target_keycode = self.KEYCODE_MAP.get(self.target_key)

    def _check_accessibility_permission(self) -> bool:
        if Quartz is None:
            self.start_error = "Quartz 不可用"
            return False
        try:
            options = {Quartz.kAXTrustedCheckOptionPrompt: True}
            trusted = bool(Quartz.AXIsProcessTrustedWithOptions(options))
        except Exception as exc:
            self.start_error = f"辅助功能权限检查失败: {exc!r}"
            app_log(self.start_error)
            return False
        if not trusted:
            self.start_error = "辅助功能权限未授予"
            app_log("全局快捷键启动前检查失败: 辅助功能权限未授予，已请求系统弹窗")
            return False
        self.start_error = None
        app_log("辅助功能权限检查通过")
        return True

    def _try_toggle(self, reason: str):
        now = time.monotonic()
        if now - self.last_toggle_time < self.toggle_cooldown:
            app_log(f"热键触发被冷却忽略: {reason}")
            return
        self.last_toggle_time = now
        app_log(f"热键触发: {reason}")
        self.toggle_window()

    def _handle_ctrl_press(self, keycode: int):
        if keycode in self.active_ctrl_keycodes:
            return
        self.active_ctrl_keycodes.add(keycode)
        self.ctrl_is_down = True
        app_log(f"Ctrl press: keycode={keycode}")

    def _handle_ctrl_release(self, keycode: int):
        if keycode not in self.active_ctrl_keycodes:
            return
        self.active_ctrl_keycodes.discard(keycode)
        self.ctrl_is_down = bool(self.active_ctrl_keycodes)
        now = time.monotonic()
        delta = now - self.last_ctrl_tap_time if self.last_ctrl_tap_time else None
        app_log(f"Ctrl release: keycode={keycode}, delta={delta}")
        if delta is not None and delta <= self.ctrl_double_tap_threshold:
            self.last_ctrl_tap_time = 0.0
            self._try_toggle("双击 Ctrl")
            return
        self.last_ctrl_tap_time = now

    def _matches_configured_hotkey(self, keycode: int, flags: int, autorepeat: int) -> bool:
        if autorepeat:
            return False
        if self.target_keycode is None or keycode != self.target_keycode:
            return False
        return (flags & self.required_flags_mask) == self.required_flags_mask

    def _event_callback(self, proxy, event_type, event, refcon):
        if event_type in (
            Quartz.kCGEventTapDisabledByTimeout,
            Quartz.kCGEventTapDisabledByUserInput,
        ):
            app_log(f"event tap disabled: type={event_type}, re-enabling")
            if self.event_tap is not None:
                Quartz.CGEventTapEnable(self.event_tap, True)
            return event

        keycode = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventKeycode)
        flags = Quartz.CGEventGetFlags(event)

        if event_type == Quartz.kCGEventFlagsChanged and keycode in self.CTRL_KEYCODES:
            is_down = bool(flags & Quartz.kCGEventFlagMaskControl)
            if is_down:
                self._handle_ctrl_press(keycode)
            else:
                self._handle_ctrl_release(keycode)
            return event

        if event_type == Quartz.kCGEventKeyDown:
            autorepeat = Quartz.CGEventGetIntegerValueField(event, Quartz.kCGKeyboardEventAutorepeat)
            if self._matches_configured_hotkey(keycode, flags, autorepeat):
                app_log(
                    f"组合热键命中: flags=0x{int(flags):x}, keycode={keycode}, "
                    f"hotkey={'+'.join(HOTKEY_MODIFIERS)}+{HOTKEY_KEY}"
                )
                self._try_toggle("+".join(HOTKEY_MODIFIERS) + f"+{HOTKEY_KEY}")

        return event

    def _run_event_loop(self):
        if Quartz is None:
            self.start_error = "Quartz 不可用"
            app_log("全局快捷键启动失败: Quartz 不可用")
            return

        if not self._check_accessibility_permission():
            return

        mask = (
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
            | Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
        )
        self.event_tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            mask,
            self._event_callback,
            None,
        )
        if self.event_tap is None:
            self.start_error = "CGEventTapCreate 返回空"
            app_log("全局快捷键启动失败: CGEventTapCreate 返回空，通常是辅助功能权限缺失")
            return

        source = Quartz.CFMachPortCreateRunLoopSource(None, self.event_tap, 0)
        self.run_loop = Quartz.CFRunLoopGetCurrent()
        Quartz.CFRunLoopAddSource(self.run_loop, source, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(self.event_tap, True)
        self.start_error = None
        app_log(f"全局快捷键已启动: {'+'.join(HOTKEY_MODIFIERS)}+{HOTKEY_KEY}")
        Quartz.CFRunLoopRun()

    def start(self):
        """启动快捷键监听"""
        if self.listener_thread and self.listener_thread.is_alive():
            return
        self.listener_thread = threading.Thread(
            target=self._run_event_loop,
            name="quickai-hotkey-listener",
            daemon=True,
        )
        self.listener_thread.start()
        print(f"全局快捷键已启动: {'+'.join(HOTKEY_MODIFIERS)}+{HOTKEY_KEY}")
        print("提示: 请在系统偏好设置 > 安全性与隐私 > 隐私 > 辅助功能 中为终端/Python授予权限")

    def stop(self):
        """停止快捷键监听"""
        if Quartz is None:
            return
        if self.run_loop is not None:
            Quartz.CFRunLoopStop(self.run_loop)
            self.run_loop = None
        self.event_tap = None
