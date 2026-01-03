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

# Increase recursion limit for PyInstaller's module analysis
# This helps with deeply nested imports in torch and transformers
sys.setrecursionlimit(5000)

# Module collection mode: Use source files (pyz+py) for problematic packages
# This prevents bytecode optimization issues with torch's lazy initialization
# See: https://github.com/orgs/pyinstaller/discussions/7944
module_collection_mode = {
    'torch': 'pyz+py',
    'transformers': 'pyz+py',
}

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

# Minimal torch imports - DO NOT use collect_submodules('torch') as it adds 2GB+ of CUDA libs
# Only include the core modules needed for CPU inference
# Note: torch.cuda must be included as torch/__init__.py imports it during initialization
torch_hidden = [
    'torch',
    'torch.cuda',  # Required for torch init even on CPU builds
    'torch.backends',
    'torch.backends.cuda',
    'torch.backends.cudnn',
    'torch.distributed',  # Required by dataloader
    'torch.nn',
    'torch.nn.functional',
    'torch.nn.modules',
    'torch.nn.modules.linear',
    'torch.nn.modules.conv',
    'torch.nn.modules.activation',
    'torch.nn.modules.normalization',
    'torch.nn.modules.dropout',
    'torch.nn.modules.container',
    'torch.nn.modules.transformer',
    'torch.nn.modules.sparse',
    'torch.nn.modules.rnn',
    'torch.nn.modules.pooling',
    'torch.nn.modules.padding',
    'torch.nn.modules.loss',
    'torch.nn.modules.batchnorm',
    'torch.nn.modules.instancenorm',
    'torch.nn.modules.lazy',
    'torch.nn.modules.fold',
    'torch.nn.modules.flatten',
    'torch.nn.modules.distance',
    'torch.nn.modules.adaptive',
    'torch.nn.modules.pixelshuffle',
    'torch.nn.modules.upsampling',
    'torch.nn.modules.channelshuffle',
    'torch._C',
    'torch.utils',
    'torch.utils.data',
    'torch.serialization',
    'torch.storage',
    'torch.autograd',
    'torch.tensor',
    'torch.jit',  # Required for torch initialization
    'torch.fx',   # Required for some torch internals
]

# Hidden imports - minimal set for translation only
hiddenimports = torch_hidden + [
    # FastAPI/Starlette
    'fastapi',
    'fastapi.staticfiles',
    'starlette',
    'starlette.responses',
    'starlette.routing',
    'starlette.staticfiles',
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

    # HTTP
    'httpx',
    'httpcore',
    'anyio',
    'h11',

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

    # CTranslate2 - fast inference backend (preferred for CPU)
    'ctranslate2',

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

    # CUDA/GPU - Exclude CUDA *runtime libraries* but NOT core torch modules
    # torch.cuda and torch.distributed are needed for torch init (even on CPU)
    'torch._inductor', 'torch.compiler',
    'triton', 'nvidia', 'cudnn', 'nccl',
    'nvidia_cublas_cu12', 'nvidia_cuda_cupti_cu12', 'nvidia_cuda_nvrtc_cu12',
    'nvidia_cuda_runtime_cu12', 'nvidia_cudnn_cu12', 'nvidia_cufft_cu12',
    'nvidia_curand_cu12', 'nvidia_cusolver_cu12', 'nvidia_cusparse_cu12',
    'nvidia_nccl_cu12', 'nvidia_nvjitlink_cu12', 'nvidia_nvtx_cu12',

    # Unused torch extras (keep core torch modules)
    # NOTE: torch.jit and torch.fx are needed for torch initialization
    'torch.onnx',
    'torch.profiler', 'torch.autograd.profiler',
    'torch.utils.tensorboard', 'torch.utils.benchmark',
    'torch.utils.bottleneck', 'torch.utils.cpp_extension',
    'torch.utils.mobile_optimizer', 'torch.quantization',
    'torch.ao', 'torch.nested',

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

    # Network we don't need
    'smtplib', 'ftplib', 'telnetlib', 'xmlrpc',
]

a = Analysis(
    ['run_server.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyi_rth_torch.py'],  # Initialize torch before any imports
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    module_collection_mode=module_collection_mode,  # Source-level collection for torch
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Check if we're building onedir (for Windows) or onefile (for Linux/macOS)
import os
ONEDIR_MODE = os.environ.get('PYINSTALLER_ONEDIR', '0') == '1'

if ONEDIR_MODE:
    # Windows: onedir mode - creates folder with separate DLLs (better AV compatibility)
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='mostlylucid-nmt',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,  # Don't strip on Windows
        upx=False,
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        name='mostlylucid-nmt',
    )
else:
    # Linux/macOS: onefile mode - single executable
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='mostlylucid-nmt',
        debug=False,
        bootloader_ignore_signals=False,
        strip=True,  # Strip symbols to reduce size
        upx=False,   # UPX causes issues with torch
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,
    )
