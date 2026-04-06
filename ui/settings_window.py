from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QDoubleSpinBox, QComboBox, QMessageBox,
    QWidget, QScrollArea, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QSize, QPropertyAnimation, QRect, pyqtProperty
from PyQt5.QtGui import QFont, QPainter, QColor, QPen, QPainterPath
import requests
import config


class ToggleSwitch(QWidget):
    """iOS 风格的开关控件"""
    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setFixedSize(51, 31)
        self.setCursor(Qt.PointingHandCursor)
        self._checked = checked
        self._handle_pos = 21.0 if checked else 2.0
        self._bg_color = QColor("#34C759") if checked else QColor("#E9E9EA")
        
    @pyqtProperty(float)
    def handlePos(self):
        return self._handle_pos
    
    @handlePos.setter
    def handlePos(self, val):
        self._handle_pos = val
        self.update()

    def isChecked(self):
        return self._checked
    
    def setChecked(self, checked):
        self._checked = checked
        self._animate(checked)

    def _animate(self, checked):
        anim = QPropertyAnimation(self, b"handlePos")
        anim.setDuration(180)
        anim.setStartValue(self._handle_pos)
        anim.setEndValue(21.0 if checked else 2.0)
        anim.start()
        self._anim = anim  # prevent GC
        self._bg_color = QColor("#34C759") if checked else QColor("#E9E9EA")
        self.update()

    def mousePressEvent(self, event):
        self._checked = not self._checked
        self._animate(self._checked)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # Track
        track = QPainterPath()
        track.addRoundedRect(0, 0, 51, 31, 15.5, 15.5)
        target_color = QColor("#34C759") if self._checked else QColor("#E9E9EA")
        self._bg_color = target_color
        p.fillPath(track, self._bg_color)
        # Handle
        p.setBrush(QColor("white"))
        p.setPen(QPen(QColor(0, 0, 0, 15), 0.5))
        p.drawEllipse(int(self._handle_pos), 2, 27, 27)
        p.end()


def _make_section_title(text):
    label = QLabel(text)
    label.setFont(QFont("PingFang SC", 13, QFont.DemiBold))
    label.setStyleSheet("color: #86868B; padding-left: 16px; padding-bottom: 2px; background: transparent;")
    return label


def _make_card():
    """创建一个现代卡片容器"""
    card = QWidget()
    card.setStyleSheet("""
        QWidget {
            background-color: white;
            border-radius: 12px;
        }
    """)
    return card


def _make_row_widget(title_text, desc_text=None, right_widget=None):
    """创建一个带标题、描述、右侧控件的卡片行"""
    row = QWidget()
    row.setStyleSheet("background: transparent;")
    h = QHBoxLayout(row)
    h.setContentsMargins(16, 12, 16, 12)
    h.setSpacing(12)

    left = QVBoxLayout()
    left.setSpacing(2)
    title = QLabel(title_text)
    title.setFont(QFont("PingFang SC", 14))
    title.setStyleSheet("color: #1D1D1F; background: transparent;")
    left.addWidget(title)
    if desc_text:
        desc = QLabel(desc_text)
        desc.setFont(QFont("PingFang SC", 12))
        desc.setStyleSheet("color: #86868B; background: transparent;")
        desc.setWordWrap(True)
        left.addWidget(desc)
    h.addLayout(left, 1)

    if right_widget:
        right_widget.setStyleSheet(right_widget.styleSheet() + "background: transparent;")
        h.addWidget(right_widget, 0, Qt.AlignRight | Qt.AlignVCenter)
    
    return row


def _make_separator():
    sep = QFrame()
    sep.setFrameShape(QFrame.HLine)
    sep.setStyleSheet("background-color: #F2F2F7; border: none; max-height: 1px; margin-left: 16px; margin-right: 16px;")
    return sep


