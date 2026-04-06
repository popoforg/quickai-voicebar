#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

# ONNX Runtime 推理优化：多线程并行
os.environ.setdefault("OMP_NUM_THREADS", "8")

import logging
logging.getLogger("funasr").setLevel(logging.ERROR)

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QMessageBox
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from ui.main_window import MainWindow
from ui.settings_window import SettingsWindow
from core.hotkey_listener import HotkeyListener
from core.speech_recognizer import SpeechRecognizer
from core.llm_client import LLMClient
from core.conversation_manager import ConversationManager

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("QuickAI")
    app.setApplicationVersion("1.0.0")
    # 关闭窗口不退出程序，保持在菜单栏运行
    app.setQuitOnLastWindowClosed(False)

    # 检查并下载离线加速引擎模型
    from ui.model_downloader_dialog import ModelDownloaderDialog
    ModelDownloaderDialog.check_and_download()

    # 初始化各个模块
    conversation_manager = ConversationManager()

    # 语音识别器
    speech_recognizer = SpeechRecognizer(
        text_update_callback=lambda text: None  # 后面会绑定到窗口
    )

    # LLM客户端
    llm_client = LLMClient(
        stream_callback=lambda content: None,
        complete_callback=lambda response: None
    )

    # 主窗口
    window = MainWindow(
        speech_recognizer=speech_recognizer,
        llm_client=llm_client,
        conversation_manager=conversation_manager
    )

    # 绑定回调（通过信号发射，避免跨线程操作UI）
    speech_recognizer.text_update_callback = lambda text: window.signal_emitter.speech_text_updated.emit(text)
    llm_client.stream_callback = lambda content: window.signal_emitter.stream_received.emit(content)
    llm_client.complete_callback = lambda response: window.signal_emitter.stream_complete.emit(response)

    # 创建带"Q"字的菜单栏图标
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # 绘制圆形背景
    painter.setBrush(QColor(0, 122, 255))  # 蓝色背景
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, 32, 32)

    # 绘制Q字符
    painter.setPen(QColor(255, 255, 255))  # 白色文字
    font = QFont("Arial", 20, QFont.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "Q")
    painter.end()

    tray_icon = QSystemTrayIcon(QIcon(pixmap), app)
    tray_icon.setToolTip("QuickAI")

    # 创建设置窗口实例
    settings_window = SettingsWindow()

    # 创建菜单栏菜单
    tray_menu = QMenu()
    show_action = QAction("显示/隐藏窗口", tray_menu)
    show_action.triggered.connect(window.toggle_visibility)
    settings_action = QAction("设置", tray_menu)

    def open_settings():
        settings_window.show()
        settings_window.raise_()
        settings_window.activateWindow()

    settings_action.triggered.connect(open_settings)
    quit_action = QAction("退出", tray_menu)
    quit_action.triggered.connect(app.quit)

    tray_menu.addAction(show_action)
    tray_menu.addAction(settings_action)
    tray_menu.addSeparator()
    tray_menu.addAction(quit_action)

    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()

    # 左键点击菜单栏图标也能触发显示/隐藏
    def on_tray_icon_activated(reason):
        if reason == QSystemTrayIcon.Trigger:  # 左键点击
            window.toggle_visibility()

    tray_icon.activated.connect(on_tray_icon_activated)

    # 快捷键监听器
    hotkey_listener = HotkeyListener(
        toggle_window_callback=lambda: window.signal_emitter.toggle_window.emit()
    )
    hotkey_listener.start()

    def notify_hotkey_permission_problem():
        if not hotkey_listener.start_error:
            return
        QMessageBox.warning(
            None,
            "全局快捷键不可用",
            "当前应用没有拿到 macOS 辅助功能权限，所以双击 Ctrl 无法呼出。\n\n"
            "请到 系统设置 -> 隐私与安全性 -> 辅助功能，删除旧的 QuickAI 记录后，重新添加当前 dist/QuickAI.app 并开启权限，然后重启应用。"
        )

    QTimer.singleShot(1200, notify_hotkey_permission_problem)

    print("="*50)
    print("QuickAI 已启动!")
    print("快捷键: Ctrl 双击 或 Ctrl+Shift+A 呼出/隐藏窗口")
    print("ESC键: 隐藏窗口")
    print("="*50)
    print("\n首次使用提示:")
    print("1. 请在系统偏好设置 > 安全性与隐私 > 隐私 > 辅助功能 中为终端/Python授予权限")
    print("2. 请在系统偏好设置 > 安全性与隐私 > 隐私 > 麦克风 中为终端/Python授予权限")
    print("3. 确保LMStudio已启动并开启API服务")

    # 启动时默认隐藏窗口，等待快捷键或菜单操作
    # window.show_animated()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
