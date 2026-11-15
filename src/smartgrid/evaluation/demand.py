"""Observed-only diagnostics for interval-average and maximum-demand channels."""

import numpy as np
import pandas as pd


def demand_diagnostics(frame: pd.DataFrame, meter: str):
    """Return descriptive statistics and every legacy ordering exception.

    Comparable rows have finite S_avg/S_dmd_max and is_imputed == False.
    The assertion's high-load group is strictly above the observed 75th
    percentile. Descriptive halves use <= median and > median; ties stay in
    the low group, so their counts need not be equal (notably for idle meters).
    Relative deviation is undefined at S_dmd_max == 0; exclude only those
    ratios, reporting their counts. Zero-demand rows remain in ordering,
    load percentile and Pearson calculations. Nothing is imputed or changed.
    """
    good = (~frame["is_imputed"].fillna(True)
            & np.isfinite(frame["S_avg"]) & np.isfinite(frame["S_dmd_max"]))
    observed = frame.loc[good, ["S_avg", "S_dmd_max"]]
    s, demand = observed["S_avg"], observed["S_dmd_max"]
    relative = (demand-s).div(demand.where(demand != 0))
    median = float(s.quantile(.5)) if len(s) else np.nan
    upper_quartile = float(s.quantile(.75)) if len(s) else np.nan
    invariant = demand >= s-.01
    failed = observed.loc[~invariant].copy()
    failed.insert(0, "meter", meter)
    failed["shortfall_kVA"] = failed["S_avg"]-failed["S_dmd_max"]
    failed.index.name = "timestamp"
    violations = failed.reset_index()[["meter", "timestamp", "S_avg", "S_dmd_max", "shortfall_kVA"]]
    stats = {"meter": meter, "comparable_rows": len(observed),
             "invariant_fraction": float(invariant.mean()) if len(s) else np.nan,
             "invariant_violations": len(violations), "median_load_kVA": median,
             "p75_load_kVA": upper_quartile,
             "pearson": float(s.corr(demand)) if len(s) > 1 and s.nunique()>1 and demand.nunique()>1 else np.nan,
             "zero_demand_rows": int(demand.eq(0).sum())}
    for label, mask in (("low_half", s <= median), ("high_half", s > median), ("high_quartile", s > upper_quartile)):
        ratios = relative.loc[mask].dropna()
        stats[label+"_rows"] = int(mask.sum())
        stats[label+"_relative_rows"] = len(ratios)
        stats[label+"_median_relative"] = float(ratios.median()) if len(ratios) else np.nan
        stats[label+"_p90_relative"] = float(ratios.quantile(.9)) if len(ratios) else np.nan
    return stats, violations


def demand_report(frames):
    """Render descriptive demand diagnostics; only the high-load test is kept."""
    summaries, violations = [], []
    for meter, frame in frames.items():
        stats, failed = demand_diagnostics(frame, meter)
        summaries.append(stats)
        violations.append(failed)
    summary = pd.DataFrame(summaries)
    failures = pd.concat(violations, ignore_index=True)
    def number(value, digits=6):
        return "NA" if pd.isna(value) else f"{value:.{digits}f}"
    lines = ["## Validation measurements and load-dependent demand diagnostics", "",
        "Observed rows only (is_imputed == False), with finite S_avg and S_dmd_max. "
        "S_avg derives from interval-average P/Q; S_dmd_max aggregates on a different clock. "
        "Ordering and Pearson correlation are EDA diagnostics ONLY, with no asserted thresholds. "
        "The CSV schema, including legacy invariant_fraction/invariant_violations column names, is retained unchanged. "
        "An ordering exception below means S_dmd_max < S_avg - 0.01; it is not an invariant failure.", "",
        "The retained check is median (S_dmd_max-S_avg)/S_dmd_max < 0.10 for S_avg strictly above the meter's observed 75th percentile.", "",
        "| Meter | Comparable rows | Ordering fraction % | Ordering exceptions | P75 S_avg kVA | Upper-quartile rows | Upper-quartile median deviation | Pearson r |",
        "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in summaries:
        lines.append(f"| {row['meter']} | {row['comparable_rows']} | {number(row['invariant_fraction']*100,4)} | {row['invariant_violations']} | {number(row['p75_load_kVA'])} | {row['high_quartile_rows']} | {number(row['high_quartile_median_relative'])} | {number(row['pearson'])} |")
    lines += ["", "Descriptive load halves (REPORT ONLY; no assertions): low means S_avg <= the meter's median, high means S_avg > median. "
        "Ties remain low, so idle-meter halves may have unequal sizes. Deviations are ratios, not percentages. "
        "S_dmd_max == 0 has an undefined relative deviation and is excluded only from ratio summaries; those rows "
        "remain in the ordering diagnostics, quantiles and correlations. The ratio sample counts make this exclusion explicit.", "",
        "| Meter | Median S_avg kVA | Low rows / ratios | Low median deviation | Low P90 deviation | High rows / ratios | High median deviation | High P90 deviation | Zero-demand rows |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in summaries:
        lines.append(f"| {row['meter']} | {number(row['median_load_kVA'])} | {row['low_half_rows']}/{row['low_half_relative_rows']} | {number(row['low_half_median_relative'])} | {number(row['low_half_p90_relative'])} | {row['high_half_rows']}/{row['high_half_relative_rows']} | {number(row['high_half_median_relative'])} | {number(row['high_half_p90_relative'])} | {row['zero_demand_rows']} |")
    lines += ["", f"Ordering exceptions (diagnostic only): {len(failures)}. Every meter/timestamp, S_avg, S_dmd_max and shortfall is listed in "
        "`outputs/demand_invariant_violations.csv` (generated measurement dump, excluded from Git). "
        "Per-meter statistics are also saved in `reports/demand_diagnostics.csv`. These diagnostics do not alter the dataset.", "",
        "Largest observed ordering difference per meter (diagnostic only; complete timestamp list in CSV above):", "",
        "| Meter | Timestamp | S_avg kVA | S_dmd_max kVA | Shortfall kVA |",
        "|---|---|---:|---:|---:|"]
    worst = failures.sort_values("shortfall_kVA", ascending=False, kind="stable").groupby("meter", sort=True).head(1).sort_values("meter")
    for row in worst.itertuples(index=False):
        lines.append(f"| {row.meter} | {row.timestamp} | {number(row.S_avg)} | {number(row.S_dmd_max)} | {number(row.shortfall_kVA)} |")
    lines += [""]
    return "\n".join(lines), summary, failures