class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QuickAI 设置")
        self.setFixedSize(560, 620)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.init_ui()
        self.load_current_config()

    def init_ui(self):
        # 全局背景色
        self.setStyleSheet("""
            QDialog { background-color: #F2F2F7; }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                border: 1px solid #E5E5EA;
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 13px;
                background-color: #F9F9FB;
                min-height: 28px;
            }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
                border-color: #007AFF;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # ==================== 语音识别 ====================
        layout.addWidget(_make_section_title("语音识别"))

        voice_card = _make_card()
        voice_layout = QVBoxLayout(voice_card)
        voice_layout.setContentsMargins(0, 4, 0, 4)
        voice_layout.setSpacing(0)

        self.toggle_strip_period = ToggleSwitch(checked=getattr(config, 'STRIP_TRAILING_PERIOD', True))
        voice_layout.addWidget(_make_row_widget(
            "删除结尾句号",
            '开启后，转录结果会自动删除结尾的句号（包括中文"。"和英文"."）。',
            self.toggle_strip_period
        ))

        voice_layout.addWidget(_make_separator())

        self.toggle_filter_filler = ToggleSwitch(checked=getattr(config, 'FILTER_FILLER_WORDS', False))
        voice_layout.addWidget(_make_row_widget(
            "过滤语气词",
            '自动删除"嗯"、"啊"等语音输入中的语气词。',
            self.toggle_filter_filler
        ))

        layout.addWidget(voice_card)

        # ==================== LLM 模型 ====================
        layout.addWidget(_make_section_title("LLM 模型"))

        llm_card = _make_card()
        llm_layout = QVBoxLayout(llm_card)
        llm_layout.setContentsMargins(16, 12, 16, 12)
        llm_layout.setSpacing(10)

        # API 地址
        api_title = QLabel("API 地址")
        api_title.setFont(QFont("PingFang SC", 13))
        api_title.setStyleSheet("color: #1D1D1F; background: transparent;")
        llm_layout.addWidget(api_title)

        api_row = QHBoxLayout()
        api_row.setSpacing(8)
        self.api_base_input = QLineEdit()
        self.api_base_input.setPlaceholderText("http://localhost:1234/v1")
        api_row.addWidget(self.api_base_input)

        self.test_connection_btn = QPushButton("检测")
        self.test_connection_btn.clicked.connect(self.test_lmstudio_connection)
        self.test_connection_btn.setFixedWidth(60)
        self.test_connection_btn.setStyleSheet("""
            QPushButton {
                background-color: #34C759; color: white; border: none;
                border-radius: 8px; padding: 7px 0; font-size: 13px; font-weight: 500;
            }
            QPushButton:hover { background-color: #2DB84E; }
        """)
        api_row.addWidget(self.test_connection_btn)
        llm_layout.addLayout(api_row)

        # 模型名称
        model_title = QLabel("模型")
        model_title.setFont(QFont("PingFang SC", 13))
        model_title.setStyleSheet("color: #1D1D1F; background: transparent;")
        llm_layout.addWidget(model_title)

        model_row = QHBoxLayout()
        model_row.setSpacing(8)
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        model_row.addWidget(self.model_combo)

        self.refresh_models_btn = QPushButton("读取")
        self.refresh_models_btn.clicked.connect(self.load_lmstudio_models)
        self.refresh_models_btn.setFixedWidth(60)
        self.refresh_models_btn.setStyleSheet("""
            QPushButton {
                background-color: #007AFF; color: white; border: none;
                border-radius: 8px; padding: 7px 0; font-size: 13px; font-weight: 500;
            }
            QPushButton:hover { background-color: #0066CC; }
        """)
        model_row.addWidget(self.refresh_models_btn)
        llm_layout.addLayout(model_row)

        # Temperature + Max Tokens 并排
        param_row = QHBoxLayout()
        param_row.setSpacing(12)

        temp_col = QVBoxLayout()
        temp_col.setSpacing(4)
        temp_label = QLabel("Temperature")
        temp_label.setFont(QFont("PingFang SC", 13))
        temp_label.setStyleSheet("color: #1D1D1F; background: transparent;")
        temp_col.addWidget(temp_label)
        self.temperature_input = QDoubleSpinBox()
        self.temperature_input.setRange(0, 2)
        self.temperature_input.setSingleStep(0.1)
        temp_col.addWidget(self.temperature_input)
        param_row.addLayout(temp_col)

        tokens_col = QVBoxLayout()
        tokens_col.setSpacing(4)
        tokens_label = QLabel("最大生成长度")
        tokens_label.setFont(QFont("PingFang SC", 13))
        tokens_label.setStyleSheet("color: #1D1D1F; background: transparent;")
        tokens_col.addWidget(tokens_label)
        self.max_tokens_input = QSpinBox()
        self.max_tokens_input.setRange(100, 8000)
        self.max_tokens_input.setSingleStep(100)
        tokens_col.addWidget(self.max_tokens_input)
        param_row.addLayout(tokens_col)

        llm_layout.addLayout(param_row)
        layout.addWidget(llm_card)

        # ==================== 快捷键 ====================
        layout.addWidget(_make_section_title("快捷键"))

        hotkey_card = _make_card()
        hotkey_layout = QVBoxLayout(hotkey_card)
        hotkey_layout.setContentsMargins(16, 12, 16, 12)
        hotkey_layout.setSpacing(8)

        hotkey_title = QLabel("全局唤醒快捷键")
        hotkey_title.setFont(QFont("PingFang SC", 13))
        hotkey_title.setStyleSheet("color: #1D1D1F; background: transparent;")
        hotkey_layout.addWidget(hotkey_title)

        hotkey_desc = QLabel("点击下方输入框，然后按下你想设置的快捷键组合。")
        hotkey_desc.setFont(QFont("PingFang SC", 12))
        hotkey_desc.setStyleSheet("color: #86868B; background: transparent;")
        hotkey_layout.addWidget(hotkey_desc)

        self.hotkey_input = QLineEdit()
        self.hotkey_input.setPlaceholderText("点击录制快捷键")
        self.hotkey_input.setReadOnly(True)
        self.hotkey_input.installEventFilter(self)
        self.is_recording_hotkey = False
        self.recorded_modifiers = set()
        self.recorded_key = ""
        hotkey_layout.addWidget(self.hotkey_input)

        layout.addWidget(hotkey_card)

        # ==================== 底部按钮 ====================
        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        btn_row.addStretch()

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setFixedHeight(36)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: white; color: #1D1D1F; border: 1px solid #D1D1D6;
                border-radius: 8px; padding: 0 24px; font-size: 14px;
            }
            QPushButton:hover { background-color: #F5F5F7; }
        """)
        btn_row.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("保存设置")
        self.save_btn.clicked.connect(self.save_config)
        self.save_btn.setFixedHeight(36)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #007AFF; color: white; border: none;
                border-radius: 8px; padding: 0 24px; font-size: 14px; font-weight: 500;
            }
            QPushButton:hover { background-color: #0066CC; }
        """)
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        scroll.setWidget(content)
        root.addWidget(scroll)

    def load_current_config(self):
        self.api_base_input.setText(config.LMSTUDIO_API_BASE)
        self.model_combo.addItem(config.LMSTUDIO_MODEL)
        self.model_combo.setCurrentText(config.LMSTUDIO_MODEL)
        self.temperature_input.setValue(config.LMSTUDIO_TEMPERATURE)
        self.max_tokens_input.setValue(config.LMSTUDIO_MAX_TOKENS)
        current_hotkey = "+".join([mod.capitalize() for mod in config.HOTKEY_MODIFIERS] + [config.HOTKEY_KEY.upper()])
        self.hotkey_input.setText(current_hotkey)
        self.toggle_strip_period.setChecked(getattr(config, 'STRIP_TRAILING_PERIOD', True))
        self.toggle_filter_filler.setChecked(getattr(config, 'FILTER_FILLER_WORDS', False))

    def load_lmstudio_models(self):
        api_base = self.api_base_input.text().strip()
        if not api_base:
            QMessageBox.warning(self, "提示", "请先填写LMStudio API地址")
            return
        try:
            self.refresh_models_btn.setText("...")
            self.refresh_models_btn.setDisabled(True)
            response = requests.get(f"{api_base}/models", timeout=10)
            response.raise_for_status()
            data = response.json()
            models = data.get('data', [])
            if not models:
                QMessageBox.information(self, "提示", "未找到可用模型")
                return
            self.model_combo.clear()
            for model in models:
                model_id = model.get('id', '')
                if model_id:
                    self.model_combo.addItem(model_id)
            QMessageBox.information(self, "成功", f"读取到 {len(models)} 个模型")
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "错误", f"读取失败：{str(e)}")
        finally:
            self.refresh_models_btn.setText("读取")
            self.refresh_models_btn.setDisabled(False)

    def test_lmstudio_connection(self):
        api_base = self.api_base_input.text().strip()
        model = self.model_combo.currentText().strip()
        if not api_base:
            QMessageBox.warning(self, "提示", "请先填写API地址")
            return
        if not model:
            QMessageBox.warning(self, "提示", "请先选择模型")
            return
        try:
            self.test_connection_btn.setText("...")
            self.test_connection_btn.setDisabled(True)
            headers = {"Content-Type": "application/json"}
            payload = {"model": model, "messages": [{"role": "user", "content": "hi"}], "stream": False, "max_tokens": 10}
            response = requests.post(f"{api_base}/chat/completions", headers=headers, json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
            if 'choices' in data and len(data['choices']) > 0:
                QMessageBox.information(self, "✅ 连接成功", "LMStudio 模型响应正常！")
            else:
                QMessageBox.warning(self, "⚠️ 异常", "连接成功但返回数据异常")
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "❌ 失败", f"检测失败：{str(e)}")
        finally:
            self.test_connection_btn.setText("检测")
            self.test_connection_btn.setDisabled(False)

    def eventFilter(self, obj, event):
        if obj == self.hotkey_input and event.type() == event.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                self.start_hotkey_recording()
                return True
        return super().eventFilter(obj, event)

    def start_hotkey_recording(self):
        self.is_recording_hotkey = True
        self.recorded_modifiers = set()
        self.recorded_key = ""
        self.hotkey_input.setText("请按下快捷键组合...")
        self.hotkey_input.setStyleSheet("""
            QLineEdit { border: 2px solid #007AFF; background-color: rgba(0,122,255,0.06); border-radius: 8px; padding: 6px 10px; font-size: 13px; }
        """)

    def stop_hotkey_recording(self):
        self.is_recording_hotkey = False
        self.hotkey_input.setStyleSheet("")  # restore to global

    def keyPressEvent(self, event):
        if not self.is_recording_hotkey:
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key_Escape:
            self.stop_hotkey_recording()
            current_hotkey = "+".join([mod.capitalize() for mod in config.HOTKEY_MODIFIERS] + [config.HOTKEY_KEY.upper()])
            self.hotkey_input.setText(current_hotkey)
            return
        modifiers = event.modifiers()
        self.recorded_modifiers = set()
        if modifiers & Qt.ControlModifier: self.recorded_modifiers.add('ctrl')
        if modifiers & Qt.ShiftModifier: self.recorded_modifiers.add('shift')
        if modifiers & Qt.AltModifier: self.recorded_modifiers.add('alt')
        if modifiers & Qt.MetaModifier: self.recorded_modifiers.add('cmd')
        key = event.key()
        if Qt.Key_A <= key <= Qt.Key_Z or Qt.Key_0 <= key <= Qt.Key_9:
            self.recorded_key = chr(key).lower()
            if self.recorded_modifiers and self.recorded_key:
                hotkey_str = "+".join([mod.capitalize() for mod in sorted(self.recorded_modifiers)] + [self.recorded_key.upper()])
                self.hotkey_input.setText(hotkey_str)
                self.stop_hotkey_recording()
        else:
            mod_str = "+".join([mod.capitalize() for mod in sorted(self.recorded_modifiers)])
            self.hotkey_input.setText(f"{mod_str}+..." if mod_str else "请按下快捷键组合...")
        event.accept()

    def save_config(self):
        if self.recorded_modifiers and self.recorded_key:
            modifiers = list(self.recorded_modifiers)
            key = self.recorded_key
        else:
            modifiers = config.HOTKEY_MODIFIERS
            key = config.HOTKEY_KEY

        strip_period = self.toggle_strip_period.isChecked()
        filter_filler = self.toggle_filter_filler.isChecked()

        new_config = f'''# 配置文件

# 全局快捷键配置
HOTKEY_MODIFIERS = {modifiers}
HOTKEY_KEY = '{key}'

# LMStudio API配置
LMSTUDIO_API_BASE = "{self.api_base_input.text().strip()}"
LMSTUDIO_MODEL = "{self.model_combo.currentText().strip()}"
LMSTUDIO_TEMPERATURE = {self.temperature_input.value()}
LMSTUDIO_MAX_TOKENS = {self.max_tokens_input.value()}

# 语音识别配置
SPEECH_LANGUAGE = 'zh-CN'
PHRASE_TIME_LIMIT = 2
STRIP_TRAILING_PERIOD = {strip_period}
FILTER_FILLER_WORDS = {filter_filler}

# 界面配置
WINDOW_WIDTH = 600
WINDOW_HEIGHT = 400
WINDOW_OPACITY = 0.95

# 对话配置
MAX_HISTORY_LENGTH = 10
'''
        config_path = config.__file__
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(new_config)

        # 直接更新内存中的 config 属性（不用 reload，避免闪退）
        config.HOTKEY_MODIFIERS = modifiers
        config.HOTKEY_KEY = key
        config.LMSTUDIO_API_BASE = self.api_base_input.text().strip()
        config.LMSTUDIO_MODEL = self.model_combo.currentText().strip()
        config.LMSTUDIO_TEMPERATURE = self.temperature_input.value()
        config.LMSTUDIO_MAX_TOKENS = self.max_tokens_input.value()
        config.STRIP_TRAILING_PERIOD = strip_period
        config.FILTER_FILLER_WORDS = filter_filler

        self.accept()
