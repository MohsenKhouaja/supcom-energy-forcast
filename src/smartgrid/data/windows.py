"""Lazy 672-to-96 windows, using origin t as the LAST input timestamp.

    X = table[t-671:t+1, :11]; y = table[t+1:t+97, :4].

Inputs may be imputed, targets must be wholly observed and finite, including
the derived closing increments marked by ingestion. Targets stay within their
own split. Validation/test may use earlier partitions as historical context.
Persist one underlying float32 [N,11] table and int64 origins, never stacked
windows. Torch is optional and imported only when its Dataset is requested.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from smartgrid.features.calendar_features import ELECTRICAL, FEATURES


def validate_grid(index):
    index = pd.DatetimeIndex(index)
    if index.tz is not None or index.hasnans or not index.is_unique or not index.is_monotonic_increasing:
        raise ValueError("Expected unique sorted finite naive timestamps")
    if len(index) > 1 and not np.all(index[1:]-index[:-1] == pd.Timedelta(minutes=15)):
        raise ValueError("Expected explicit consecutive 15-minute grid")
    return index


def split_ranges(config):
    """Inclusive start, exclusive end; require ordered, adjacent partitions."""
    result = {}
    previous_end = None
    for name, period in config["splits"].items():
        start = pd.Timestamp(period["start"])
        end = pd.Timestamp(period["end"])+pd.Timedelta(days=1)
        if end <= start or (previous_end is not None and start != previous_end):
            raise ValueError("Splits must be ordered, adjacent, nonempty date ranges")
        result[name] = (start, end)
        previous_end = end
    if "train" not in result or next(iter(result)) != "train":
        raise ValueError("First split must be train")
    return result


def eligible_origins(table, is_imputed, config):
    """O(N) prefix-sum checks. Return last-input row positions per split.

    A boundary origin may be the previous split's final timestamp; all 96
    target timestamps, rather than the origin timestamp, identify the split.
    """
    index = validate_grid(table.index)
    context, horizon = int(config["context"]), int(config["horizon"])
    if context <= 0 or horizon <= 0:
        raise ValueError("Context and horizon must be positive")
    if tuple(table.columns) != FEATURES:
        raise ValueError(f"Expected feature order {FEATURES}")
    if not is_imputed.index.equals(index):
        raise ValueError("Imputation flags must align exactly with the feature grid")
    values = table.to_numpy(copy=False)
    bad_input = ~np.isfinite(values).all(axis=1)
    bad_target = ~np.isfinite(values[:, :4]).all(axis=1) | is_imputed.fillna(True).to_numpy(dtype=bool)
    input_prefix = np.r_[0, np.cumsum(bad_input, dtype=np.int64)]
    target_prefix = np.r_[0, np.cumsum(bad_target, dtype=np.int64)]
    origins = np.arange(context-1, max(context-1, len(table)-horizon), dtype=np.int64)
    good = ((input_prefix[origins+1] == input_prefix[origins-context+1]) &
            (target_prefix[origins+horizon+1] == target_prefix[origins+1]))
    return {name: origins[good & (index[origins+1] >= start) & (index[origins+horizon] < end)]
            for name, (start, end) in split_ranges(config).items()}


def touched_train_rows(index, origins, config):
    """Unique train-range rows in ANY training input OR target; no repetition."""
    index = validate_grid(index)
    context, horizon = int(config["context"]), int(config["horizon"])
    origins = np.asarray(origins, dtype=np.int64)
    delta = np.zeros(len(index)+1, dtype=np.int64)
    if len(origins):
        if origins.min() < context-1 or origins.max()+horizon >= len(index):
            raise ValueError("Training origin outside available context/horizon")
        train_start, train_end = split_ranges(config)["train"]
        if ((index[origins+1] < train_start) | (index[origins+horizon] >= train_end)).any():
            raise ValueError("Non-training target passed to scaler row selection")
        np.add.at(delta, origins-context+1, 1)
        np.add.at(delta, origins+horizon+1, -1)
    else:
        train_start, train_end = split_ranges(config)["train"]
    return (np.cumsum(delta[:-1]) > 0) & (index >= train_start) & (index < train_end)


class LazyWindows:
    """One shared float32 table, tiny origin list, and on-demand NumPy views.

    Construct via from_processed for validated persisted artifacts. A caller
    constructing directly must supply origins returned by eligible_origins.
    Views are read-only to avoid accidentally mutating subsequent samples.
    """

    def __init__(self, values, origins, *, context=672, horizon=96):
        if values.dtype != np.float32 or values.ndim != 2 or values.shape[1] != 11:
            raise ValueError("Expected one float32 [N,11] table")
        self.values = values.view()
        self.values.flags.writeable = False
        self.origins = np.asarray(origins, dtype=np.int64).copy()
        self.context, self.horizon = int(context), int(horizon)
        if self.context <= 0 or self.horizon <= 0:
            raise ValueError("Positive context/horizon required")
        if len(self.origins) and (self.origins.min() < context-1 or self.origins.max()+horizon >= len(values)):
            raise ValueError("Origin has insufficient context or target history")

    def __len__(self):
        return len(self.origins)

    def __getitem__(self, position):
        origin = int(self.origins[position])
        return (self.values[origin-self.context+1:origin+1],
                self.values[origin+1:origin+self.horizon+1, :4])


def window_at(values, origin, *, context=672, horizon=96):
    """Slice one validated origin; no [number_of_windows,672,11] allocation."""
    return LazyWindows(values, [origin], context=context, horizon=horizon)[0]


def torch_dataset(windows):
    """Return a genuine torch.utils.data.Dataset; CPU tensors only.

    Requires an already-installed torch. This function never installs packages,
    allocates VRAM, or stacks windows. Copies only the requested single sample
    so writable Torch tensors cannot modify the shared read-only NumPy table.
    """
    from ._torch_windows import TorchWindows
    return TorchWindows(windows)


def from_processed(directory, split):
    """Load one [N,11] memory-mapped array plus the selected tiny origin list."""
    import json
    directory = Path(directory)
    metadata = json.loads((directory/"features.json").read_text(encoding="utf-8"))
    if tuple(metadata["features"]) != FEATURES:
        raise ValueError("Persisted feature order changed")
    if split not in metadata["origin_files"]:
        raise ValueError(f"Unknown split {split}")
    origins = pd.read_parquet(directory/metadata["origin_files"][split])["origin_index"].to_numpy(dtype=np.int64)
    values = np.load(directory/"features.npy", mmap_mode="r", allow_pickle=False)
    return LazyWindows(values, origins, context=metadata["context"], horizon=metadata["horizon"])
