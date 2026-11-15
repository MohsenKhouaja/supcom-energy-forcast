"""Bounded short interpolation and energy-anchored earlier-weekday reconstruction.

Short gaps read only their original left/right readings, with the right anchor
on the gap's starting day. Medium gaps read original C0/C1 and both reactive
counter anchors; C1 is lookahead within the SAME supplied split partition.
Donors read only original, wholly observed clock-aligned windows 1..8 weeks
earlier; neither imputed donors nor later weekdays are used. No anchor or donor
crosses an explicit split boundary. Missing anchors or gaps >96 stay missing.

Analysis-ready imputation is not an observed label. Mark the closing derived
increment too, and exclude all H=96 target regions containing any imputed row.
Provide actual split boundaries before preparing model data. Month PF ranges
are read only for diagnostics, never to choose reconstructed values.
"""

from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

from .derive import derive

PRIMARY = ["Ea_counter", "P_avg", "Q_avg"]


def missing_runs(mask):
    mask = np.asarray(mask, dtype=bool)
    edges = np.diff(np.concatenate(([False], mask, [False])).astype(np.int8))
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)))


def _counter_profile(values, left, right, shape):
    """Honor ALL observed internal anchors as well as the two gap endpoints."""
    result = values[left:right+1].copy()
    known = np.flatnonzero(np.isfinite(result))
    uniform = False
    for a, b in zip(known, known[1:]):
        total = result[b]-result[a]
        if total < -1e-8:
            raise ValueError("Observed active counter decreases across an imputation anchor")
        weights = shape[a:b]
        if weights.sum() > 0:
            increments = max(total, 0) * weights / weights.sum()
        else:
            increments = np.full(b-a, max(total, 0)/(b-a))
            uniform = True
        if b-a > 1:
            result[a+1:b] = result[a] + np.cumsum(increments)[:-1]
    return result, np.diff(result), uniform


