# Runtime hook to initialize torch before transformers
# This fixes circular import issues in frozen executables

import torch
import torch.nn
import torch.nn.functional
