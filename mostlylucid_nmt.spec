# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for MostlyLucid-NMT standalone executable.

Build with:
    pyinstaller mostlylucid_nmt.spec

This creates a compact executable that downloads models on first use.
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect necessary data files
datas = []

# Transformers needs tokenizer and model config files
datas += collect_data_files('transformers', include_py_files=False)

# Sentencepiece model files
datas += collect_data_files('sentencepiece', include_py_files=False)

# Sacremoses tokenizer data
datas += collect_data_files('sacremoses', include_py_files=False)

# Langdetect profiles
datas += collect_data_files('langdetect', include_py_files=False)

# Include our source package
datas += [('src', 'src')]

# Hidden imports that PyInstaller doesn't detect automatically
hiddenimports = [
    # FastAPI and Starlette
    'fastapi',
    'starlette',
    'starlette.responses',
    'starlette.routing',
    'starlette.middleware',
    'starlette.middleware.cors',
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',

    # Pydantic
    'pydantic',
    'pydantic_core',
    'pydantic.deprecated',
    'pydantic.deprecated.decorator',

    # HTTP
    'httpx',
    'httpcore',
    'anyio',
    'sniffio',
    'h11',
    'certifi',

    # PyTorch - core
    'torch',
    'torch.nn',
    'torch.nn.functional',
    'torch.utils',
    'torch.utils.data',
    'torch._C',
    'torch.cuda',
    'torch.backends',
    'torch.backends.cudnn',

    # Transformers
    'transformers',
    'transformers.models',
    'transformers.models.marian',
    'transformers.models.mbart',
    'transformers.models.m2m_100',
    'transformers.pipelines',
    'transformers.pipelines.text2text_generation',
    'transformers.tokenization_utils_base',
    'transformers.modeling_utils',
    'transformers.configuration_utils',

    # Tokenizers and NLP
    'sentencepiece',
    'sacremoses',
    'langdetect',
    'langdetect.detector_factory',

    # Other utilities
    'tqdm',
    'tqdm.auto',
    'psutil',
    'protobuf',
    'google.protobuf',

    # Standard library that might be missed
    'multiprocessing',
    'concurrent.futures',
    'asyncio',
    'json',
    'logging.handlers',
]

# Collect all transformers submodules for model support
hiddenimports += collect_submodules('transformers.models.marian')
hiddenimports += collect_submodules('transformers.models.mbart')
hiddenimports += collect_submodules('transformers.models.m2m_100')

# Exclude unnecessary large packages to keep size down
# CPU-only build - exclude all CUDA/GPU related packages
excludes = [
    # GUI frameworks
    'tkinter',
    'PyQt5',
    'PyQt6',
    'PySide2',
    'PySide6',

    # Data science (not needed)
    'matplotlib',
    'PIL',
    'IPython',
    'jupyter',
    'notebook',
    'scipy',
    'sklearn',
    'pandas',

    # Build tools
    'numpy.distutils',
    'setuptools',
    'pkg_resources',
    'pip',
    'wheel',

    # Tests
    'test',
    'tests',
    'pytest',

    # CUDA/GPU - exclude to keep size small (CPU-only build)
    'torch.cuda',
    'torch.backends.cuda',
    'torch.backends.cudnn',
    'torch.distributed',
    'torch._inductor',
    'triton',
    'nvidia',
    'cudnn',

    # Unused torch features
    'torch.onnx',
    'torch.testing',
    'torch.utils.tensorboard',
    'torch.utils.benchmark',
    'torch.utils.bottleneck',
    'torch.profiler',

    # Unused transformers features
    'transformers.onnx',
    'transformers.training_args',
    'transformers.trainer',
    'transformers.optimization',

    # MCP is optional - exclude from exe
    'mcp',
]

a = Analysis(
    ['run_server.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Use onedir mode - creates a folder with exe + libs
# This is more practical for large dependencies like PyTorch
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # Don't bundle binaries into exe
    name='mostlylucid-nmt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Skip UPX - too slow for large builds
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

# Collect into a directory
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='mostlylucid-nmt',
)
