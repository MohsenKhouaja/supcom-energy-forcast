"""Seven bounded calendar features; academic dates are RECONSTRUCTED, not official."""

import numpy as np
import pandas as pd

from .calendar import academic_periods, tunisian_holidays, vacation_mask

ELECTRICAL = ("dEa", "dEr", "P_avg", "S_avg")
CALENDAR = ("hour_sin", "hour_cos", "weekday_sin", "weekday_cos", "doy_sin", "doy_cos", "is_non_working_day")
FEATURES = ELECTRICAL + CALENDAR


def calendar_features(index, config):
    """Fractional local clock hours; Monday=0; day-of-year starts at 1.

    Non-working = Saturday/Sunday OR TN holiday OR RECONSTRUCTED vacation.
    Examinations are working days unless another non-working rule applies.
    """
    index = pd.DatetimeIndex(index)
    if index.tz is not None or index.hasnans:
        raise ValueError("Expected finite, timezone-naive export-local timestamps")
    if not set(index.year).issubset(config["holiday_years"]):
        raise ValueError("Holiday configuration does not cover every feature year")
    result = pd.DataFrame(index=index)
    for name, values, period in (("hour", index.hour+index.minute/60+index.second/3600, 24),
                                  ("weekday", index.day_of_week, 7), ("doy", index.day_of_year, 365.25)):
        result[f"{name}_sin"] = np.sin(2*np.pi*values/period)
        result[f"{name}_cos"] = np.cos(2*np.pi*values/period)
    public = tunisian_holidays(config)
    result["is_non_working_day"] = ((index.day_of_week >= 5) | np.isin(index.date, list(public)) |
                                     vacation_mask(index, academic_periods(config))).astype(np.float32)
    return result.loc[:, CALENDAR].astype(np.float32)


def feature_table(frame, config):
    """Return [N,11] in documented order, retaining explicit electrical NaNs."""
    return pd.concat([frame.loc[:, ELECTRICAL], calendar_features(frame.index, config)], axis=1).astype(np.float32)
