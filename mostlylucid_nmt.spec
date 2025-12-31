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

# Hidden imports - minimal set for translation only
hiddenimports = [
    # FastAPI core only
    'fastapi',
    'starlette.responses',
    'starlette.routing',
    'uvicorn',

    # Pydantic
    'pydantic',
    'pydantic_core',

    # HTTP
    'httpx',
    'httpcore',
    'anyio',
    'h11',

    # PyTorch - minimal CPU only
    'torch',
    'torch.nn',
    'torch.nn.functional',

    # Transformers - only what we need for 3 model types
    'transformers',
    'transformers.models.marian',
    'transformers.models.marian.modeling_marian',
    'transformers.models.marian.tokenization_marian',
    'transformers.models.marian.configuration_marian',
    'transformers.models.mbart',
    'transformers.models.mbart.modeling_mbart',
    'transformers.models.mbart.tokenization_mbart',
    'transformers.models.mbart.tokenization_mbart_fast',
    'transformers.models.mbart.configuration_mbart',
    'transformers.models.m2m_100',
    'transformers.models.m2m_100.modeling_m2m_100',
    'transformers.models.m2m_100.tokenization_m2m_100',
    'transformers.models.m2m_100.configuration_m2m_100',
    'transformers.pipelines',
    'transformers.pipelines.text2text_generation',

    # Tokenizers
    'sentencepiece',
    'sacremoses',
    'langdetect',

    # Utilities
    'tqdm',
    'psutil',
]

