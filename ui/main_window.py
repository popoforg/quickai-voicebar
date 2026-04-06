import time
import html
import re
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit, QTextBrowser,
    QHBoxLayout, QPushButton, QLabel, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QRect, QTimer, pyqtSignal, QObject, QSettings, QPoint, QEvent, QSize, QUrl
from PyQt5.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen, QPainterPath, QDesktopServices, QCursor
import random
import markdown
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name
import config
from config import WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_OPACITY
from core.speech_recognizer import app_log

class SignalEmitter(QObject):
    """信号发射器，用于跨线程通信"""
    toggle_window = pyqtSignal()
    speech_text_updated = pyqtSignal(str)
    stream_received = pyqtSignal(str)
    stream_complete = pyqtSignal(str)

class VoiceIconWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 36)
        self.is_animating = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        
        self.bar_heights = [4, 8, 14, 8, 4]
        self.bar_targets = [4, 8, 14, 8, 4]

    def set_animating(self, anim: bool):
        if self.is_animating == anim:
            return
        self.is_animating = anim
        if anim:
            self.bar_heights = [4, 8, 14, 8, 4]
            self.timer.start(80)
        else:
            self.timer.stop()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        
        if self.is_animating:
            painter.setBrush(QColor("#CBDCFC"))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 8, 8)
            
            painter.setPen(QPen(QColor("#2B6CFA"), 2.5, Qt.SolidLine, Qt.RoundCap))
            cx = rect.width() / 2
            cy = rect.height() / 2
            
            for i in range(5):
                diff = self.bar_targets[i] - self.bar_heights[i]
                self.bar_heights[i] += diff * 0.4
                if abs(diff) < 1.5:
                    self.bar_targets[i] = random.randint(4, 18)
                    
                h = self.bar_heights[i]
                x = cx - 12 + i * 6
                painter.drawLine(int(x), int(cy - h/2), int(x), int(cy + h/2))
        else:
            painter.setBrush(Qt.NoBrush)
            pen = QPen(QColor("#666666"), 2)
            painter.setPen(pen)
            cx = rect.width() / 2
            cy = rect.height() / 2
            
            painter.drawEllipse(int(cx - 10), int(cy - 10), 20, 20)
            
            # 使用精准偏移让内部元素在20x20的圆框内完美居中
            inner_cx = cx - 3
            inner_cy = cy
            
            painter.setBrush(QColor("#666666"))
            painter.drawEllipse(int(inner_cx - 1.5), int(inner_cy - 1.5), 3, 3)
            
            painter.setBrush(Qt.NoBrush)
            painter.drawArc(int(inner_cx - 4), int(inner_cy - 4), 8, 8, -45 * 16, 90 * 16)
            painter.drawArc(int(inner_cx - 7), int(inner_cy - 7), 14, 14, -45 * 16, 90 * 16)