def impute(frame: pd.DataFrame, policy: dict):
    """Return derived frame, per-method filled-cell counts, and gap provenance.

    Runs are consecutive slots missing any primary channel, independently for
    each meter. Existing counter readings are preserved. For medium runs the
    reconstructed P/Q replace the entire L+1 interval span, INCLUDING the closing
    slot; raw readings remain available in the loader cache. The closing row is
    explicitly flagged. Individual reactive counters remain observed-only cross
    checks; their net change anchors reconstructed signed Q exactly.
    """
    short = int(policy["short_gap_max_intervals"])
    medium = int(policy["medium_gap_max_intervals"])
    weeks = int(policy.get("donor_lookback_weeks", 8))
    if (short, medium, weeks) != (4, 96, 8):
        raise ValueError("This policy requires 4/96 interval thresholds and 8 donor weeks")
    original = derive(frame)
    result = frame.copy()
    n = len(result)
    index = result.index
    boundaries = pd.DatetimeIndex(pd.to_datetime(policy.get("split_boundaries", [])))
    if boundaries.tz is not None:
        raise ValueError("Split boundaries must be naive timestamps")
    partitions = np.searchsorted(boundaries.sort_values().asi8, index.asi8, side="right")
    existing_flags = frame.get("is_imputed", pd.Series(False, index=index)).fillna(True).to_numpy(dtype=bool)
    flags = existing_flags.copy()
    methods = Counter()
    remaining_reasons = Counter()
    logs = []
    raw = {c: result[c].to_numpy(dtype=float, copy=True) for c in result.columns}
    masks = result[PRIMARY].isna().any(axis=1).to_numpy()
    pf_ranges = original["PF"].groupby(index.to_period("M")).agg(["min", "max"])

    for start, stop in missing_runs(masks):
        length = int(stop-start)
        entry = {"start": str(index[start]), "length": length, "intervals": length+1,
                 "method": "unfilled", "reactive_method": "unfilled", "donor_date": "",
                 "k": None, "k_q": None, "kq_over_k": None,
                 "min_PF": None, "max_PF": None, "warnings": []}
        if length > medium:
            remaining_reasons["long_gap"] += 1
            continue
        if start == 0 or stop == n:
            remaining_reasons["unbounded_gap"] += 1
            entry["warnings"].append("no two bounding readings")
            logs.append(entry)
            continue
        left, right = start-1, stop
        if partitions[left] != partitions[right]:
            remaining_reasons["split_boundary"] += 1
            entry["warnings"].append("anchors cross a split boundary")
            logs.append(entry)
            continue
        if length <= short:
            if index[right].normalize() != index[start].normalize():
                remaining_reasons["short_cross_day_boundary"] += 1
                continue
            for col in PRIMARY:
                if not (np.isfinite(raw[col][left]) and np.isfinite(raw[col][right])):
                    continue
                if col == "Ea_counter" and raw[col][right] < raw[col][left]:
                    raise ValueError("Observed active counter decreases across short gap")
                interpolated = np.linspace(raw[col][left], raw[col][right], length+2)[1:-1]
                positions = np.arange(start, stop)[~np.isfinite(raw[col][start:stop])]
                if len(positions):
                    result.loc[index[positions], col] = interpolated[positions-start]
                    flags[positions] = True
                    methods[("linear", col)] += len(positions)
            continue

        needed = ["Ea_counter", "Er_pos_counter", "Er_neg_counter"]
        if any(not (np.isfinite(raw[c][left]) and np.isfinite(raw[c][right])) for c in needed):
            remaining_reasons["missing_counter_anchor"] += 1
            entry["warnings"].append("missing active or reactive bounding counter")
            logs.append(entry)
            continue
        total = raw["Ea_counter"][right]-raw["Ea_counter"][left]
        positive = raw["Er_pos_counter"][right]-raw["Er_pos_counter"][left]
        negative = raw["Er_neg_counter"][right]-raw["Er_neg_counter"][left]
        if min(total, positive, negative) < -1e-8:
            raise ValueError("A bounding energy counter decreases; anchored policy is invalid")
        net_total = positive-negative
        active_shape = reactive_shape = None
        for week in range(1, weeks+1):
            donor_left, donor_right = left-week*672, right-week*672
            if donor_left < 0:
                break
            if partitions[donor_left] != partitions[left] or partitions[donor_right] != partitions[left]:
                continue
            if index[donor_right] >= index[start].normalize():
                continue
            if existing_flags[donor_left:donor_right+1].any():
                continue
            if not all(np.isfinite(raw[c][donor_left:donor_right+1]).all()
                       for c in [*PRIMARY, "Er_pos_counter", "Er_neg_counter"]):
                continue
            active_shape = np.maximum(np.diff(raw["Ea_counter"][donor_left:donor_right+1]), 0)
            reactive_shape = (np.diff(raw["Er_pos_counter"][donor_left:donor_right+1])
                              - np.diff(raw["Er_neg_counter"][donor_left:donor_right+1]))
            entry["donor_date"] = str(index[donor_left+1].date())
            break
        if active_shape is None or active_shape.sum() <= 0:
            active_shape = np.ones(length+1)
            entry["method"] = "uniform"
        else:
            entry["method"] = "scaled_weekday"
            entry["k"] = float(total/active_shape.sum())
        counter, increments, used_uniform_segment = _counter_profile(raw["Ea_counter"], left, right, active_shape)
        if used_uniform_segment and entry["method"] == "scaled_weekday":
            entry["warnings"].append("zero donor sum in an internal-anchor segment: uniform there")
        if reactive_shape is None or abs(reactive_shape.sum()) <= 1e-10:
            reactive_increments = np.full(length+1, net_total/(length+1))
            entry["reactive_method"] = "uniform"
        else:
            entry["k_q"] = float(net_total/reactive_shape.sum())
            reactive_increments = reactive_shape*entry["k_q"]
            entry["reactive_method"] = "scaled_weekday"
        missing_counter = np.flatnonzero(~np.isfinite(raw["Ea_counter"][start:stop])) + start
        result.loc[index[missing_counter], "Ea_counter"] = counter[missing_counter-left]
        methods[(entry["method"], "Ea_counter")] += len(missing_counter)
        span = index[start:right+1]
        result.loc[span, "P_avg"] = increments*4
        result.loc[span, "Q_avg"] = reactive_increments*4
        methods[(entry["method"], "P_avg")] += len(span)
        methods[(entry["reactive_method"], "Q_avg")] += len(span)
        flags[start:right+1] = True
        entry["active_total_kWh"] = float(total)
        entry["net_reactive_total_kvarh"] = float(net_total)
        if entry["k"] is not None and (entry["k"] < .5 or entry["k"] > 2):
            entry["warnings"].append("k outside [0.5, 2]")
        if entry["k"] not in (None, 0) and entry["k_q"] is not None:
            entry["kq_over_k"] = entry["k_q"]/entry["k"]
            if not .8 <= entry["kq_over_k"] <= 1.25:
                entry["warnings"].append("k_q/k outside [0.8, 1.25]")
        elif entry["k"] == 0 and entry["k_q"] not in (None, 0):
            entry["warnings"].append("k=0 but k_q!=0: ratio undefined")
        rebuilt_s = np.hypot(increments*4, reactive_increments*4)
        pf = np.divide(increments*4, rebuilt_s, out=np.full(len(span), np.nan), where=rebuilt_s>0)
        if np.isfinite(pf).any():
            entry["min_PF"], entry["max_PF"] = float(np.nanmin(pf)), float(np.nanmax(pf))
            for j, ts in enumerate(span):
                bounds = pf_ranges.loc[ts.to_period("M")]
                if np.isfinite(pf[j]) and np.isfinite(bounds["min"]) and (
                        pf[j] < bounds["min"]-1e-9 or pf[j] > bounds["max"]+1e-9):
                    entry["warnings"].append("PF outside observed surrounding-month range")
                    break
        logs.append(entry)
    result = derive(result)
    affected_increments = result["dEa"].notna() & original["dEa"].isna()
    flags |= affected_increments.to_numpy()
    result["is_imputed"] = flags
    stats = {"methods": {f"{method}:{col}": int(count) for (method, col), count in sorted(methods.items())},
             "unfilled_reasons": dict(remaining_reasons),
             "imputed_rows": int(flags.sum()),
             "newly_filled_primary_cells": int((frame[PRIMARY].isna() & result[PRIMARY].notna()).sum().sum()),
             "replaced_observed_primary_cells": int(((frame[PRIMARY] != result[PRIMARY]) & frame[PRIMARY].notna() & result[PRIMARY].notna()).sum().sum()),
             "remaining_nan": {c: int(result[c].isna().sum()) for c in result.columns if c != "is_imputed"}}
    return result, stats, logs