# Aggressive exclusions for minimal size
excludes = [
    # GUI
    'tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',

    # Data science
    'matplotlib', 'PIL', 'IPython', 'jupyter', 'notebook',
    'scipy', 'sklearn', 'pandas', 'seaborn', 'plotly',

    # Build/dev tools
    'setuptools', 'pkg_resources', 'pip', 'wheel', 'distutils',
    'pytest', 'test', 'tests', 'unittest',

    # CUDA/GPU (CPU-only build)
    'torch.cuda', 'torch.backends.cuda', 'torch.backends.cudnn',
    'torch.distributed', 'torch._inductor', 'torch.compiler',
    'triton', 'nvidia', 'cudnn', 'nccl',

    # Unused torch
    'torch.onnx', 'torch.jit', 'torch.fx',
    'torch.testing', 'torch.profiler', 'torch.autograd.profiler',
    'torch.utils.tensorboard', 'torch.utils.benchmark',
    'torch.utils.bottleneck', 'torch.utils.cpp_extension',
    'torch.utils.mobile_optimizer', 'torch.quantization',
    'torch.ao', 'torch.sparse', 'torch.nested',

    # Unused transformers (we only need marian, mbart, m2m_100)
    'transformers.onnx', 'transformers.trainer', 'transformers.training_args',
    'transformers.optimization', 'transformers.integrations',
    'transformers.generation.tf_utils', 'transformers.generation.flax_utils',
    'transformers.modeling_tf_utils', 'transformers.modeling_flax_utils',
    'transformers.tf_utils', 'transformers.keras_callbacks',

    # All other transformers models (100+ we don't use)
    'transformers.models.albert', 'transformers.models.bart', 'transformers.models.bert',
    'transformers.models.blenderbot', 'transformers.models.bloom', 'transformers.models.clip',
    'transformers.models.codegen', 'transformers.models.convbert', 'transformers.models.ctrl',
    'transformers.models.deberta', 'transformers.models.distilbert', 'transformers.models.dpr',
    'transformers.models.electra', 'transformers.models.encoder_decoder', 'transformers.models.falcon',
    'transformers.models.flaubert', 'transformers.models.fnet', 'transformers.models.funnel',
    'transformers.models.gemma', 'transformers.models.gpt2', 'transformers.models.gpt_neo',
    'transformers.models.gpt_neox', 'transformers.models.gptj', 'transformers.models.llama',
    'transformers.models.longformer', 'transformers.models.luke', 'transformers.models.lxmert',
    'transformers.models.mobilebert', 'transformers.models.mpnet', 'transformers.models.mt5',
    'transformers.models.nllb', 'transformers.models.opt', 'transformers.models.pegasus',
    'transformers.models.phi', 'transformers.models.qwen2', 'transformers.models.reformer',
    'transformers.models.roberta', 'transformers.models.roformer', 'transformers.models.speech_to_text',
    'transformers.models.squeezebert', 'transformers.models.switch_transformers', 'transformers.models.t5',
    'transformers.models.transfo_xl', 'transformers.models.wav2vec2', 'transformers.models.whisper',
    'transformers.models.xlm', 'transformers.models.xlm_roberta', 'transformers.models.xlnet',
    'transformers.models.xmod', 'transformers.models.yolos', 'transformers.models.vit',
    'transformers.models.vision_encoder_decoder', 'transformers.models.visual_bert',
    'transformers.models.detr', 'transformers.models.deit', 'transformers.models.beit',
    'transformers.models.layoutlm', 'transformers.models.layoutlmv2', 'transformers.models.layoutlmv3',
    'transformers.models.tapas', 'transformers.models.rag', 'transformers.models.realm',
    'transformers.models.retribert', 'transformers.models.splinter', 'transformers.models.data2vec',
    'transformers.models.decision_transformer', 'transformers.models.deformable_detr',
    'transformers.models.dinat', 'transformers.models.dpt', 'transformers.models.efficientformer',
    'transformers.models.efficientnet', 'transformers.models.ernie', 'transformers.models.esm',
    'transformers.models.flava', 'transformers.models.git', 'transformers.models.glpn',
    'transformers.models.gpt_bigcode', 'transformers.models.graphormer', 'transformers.models.groupvit',
    'transformers.models.hubert', 'transformers.models.ibert', 'transformers.models.idefics',
    'transformers.models.imagegpt', 'transformers.models.informer', 'transformers.models.jukebox',
    'transformers.models.kosmos', 'transformers.models.led', 'transformers.models.levit',
    'transformers.models.llava', 'transformers.models.lilt', 'transformers.models.longformer',
    'transformers.models.longt5', 'transformers.models.maskformer', 'transformers.models.mctct',
    'transformers.models.mega', 'transformers.models.megatron_bert', 'transformers.models.mistral',
    'transformers.models.mixtral', 'transformers.models.mobilenet_v1', 'transformers.models.mobilenet_v2',
    'transformers.models.mobilevit', 'transformers.models.mvp', 'transformers.models.nat',
    'transformers.models.nezha', 'transformers.models.nystromformer', 'transformers.models.oneformer',
    'transformers.models.openai', 'transformers.models.owlvit', 'transformers.models.patchst',
    'transformers.models.patchtsmixer', 'transformers.models.perceiver', 'transformers.models.persimmon',
    'transformers.models.pix2struct', 'transformers.models.plbart', 'transformers.models.poolformer',
    'transformers.models.pop2piano', 'transformers.models.prophetnet', 'transformers.models.pvt',
    'transformers.models.qdqbert', 'transformers.models.regnet', 'transformers.models.rembert',
    'transformers.models.resnet', 'transformers.models.rwkv', 'transformers.models.sam',
    'transformers.models.seamless_m4t', 'transformers.models.segformer', 'transformers.models.sew',
    'transformers.models.speecht5', 'transformers.models.stablelm', 'transformers.models.starcoder2',
    'transformers.models.superpoint', 'transformers.models.swiftformer', 'transformers.models.swin',
    'transformers.models.swin2sr', 'transformers.models.swinv2', 'transformers.models.table_transformer',
    'transformers.models.time_series_transformer', 'transformers.models.timesformer',
    'transformers.models.timm_backbone', 'transformers.models.trocr', 'transformers.models.tvlt',
    'transformers.models.udop', 'transformers.models.umt5', 'transformers.models.unispeech',
    'transformers.models.upernet', 'transformers.models.videomae', 'transformers.models.vilt',
    'transformers.models.vipllava', 'transformers.models.vision_text_dual_encoder',
    'transformers.models.vivit', 'transformers.models.wav2vec2_conformer', 'transformers.models.wavlm',
    'transformers.models.x_clip', 'transformers.models.xglm', 'transformers.models.xlm_prophetnet',

    # Accelerate, bitsandbytes, etc
    'accelerate', 'bitsandbytes', 'optimum', 'auto_gptq', 'autoawq',
    'safetensors.torch', 'datasets', 'evaluate', 'tokenizers.implementations',

    # MCP optional
    'mcp',

    # Email/network we don't need
    'email', 'smtplib', 'ftplib', 'telnetlib', 'xmlrpc',
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
