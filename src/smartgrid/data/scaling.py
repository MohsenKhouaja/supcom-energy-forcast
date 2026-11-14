"""Train-only electrical StandardScaler, persisted as plain JSON numbers.

Fit once per unique train-range row touched by any eligible training INPUT or
TARGET. Both X electrical channels and y use the same normalization; the seven
calendar channels pass through untouched. No fit is performed on val/test.
"""

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from smartgrid.features.calendar_features import ELECTRICAL, FEATURES
from .windows import split_ranges, touched_train_rows


@dataclass
class ElectricalScaler:
    mean: np.ndarray
    std: np.ndarray
    scale: np.ndarray
    n_rows: int
    fit_first: str
    fit_last: str

    def transform(self, values):
        """Return float32 scaled table/targets; calendar columns retain bits."""
        values = np.asarray(values)
        if values.ndim != 2 or values.shape[1] not in (4, 11):
            raise ValueError("Expected [N,4] targets or [N,11] features")
        output = values.astype(np.float32, copy=True)
        output[:, :4] = ((values[:, :4].astype(np.float64)-self.mean)/self.scale).astype(np.float32)
        return output

    def inverse_electrical(self, values):
        return np.asarray(values)*self.scale+self.mean

    def to_dict(self):
        return dict(channels=list(ELECTRICAL), mean=self.mean.tolist(), std=self.std.tolist(),
                    scale=self.scale.tolist(), variance_ddof=0, n_fit_rows=self.n_rows,
                    fit_first=self.fit_first, fit_last=self.fit_last,
                    fit_policy="unique train-range rows touched by eligible training inputs OR targets",
                    calendar_scaled=False)

    def save(self, path):
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, allow_nan=False)+"\n", encoding="utf-8")

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if tuple(data["channels"]) != ELECTRICAL:
            raise ValueError("Unexpected scaler channel order")
        return cls(np.array(data["mean"]), np.array(data["std"]), np.array(data["scale"]),
                   data["n_fit_rows"], data["fit_first"], data["fit_last"])


def scaler_fit_coverage(table, train_origins, config):
    mask = touched_train_rows(table.index, train_origins, config)
    start, end = split_ranges(config)["train"]
    in_train = (table.index >= start) & (table.index < end)
    finite = np.isfinite(table.loc[:, ELECTRICAL].to_numpy()).all(axis=1)
    excluded = in_train & ~mask
    return mask, dict(train_range_rows=int(in_train.sum()), fitted_rows=int(mask.sum()),
        excluded_rows=int(excluded.sum()), excluded_pct=float(100*excluded.sum()/in_train.sum()),
        excluded_nonfinite_electrical=int((excluded & ~finite).sum()),
        excluded_finite_not_touched=int((excluded & finite).sum()))


def fit_electrical_scaler(table, train_origins, config):
    if tuple(table.columns) != FEATURES:
        raise ValueError("Unexpected feature order")
    mask, coverage = scaler_fit_coverage(table, train_origins, config)
    selected = table.loc[mask, ELECTRICAL]
    if selected.empty or not np.isfinite(selected.to_numpy()).all():
        raise ValueError("Scaler fit requires finite, nonempty eligible training rows")
    fitted = StandardScaler().fit(selected.to_numpy(dtype=np.float64))
    scaler = ElectricalScaler(fitted.mean_, np.sqrt(fitted.var_), fitted.scale_,
        len(selected), str(selected.index[0]), str(selected.index[-1]))
    return scaler, mask, coverage
