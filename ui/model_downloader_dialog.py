from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QProgressBar
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QFont
import os
import sys
import re

class StderrInterceptor(QObject):
    progress_signal = pyqtSignal(int, str)
    
    def __init__(self, original_stderr):
        super().__init__()
        self._original = original_stderr
        
    def write(self, message):
        self._original.write(message)
        self._original.flush()
        match = re.search(r'(\d+)%\|', message)
        if match:
            percent = int(match.group(1))
            self.progress_signal.emit(percent, message.strip())
            
    def flush(self):
        self._original.flush()

# ONNX 模型列表（与 Vocotype 完全一致）
ONNX_MODELS = [
    "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-onnx",
    "iic/punc_ct-transformer_zh-cn-common-vocab272727-onnx",
]
MODEL_REVISION = "v2.0.5"

class ModelDownloadThread(QThread):
    progress_text = pyqtSignal(str)
    finished = pyqtSignal(bool)
    
    def run(self):
        try:
            from modelscope.hub.snapshot_download import snapshot_download
            for model_name in ONNX_MODELS:
                short_name = model_name.split("/")[-1]
                self.progress_text.emit(f"正在下载: {short_name}")
                snapshot_download(model_name, revision=MODEL_REVISION)
            self.finished.emit(True)
        except Exception as e:
            print(f"Error downloading ONNX models: {e}")
            self.finished.emit(False)

class ModelDownloaderDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("语音引擎初始化")
        self.setFixedSize(520, 280)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
                border: 1px solid #DDDDDD;
                border-radius: 10px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)

        self.title_label = QLabel("🚀 首次配置：ONNX 极速语音引擎")
        self.title_label.setFont(QFont("PingFang SC", 18, QFont.Bold))
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)

        self.info_label = QLabel("需要从 ModelScope 下载 ONNX 模型文件（约 1GB）。\n\n这些模型使用 ONNX Runtime 进行推理，比 PyTorch 快 3~10 倍。\n此过程只需进行一次，是否立即开始？")
        self.info_label.setFont(QFont("PingFang SC", 14))
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #666666; line-height: 1.5;")
        layout.addWidget(self.info_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        self.detail_label = QLabel("")
        self.detail_label.setFont(QFont("PingFang SC", 12))
        self.detail_label.setStyleSheet("color: #999999;")
        self.detail_label.hide()
        layout.addWidget(self.detail_label)

        self.btn_layout = QHBoxLayout()
        self.btn_layout.setSpacing(15)
        
        self.btn_cancel = QPushButton("退出应用 (Esc)")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #F0F0F0;
                color: #555555;
                border-radius: 6px;
                padding: 10px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #E5E5E5; }
        """)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_ok = QPushButton("开启极速体验 (Enter)")
        self.btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #007AFF;
                color: white;
                border-radius: 6px;
                padding: 10px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #0066CC; }
        """)
        self.btn_ok.clicked.connect(self.start_download)

        self.btn_layout.addWidget(self.btn_cancel)
        self.btn_layout.addWidget(self.btn_ok)
        layout.addLayout(self.btn_layout)

        self.thread = None

    def start_download(self):
        self.info_label.setText("正在连接 ModelScope 下载 ONNX 模型...")
        self.btn_cancel.setEnabled(False)
        self.btn_ok.hide()
        self.progress_bar.show()
        self.detail_label.show()

        self.interceptor = StderrInterceptor(sys.stderr)
        self.interceptor.progress_signal.connect(self.update_progress)
        sys.stderr = self.interceptor

        self.thread = ModelDownloadThread()
        self.thread.progress_text.connect(lambda t: self.detail_label.setText(t))
        self.thread.finished.connect(self.on_download_finished)
        self.thread.start()

    def update_progress(self, percent, detail_text):
        self.progress_bar.setValue(percent)
        match = re.search(r'\|\s*([^|]+)$', detail_text)
        if match:
            self.detail_label.setText("下载详情: " + match.group(1).strip())

    def on_download_finished(self, success):
        if hasattr(self, 'interceptor'):
            sys.stderr = self.interceptor._original
            
        self.progress_bar.hide()
        self.detail_label.hide()
        if success:
            self.accept()
        else:
            self.info_label.setText("下载或加载失败，请检查网络连接后重试。")
            self.btn_cancel.setEnabled(True)
            self.btn_cancel.setText("关闭")

    @staticmethod
    def check_and_download():
        """检查所有 ONNX 模型是否已完整下载（检查实际的 .onnx 文件）"""
        all_ready = True
        for model_name in ONNX_MODELS:
            model_dir = os.path.expanduser(
                f"~/.cache/modelscope/hub/models/{model_name}"
            )
            # 检查目录内是否存在实际的 onnx 模型文件
            quant_file = os.path.join(model_dir, "model_quant.onnx")
            base_file = os.path.join(model_dir, "model.onnx")
            if not os.path.exists(quant_file) and not os.path.exists(base_file):
                all_ready = False
                break
        
        if not all_ready:
            dialog = ModelDownloaderDialog()
            result = dialog.exec_()
            if result != QDialog.Accepted:
                sys.exit(0)
