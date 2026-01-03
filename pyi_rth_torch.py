"""PyInstaller runtime hook: Initialize torch and transformers before any other imports.

This hook runs BEFORE any application code is imported.
It ensures torch and transformers are fully initialized to prevent circular import
issues when other modules try to access torch.nn from worker threads.

See: https://pyinstaller.org/en/stable/runtime-hooks.html
"""

import os
import sys

# Disable torch JIT compilation which can cause issues in frozen executables
os.environ["PYTORCH_JIT"] = "0"

# Ensure PYTHONHASHSEED is set for reproducibility
if "PYTHONHASHSEED" not in os.environ:
    os.environ["PYTHONHASHSEED"] = "0"

# Force torch to initialize completely before anything else imports it
_torch_ready = False
_transformers_ready = False

try:
    import torch
    import torch.nn
    import torch.nn.functional
    import torch.autograd
    import torch.utils
    import torch.utils.data

    # Warmup: create a small tensor to force complete initialization
    # This triggers lazy initialization of internal torch components
    _dummy = torch.tensor([1.0, 2.0, 3.0])
    _ = _dummy.sum()  # Force computation
    del _dummy, _

    _torch_ready = True
    os.environ["_TORCH_READY"] = "1"

except ImportError:
    # Torch not installed - that's okay for some configurations
    pass
except Exception as e:
    # Log but don't crash - some torch features may still work
    print(f"Warning: torch pre-initialization error: {e}", file=sys.stderr)

# CRITICAL: Also pre-import transformers and AutoTokenizer
# This prevents circular imports when worker threads try to load tokenizers
if _torch_ready:
    try:
        from transformers import AutoTokenizer
        _transformers_ready = True
        os.environ["_TRANSFORMERS_READY"] = "1"

        # Store AutoTokenizer in a global that ct2_wrapper can access
        # This is a workaround for the circular import issue
        import builtins
        builtins._AUTOTOKENIZER_CLASS = AutoTokenizer

    except ImportError as e:
        print(f"Warning: transformers pre-initialization error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: transformers pre-initialization error: {e}", file=sys.stderr)
