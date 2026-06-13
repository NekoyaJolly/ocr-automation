# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_all

# データファイルの定義 (プロジェクトルートからの相対パス)
# spec ファイルが build/ ディレクトリにあるため、../ を使用
datas = [
    ('../templates', 'templates'),
    ('../template_sets', 'template_sets'),
]

# NDL OCR Lite のソースコードのみをコピーし、.onnx モデルファイルは除外する
ndl_src = os.path.abspath(os.path.join(SPECPATH, '../vendor/ndlocr_lite/src'))
for root, dirs, files in os.walk(ndl_src):
    for file in files:
        if file.endswith('.onnx'):
            continue
        full_path = os.path.join(root, file)
        # vendor/ndlocr_lite/src からの相対ディレクトリを計算
        rel_dir = os.path.relpath(root, ndl_src)
        if rel_dir == '.':
            dest_dir = 'vendor/ndlocr_lite/src'
        else:
            dest_dir = os.path.join('vendor/ndlocr_lite/src', rel_dir)
        datas.append((full_path, dest_dir))

# 主要なサードパーティライブラリのリソースとインポートを強制収集 (PySide6 以外)
onnx_datas, onnx_binaries, onnx_hiddenimports = collect_all('onnxruntime')
pil_datas, pil_binaries, pil_hiddenimports = collect_all('PIL')
yaml_datas, yaml_binaries, yaml_hiddenimports = collect_all('yaml')

datas.extend(onnx_datas)
datas.extend(pil_datas)
datas.extend(yaml_datas)

binaries = []
binaries.extend(onnx_binaries)
binaries.extend(pil_binaries)
binaries.extend(yaml_binaries)

hiddenimports = [
    'onnxruntime',
    'PIL',
    'numpy',
    'cv2',
    'lxml',
    'networkx',
    'ordered_set',
    'pyparsing',
    'tqdm',
    'dill',
    'yaml',
    'pydantic',
    'watchdog',
]
hiddenimports.extend(onnx_hiddenimports)
hiddenimports.extend(pil_hiddenimports)
hiddenimports.extend(yaml_hiddenimports)

# PySide6 の使用するインポートを明示的に追加
hiddenimports.extend([
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtNetwork',
])

block_cipher = None

# 使用しない巨大な Qt モジュールを明示的に除外
excluded_modules = [
    'PySide6.QtWebEngine',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
    'PySide6.Qt3D',
    'PySide6.Qt3DCore',
    'PySide6.Qt3DRender',
    'PySide6.QtQuick',
    'PySide6.QtQml',
    'PySide6.QtVirtualKeyboard',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
    'PySide6.QtPdf',
    'PySide6.QtPdfWidgets',
    'PySide6.QtCharts',
    'PySide6.QtSql',
    'PySide6.QtTest',
    'PySide6.QtBluetooth',
    'PySide6.QtDesigner',
    'PySide6.QtHelp',
    'PySide6.QtSensors',
    'PySide6.QtSerialPort',
    'PySide6.QtSvg',
    'PySide6.QtTextToSpeech',
    'PySide6.QtWebChannel',
    'PySide6.QtWebSockets',
]

a = Analysis(
    ['../app/main.py'],
    pathex=['..'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_modules,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ocr-automation',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # WindowsのGUIアプリなので黒いコンソールを表示しない
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ocr-automation',
)
