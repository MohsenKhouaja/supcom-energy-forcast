"""Forecasting contract shared by baselines and all later benchmark models.

Origins are absolute grid row indices, identifying the LAST input timestamp t.
predict returns normalized electrical channels [dEa,dEr,P_avg,S_avg] at
t+1..t+96. The harness inverse-transforms before computing any metric or
persisting predictions. A model may accept batched origins; it must not modify
the underlying history. Future models receive training/validation origins in
fit; test origins are supplied only to predict.
"""

from abc import ABC, abstractmethod

import numpy as np

CHANNELS = ("dEa", "dEr", "P_avg", "S_avg")
UNITS = ("kWh", "kvarh", "kW", "kVA")
HORIZON = 96


class ForecastModel(ABC):
    @abstractmethod
    def fit(self, train_origins: np.ndarray, val_origins: np.ndarray) -> None:
        """Fit using these partitions only. The harness times this call."""

    @abstractmethod
    def predict(self, origins: np.ndarray) -> np.ndarray:
        """Return [n_origins,96,4] normalized predictions; NaN if unavailable."""

    @property
    @abstractmethod
    def n_parameters(self) -> int:
        """Number of fitted model parameters, excluding input data/scaler."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable model identifier, also used in benchmark/prediction filenames."""
