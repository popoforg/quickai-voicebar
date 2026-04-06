# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'funasr_onnx.paraformer_bin',
        'funasr_onnx.punc_bin',
        'funasr_onnx.utils',
        'funasr_onnx.utils.frontend',
        'funasr_onnx.utils.postprocess_utils',
        'funasr_onnx.utils.sentencepiece_tokenizer',
        'funasr_onnx.utils.utils',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # This app uses ONNX inference at runtime. Exclude unused PyTorch/FunASR
    # packages so a dirty venv does not pull hundreds of MB into the bundle.
    excludes=[
        'funasr',
        'torch',
        'torchaudio',
        'torchvision',
        'torchgen',
        'pytorch_wpe',
        'torch_complex',
        'tensorboardX',
        'sklearn',
        'scikit_learn',
        'umap',
        'umap_learn',
        'pynndescent',
        'numba',
        'llvmlite',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='QuickAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='QuickAI',
)
app = BUNDLE(
    coll,
    name='QuickAI.app',
    icon='assets/quickai-voicebar.icns',
    bundle_identifier='com.quickai.minimax',
    info_plist={
        'CFBundleDisplayName': 'QuickAI',
        'NSMicrophoneUsageDescription': 'QuickAI 需要访问麦克风来进行按住说话的语音识别。',
    },
)
