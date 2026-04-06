# QuickAI Voicebar

一个 macOS 上的轻量级 AI 对话浮窗。通过全局快捷键呼出，支持按住说话、实时转写、Markdown 渲染和 LM Studio 本地模型流式回复。

## 特性

- 全局快捷键唤醒，像 Spotlight 一样随时呼出
- 按住 `Option` 说话，松开后自动识别
- 支持键盘输入和多轮对话
- 支持 Markdown 渲染、代码高亮和代码块复制
- 托盘常驻运行，支持设置窗口和自定义快捷键
- 可打包为独立 `.app`

## 环境要求

- macOS
- Python 3.14
- LM Studio 已启动并开启本地 API
- 已授予麦克风和辅助功能权限

## 安装

```bash
brew install portaudio

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 运行

```bash
source venv/bin/activate
python main.py
```

## 使用方式

1. 按全局快捷键呼出对话窗口。
2. 直接输入内容，或按住 `Option` 开始说话。
3. 松开 `Option` 完成识别。
4. 按 `Enter` 发送给 LM Studio。
5. 回复会以流式方式显示在内容区。

## 权限配置

首次运行需要在系统设置中授权：

- 麦克风：用于语音识别
- 辅助功能：用于全局快捷键监听

如果你运行的是打包后的 `.app`，需要给 `.app` 本身授权，而不是给终端授权。

## 主要配置

配置文件在 [config.py](/Users/rb/Documents/AIProjects/quickai-minimax/config.py)。

- `HOTKEY_MODIFIERS` / `HOTKEY_KEY`: 全局快捷键
- `LMSTUDIO_API_BASE`: LM Studio API 地址
- `LMSTUDIO_MODEL`: 默认模型名
- `STRIP_TRAILING_PERIOD`: 去掉结尾句号
- `FILTER_FILLER_WORDS`: 过滤“嗯”“啊”等语气词

## 打包

项目当前使用 PyInstaller 打包：

```bash
PYINSTALLER_CONFIG_DIR=.pyinstaller-cache venv/bin/pyinstaller -y QuickAI.spec
```

产物位于：

```bash
dist/QuickAI.app
```

## 常见问题

- 快捷键没反应：确认辅助功能权限已经给到终端或 `.app`
- 打包后不能录音：确认 `.app` 已获得麦克风权限
- 没有模型回复：确认 LM Studio 已启动并开启 API
