"""64 causal tabular features for pooled direct multi-horizon forecasting.

32 electrical lags +24 trailing mean/std features +7 target-calendar values
+h. Electrical data never come from after origin t. Target calendar values
at t+h are known in advance and are legitimate predictors, not measured future
load. Historical imputed inputs are permitted; imputed labels are forbidden.
The explicit t-672 lag needs 673 timestamps (one more than a 672-slot window).
Rolling intervals include t, with population standard deviation (ddof=0).
"""

from dataclasses import dataclass

import numpy as np

from smartgrid.models.base import CHANNELS, HORIZON

LAGS = (0,1,2,3,4,96,192,672)
ROLLING = (4,96,672)
CALENDAR = ("hour_sin","hour_cos","weekday_sin","weekday_cos","doy_sin","doy_cos","is_non_working_day")


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    kind: str
    earliest_relative_row: int | None
    latest_relative_row: int | None


FEATURE_SPECS = tuple(
    [FeatureSpec(f"{channel}_lag_{lag}","electrical_history",-lag,-lag) for channel in CHANNELS for lag in LAGS]
    +[FeatureSpec(f"{channel}_rolling_{stat}_{width}","electrical_history",1-width,0)
      for channel in CHANNELS for width in ROLLING for stat in ("mean","std")]
    +[FeatureSpec(f"target_{name}","known_future_calendar",None,None) for name in CALENDAR]
    +[FeatureSpec("h","known_horizon",None,None)]
)
FEATURE_NAMES = tuple(spec.name for spec in FEATURE_SPECS)


class TabularFeatures:
    """Cache only [N,56] origin summaries; construct requested pairs on demand.

    Electrical inputs/targets are already normalized with the saved train-only
    scaler. Calendar features pass through unscaled. Raw h is exactly1..96;
    the SVR adapter may divide h by 96 using its known bound, without fitting.
    """

    def __init__(self, history, calendar, is_imputed):
        self.history = np.asarray(history,dtype=np.float64)
        self.calendar = np.asarray(calendar,dtype=np.float32)
        self.is_imputed = np.asarray(is_imputed,dtype=bool)
        n = len(self.history)
        if self.history.shape != (n,4) or self.calendar.shape != (n,7) or self.is_imputed.shape != (n,):
            raise ValueError("Expected aligned history[N,4], calendar[N,7], flags[N]")
        self.origin_features = np.full((n,56),np.nan,dtype=np.float32)
        column = 0
        for channel in range(4):
            for lag in LAGS:
                if lag < n:
                    self.origin_features[lag:,column] = self.history[:n-lag,channel]
                column += 1
        for channel in range(4):
            values = self.history[:,channel]
            finite = np.isfinite(values)
            safe = np.where(finite,values,0.)
            prefix = np.r_[0.,np.cumsum(safe,dtype=np.float64)]
            squares = np.r_[0.,np.cumsum(safe*safe,dtype=np.float64)]
            counts = np.r_[0,np.cumsum(finite,dtype=np.int64)]
            for width in ROLLING:
                if width <= n:
                    complete = counts[width:]-counts[:-width] == width
                    mean = (prefix[width:]-prefix[:-width])/width
                    variance = np.maximum(0.,(squares[width:]-squares[:-width])/width-mean*mean)
                    self.origin_features[width-1:,column] = np.where(complete,mean,np.nan)
                    self.origin_features[width-1:,column+1] = np.where(complete,np.sqrt(variance),np.nan)
                column += 2

    def _pairs(self,origins,horizons):
        origins = np.asarray(origins)
        horizons = np.asarray(horizons)
        if origins.ndim != 1 or horizons.shape != origins.shape or not np.issubdtype(origins.dtype,np.integer) or not np.issubdtype(horizons.dtype,np.integer):
            raise ValueError("Origins and horizons must be aligned integer vectors")
        if len(origins) and ((origins < 0).any() or (horizons < 1).any() or (horizons > HORIZON).any() or (origins+horizons >= len(self.history)).any()):
            raise ValueError("Origin/horizon outside the available grid or1..96")
        return origins,horizons

    def build(self,origins,horizons):
        """Read measured electrical rows only at/before t; never read labels."""
        origins,horizons = self._pairs(origins,horizons)
        result = np.empty((len(origins),64),dtype=np.float32)
        result[:,:56] = self.origin_features[origins]
        result[:,56:63] = self.calendar[origins+horizons]
        result[:,63] = horizons
        return result

    def usable_origins(self,origins):
        origins = np.asarray(origins,dtype=np.int64)
        return np.isfinite(self.origin_features[origins]).all(axis=1)

    def targets(self,origins,horizons):
        """Read labels ONLY after checking none of their rows are imputed."""
        origins,horizons = self._pairs(origins,horizons)
        positions = origins+horizons
        if self.is_imputed[positions].any():
            raise ValueError("Imputed rows must never be read as training/validation targets")
        result = self.history[positions]
        if not np.isfinite(result).all():
            raise ValueError("Training/validation targets must be finite")
        return result


def complete_pairs(origins):
    """All 96 horizons for each selected origin, in deterministic origin order."""
    origins = np.asarray(origins,dtype=np.int64)
    return np.repeat(origins,HORIZON),np.tile(np.arange(1,HORIZON+1),len(origins))


def evenly_spaced_origins(origins,count):
    """Deterministic chronological coverage; no random subsampling."""
    origins = np.asarray(origins,dtype=np.int64)
    count = min(int(count),len(origins))
    if count <= 0:
        raise ValueError("Need a nonempty origin selection")
    return origins[np.linspace(0,len(origins)-1,count,dtype=np.int64)]


def capped_training_pairs(origins,max_rows=20000):
    """Deterministic SVR training concession only; never used for evaluation."""
    chosen = evenly_spaced_origins(origins,min(len(origins),max_rows//HORIZON+1))
    left,right = complete_pairs(chosen)
    if len(left) > max_rows:
        keep = np.linspace(0,len(left)-1,max_rows,dtype=np.int64)
        left,right = left[keep],right[keep]
    return left,right