class ShortcutButton(QWidget):
    clicked = pyqtSignal()
    
    def __init__(self, key_text, label_text, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 2, 6, 2)
        layout.setSpacing(5)
        
        self.key_label = QLabel(key_text)
        self.key_label.setAlignment(Qt.AlignCenter)
        self.key_label.setStyleSheet("""
            QLabel {
                background-color: #E6E6E6;
                border-radius: 4px;
                padding: 2px 5px;
                font-size: 12px;
                color: #555555;
                font-family: inherit;
                font-weight: 500;
            }
        """)
        
        self.text_label = QLabel(label_text)
        self.text_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                color: #555555;
                font-family: "PingFang SC";
            }
        """)
        
        layout.addWidget(self.key_label)
        layout.addWidget(self.text_label)
        
        self.setStyleSheet("""
            ShortcutButton {
                background-color: transparent;
                border-radius: 6px;
            }
            ShortcutButton:hover {
                background-color: rgba(230, 230, 230, 0.6);
            }
        """)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(24)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
            
    def setText(self, text):
        self.text_label.setText(text)

    def setKeyText(self, text):
        self.key_label.setText(text)
        
    def setLabelText(self, text):
        self.text_label.setText(text)

class MainWindow(QWidget):
    RESIZE_MARGIN = 16
    EDGE_LEFT = 1
    EDGE_TOP = 2
    EDGE_RIGHT = 4
    EDGE_BOTTOM = 8
    COMPACT_HEIGHT = 154
    DEFAULT_RESPONSE_HEIGHT = 360

    def __init__(self, speech_recognizer, llm_client, conversation_manager):
        super().__init__()
        self.speech_recognizer = speech_recognizer
        self.llm_client = llm_client
        self.conversation_manager = conversation_manager
        self.signal_emitter = SignalEmitter()

        self.is_listening = False
        self.is_waiting_for_send = False
        self.assistant_response = ""
        self.is_waiting_for_response = False
        self.loading_dots = 0
        self.pending_render_markdown = ""
        self.render_update_interval_ms = 100

        self.response_loading_timer = QTimer(self)
        self.response_loading_timer.timeout.connect(self.update_loading_indicator)
        self.response_render_timer = QTimer(self)
        self.response_render_timer.setSingleShot(True)
        self.response_render_timer.timeout.connect(self.flush_pending_render)
        self.deactivate_hide_timer = QTimer(self)
        self.deactivate_hide_timer.setSingleShot(True)
        self.deactivate_hide_timer.timeout.connect(self._hide_if_inactive)
        self.markdown_renderer = markdown.Markdown(
            extensions=["fenced_code", "codehilite", "nl2br", "sane_lists"],
            extension_configs={
                "codehilite": {
                    "guess_lang": False,
                    "noclasses": True,
                    "linenums": False,
                    "css_class": "codehilite",
                }
            },
        )
        self.codehilite_css = HtmlFormatter(style="default", noclasses=True).get_style_defs(".codehilite")
        self.code_formatter = HtmlFormatter(style="default", noclasses=True, nowrap=True)
        self.code_blocks = {}

        # 窗口拖动相关
        self.is_dragging = False
        self.drag_start_position = QPoint()
        self.resize_edges = 0
        self.resize_start_geometry = QRect()
        self.resize_start_global_pos = QPoint()

        # 手动跟踪窗口状态
        self._is_window_shown = False
        self._suppress_deactivate_until = 0.0
        self._has_activated_since_show = False
        self._ignore_outside_click_until = 0.0
        self._global_mouse_monitor = None
        self._local_mouse_monitor = None

        # 读取保存的窗口位置
        self.settings = QSettings("QuickAI", "QuickAI")
        self.saved_position = self.settings.value("window_position", QPoint())
        self.saved_size = self.settings.value("window_size", QSize(WINDOW_WIDTH, WINDOW_HEIGHT), type=QSize)
        self.saved_response_size = self.settings.value(
            "response_window_size",
            QSize(WINDOW_WIDTH, self.DEFAULT_RESPONSE_HEIGHT),
            type=QSize
        )

        self.init_ui()
        self.setup_connections()
        self.setup_signals()
        self._install_outside_click_monitor()

    def init_ui(self):
        """初始化界面"""
        # 使用普通顶层窗口而不是 Qt.Tool，避免 macOS 在应用失焦时自动隐藏窗口
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Window
        )

        # 窗口透明设置
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 为了防止阴影引起背景闪烁，我们使用一个内部容器
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setMinimumSize(420, self.COMPACT_HEIGHT)
        initial_width = self.saved_response_size.width() if self.saved_response_size.isValid() else WINDOW_WIDTH
        self.resize(max(420, initial_width), self.COMPACT_HEIGHT)
        
        self.container = QWidget()
        self.container.setObjectName("mainContainer")
        # 整体大背景白框
        self.container.setStyleSheet("""
            QWidget#mainContainer {
                background-color: rgba(255, 255, 255, 0.95);
                border-radius: 12px;
            }
        """)
        main_layout.addWidget(self.container)
        self.setMouseTracking(True)
        self.container.setMouseTracking(True)

        # 内部主布局
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(12, 10, 12, 8)
        layout.setSpacing(4) # 减小组件间距保持紧凑

        # 模型名字显示 (在输入框上方小字)
        display_model = config.LMSTUDIO_MODEL.split('/')[-1] if '/' in config.LMSTUDIO_MODEL else config.LMSTUDIO_MODEL
        self.model_label = QLabel(display_model)
        self.model_label.setStyleSheet("""
            QLabel {
                color: #A0A0A0;
                font-size: 10px;
                font-family: "PingFang SC";
                padding-left: 4px;
            }
        """)
        self.model_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(self.model_label)

        # 输入区域布局
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(2, 0, 2, 0)
        input_layout.setSpacing(10)

        # 输入框
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("正在听你说话...")
        self.input_box.setFont(QFont("PingFang SC", 16))
        self.input_box.setStyleSheet("""
            QLineEdit {
                border: none;
                padding: 2px 2px;
                font-size: 16px;
                background-color: transparent;
                selection-background-color: #007AFF;
            }
            QLineEdit:focus {
                border: none;
                background-color: transparent;
            }
        """)
        self.input_box.setFixedHeight(28)
        input_layout.addWidget(self.input_box)
        
        # 语音图标
        self.voice_icon = VoiceIconWidget()
        input_layout.addWidget(self.voice_icon)
        
        layout.addLayout(input_layout)

        # 回复区域
        self.response_area = QTextBrowser()
        self.response_area.setReadOnly(True)
        self.response_area.setOpenExternalLinks(False)
        self.response_area.setOpenLinks(False)
        self.response_area.anchorClicked.connect(self.on_response_link_clicked)
        self.response_area.setFont(QFont("PingFang SC", 15))
        self.response_area.setStyleSheet("""
            QTextBrowser {
                border: none;
                padding: 0px;
                font-size: 15px;
                line-height: 1.6;
                background-color: transparent;
                selection-background-color: #007AFF;
            }
            QScrollBar:vertical {
                width: 8px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 0, 0, 0.2);
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.response_area.setMinimumHeight(180)
        self.response_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.response_area.hide() # 初始状态下隐藏
        self.response_area.installEventFilter(self)
        self.response_area.viewport().installEventFilter(self)
        self.response_area.setMouseTracking(True)
        self.response_area.viewport().setMouseTracking(True)
        layout.addWidget(self.response_area, 1)

        # 分隔线 (在回复区之后，状态栏之前)
        self.bottom_sep = QFrame()
        self.bottom_sep.setFrameShape(QFrame.HLine)
        self.bottom_sep.setStyleSheet(
            "background-color: #EAEAEA; border: none; max-height: 1px; margin-top: 6px; margin-bottom: 4px;"
        )
        layout.addWidget(self.bottom_sep)

        # 状态栏
        self.status_bar_widget = QWidget()
        self.status_bar_widget.setFixedHeight(34)
        self.status_bar_layout = QHBoxLayout(self.status_bar_widget)
        self.status_bar_layout.setContentsMargins(2, 8, 2, 0)
        self.status_bar_layout.setSpacing(6)
        
        # 状态栏左侧的录音状态提示
        self.status_voice_label = QLabel("🎙️ 自动语音识别")
        self.status_voice_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 12px;
                font-family: "PingFang SC";
            }
        """)
        self.status_voice_label.setFixedHeight(22)
        self.status_bar_layout.addWidget(self.status_voice_label)

        self.status_bar_layout.addStretch()

        self.btn_finish_voice = ShortcutButton("Esc", "完成输入")
        self.btn_finish_voice.clicked.connect(self.toggle_voice_input)

        self.btn_send = ShortcutButton("Enter", "发起")
        self.btn_send.clicked.connect(self.on_enter_pressed)

        self.btn_copy = ShortcutButton("⌘ C", "复制")
        self.btn_copy.clicked.connect(self.copy_all_content)

        self.btn_esc = ShortcutButton("Esc", "返回")
        self.btn_esc.clicked.connect(self.return_to_input)

        self.btn_enter = ShortcutButton("Enter", "接着聊")
        self.btn_enter.clicked.connect(self.focus_input)

        self.status_bar_layout.addWidget(self.btn_finish_voice)
        self.status_bar_layout.addWidget(self.btn_send)
        self.status_bar_layout.addWidget(self.btn_copy)
        self.status_bar_layout.addWidget(self.btn_esc)
        self.status_bar_layout.addWidget(self.btn_enter)

        self.status_bar_widget.hide()
        self.status_bar_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(self.status_bar_widget)
        layout.setStretch(0, 0)
        layout.setStretch(1, 0)
        layout.setStretch(2, 1)
        layout.setStretch(3, 0)
        layout.setStretch(4, 0)

        resize_widgets = [
            self,
            self.container,
            self.model_label,
            self.input_box,
            self.voice_icon,
            self.bottom_sep,
            self.status_bar_widget,
            self.btn_finish_voice,
            self.btn_send,
            self.btn_copy,
            self.btn_esc,
            self.btn_enter,
        ]
        for widget in resize_widgets:
            widget.installEventFilter(self)
            widget.setMouseTracking(True)

    def setup_connections(self):
        """设置信号连接"""
        self.input_box.returnPressed.connect(self.on_enter_pressed)

    def setup_signals(self):
        """设置跨线程信号槽"""
        self.signal_emitter.toggle_window.connect(self.toggle_visibility)
        self.signal_emitter.speech_text_updated.connect(self.on_speech_text_updated)
        self.signal_emitter.stream_received.connect(self.on_stream_received)
        self.signal_emitter.stream_complete.connect(self.on_stream_complete)

    def update_status_bar(self, mode):
        """更新状态栏按钮显示"""
        self.status_bar_widget.show()
        if mode == "voice":
            self.bottom_sep.show()
            self.status_voice_label.show()
            self.btn_finish_voice.show()
            self.btn_finish_voice.setKeyText("Esc")
            self.btn_finish_voice.setLabelText("完成输入")
            self.btn_send.show()
            self.btn_copy.hide()
            self.btn_esc.hide()
            self.btn_enter.hide()
        elif mode == "input":
            self.bottom_sep.show()
            self.status_voice_label.hide()
            self.btn_finish_voice.show()
            self.btn_finish_voice.setKeyText("⌥")
            self.btn_finish_voice.setLabelText("语音输入")
            self.btn_send.show()
            self.btn_copy.hide()
            self.btn_esc.hide()
            self.btn_enter.hide()
        elif mode == "response":
            self.bottom_sep.show()
            self.status_voice_label.hide()
            self.btn_finish_voice.hide()
            self.btn_send.hide()
            self.btn_copy.show()
            self.btn_esc.show()
            self.btn_enter.show()
        elif mode == "hide":
            self.bottom_sep.hide()
            self.status_bar_widget.hide()

    def show_window(self):
        """显示窗口"""
        app_log(f"show_window called: shown={self._is_window_shown}, visible={self.isVisible()}")
        self.deactivate_hide_timer.stop()
        self._suppress_deactivate_until = time.monotonic() + 0.4
        self._ignore_outside_click_until = time.monotonic() + 0.35
        self._has_activated_since_show = False
        self.input_box.clear()
        self.response_area.clear()
        self.response_area.hide() 
        self.stop_loading_indicator()
        self.update_status_bar("input")
        self._apply_compact_size()
        self.assistant_response = ""
        self.is_waiting_for_send = True
        self.input_box.setPlaceholderText("按住 ⌥(Option) 键说话，或直接打字...")
        self._is_window_shown = True
        self.show_animated()
        # 不再默认启动语音识别

    def hide_window(self):
        """关闭窗口"""
        app_log(f"hide_window called: shown={self._is_window_shown}, visible={self.isVisible()}")
        self.deactivate_hide_timer.stop()
        self.saved_position = self.pos()
        self.settings.setValue("window_position", self.saved_position)
        self.settings.setValue("window_size", self.size())
        if self.response_area.isVisible():
            self.settings.setValue("response_window_size", self.size())
            self.saved_response_size = self.size()
        self.stop_loading_indicator()
        self.response_render_timer.stop()
        self.pending_render_markdown = ""
        self.hide()
        self.speech_recognizer.stop_listening()
        self.is_listening = False
        self._is_window_shown = False

    def toggle_visibility(self):
        """切换窗口显示/隐藏 - 直接用_is_window_shown变量"""
        actually_visible = self._is_window_shown and self.isVisible()
        app_log(
            f"toggle_visibility called: tracked={self._is_window_shown}, "
            f"visible={self.isVisible()}, active={QApplication.activeWindow() is self}"
        )
        self._is_window_shown = actually_visible
        if actually_visible:
            app_log("toggle_visibility -> hide_window")
            self.hide_window()
        else:
            app_log("toggle_visibility -> show_window")
            self.show_window()

    def show_animated(self):
        """带动画显示窗口"""
        self.deactivate_hide_timer.stop()
        self._suppress_deactivate_until = time.monotonic() + 0.4
        self._ignore_outside_click_until = time.monotonic() + 0.35
        self._has_activated_since_show = False
        self._activate_app()
        # 使用保存的位置或者默认居中
        screen_geo = QApplication.desktop().availableGeometry()
        if self.saved_position.isNull() or not self._is_position_valid(self.saved_position):
            x = (screen_geo.width() - self.width()) // 2
            y = (screen_geo.height() - self.height()) // 2
        else:
            x = self.saved_position.x()
            y = self.saved_position.y()

        # 从上方滑入
        self.setGeometry(x, y - 80, self.width(), self.height())
        self.show()
        self.raise_()  # 提升到最上层
        self.activateWindow()  # 强制激活
        self.input_box.setFocus()
        # MacOS特有的强制激活
        QApplication.setActiveWindow(self)
        QTimer.singleShot(0, self._activate_app)
        QTimer.singleShot(50, self._activate_app)

        # 动画
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(250)
        self.animation.setStartValue(QRect(x, y - 80, self.width(), self.height()))
        self.animation.setEndValue(QRect(x, y, self.width(), self.height()))
        self.animation.start()

        # 初始化状态：允许直接发送消息
        self.is_waiting_for_send = True
        self._is_window_shown = True

    def _activate_app(self):
        """在 macOS 上把应用重新激活到前台，避免失焦后热键无法再次呼出窗口。"""
        try:
            from AppKit import NSApplication, NSApp, NSRunningApplication
            from Foundation import NSProcessInfo

            app = NSApp() or NSApplication.sharedApplication()
            if app is not None:
                app.activateIgnoringOtherApps_(True)
            current_app = NSRunningApplication.runningApplicationWithProcessIdentifier_(
                NSProcessInfo.processInfo().processIdentifier()
            )
            if current_app is not None:
                current_app.activateWithOptions_(1 << 1)
        except Exception:
            pass

    def _install_outside_click_monitor(self):
        """监听全局和应用内鼠标点击，点击窗口外部时主动隐藏窗口。"""
        try:
            from AppKit import (
                NSEvent,
                NSEventMaskLeftMouseDown,
                NSEventMaskRightMouseDown,
                NSEventMaskOtherMouseDown,
            )
        except Exception as exc:
            app_log(f"outside click monitor unavailable: {exc!r}")
            return

        if self._global_mouse_monitor is not None or self._local_mouse_monitor is not None:
            return

        mask = NSEventMaskLeftMouseDown | NSEventMaskRightMouseDown | NSEventMaskOtherMouseDown

        def local_handler(event):
            QTimer.singleShot(0, self._hide_if_clicked_outside)
            return event

        def global_handler(_event):
            QTimer.singleShot(0, self._hide_if_clicked_outside)

        self._local_mouse_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(mask, local_handler)
        self._global_mouse_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(mask, global_handler)
        app_log("outside click monitor installed")

    def _hide_if_clicked_outside(self):
        if not self._is_window_shown or not self.isVisible():
            return
        if time.monotonic() < self._ignore_outside_click_until:
            app_log("outside click ignored during post-show guard window")
            return
        if self.frameGeometry().contains(QCursor.pos()):
            return
        app_log("outside click detected -> hide_window")
        self.hide_window()

    def _is_position_valid(self, pos):
        """检查位置是否在任意一个屏幕范围内（支持多屏/扩展屏）"""
        desktop = QApplication.desktop()
        screen_count = desktop.screenCount()
        for i in range(screen_count):
            screen_geo = desktop.availableGeometry(i)
            if (screen_geo.left() <= pos.x() <= screen_geo.right() and
                screen_geo.top() <= pos.y() <= screen_geo.bottom()):
                return True
        return False

    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件，记录拖动起始位置"""
        if event.button() == Qt.LeftButton:
            self.resize_edges = self._get_resize_edges(event.pos())
            if self.resize_edges:
                self.resize_start_geometry = self.geometry()
                self.resize_start_global_pos = event.globalPos()
            else:
                self.is_dragging = True
                self.drag_start_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """鼠标移动事件，拖动窗口"""
        if event.buttons() == Qt.LeftButton and self.resize_edges:
            self._resize_window(event.globalPos())
            event.accept()
        elif event.buttons() == Qt.LeftButton and self.is_dragging:
            self.move(event.globalPos() - self.drag_start_position)
            event.accept()
        else:
            self._update_cursor(event.pos())

    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件，结束拖动"""
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
            self.resize_edges = 0
            self.unsetCursor()
            # 保存当前位置
            self.saved_position = self.pos()
            self.settings.setValue("window_position", self.saved_position)
            self.settings.setValue("window_size", self.size())
            if self.response_area.isVisible():
                self.saved_response_size = self.size()
                self.settings.setValue("response_window_size", self.saved_response_size)
            event.accept()

    def hideEvent(self, event):
        """窗口隐藏事件，保存位置"""
        app_log("hideEvent fired")
        self.deactivate_hide_timer.stop()
        self.saved_position = self.pos()
        self.settings.setValue("window_position", self.saved_position)
        self.settings.setValue("window_size", self.size())
        self.speech_recognizer.stop_listening()
        self.is_listening = False
        self.voice_icon.set_animating(False)
        self._is_window_shown = False  # 窗口隐藏时更新状态
        super().hideEvent(event)

    def toggle_voice_input(self):
        """切换语音输入状态"""
        if self.is_listening:
            self.stop_voice_input()
        else:
            self.start_listening()

    def stop_voice_input(self):
        """停止语音输入并提取文字"""
        if self.is_listening:
            self.voice_icon.set_animating(False)
            self.input_box.setPlaceholderText("正在识别中...")
            
            # 异步触发提取，不再阻塞 UI
            self.speech_recognizer.stop_and_recognize()
            
            self.is_listening = False
            self.update_status_bar("input")

    def cancel_voice_input(self):
        """强制取消录音（例如ESC直接退出丢弃音频）"""
        if self.is_listening:
            self.speech_recognizer.stop_listening()
            self.is_listening = False
            self.voice_icon.set_animating(False)
            self.input_box.setPlaceholderText("输入消息，按回车发送...")
            self.update_status_bar("input")

    def start_listening(self):
        """开始语音识别"""
        self.is_listening = True
        self.is_waiting_for_send = False
        self.voice_base_text = self.input_box.text().strip()
        self.input_box.setPlaceholderText("正在听你说话...")
        self.voice_icon.set_animating(True)
        self.update_status_bar("voice")
        self.speech_recognizer.start_listening()

    def on_speech_text_updated(self, text):
        """语音识别结果更新回调（支持流式实时替换与一次性 PTT 回调）"""
        if text:
            if self.voice_base_text:
                new_text = self.voice_base_text + " " + text
            else:
                current_text = self.input_box.text().strip()
                new_text = current_text + " " + text if current_text else text
            
            self.input_box.setText(new_text.strip())
            self.input_box.setCursorPosition(len(self.input_box.text()))
            
            if not self.is_listening:
                self.input_box.setPlaceholderText("按住 ⌥(Option) 键说话，或直接打字...")

    def on_enter_pressed(self):
        """回车键按下处理"""
        # 如果正在识别语音，先停止识别
        if self.is_listening:
            self.stop_voice_input()

        # 如果输入框有内容并且不是正在请求中，直接发送
        user_input = self.input_box.text().strip()
        if not user_input:
            return

        # 检查是否正在请求中
        if self.input_box.isEnabled() == False:
            return

        # 清空回复区域
        self.response_area.clear()
        self.assistant_response = ""

        # 添加到对话历史
        self.conversation_manager.add_user_message(user_input)

        # 禁用输入框，展示出回复框让大窗口展开
        self.input_box.setDisabled(True)
        self.input_box.setPlaceholderText("正在思考...")
        self.response_area.show()
        self._apply_response_size()
        self.start_loading_indicator()
        self.update_status_bar("hide")

        # 发送请求
        messages = self.conversation_manager.get_conversation()
        self.llm_client.chat(messages)

    def on_stream_received(self, content):
        """流式响应回调"""
        if self.is_waiting_for_response:
            self.stop_loading_indicator(clear_content=True)
        self.assistant_response += content
        self.pending_render_markdown = self.assistant_response
        if not self.response_render_timer.isActive():
            self.response_render_timer.start(self.render_update_interval_ms)

    def on_stream_complete(self, full_response):
        """流式响应完成回调"""
        if self.is_waiting_for_response:
            self.stop_loading_indicator(clear_content=True)
            if not full_response:
                full_response = "模型没有返回内容。"
                self.response_area.setPlainText(full_response)
            else:
                self.pending_render_markdown = full_response
                self.flush_pending_render()
        elif full_response:
            self.pending_render_markdown = full_response
            self.flush_pending_render()
        self.conversation_manager.add_assistant_message(full_response)
        self.input_box.setDisabled(False)
        self.input_box.clear()
        self.input_box.setPlaceholderText("输入消息，按回车发送...")
        self.is_waiting_for_send = True  # 允许直接发送下一条
        self.update_status_bar("response")

    def render_response_markdown(self, markdown_text, complete=True):
        """将回复内容渲染为 HTML，流式阶段也尽量保持 Markdown 外观"""
        self.response_area.setHtml(self._markdown_to_html(markdown_text))
        scroll_bar = self.response_area.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

    def flush_pending_render(self):
        """按节流后的频率刷新内容区，避免流式阶段频繁整页重绘"""
        if not self.pending_render_markdown:
            return
        self.render_response_markdown(self.pending_render_markdown, complete=False)

    def _markdown_to_html(self, markdown_text):
        self.code_blocks = {}
        normalized_markdown = self._normalize_markdown(markdown_text)
        body_html = self._render_markdown_with_code_blocks(normalized_markdown)
        return (
            "<html><head><style>"
            "body { color:#1D1D1F; font-family:'PingFang SC'; font-size:15px; line-height:1.65; }"
            "p { margin:6px 0; }"
            "h1,h2,h3,h4,h5,h6 { color:#111111; font-weight:700; margin:10px 0 6px 0; }"
            "ul,ol { margin:6px 0 6px 20px; }"
            "li { margin:3px 0; }"
            "blockquote { margin:8px 0; padding:2px 0 2px 10px; color:#5F6368; border-left:3px solid #D0D7E2; }"
            "pre { margin:0; white-space:pre-wrap; }"
            "code { background:#EEF2F7; padding:2px 5px; border-radius:6px; font-family:'SF Mono','Menlo',monospace; }"
            "a { color:#2B6CFA; text-decoration:none; }"
            f"{self.codehilite_css}"
            "</style></head><body>"
            f"{body_html}"
            "</body></html>"
        )

    def _normalize_markdown(self, markdown_text):
        normalized = markdown_text.replace("\r\n", "\n")
        normalized = re.sub(r"```c#\s*\n", "```csharp\n", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"```cs\s*\n", "```csharp\n", normalized, flags=re.IGNORECASE)
        if normalized.count("```") % 2 == 1:
            normalized += "\n```"
        return normalized

    def _render_markdown_with_code_blocks(self, markdown_text):
        parts = []
        cursor = 0
        pattern = re.compile(r"```([\w.+-]*)\n(.*?)```", re.DOTALL)

        for idx, match in enumerate(pattern.finditer(markdown_text)):
            text_part = markdown_text[cursor:match.start()]
            if text_part.strip():
                self.markdown_renderer.reset()
                parts.append(self.markdown_renderer.convert(text_part))

            language = (match.group(1) or "").strip()
            code = match.group(2).rstrip("\n")
            code_id = f"code-{idx}"
            self.code_blocks[code_id] = code
            parts.append(self._render_code_block(code, language, code_id))
            cursor = match.end()

        tail = markdown_text[cursor:]
        if tail.strip():
            self.markdown_renderer.reset()
            parts.append(self.markdown_renderer.convert(tail))

        return "".join(parts) or "<p></p>"

    def _render_code_block(self, code, language, code_id):
        lexer = self._get_code_lexer(language)
        highlighted = highlight(code, lexer, self.code_formatter)
        label = html.escape(language or "code")
        return (
            "<table cellspacing=\"0\" cellpadding=\"0\" "
            "style=\"width:100%; margin:10px 0; border:1px solid #D9DEE7; "
            "background:#FFFFFF; border-collapse:collapse;\">"
            "<tr>"
            "<td style=\"padding:10px 14px; background:#F6F7F9; border-bottom:1px solid #E6EAF0;\">"
            f"<span style=\"font-size:12px;font-weight:600;color:#2B2F36;font-family:'SF Mono','Menlo',monospace;\">{label}</span>"
            "</td>"
            "<td align=\"right\" style=\"padding:10px 14px; background:#F6F7F9; border-bottom:1px solid #E6EAF0;\">"
            f"<a href=\"copy://{code_id}\" style=\"font-size:12px;font-weight:600;color:#7A7F87; text-decoration:none;\">复制</a>"
            "</td>"
            "</tr>"
            "<tr>"
            "<td colspan=\"2\" style=\"padding:14px 16px; background:#FFFFFF;\">"
            f"<pre style=\"margin:0;white-space:pre-wrap;font-family:'SF Mono','Menlo',monospace;font-size:13px;line-height:1.6;\">{highlighted}</pre>"
            "</td>"
            "</tr>"
            "</table>"
        )

    def _get_code_lexer(self, language):
        lang = (language or "").strip().lower()
        aliases = {
            "c#": "csharp",
            "cs": "csharp",
            "js": "javascript",
            "ts": "typescript",
            "sh": "bash",
            "shell": "bash",
            "yml": "yaml",
        }
        lang = aliases.get(lang, lang)
        try:
            return get_lexer_by_name(lang) if lang else TextLexer()
        except Exception:
            return TextLexer()

    def _apply_compact_size(self):
        width = max(420, self.width())
        self.setMinimumHeight(self.COMPACT_HEIGHT)
        self.setMaximumHeight(self.COMPACT_HEIGHT)
        self.resize(width, self.COMPACT_HEIGHT)

    def _apply_response_size(self):
        target = self.saved_response_size if self.saved_response_size.isValid() else QSize(WINDOW_WIDTH, self.DEFAULT_RESPONSE_HEIGHT)
        width = max(420, self.width())
        height = max(self.DEFAULT_RESPONSE_HEIGHT, target.height())
        self.setMinimumHeight(self.COMPACT_HEIGHT)
        self.setMaximumHeight(16777215)
        self.resize(width, height)

    def start_loading_indicator(self):
        """显示模型回复等待态"""
        self.is_waiting_for_response = True
        self.loading_dots = 0
        self.update_loading_indicator()
        self.response_loading_timer.start(350)

    def stop_loading_indicator(self, clear_content=False):
        """关闭模型回复等待态"""
        self.response_loading_timer.stop()
        self.is_waiting_for_response = False
        self.loading_dots = 0
        if clear_content:
            self.response_area.clear()

    def update_loading_indicator(self):
        """更新内容区中的动态等待文案"""
        dots = "." * self.loading_dots
        self.response_area.setHtml(
            f"""
            <div style="color:#7A7A7A; font-size:14px; line-height:1.7; padding:8px 2px;">
                正在等待模型回复<span style="color:#2B6CFA;">{dots}</span>
            </div>
            """
        )
        self.loading_dots = (self.loading_dots + 1) % 4

    def copy_all_content(self):
        """复制所有返回内容"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.assistant_response)
        self.btn_copy.setText("已复制")
        QTimer.singleShot(2000, lambda: self.btn_copy.setText("复制"))

    def on_response_link_clicked(self, url):
        if url.scheme() == "copy":
            code = self.code_blocks.get(url.host() or url.path().lstrip("/"), "")
            if code:
                QApplication.clipboard().setText(code)
            return
        QDesktopServices.openUrl(url)

    def return_to_input(self):
        """返回到仅显示输入框的状态"""
        self.response_render_timer.stop()
        self.pending_render_markdown = ""
        self.response_area.hide()
        self.update_status_bar("input")
        self._apply_compact_size()
        self.input_box.clear()
        self.input_box.setFocus()

    def focus_input(self):
        """激活输入框"""
        self.input_box.setFocus()

    def keyPressEvent(self, event):
        """全局键盘事件"""
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_C:
            if self.response_area.isVisible() and not self.response_area.textCursor().hasSelection():
                self.copy_all_content()
                event.accept()
                return

        # macOS下的Option键 (Alt) 作为 PTT
        if event.key() == Qt.Key_Alt:
            if not event.isAutoRepeat():
                if not self.is_listening and not self.response_area.isVisible():
                    self.start_listening()
            event.accept()
            return

        if event.key() == Qt.Key_Escape:
            if self.is_listening:
                self.cancel_voice_input()
                event.accept()
                return

            if self.response_area.isVisible():
                self.return_to_input()
                event.accept()
                return
            else:
                # ESC键隐藏窗口
                self.hide_window()
                event.accept()
                return
                
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.response_area.isVisible():
                self.focus_input()
                
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """全局按键松开事件"""
        if event.key() == Qt.Key_Alt:
            if not event.isAutoRepeat():
                if self.is_listening:
                    self.stop_voice_input()
            event.accept()
            return
            
        super().keyReleaseEvent(event)

    def eventFilter(self, obj, event):
        """事件过滤器，用于拦截特定组件的事件"""
        if obj == self.response_area and event.type() == QEvent.KeyPress:
            if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_C:
                if not self.response_area.textCursor().hasSelection():
                    self.copy_all_content()
                    return True # 拦截事件
        if event.type() in (QEvent.MouseButtonPress, QEvent.MouseMove, QEvent.MouseButtonRelease):
            mapped_pos = self._map_event_pos_to_self(obj, event)
            if mapped_pos is not None:
                if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                    edges = self._get_resize_edges(mapped_pos)
                    if edges:
                        self.resize_edges = edges
                        self.resize_start_geometry = self.geometry()
                        self.resize_start_global_pos = event.globalPos()
                        event.accept()
                        return True
                elif event.type() == QEvent.MouseMove:
                    if event.buttons() & Qt.LeftButton and self.resize_edges:
                        self._resize_window(event.globalPos())
                        event.accept()
                        return True
                    self._update_cursor(mapped_pos)
                elif event.type() == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton and self.resize_edges:
                    self.resize_edges = 0
                    self.unsetCursor()
                    self.saved_position = self.pos()
                    self.settings.setValue("window_position", self.saved_position)
                    self.settings.setValue("window_size", self.size())
                    if self.response_area.isVisible():
                        self.saved_response_size = self.size()
                        self.settings.setValue("response_window_size", self.saved_response_size)
                    event.accept()
                    return True
        return super().eventFilter(obj, event)

    def event(self, event):
        """全局事件处理"""
        if event.type() == QEvent.WindowActivate:
            self._has_activated_since_show = True
            app_log(
                f"WindowActivate: shown={self._is_window_shown}, visible={self.isVisible()}"
            )
        return super().event(event)

    def _get_resize_edges(self, pos):
        rect = self.rect()
        edges = 0
        if pos.x() <= self.RESIZE_MARGIN:
            edges |= self.EDGE_LEFT
        elif pos.x() >= rect.width() - self.RESIZE_MARGIN:
            edges |= self.EDGE_RIGHT
        if self.response_area.isVisible():
            if pos.y() <= self.RESIZE_MARGIN:
                edges |= self.EDGE_TOP
            elif pos.y() >= rect.height() - self.RESIZE_MARGIN:
                edges |= self.EDGE_BOTTOM
        return edges

    def _update_cursor(self, pos):
        edges = self._get_resize_edges(pos)
        if edges in (self.EDGE_LEFT, self.EDGE_RIGHT):
            self.setCursor(Qt.SizeHorCursor)
        elif edges in (self.EDGE_TOP, self.EDGE_BOTTOM):
            self.setCursor(Qt.SizeVerCursor)
        elif edges in (self.EDGE_LEFT | self.EDGE_TOP, self.EDGE_RIGHT | self.EDGE_BOTTOM):
            self.setCursor(Qt.SizeFDiagCursor)
        elif edges in (self.EDGE_RIGHT | self.EDGE_TOP, self.EDGE_LEFT | self.EDGE_BOTTOM):
            self.setCursor(Qt.SizeBDiagCursor)
        else:
            self.unsetCursor()

    def _map_event_pos_to_self(self, obj, event):
        if not hasattr(event, "pos"):
            return None
        if obj is self:
            return event.pos()
        if hasattr(obj, "mapTo"):
            return obj.mapTo(self, event.pos())
        return None

    def _hide_if_inactive(self):
        """外部点击自动隐藏已禁用，避免影响热键再次呼出。"""
        app_log("_hide_if_inactive skipped because auto-hide-on-deactivate is disabled")

    def _resize_window(self, global_pos):
        delta = global_pos - self.resize_start_global_pos
        geom = QRect(self.resize_start_geometry)
        min_width = self.minimumWidth()
        min_height = self.minimumHeight()

        if self.resize_edges & self.EDGE_LEFT:
            new_left = min(geom.right() - min_width + 1, geom.left() + delta.x())
            geom.setLeft(new_left)
        if self.resize_edges & self.EDGE_RIGHT:
            geom.setRight(max(geom.left() + min_width - 1, geom.right() + delta.x()))
        if self.resize_edges & self.EDGE_TOP:
            new_top = min(geom.bottom() - min_height + 1, geom.top() + delta.y())
            geom.setTop(new_top)
        if self.resize_edges & self.EDGE_BOTTOM:
            geom.setBottom(max(geom.top() + min_height - 1, geom.bottom() + delta.y()))

        self.setGeometry(geom)
