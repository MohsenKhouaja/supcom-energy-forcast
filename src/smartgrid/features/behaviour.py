"""Observed-only descriptive behaviour parameters; no models or window arrays.

Timestamps remain naive export local time. Imputed measurements are masked on
the ORIGINAL grid, never dropped before consecutive-run or lag calculations.
Meteorological seasons use DJF/MAM/JJA/SON in the northern hemisphere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import calendar

import numpy as np
import pandas as pd


@dataclass
class BehaviourResult:
    tables: dict[str, pd.DataFrame]
    excluded_imputed: int
    missing_observed: int
    findings: dict = field(default_factory=dict)


def _observed(data):
    frame = data.copy()
    if "timestamp" in frame:
        frame = frame.set_index("timestamp")
    frame = frame.sort_index(kind="stable")
    frame["is_imputed"] = frame["is_imputed"].fillna(True).astype(bool)
    numeric = frame.select_dtypes(include="number").columns
    frame.loc[frame["is_imputed"], numeric] = np.nan
    return frame


def _counts(frame, columns):
    flag = frame["is_imputed"]
    return {"observed_intervals": int((~flag & frame[columns].notna().all(axis=1)).sum()),
            "excluded_imputed": int(flag.sum()),
            "missing_observed": int((~flag & frame[columns].isna().any(axis=1)).sum())}


def _result(frame, columns, tables, findings=None):
    counts = _counts(frame, columns)
    return BehaviourResult(tables, counts["excluded_imputed"], counts["missing_observed"], findings or {})


def _aggregate(frame, keys, column, operation="mean"):
    rows = []
    for key, group in frame.groupby(keys, sort=True):
        valid = group[column].dropna()
        value = (valid.sum() if len(valid) else np.nan) if operation == "sum" else valid.mean()
        rows.append({"period": key, "value": value, **_counts(group, [column])})
    return pd.DataFrame(rows).set_index("period")


def _seasons(index):
    month = index.month
    return np.select([month.isin([12, 1, 2]), month.isin([3, 4, 5]), month.isin([6, 7, 8])],
                     ["Winter", "Spring", "Summer"], default="Autumn")


def weekday_weekend(index):
    """Saturday and Sunday are weekend; this calendar classification uses no load."""
    return np.where(pd.DatetimeIndex(index).day_of_week >= 5, "Weekend", "Weekday")


def cumulative_energy(data):
    """Observed dEa sums by calendar day, Monday-start week, month and year."""
    frame = _observed(data)
    tables = {}
    for name, frequency in (("daily", "D"), ("weekly", "W-SUN"), ("monthly", "M"), ("annual", "Y")):
        table = _aggregate(frame, frame.index.to_period(frequency).start_time, "dEa", "sum").rename(columns={"value": "energy_kWh"})
        table["running_total_kWh"] = table["energy_kWh"].cumsum()
        tables[name] = table
    return _result(frame, ["dEa"], tables, {"total_observed_kWh": float(frame["dEa"].sum(min_count=1))})


def base_load(data):
    """Minimum observed daily P_avg, earliest tied occurrence, and hour-bin counts."""
    frame = _observed(data)
    rows = []
    for day, group in frame.groupby(frame.index.normalize()):
        values = group["P_avg"].dropna()
        when = values.idxmin() if len(values) else None
        rows.append({"day": day, "minimum_kW": values.min(), "time": when,
                     "hour": when.hour if when is not None else np.nan, **_counts(group, ["P_avg"])})
    daily = pd.DataFrame(rows).set_index("day")
    hours = daily["hour"].dropna().astype(int).value_counts().reindex(range(24), fill_value=0).sort_index().to_frame("days")
    hours.index.name = "hour"
    hours["excluded_imputed"] = int(frame["is_imputed"].sum())
    return _result(frame, ["P_avg"], {"daily": daily, "hour_distribution": hours})


def _longest_run(mask, index):
    longest = run = 0
    previous = None
    for flag, timestamp in zip(mask, index):
        if not flag:
            run = 0
        else:
            run = run+1 if previous is not None and timestamp-previous == pd.Timedelta(minutes=15) else 1
            longest = max(longest, run)
        previous = timestamp
    return longest


def peak_demand(data):
    """Daily maxima and LONGEST consecutive run >=90% of each daily maximum.

    Missing/imputed slots and timestamp gaps break runs. Equal maxima use their
    earliest occurrence. Duration is not the sum of disconnected near-peak runs.
    """
    frame = _observed(data)
    rows = []
    for day, group in frame.groupby(frame.index.normalize()):
        row = {"day": day, **_counts(group, ["P_avg", "S_avg"])}
        for prefix, column in (("P", "P_avg"), ("S", "S_avg")):
            values = group[column].dropna()
            maximum = values.max()
            duration = _longest_run((group[column] >= .9*maximum).fillna(False), group.index) if len(values) else np.nan
            row.update({prefix+"_maximum": maximum, prefix+"_time": values.idxmax() if len(values) else None,
                        prefix+"_duration_intervals": duration, prefix+"_duration_hours": duration*.25})
        rows.append(row)
    return _result(frame, ["P_avg", "S_avg"], {"daily": pd.DataFrame(rows).set_index("day")})


def provisional_vacation_weeks(data):
    """PROVISIONAL only: abs(weekday/weekend - 1)<=0.20 when both means exist.

    Partial weeks are classified by the same requested rule and flagged as
    partial; no unsupported SUP'COM term dates are introduced. Zero/zero means
    have zero contrast; positive weekday / zero weekend is not vacation-like.
    """
    frame = _observed(data)
    rows = []
    for week, group in frame.groupby(frame.index.to_period("W-SUN").start_time):
        weekend = group.index.day_of_week >= 5
        weekday_mean = group.loc[~weekend, "P_avg"].mean()
        weekend_mean = group.loc[weekend, "P_avg"].mean()
        available = pd.notna(weekday_mean) and pd.notna(weekend_mean)
        contrast = (abs(weekday_mean-weekend_mean)/abs(weekend_mean)
                    if available and weekend_mean != 0 else 0. if available and weekday_mean == 0 else np.nan)
        vacation = bool(abs(weekday_mean-weekend_mean) <= .20*abs(weekend_mean)) if available else None
        rows.append({"week_start": week, "weekday_mean_kW": weekday_mean, "weekend_mean_kW": weekend_mean,
                     "contrast": contrast, "PROVISIONAL_vacation_like": vacation,
                     "partial_week": len(group) != 672,
                     "weekday_excluded_imputed": int(group.loc[~weekend, "is_imputed"].sum()),
                     "weekend_excluded_imputed": int(group.loc[weekend, "is_imputed"].sum()), **_counts(group, ["P_avg"])})
    return _result(frame, ["P_avg"], {"weeks": pd.DataFrame(rows).set_index("week_start")})


def power_comparisons(data):
    """Observed mean power by day type, PROVISIONAL academic proxy and season."""
    frame = _observed(data)
    weeks = provisional_vacation_weeks(data).tables["weeks"]
    lookup = weeks["PROVISIONAL_vacation_like"].to_dict()
    labels = []
    for week in frame.index.to_period("W-SUN").start_time:
        flag = lookup.get(week)
        labels.append("Vacation-like PROVISIONAL" if flag is True else "Term-like PROVISIONAL" if flag is False else "Unclassified PROVISIONAL")
    frame["day_type"] = weekday_weekend(frame.index)
    frame["academic_PROXY_PROVISIONAL"] = labels
    frame["season"] = _seasons(frame.index)
    tables = {}
    for column in ("day_type", "academic_PROXY_PROVISIONAL", "season"):
        rows = []
        for key, group in frame.groupby(column):
            rows.append({"group": key, "mean_kW": group["P_avg"].mean(), "median_kW": group["P_avg"].median(),
                         **_counts(group, ["P_avg"])})
        tables[column] = pd.DataFrame(rows).set_index("group")
    # Plot data contains masked measurements, so no imputed value can enter a boxplot.
    tables["plot_data"] = frame[["P_avg", "day_type", "academic_PROXY_PROVISIONAL", "season", "is_imputed"]]
    return _result(frame, ["P_avg"], tables)


def site_behaviour(data):
    """First/last observed P>1.5*daily minimum; flat days return Python None.

    These are activity proxies, not observed switch states. Variability uses
    sample standard deviation and variance (ddof=1).
    """
    frame = _observed(data)
    rows = []
    for day, group in frame.groupby(frame.index.normalize()):
        minimum = group["P_avg"].min()
        crossing = group.index[group["P_avg"] > 1.5*minimum]
        rows.append({"day": day, "threshold_kW": 1.5*minimum,
                     "activation": crossing[0] if len(crossing) else None,
                     "deactivation": crossing[-1] if len(crossing) else None, **_counts(group, ["P_avg"])})
    daily = pd.DataFrame(rows).set_index("day")
    for col in ("activation", "deactivation"):
        daily[col] = pd.Series([row[col] for row in rows], index=daily.index, dtype=object)
    tables = {"daily": daily}
    for name, keys in (("monthly_variability", frame.index.to_period("M").start_time), ("weekday_variability", frame.index.day_of_week)):
        records = []
        for key, group in frame.groupby(keys):
            records.append({"group": key, "std_kW": group["P_avg"].std(ddof=1),
                            "variance_kW2": group["P_avg"].var(ddof=1), **_counts(group, ["P_avg"])})
        tables[name] = pd.DataFrame(records).set_index("group")
    return _result(frame, ["P_avg"], tables)


def seasonality(data):
    """Monthly observed energy plus season-specific quarter-hour mean P profiles."""
    frame = _observed(data)
    monthly = cumulative_energy(data).tables["monthly"]
    frame["season"] = _seasons(frame.index)
    frame["quarter"] = frame.index.hour*4+frame.index.minute//15
    profile = []
    for (season, quarter), group in frame.groupby(["season", "quarter"]):
        profile.append({"season": season, "quarter": quarter, "mean_kW": group["P_avg"].mean(), **_counts(group, ["P_avg"])})
    seasons = []
    for season, group in frame.groupby("season"):
        seasons.append({"season": season, "total_kWh": group["dEa"].sum(min_count=1),
                        "observed_daily_equivalent_kWh": group["dEa"].mean()*96,
                        "mean_monthly_observed_kWh": monthly.loc[_seasons(monthly.index) == season, "energy_kWh"].mean(),
                        "month_count": group.index.to_period("M").nunique(), **_counts(group, ["dEa"])})
    return _result(frame, ["dEa", "P_avg"], {"monthly": monthly, "seasonal": pd.DataFrame(seasons).set_index("season"),
                   "daily_profiles": pd.DataFrame(profile).set_index(["season", "quarter"])})


def autocorrelation(data, max_lag=700):
    """Pairwise Pearson ACF on original 15-minute positions, never compressed.

    A lag uses only pairs whose two endpoints are observed and finite. Pair
    exclusion counts are supplied separately from global excluded-row counts.
    """
    frame = _observed(data)
    values = frame["dEa"].to_numpy(float)
    flags = frame["is_imputed"].to_numpy(bool)
    rows = []
    for lag in range(max_lag+1):
        a = values[:len(values)-lag] if lag else values
        b = values[lag:]
        if lag >= len(values):
            a = b = np.array([], dtype=float)
        good = np.isfinite(a) & np.isfinite(b)
        x, y = a[good], b[good]
        denominator = np.sqrt(np.sum((x-x.mean())**2)*np.sum((y-y.mean())**2)) if len(x)>1 else 0.
        correlation = float(np.sum((x-x.mean())*(y-y.mean()))/denominator) if denominator>0 else np.nan
        flagged = int((flags[:len(flags)-lag] | flags[lag:]).sum()) if 0<lag<len(flags) else int(flags.sum()) if lag==0 else 0
        rows.append({"lag": lag, "correlation": correlation, "observed_pairs": len(x),
                     "excluded_imputed_pairs": flagged, "other_missing_pairs": len(a)-len(x)-flagged})
    return _result(frame, ["dEa"], {"lags": pd.DataFrame(rows).set_index("lag")})


def power_factor(data):
    """Monthly observed PF and positive-Q shares; alerts are screening candidates.

    Candidate warning/severe means ANY PF interval below .90/.80, respectively;
    an official persistence/duration alert policy has not been supplied.
    """
    frame = _observed(data)
    rows = []
    for month, group in frame.groupby(frame.index.to_period("M").start_time):
        pf, q = group["PF"].dropna(), group["Q_avg"].dropna()
        below90, below80 = int(pf.lt(.90).sum()), int(pf.lt(.80).sum())
        rows.append({"month": month, "mean_PF": pf.mean(), "minimum_PF": pf.min(), "PF_intervals": len(pf),
                     "below_090": below90, "below_080": below80,
                     "Phase5_screening_candidate": "severe" if below80 else "warning" if below90 else "none",
                     "Phase5_monthly_mean_candidate": "severe" if pf.mean()<.80 else "warning" if pf.mean()<.90 else "none",
                     "positive_Q_intervals": int(q.gt(0).sum()), "Q_intervals": len(q),
                     "positive_Q_share": float(q.gt(0).mean()) if len(q) else np.nan,
                     **_counts(group, ["PF", "Q_avg"])})
    return _result(frame, ["PF", "Q_avg"], {"monthly": pd.DataFrame(rows).set_index("month")})


def load_duration(data, subscribed_kva=600.):
    """Observed S duration curve and strict exceedances of the supplied reference."""
    frame = _observed(data)
    values = frame["S_avg"].dropna().sort_values(ascending=False)
    curve = pd.DataFrame({"exceedance_percent": (np.arange(len(values))+1)/max(1, len(values))*100,
                          "S_avg_kVA": values.to_numpy()})
    table = pd.DataFrame([{"fraction_of_subscription": fraction, "threshold_kVA": subscribed_kva*fraction,
                           "intervals_above": int(values.gt(subscribed_kva*fraction).sum()),
                           "percent_above": float(values.gt(subscribed_kva*fraction).mean()*100) if len(values) else np.nan,
                           **_counts(frame, ["S_avg"])} for fraction in (.5, .6, .7, .8)])
    return _result(frame, ["S_avg"], {"curve": curve, "thresholds": table},
                   {"maximum_observed_kVA": values.max(), "subscribed_reference_kVA": subscribed_kva})


def demand_divergence(data):
    """Signed and absolute demand-minus-average gaps, reported without invariants."""
    frame = _observed(data)
    frame["gap_kVA"] = frame["S_dmd_max"]-frame["S_avg"]
    rows, seasons = [], []
    for month, group in frame.groupby(frame.index.to_period("M").start_time):
        gap = group["gap_kVA"].dropna()
        rows.append({"month": month, "mean_gap_kVA": gap.mean(), "median_gap_kVA": gap.median(),
                     "P90_gap_kVA": gap.quantile(.9), "mean_absolute_gap_kVA": gap.abs().mean(), **_counts(group, ["gap_kVA"])})
    for season, group in frame.groupby(_seasons(frame.index)):
        seasons.append({"season": season, "mean_gap_kVA": group["gap_kVA"].mean(),
                        "mean_absolute_gap_kVA": group["gap_kVA"].abs().mean(), **_counts(group, ["gap_kVA"])})
    return _result(frame, ["gap_kVA"], {"monthly": pd.DataFrame(rows).set_index("month"), "seasonal": pd.DataFrame(seasons).set_index("season")})


def meter_contributions(data, all_meters):
    """Meter observed energy / observed EM_VIRTUAL energy, not a disjoint stack.

    Transformer and downstream meters overlap. Their shares MUST NOT be summed.
    Each meter's coverage/exclusion counts are shown; differing missingness can
    affect shares. Seasonal mean P gives a coverage-normalized comparison.
    """
    site = _observed(data)
    denominator = site["dEa"].groupby(site.index.to_period("M").start_time).sum(min_count=1)
    meters = _observed(all_meters)
    monthly, seasonal = [], []
    for meter, group in meters.groupby("meter"):
        for month, block in group.groupby(group.index.to_period("M").start_time):
            energy = block["dEa"].sum(min_count=1)
            monthly.append({"meter": meter, "month": month, "energy_kWh": energy,
                            "EM_observed_kWh": denominator.get(month, np.nan),
                            "share_percent": energy/denominator.get(month, np.nan)*100,
                            **_counts(block, ["dEa"])})
        row = {"meter": meter}
        for season in ("Summer", "Winter"):
            block = group.loc[_seasons(group.index) == season]
            row[season+"_mean_kW"] = block["P_avg"].mean()
            row[season+"_excluded_imputed"] = int(block["is_imputed"].sum())
            row[season+"_observed_intervals"] = int(block["P_avg"].notna().sum())
        row["summer_minus_winter_kW"] = row["Summer_mean_kW"]-row["Winter_mean_kW"]
        seasonal.append(row)
    return _result(meters, ["dEa"], {"monthly": pd.DataFrame(monthly).set_index(["meter", "month"]),
                   "seasonal_change": pd.DataFrame(seasonal).set_index("meter")})


def _rolling_all(mask, width):
    values = np.asarray(mask, dtype=np.int64)
    prefix = np.concatenate(([0], np.cumsum(values)))
    result = np.zeros(len(values), dtype=bool)
    if len(values) >= width:
        result[width-1:] = prefix[width:]-prefix[:-width] == width
    return result


def split_coverage(data):
    """Counts only: no windows or model features are materialized.

    Explicit exception to observed-only summaries: finite imputed INPUTS may be
    used, as previously agreed. All 96 future labels must be observed and finite.
    Count both earlier-split historical context and strict within-split context.
    """
    raw = data.copy()
    if "timestamp" in raw:
        raw = raw.set_index("timestamp")
    raw = raw.sort_index()
    fields = ["dEa", "dEr", "P_avg", "S_avg"]
    flags = raw["is_imputed"].fillna(True).to_numpy(bool)
    finite = np.isfinite(raw[fields]).all(axis=1).to_numpy()
    label_valid = finite & ~flags
    history = _rolling_all(finite, 672)
    # Count the following 96 labels by suffix prefix sums, without window arrays.
    next_valid = np.zeros(len(raw), dtype=bool)
    prefix = np.concatenate(([0], np.cumsum(label_valid, dtype=np.int64)))
    origins = np.arange(max(0, len(raw)-96))
    next_valid[origins] = prefix[origins+97]-prefix[origins+1] == 96
    proposals = [("train", "2022-07-01", "2025-03-01"), ("val", "2025-03-01", "2025-09-01"), ("test", "2025-09-01", "2026-03-01")]
    rows, blocked, energy_ranges = [], [], []
    observed_frame = _observed(raw)
    for name, begin, end in proposals:
        start, stop = pd.Timestamp(begin), pd.Timestamp(end)
        inside = (raw.index >= start) & (raw.index < stop)
        target_inside = inside & (raw.index+pd.Timedelta(minutes=96*15) < stop)
        context_inside = raw.index-pd.Timedelta(minutes=671*15) >= start
        possible = target_inside & history & next_valid
        strict = possible & context_inside
        observed = inside & label_valid
        rows.append({"split": name, "start": start, "end_exclusive": stop,
                     "grid_rows": int(inside.sum()), "observed_complete_rows": int(observed.sum()),
                     "excluded_imputed": int((inside & flags).sum()), "missing_observed": int((inside & ~flags & ~finite).sum()),
                     "eligible_origins_prior_context": int(possible.sum()), "eligible_origins_strict_context": int(strict.sum()),
                     "history_unavailable_origins": int((inside & ~history).sum()),
                     "target_boundary_origins": int((inside & ~target_inside).sum()),
                     "target_unobserved_origins": int((target_inside & ~next_valid).sum())})
        block = observed_frame.loc[inside]
        if len(block):
            monthly = _aggregate(block, block.index.to_period("M").start_time, "dEa", "sum")
            finite_months = monthly.dropna(subset=["value"])
            if len(finite_months):
                high, low = finite_months.value.idxmax(), finite_months.value.idxmin()
                energy_ranges.append({"split": name, "high_load_month": high, "high_month_observed_kWh": monthly.loc[high,"value"],
                                      "high_month_excluded_imputed": int(monthly.loc[high,"excluded_imputed"]),
                                      "low_load_month": low, "low_month_observed_kWh": monthly.loc[low,"value"],
                                      "low_month_excluded_imputed": int(monthly.loc[low,"excluded_imputed"])})
        # All blocked runs, retaining their exact original grid timestamps.
        bad = inside & ~possible
        edges = np.diff(np.concatenate(([False], bad, [False])).astype(np.int8))
        for a, b in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
            blocked.append({"split": name, "first_origin": raw.index[a], "last_origin": raw.index[b-1], "intervals": int(b-a)})
    ranges = pd.DataFrame(energy_ranges) if energy_ranges else pd.DataFrame(columns=["split"])
    return _result(observed_frame, fields, {"splits": pd.DataFrame(rows).set_index("split"),
                   "blocked_origin_runs": pd.DataFrame(blocked), "monthly_energy_range": ranges.set_index("split")})


@dataclass
class EDAContext:
    root: Path
    em: pd.DataFrame
    meters: pd.DataFrame
    source_hashes: dict
    results: dict = field(default_factory=dict)
    figures: list = field(default_factory=list)


def load_eda_data(root=None):
    """Read only the existing Parquets; never invoke or import ingestion."""
    import hashlib
    root = Path(root) if root else Path(__file__).resolve().parents[3]
    sources = [root/"data/processed/em_virtual.parquet", root/"data/processed/all_meters.parquet"]
    hashes = {}
    for path in sources:
        with path.open("rb") as handle:
            hashes[path.name] = hashlib.file_digest(handle, "sha256").hexdigest()
    em = pd.read_parquet(sources[0], use_threads=False).set_index("timestamp")
    meters = pd.read_parquet(sources[1], columns=["timestamp", "meter", "dEa", "P_avg", "Q_avg", "S_avg", "is_imputed"], use_threads=False).set_index("timestamp")
    print(f"Existing Parquets: EM={len(em):,} rows, all_meters={len(meters):,} rows; EM imputed rows excluded={int(em.is_imputed.sum())}.")
    return EDAContext(root, em, meters, hashes)


def _parameter_figures(key, result):
    """Standard static scientific plots; every saved figure is 150 dpi."""
    import matplotlib.pyplot as plt
    tables = result.tables
    figures = []
    if key == "energy":
        fig, axes = plt.subplots(4, 1, figsize=(12, 11))
        for ax, name in zip(axes, ("daily", "weekly", "monthly", "annual")):
            table = tables[name]
            ax.plot(table.index, table["energy_kWh"], marker="o" if name=="annual" else None, linewidth=.8)
            ax.set(ylabel="kWh", title=f"{name.capitalize()} observed active energy")
        figures.append(("energy_totals.png", fig))
    elif key == "base_load":
        fig, axes = plt.subplots(2, 1, figsize=(12, 7))
        axes[0].plot(tables["daily"].index, tables["daily"]["minimum_kW"], linewidth=.6)
        axes[0].set(ylabel="Daily minimum P (kW)")
        hours = tables["hour_distribution"]
        axes[1].bar(hours.index, hours["days"])
        axes[1].set(xlabel="Hour of earliest daily minimum (export local time)", ylabel="Days", xticks=range(24))
        figures.append(("base_load_and_hour.png", fig))
    elif key == "peaks":
        table = tables["daily"]
        fig, axes = plt.subplots(3, 1, figsize=(12, 10))
        for prefix in ("P", "S"):
            axes[0].plot(table.index, table[prefix+"_maximum"], label=prefix, linewidth=.7)
            axes[1].plot(table.index, table[prefix+"_duration_hours"], label=prefix, linewidth=.7)
            times = pd.to_datetime(table[prefix+"_time"])
            axes[2].scatter(table.index, times.dt.hour+times.dt.minute/60, label=prefix, s=3)
        for ax in axes:
            ax.legend()
        axes[0].set(ylabel="Daily max P (kW), S (kVA)")
        axes[1].set(ylabel="Longest consecutive >=90% band (h)")
        axes[2].set(ylabel="Earliest max hour", ylim=(0, 24))
        figures.append(("daily_peaks_and_duration.png", fig))
    elif key == "power_comparisons":
        fig, axes = plt.subplots(1, 3, figsize=(15, 6))
        for ax, column in zip(axes, ("day_type", "academic_PROXY_PROVISIONAL", "season")):
            groups = [(label, block["P_avg"].dropna().to_numpy()) for label, block in tables["plot_data"].groupby(column)]
            ax.boxplot([values for _, values in groups], showfliers=False)
            ax.set_xticks(range(1, len(groups)+1), [label for label, _ in groups], rotation=30, ha="right")
            ax.set(ylabel="Observed P_avg (kW)", title="PROVISIONAL academic proxy" if "PROVISIONAL" in column else column)
        figures.append(("mean_power_comparisons.png", fig))
    elif key == "activity":
        fig, axes = plt.subplots(3, 1, figsize=(12, 10))
        daily = tables["daily"]
        for col in ("activation", "deactivation"):
            times = pd.to_datetime(daily[col])
            axes[0].scatter(daily.index, times.dt.hour+times.dt.minute/60, s=3, label=col)
        axes[0].set(ylabel="Activity proxy clock hour", ylim=(0, 24))
        axes[0].legend()
        monthly = tables["monthly_variability"]
        axes[1].plot(monthly.index, monthly.std_kW)
        axes[1].set(ylabel="Monthly std P (kW)")
        weekly = tables["weekday_variability"]
        axes[2].bar(weekly.index, weekly.std_kW)
        axes[2].set_xticks(range(7), [calendar.day_abbr[i] for i in range(7)])
        axes[2].set(ylabel="Weekday std P (kW)")
        figures.append(("activity_and_variability.png", fig))
    elif key == "PROVISIONAL_calendar":
        from matplotlib.patches import Patch
        table = tables["weeks"]
        fig, ax = plt.subplots(figsize=(14, 5))
        ax.plot(table.index, table.weekday_mean_kW, label="Weekday mean")
        ax.plot(table.index, table.weekend_mean_kW, label="Weekend mean")
        for start, row in table.iterrows():
            if row["PROVISIONAL_vacation_like"] is True or row["PROVISIONAL_vacation_like"] == True:
                ax.axvspan(start, start+pd.Timedelta(days=7), color="orange", alpha=.17)
        handles, labels = ax.get_legend_handles_labels()
        ax.legend(handles+[Patch(color="orange", alpha=.17)], labels+["Vacation-like PROVISIONAL"])
        ax.set(ylabel="Observed mean P (kW)", title="PROVISIONAL inferred calendar; not an academic calendar")
        figures.append(("PROVISIONAL_vacation_timeline.png", fig))
    elif key == "seasonality":
        table = tables["monthly"]
        colors = {"Summer": "#d97706", "Winter": "#2563eb", "Spring": "#16a34a", "Autumn": "#9333ea"}
        fig, ax = plt.subplots(figsize=(15, 5))
        ax.bar(np.arange(len(table)), table.energy_kWh, color=[colors[s] for s in _seasons(table.index)])
        ax.set_xticks(range(len(table)), table.index.strftime("%Y-%m"), rotation=90)
        ax.set(ylabel="Observed dEa total (kWh)", title=f"Whole history: {len(table)} calendar months")
        figures.append(("monthly_energy_seasonality.png", fig))
        fig, ax = plt.subplots(figsize=(11, 5))
        for season, group in tables["daily_profiles"].reset_index().groupby("season"):
            excluded = int(tables["seasonal"].loc[season, "excluded_imputed"])
            ax.plot(group.quarter/4, group.mean_kW, label=f"{season} (excluded {excluded})", color=colors[season])
        ax.set(xlabel="Export local hour", ylabel="Mean observed P_avg (kW)", xlim=(0, 24))
        ax.legend()
        figures.append(("seasonal_daily_profiles.png", fig))
    elif key == "autocorrelation":
        table = tables["lags"]
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(table.index, table.correlation)
        for lag, color in ((96, "#dc2626"), (672, "#16a34a")):
            ax.axvline(lag, color=color, linestyle="--", label=f"lag {lag}: r={table.loc[lag, 'correlation']:.4f}; pairs={table.loc[lag, 'observed_pairs']}")
        ax.set(xlabel="Lag (15-minute intervals)", ylabel="Pairwise observed Pearson ACF", xlim=(0, table.index.max()))
        ax.legend()
        figures.append(("energy_autocorrelation.png", fig))
    elif key == "power_factor":
        table = tables["monthly"]
        fig, axes = plt.subplots(3, 1, figsize=(12, 10))
        axes[0].plot(table.index, table.mean_PF, label="Mean")
        axes[0].plot(table.index, table.minimum_PF, label="Minimum")
        for threshold in (.90, .80):
            axes[0].axhline(threshold, linestyle="--", color="grey")
        axes[0].set(ylabel="Observed PF")
        axes[0].legend()
        axes[1].plot(table.index, table.below_090, label="PF <0.90")
        axes[1].plot(table.index, table.below_080, label="PF <0.80")
        axes[1].set(ylabel="Observed intervals")
        axes[1].legend()
        axes[2].plot(table.index, table.positive_Q_share*100)
        axes[2].set(ylabel="Positive Q intervals (%)")
        figures.append(("monthly_power_factor.png", fig))
    elif key == "load_duration":
        fig, ax = plt.subplots(figsize=(11, 6))
        ax.plot(tables["curve"].exceedance_percent, tables["curve"].S_avg_kVA)
        subscription = result.findings["subscribed_reference_kVA"]
        ax.axhline(subscription, color="red", label=f"Subscribed reference: {subscription:g} kVA (supplied)")
        for value in tables["thresholds"].threshold_kVA:
            ax.axhline(value, color="grey", linestyle=":", linewidth=.6)
        ax.set(xlabel="Observed intervals equalled/exceeded (%)", ylabel="S_avg (kVA)", xlim=(0, 100), ylim=(0, subscription*1.05))
        ax.legend()
        figures.append(("apparent_load_duration.png", fig))
    elif key == "demand_divergence":
        table = tables["monthly"]
        fig, axes = plt.subplots(2, 1, figsize=(12, 7))
        axes[0].plot(table.index, table.mean_gap_kVA, label="Mean signed gap")
        axes[0].plot(table.index, table.median_gap_kVA, label="Median signed gap")
        axes[0].axhline(0, color="grey", linestyle="--")
        axes[0].set(ylabel="S_dmd_max - S_avg (kVA)")
        axes[0].legend()
        axes[1].plot(table.index, table.mean_absolute_gap_kVA)
        axes[1].set(ylabel="Mean absolute gap (kVA)")
        figures.append(("monthly_demand_gap.png", fig))
    elif key == "meter_contributions":
        matrix = tables["monthly"].reset_index().pivot(index="meter", columns="month", values="share_percent").drop(index="EM_VIRTUAL", errors="ignore")
        fig, ax = plt.subplots(figsize=(15, 8))
        plot = ax.imshow(np.ma.masked_invalid(matrix.to_numpy()), aspect="auto", interpolation="none")
        ax.set_xticks(range(len(matrix.columns)), pd.DatetimeIndex(matrix.columns).strftime("%Y-%m"), rotation=90)
        ax.set_yticks(range(len(matrix.index)), matrix.index)
        fig.colorbar(plot, ax=ax, label="Meter observed dEa / site observed dEa (%)")
        ax.set(title="Overlapping meter shares: do not sum parents and downstream meters")
        figures.append(("monthly_meter_shares.png", fig))
        change = tables["seasonal_change"].drop(index="EM_VIRTUAL", errors="ignore").sort_values("summer_minus_winter_kW")
        fig, ax = plt.subplots(figsize=(12, 8))
        ax.barh(change.index, change.summer_minus_winter_kW)
        ax.axvline(0, color="grey")
        ax.set(xlabel="Summer minus winter mean observed P_avg (kW)", title="Meter changes overlap; hierarchy is not a disjoint allocation")
        figures.append(("summer_meter_changes.png", fig))
    for _, fig in figures:
        fig.suptitle(f"Observed only; excluded imputed rows={result.excluded_imputed:,}; other missing={result.missing_observed:,}", fontsize=10)
        fig.tight_layout(rect=(0, 0, 1, .96))
    return figures


def present(context, key, result):
    """Notebook presentation only; persist full aggregate tables and PNGs."""
    import matplotlib.pyplot as plt
    from IPython.display import Image, display
    context.results[key] = result
    reports = context.root/"reports"
    figures = reports/"figures"
    figures.mkdir(parents=True, exist_ok=True)
    for name, table in result.tables.items():
        if name not in ("plot_data", "curve"):
            table.to_csv(reports/f"eda_{key}_{name}.csv")
    print(f"{key}: excluded imputed={result.excluded_imputed:,}; other missing observed={result.missing_observed:,}")
    for name, fig in _parameter_figures(key, result):
        path = figures/name
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        context.figures.append((name, key, result.excluded_imputed, result.missing_observed))
        display(Image(filename=str(path)))


def _markdown(table, digits=4):
    def cell(value):
        if value is None or pd.isna(value):
            return "NA"
        if isinstance(value, (float, np.floating)):
            return f"{value:.{digits}f}"
        if isinstance(value, pd.Timestamp):
            return value.strftime("%Y-%m-%d %H:%M")
        return str(value).replace("|", "/")
    data = table.reset_index()
    lines = ["| "+" | ".join(str(c) for c in data.columns)+" |", "|"+"|".join("---" for _ in data.columns)+"|"]
    lines += ["| "+" | ".join(cell(v) for v in row)+" |" for row in data.itertuples(index=False, name=None)]
    return "\n".join(lines)


def write_eda_report(context):
    """Generate factual findings from computed results; no analysis in notebook."""
    import hashlib
    for name, expected in context.source_hashes.items():
        with (context.root/"data/processed"/name).open("rb") as handle:
            if hashlib.file_digest(handle, "sha256").hexdigest() != expected:
                raise RuntimeError(f"Input Parquet changed during EDA: {name}")
    results = context.results
    def intro(key):
        result = results[key]
        return f"Excluded imputed rows: **{result.excluded_imputed:,}**; other missing/undefined observed rows for this parameter: **{result.missing_observed:,}**. Group-specific exclusions are included in the full CSV tables."
    energy = results["energy"].tables
    base = results["base_load"].tables
    peaks = results["peaks"].tables["daily"]
    activity = results["activity"].tables
    weeks = results["PROVISIONAL_calendar"].tables["weeks"]
    provisional = weeks.loc[weeks.PROVISIONAL_vacation_like.eq(True)]
    seasonal = results["seasonality"].tables["seasonal"]
    lag = results["autocorrelation"].tables["lags"]
    pf = results["power_factor"].tables["monthly"]
    gap = results["demand_divergence"].tables["seasonal"]
    split = results["splits"].tables["splits"]
    summer_ratio = seasonal.loc["Summer", "observed_daily_equivalent_kWh"]/seasonal.loc["Winter", "observed_daily_equivalent_kWh"]
    monthly_ratio = seasonal.loc["Summer", "mean_monthly_observed_kWh"]/seasonal.loc["Winter", "mean_monthly_observed_kWh"]
    maximum = results["load_duration"].findings["maximum_observed_kVA"]
    daily = activity["daily"]
    activation = pd.to_datetime(daily.activation)
    deactivation = pd.to_datetime(daily.deactivation)
    mean_times = pd.DataFrame({"quantity": ["activation median hour", "deactivation median hour", "observed days with no crossing", "days with no observed P"],
                              "value": [(activation.dt.hour+activation.dt.minute/60).median(), (deactivation.dt.hour+deactivation.dt.minute/60).median(),
                                        int((daily.activation.isna() & daily.observed_intervals.gt(0)).sum()), int(daily.observed_intervals.eq(0).sum())]})
    lines = ["# EDA: SInERT observed behaviour", "",
        f"Read existing Parquets only; ingestion was not rerun. Canonical site grid: {context.em.index[0]} to {context.em.index[-1]}, "
        f"{len(context.em):,} quarter-hours and {len(energy['monthly'])} months. No models, features for models, or windows were created.", "",
        "## Methods and exclusions", "",
        "Every descriptive statistic masks is_imputed=True rows on the original grid. Lag pairs and consecutive runs never compress gaps. "
        "Tables list imputed exclusions separately from missing/undefined observed values. Timestamps are naive export local time; "
        "no timezone is inferred. Seasons are northern meteorological DJF winter, MAM spring, JJA summer and SON autumn. "
        "Max/min ties use the earliest observed timestamp; variability uses sample variance/std (ddof=1). "
        "The only explicit exception is split input-completeness counting: imputed inputs are allowed, but every future target must be observed.", "",
        "The university academic calendar is unavailable. All vacation/term classifications below are PROVISIONAL data proxies, "
        "not facts about SUP'COM. Obtain the actual calendar from the supervisor and replace this proxy.", "",
        "## 1. Active energy at four time scales", "", intro("energy"), "",
        f"Observed active energy total: **{results['energy'].findings['total_observed_kWh']:,.3f} kWh**. "
        "These are sums of observed dEa, not counter levels and not complete consumption estimates where intervals were excluded. "
        "Daily/weekly/monthly/annual CSVs include period totals, running totals, sample counts and exclusions. Weeks start Monday. "
        "2022 and 2026 are partial calendar years.", "",
        _markdown(energy["annual"]), "",
        "Daily energy distribution (kWh): "+energy["daily"].energy_kWh.describe().to_string().replace("\n", "; ")+".", "",
        "Full daily/weekly values: [daily](eda_energy_daily.csv), [weekly](eda_energy_weekly.csv). Figure: [energy_totals.png](figures/energy_totals.png).", "",
        "## 2. Base load and occurrence hour", "", intro("base_load"), "",
        f"Daily minimum P_avg: median **{base['daily'].minimum_kW.median():.3f} kW**, range "
        f"**{base['daily'].minimum_kW.min():.3f}–{base['daily'].minimum_kW.max():.3f} kW**. Hour distribution counts the earliest occurrence per day.", "",
        _markdown(base["hour_distribution"]), "", "Daily values and timestamps: [table](eda_base_load_daily.csv). Figure: [base_load_and_hour.png](figures/base_load_and_hour.png).", "",
        "## 3. Daily peak demand and duration", "", intro("peaks"), "",
        "Peak duration is the LONGEST consecutive run of quarter-hours at or above 90% of that day's maximum, separately for P and S. "
        "Missing/imputed slots or a timestamp gap break a run; disconnected runs are never added. "
        "A day with no observed values has undefined peak/duration (NaN), not a measured zero. The maximum's earliest timestamp is also recorded.", "",
        _markdown(peaks[["P_maximum", "S_maximum", "P_duration_hours", "S_duration_hours"]].describe()), "",
        "All daily peak times and durations: [table](eda_peaks_daily.csv). Figure: [daily_peaks_and_duration.png](figures/daily_peaks_and_duration.png).", "",
        "## 4. Mean power comparisons", "", intro("power_comparisons"), ""]
    for name in ("day_type", "academic_PROXY_PROVISIONAL", "season"):
        lines += ["PROVISIONAL academic proxy:" if "PROVISIONAL" in name else name+":", "", _markdown(results["power_comparisons"].tables[name]), ""]
    lines += ["Boxplots suppress displayed outliers only; all observed measurements remain in the numerical results. "
        f"The PROVISIONAL vacation-like mean is {results['power_comparisons'].tables['academic_PROXY_PROVISIONAL'].loc['Vacation-like PROVISIONAL','mean_kW']:.4f} kW "
        f"versus {results['power_comparisons'].tables['academic_PROXY_PROVISIONAL'].loc['Term-like PROVISIONAL','mean_kW']:.4f} kW for the PROVISIONAL term-like group. "
        "Collapsed weekday/weekend contrast therefore does not mean low consumption; this proxy is confounded by seasonal operating patterns and is not an academic-calendar label. "
        "Figure: [mean_power_comparisons.png](figures/mean_power_comparisons.png).", "",
        "## 5. Activity proxies and variability", "", intro("activity"), "",
        "Activation/deactivation are the first/last observed interval with P_avg >1.5 times that day's observed minimum. "
        "A flat day with no crossing returns None. This is a descriptive site-activity proxy, not an equipment switching log.", "",
        _markdown(mean_times), "", "Monthly P_avg standard deviation and variance:", "", _markdown(activity["monthly_variability"]), "",
        "By weekday (0=Monday, 6=Sunday):", "", _markdown(activity["weekday_variability"]), "",
        "Daily times: [table](eda_activity_daily.csv). Figure: [activity_and_variability.png](figures/activity_and_variability.png).", "",
        "## B. PROVISIONAL vacation-like weeks", "", intro("PROVISIONAL_calendar"), "",
        "PROVISIONAL rule: abs(weekday_mean - weekend_mean) <=0.20*abs(weekend_mean). Saturday/Sunday are weekend. "
        "Both means must exist. A zero/zero week has collapsed contrast; positive weekday with zero weekend does not. "
        "Partial boundary weeks use the same rule and are explicitly flagged; their classification is less supported. "
        "This PROVISIONAL rule can also reflect holidays, outages or operational changes and does not establish university vacations.", "",
        f"PROVISIONAL vacation-like weeks: **{len(provisional)} / {len(weeks)}**; flagged partial among those: **{int(provisional.partial_week.sum())}**.", "",
        _markdown(provisional[["weekday_mean_kW", "weekend_mean_kW", "contrast", "partial_week", "observed_intervals", "excluded_imputed"]]), "",
        "Full PROVISIONAL weekly table: [table](eda_PROVISIONAL_calendar_weeks.csv). "
        "PROVISIONAL timeline: [PROVISIONAL_vacation_timeline.png](figures/PROVISIONAL_vacation_timeline.png).", "",
        "## 6. Seasonality", "", intro("seasonality"), "",
        f"Summer/winter energy-rate ratio: **{summer_ratio:.4f}** using mean observed dEa ×96 (coverage-normalized daily equivalents). "
        f"Ratio of mean monthly observed totals: **{monthly_ratio:.4f}**. These avoid confusing unequal numbers of summer/winter months with higher consumption.", "",
        _markdown(seasonal), "", "All monthly totals:", "", _markdown(energy["monthly"]), "",
        "Figures: [monthly_energy_seasonality.png](figures/monthly_energy_seasonality.png), "
        "[seasonal_daily_profiles.png](figures/seasonal_daily_profiles.png).", "",
        "## 7. Autocorrelation and later baseline/context choices", "", intro("autocorrelation"), "",
        "ACF uses pairwise Pearson correlation of dEa at original grid lags 0–700; both endpoints must be observed and finite. "
        "Pair-specific excluded counts are listed below and in the full CSV. It is not an ACF of a compressed observed-only sequence.", "",
        _markdown(lag.loc[[0, 96, 672, 700]]), "",
        f"Observed daily lag-96 correlation is **{lag.loc[96,'correlation']:.4f}**; weekly lag-672 is **{lag.loc[672,'correlation']:.4f}**. "
        +( "These positive correlations provide empirical evidence for evaluating daily/weekly seasonal-naive baselines and the proposed 672-step input context. "
           if lag.loc[96,"correlation"]>0 and lag.loc[672,"correlation"]>0 else "These values do not provide positive evidence for both proposed seasonal lags. ")+
        "They do not prove that 672 is optimal; trend/annual seasonality can contribute. No baseline or model was fitted.", "",
        "Figure: [energy_autocorrelation.png](figures/energy_autocorrelation.png).", "",
        "## 8. Power factor, inductive intervals and Phase 5 screening", "", intro("power_factor"), "",
        "Counts use strict PF<0.90 and PF<0.80. For EDA screening only, any such observed interval makes the month a warning/severe "
        "Phase 5 interval candidate, respectively. A separate monthly-mean candidate applies the same cutoffs to mean PF. "
        "An official persistence/duration alert policy was not supplied; these are candidates, not deployed alerts. "
        "PF alerts must exclude reconstructed data. Positive Q is the inductive share of finite observed Q intervals.", "",
        _markdown(pf), "", "Figure: [monthly_power_factor.png](figures/monthly_power_factor.png).", "",
        "## 9. Apparent-load duration and the supplied 600 kVA subscription", "", intro("load_duration"), "",
        f"Maximum observed S_avg: **{maximum:.4f} kVA**, or **{maximum/600*100:.3f}%** of the supplied 600 kVA reference.", "",
        _markdown(results["load_duration"].tables["thresholds"]), "",
        "These measured exceedances are evidence for evaluating subscription headroom. They do not select a new subscription: "
        "excluded observations and interval-average peaks do not establish unobserved/transient demand, and no tariff calculation was performed.", "",
        "Figure: [apparent_load_duration.png](figures/apparent_load_duration.png).", "",
        "## 10. Demand-channel divergence: test the seasonal pattern", "", intro("demand_divergence"), "",
        "Demand-minus-average is a diagnostic, not an ordering invariant. Report both signed and absolute differences so sign changes are not hidden.", "",
        _markdown(gap), "",
        f"Summer mean absolute gap **{gap.loc['Summer','mean_absolute_gap_kVA']:.4f} kVA** versus winter "
        f"**{gap.loc['Winter','mean_absolute_gap_kVA']:.4f} kVA**. The proposed summer-widening pattern is "
        +( "SUPPORTED in mean absolute gap." if gap.loc["Summer","mean_absolute_gap_kVA"]>gap.loc["Winter","mean_absolute_gap_kVA"] else "NOT SUPPORTED in mean absolute gap.")+" "
        "This seasonal association alone cannot establish air-conditioning as its cause; meter changes below provide separate descriptive evidence. "
        "No result is assumed from the equipment names.", "",
        "Full monthly aggregation: [table](eda_demand_divergence_monthly.csv). Figure: [monthly_demand_gap.png](figures/monthly_demand_gap.png).", "",
        "## 11. Meter contributions and the summer rise", "", intro("meter_contributions"), "",
        "Shares use each meter's observed monthly dEa divided by EM_VIRTUAL observed monthly dEa. Transformer and downstream meters overlap; "
        "do not add their shares. Different missing/imputed coverage also affects these ratios. For seasonal attribution the table compares "
        "mean observed P rather than sums over unequal season lengths. These are descriptive contributors, not a validated disjoint electrical topology.", "",
        _markdown(results["meter_contributions"].tables["seasonal_change"].sort_values("summer_minus_winter_kW", ascending=False)), "",
        "Among downstream meter names, the two CLIM channels have the largest positive summer-minus-winter mean-power changes. "
        "Their tabled increases are only a partial explanation of the site's summer rise, not a complete air-conditioning allocation. "
        "At transformer level, TGBT_TR2's increase is partly offset by TGBT_TR1's decrease; do not count these again as downstream contributions.", "",
        "All meter/month shares: [table](eda_meter_contributions_monthly.csv). "
        "Figures: [monthly_meter_shares.png](figures/monthly_meter_shares.png), [summer_meter_changes.png](figures/summer_meter_changes.png).", "",
        "## D. Proposed split validation — counts only", "", intro("splits"), "",
        "Train/val/test boundaries are exactly the proposal, with end dates inclusive by calendar day. "
        "Eligibility requires 672 consecutive finite input slots and 96 following observed, finite target slots (dEa,dEr,P_avg,S_avg). "
        "Imputed INPUTS are permitted; imputed labels are not. Targets stay inside their split. "
        "Both strict within-split history and prior-split historical context counts are shown. No window arrays, labels or model features were created.", "",
        _markdown(split), "",
        "All three partitions have nonzero, workable counts of eligible overlapping origins for later sample construction. "
        "These counts do not imply independent samples or prove statistical adequacy. The initial unavailable-history range and "
        "all target-imputation/boundary exclusions are recorded below.", "",
        "The claim that EACH validation/test period spans both meteorological summer and winter is false: "
        "validation (March–August 2025) contains spring and summer, with NO DJF winter; test (September 2025–February 2026) "
        "contains autumn and winter, with NO JJA summer. September may have high measured load, but that does not make it a meteorological summer month. "
        "Thus these are populated chronological splits, not demonstrated season-balanced validation/test sets.", "",
        "Both validation and test nevertheless contain measured high- and low-load months; the table distinguishes energy-regime coverage "
        "from meteorological season labels:", "", _markdown(results["splits"].tables["monthly_energy_range"]), "",
        "Longest blocked-origin runs per split (all ranges are in eda_splits_blocked_origin_runs.csv):", ""]
    blocked = results["splits"].tables["blocked_origin_runs"]
    longest = blocked.sort_values("intervals", ascending=False).groupby("split", sort=False).head(3)
    lines += [_markdown(longest.set_index(["split", "first_origin"])), "",
        "Split counts are provisional feasibility checks on the existing analysis artifact. "
        "Before modeling, actual split boundaries and the imputation leakage policy must be enforced; ingestion/imputation was not rerun here.", "",
        "## Three findings for the modelling phase", "",
        f"1. Seasonal load differs: summer/winter observed daily-energy rate ratio {summer_ratio:.4f}. Use calendar/season-aware comparisons and chronological evaluation, not random splits.",
        f"2. Observed lag correlations at 96/672 are {lag.loc[96,'correlation']:.4f}/{lag.loc[672,'correlation']:.4f}; evaluate both seasonal-naive baselines and the proposed week-long context without assuming an optimal model.",
        f"3. The proposed split season-balance claim fails. Eligible prior-context origins are train={int(split.loc['train','eligible_origins_prior_context'])}, val={int(split.loc['val','eligible_origins_prior_context'])}, test={int(split.loc['test','eligible_origins_prior_context'])}; keep imputed targets excluded and review seasonal coverage with the supervisor.", "",
        "## Figures (all PNG, 150 dpi)", "", "| Figure | Parameter | Excluded imputed rows | Other missing observed |", "|---|---|---:|---:|"]
    lines += [f"| [{name}](figures/{name}) | {key} | {excluded} | {missing} |" for name, key, excluded, missing in context.figures]
    lines += ["", "## Input provenance", "", "Input SHA-256 hashes were checked unchanged after EDA:", ""]
    lines += [f"- `{name}`: `{digest}`" for name, digest in context.source_hashes.items()]
    log = context.root/"logs/eda-pytest.log"
    if log.exists():
        lines += ["", "## Synthetic pytest output", "", "```text", log.read_text(encoding="utf-8").rstrip(), "```"]
    (context.root/"reports/EDA.md").write_text("\n".join(lines)+"\n", encoding="utf-8")
    print("Wrote reports/EDA.md;", len(context.figures), "figures at 150 dpi; input Parquet hashes unchanged.")
