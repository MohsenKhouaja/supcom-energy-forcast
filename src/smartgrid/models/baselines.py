"""Zero-parameter forecasts using only original observed history at/before t.

History is normalized [N,4]. An imputed or incomplete lagged row produces an
all-NaN four-channel prediction at that forecast step. No backward search,
interpolation, zero fill, fitted statistic, or future observation is used.
"""

import numpy as np

from .base import ForecastModel, HORIZON


class _HistoricalBaseline(ForecastModel):
    lag = None

    def __init__(self, history, is_imputed):
        history = np.asarray(history)
        flags = np.asarray(is_imputed)
        if history.ndim != 2 or history.shape[1] != 4 or flags.shape != (len(history),):
            raise ValueError("Expected history [N,4] and aligned imputation flags [N]")
        if flags.dtype != bool:
            raise ValueError("Imputation flags must be boolean (unknown flags count as imputed)")
        self.history = history.view()
        self.history.flags.writeable = False
        self.observed = ~flags & np.isfinite(history).all(axis=1)

    def fit(self, train_origins, val_origins):
        # No statistics or parameters are estimated. Timing remains observable.
        return None

    @property
    def n_parameters(self):
        return 0

    @property
    def name(self):
        return type(self).__name__

    def predict(self, origins):
        origins = np.asarray(origins)
        if origins.ndim != 1 or not np.issubdtype(origins.dtype, np.integer):
            raise ValueError("Origins must be a one-dimensional integer array")
        if len(origins) and (origins.min() < 0 or origins.max() >= len(self.history)):
            raise ValueError("Origin lies outside the history grid")
        steps = np.arange(1,HORIZON+1)
        if self.lag is None:
            required = np.broadcast_to(origins[:,None],(len(origins),HORIZON))
        else:
            required = origins[:,None]+steps-self.lag
        in_bounds = (required >= 0) & (required < len(self.history)) & (required <= origins[:,None])
        if not len(self.history):
            return np.full((len(origins),HORIZON,4),np.nan)
        safe = np.clip(required,0,len(self.history)-1)
        output = self.history[safe].astype(np.float64,copy=True)
        output[~(in_bounds & self.observed[safe])] = np.nan
        return output


class SeasonalNaiveDaily(_HistoricalBaseline):
    """yhat(t+h) = y(t+h-96), h=1..96."""
    lag = 96


class SeasonalNaiveWeekly(_HistoricalBaseline):
    """yhat(t+h) = y(t+h-672), h=1..96."""
    lag = 672


class Persistence(_HistoricalBaseline):
    """yhat(t+h) = y(t). An imputed t invalidates the whole forecast."""
