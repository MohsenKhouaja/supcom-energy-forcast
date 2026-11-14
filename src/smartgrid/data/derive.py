"""Electrical derivations on an explicit 15-minute grid; no gap bridging."""

import numpy as np
import pandas as pd


def clean_demand_registers(frame: pd.DataFrame):
    """Mark failed zero reads missing at S_avg>1 kVA; retain valid idle zeros.

    This is missing-read cleanup, not imputation: is_imputed is unchanged.
    Apply after P/Q reconstruction so the rule uses the final same-row S_avg.
    """
    result = frame.copy()
    counts = {}
    for column in ("P_dmd_max", "S_dmd_max"):
        failed_read = result[column].eq(0) & result["S_avg"].gt(1.0)
        counts[column] = int(failed_read.sum())
        result.loc[failed_read, column] = np.nan
    return result, counts


def derive(frame: pd.DataFrame) -> pd.DataFrame:
    """diff reads only the current and previous grid slot, including their NaNs."""
    result = frame.copy()
    if not result.index.is_unique or not result.index.is_monotonic_increasing:
        raise ValueError("Derivation requires a unique, increasing timestamp index")
    if len(result) > 1 and not (result.index.to_series().diff().iloc[1:] == pd.Timedelta(minutes=15)).all():
        raise ValueError("Derivation requires an explicit complete 15-minute grid")
    result["dEa"] = result["Ea_counter"].diff()
    result["dEr"] = result["Q_avg"] * 0.25
    result["S_avg"] = np.hypot(result["P_avg"], result["Q_avg"])
    result["PF"] = result["P_avg"].div(result["S_avg"].where(result["S_avg"] > 0))
    return result
