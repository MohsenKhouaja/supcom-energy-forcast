"""Optional CPU-only Torch adapter; imported only by windows.torch_dataset."""

import torch
from torch.utils.data import Dataset


class TorchWindows(Dataset):
    """A pickleable lazy dataset. Allocate only the requested sample on CPU."""

    def __init__(self, windows):
        self.windows = windows

    def __len__(self):
        return len(self.windows)

    def __getitem__(self, position):
        x, y = self.windows[position]
        return torch.from_numpy(x.copy()), torch.from_numpy(y.copy())
