# QuickAI Voicebar

一个 macOS 上的轻量级 AI 对话浮窗。通过全局快捷键呼出，支持按住说话、实时转写、Markdown 渲染和 LM Studio 本地模型流式回复。

## 特性

- 支持双击 `Ctrl` 呼出/隐藏窗口
- 同时支持 `Ctrl+Shift+A` 呼出/隐藏窗口
- 按住 `Option` 说话，松开后自动识别
- 支持键盘输入和多轮对话
- 支持 Markdown 渲染、代码高亮和代码块复制
- 点击窗口外部可自动隐藏
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

建议使用全新的虚拟环境，不要复用装过 `funasr`、`torch`、`torchaudio` 的旧环境，否则 PyInstaller 很容易把这批大型依赖一起打进 `.app`。

如果你要重新打包，建议单独准备一个干净的构建环境，例如：

```bash
python3 -m venv venv-build
source venv-build/bin/activate
pip install -r requirements.txt
```

## 运行

```bash
source venv/bin/activate
python main.py
```

## 使用方式

1. 双击 `Ctrl`，或按 `Ctrl+Shift+A` 呼出对话窗口。
2. 直接输入内容，或按住 `Option` 开始说话。
3. 松开 `Option` 完成识别。
4. 按 `Enter` 发送给 LM Studio。
5. 回复会以流式方式显示在内容区。
6. 点击窗口外部可隐藏窗口，再次双击 `Ctrl` 可重新呼出。

## 权限配置

首次运行需要在系统设置中授权：

- 麦克风：用于语音识别
- 辅助功能：用于全局快捷键监听

如果你运行的是打包后的 `.app`，需要给 `.app` 本身授权，而不是给终端授权。

如果重打包后热键突然失效，通常是 macOS 把新包视为新的应用实例。此时请到“辅助功能”里删除旧的 `QuickAI` 记录，再重新添加当前的 `dist/QuickAI.app`。

## 主要配置

配置文件在 [config.py](/Users/rb/Documents/AIProjects/quickai-voicebar/config.py)。

- `HOTKEY_MODIFIERS` / `HOTKEY_KEY`: 全局快捷键
- `LMSTUDIO_API_BASE`: LM Studio API 地址
- `LMSTUDIO_MODEL`: 默认模型名
- `STRIP_TRAILING_PERIOD`: 去掉结尾句号
- `FILTER_FILLER_WORDS`: 过滤“嗯”“啊”等语气词

## 打包

项目当前使用 PyInstaller 打包：

```bash
PYINSTALLER_CONFIG_DIR=.pyinstaller-cache venv-build/bin/pyinstaller -y QuickAI.spec
```

产物位于：

```bash
dist/QuickAI.app
```

当前包体积约为 `250MB`。如果打包出来体积异常大，先确认当前环境里没有额外安装 `funasr`、`torch`、`torchaudio`。这个项目运行语音识别用的是 `funasr_onnx` + `onnxruntime`，不是 PyTorch。

## 常见问题

- 快捷键没反应：确认辅助功能权限已经给到终端或 `.app`；如果是新打包的 `.app`，先删除系统里旧的 `QuickAI` 授权再重新添加
- 打包后不能录音：确认 `.app` 已获得麦克风权限
- 没有模型回复：确认 LM Studio 已启动并开启 API
- 打包后语音识别缺依赖：确认使用的是当前仓库内置的 `funasr_onnx`，并使用干净的构建环境重新打包
