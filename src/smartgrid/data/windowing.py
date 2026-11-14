"""Window eligibility only: no model features or training windows are built here."""

import numpy as np
import pandas as pd


def eligible_target_origins(is_imputed: pd.Series, horizon: int = 96) -> pd.Series:
    """True at t only if all labels t+1..t+H exist and none are imputed.

    Flags include derived increments influenced by an imputed counter, including
    the observed closing row. Call this before constructing any training window.
    Historical imputed inputs are permitted. A future split must also be supplied
    to imputation, or each split must be processed separately.
    """
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    flags = is_imputed.fillna(True).to_numpy(dtype=bool)
    n = len(flags)
    prefix = np.concatenate(([0], np.cumsum(flags, dtype=np.int64)))
    eligible = np.zeros(n, dtype=bool)
    starts = np.arange(max(0, n-horizon))
    eligible[starts] = prefix[starts+horizon+1] == prefix[starts+1]
    return pd.Series(eligible, index=is_imputed.index, name="eligible_target_origin")
