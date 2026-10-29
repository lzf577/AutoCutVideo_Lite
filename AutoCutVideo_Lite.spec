# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import site
import glob
from PyInstaller.utils.hooks import copy_metadata, collect_data_files, collect_submodules

BASE_DIR = os.path.dirname(os.path.abspath('main.py'))

datas = []
# 收集必要库的元数据与数据文件
datas += copy_metadata('imageio')
datas += copy_metadata('imageio_ffmpeg')
datas += copy_metadata('rapidocr_onnxruntime')
datas += copy_metadata('faster_whisper')
datas += copy_metadata('openai')

datas += collect_data_files('faster_whisper')
datas += collect_data_files('rapidocr_onnxruntime')
datas += collect_data_files('zhconv')

# 包含图标和界面资源 (不包含 models 权重目录)
if os.path.exists('logo.ico'):
    datas.append(('logo.ico', '.'))
if os.path.exists('logo.png'):
    datas.append(('logo.png', '.'))

hiddenimports = []
hiddenimports += collect_submodules('pipeline')
hiddenimports += collect_submodules('rapidocr_onnxruntime')
hiddenimports += collect_submodules('faster_whisper')
hiddenimports += ['PyQt6', 'fitz', 'PIL', 'imageio_ffmpeg', 'openai', 'dotenv', 'zhconv']

binaries = []
# 显式打包 Python 核心 DLL，杜绝 LoadLibrary 报错
py_dir = os.path.dirname(sys.executable)
for py_dll in ['python312.dll', 'python3.dll']:
    full_py_dll = os.path.join(py_dir, py_dll)
    if os.path.exists(full_py_dll):
        binaries.append((full_py_dll, '.'))

for dll in ['vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll']:
    sys_dll = os.path.join('C:\\Windows\\System32', dll)
    if os.path.exists(sys_dll):
        binaries.append((sys_dll, '.'))

# 收集 CTranslate2 相关 CPU 运行库
for sp in site.getsitepackages():
    ct2_bin_pattern = os.path.join(sp, 'ctranslate2', '*.dll')
    for dll_path in glob.glob(ct2_bin_pattern):
        lower_dll = dll_path.lower()
        if any(cuda_k in lower_dll for cuda_k in ['cublas', 'cudnn', 'cufft', 'curand', 'cusolver', 'cusparse', 'nvrtc']):
            continue
        binaries.append((dll_path, '.'))

a = Analysis(
    ['main.py'],
    pathex=[BASE_DIR],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['models', 'torch', 'nvidia', 'tensorrt', 'cupy', 'triton', 'matplotlib', 'pandas', 'scipy'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AutoCutVideo_Lite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=r'%TEMP%\AutoCutVideo_Lite',
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['logo.ico'],
)
