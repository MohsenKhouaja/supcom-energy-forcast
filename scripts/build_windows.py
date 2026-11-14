#!/usr/bin/env python3
"""Build RECONSTRUCTED calendars, eleven features, and lazy origin artifacts.

No model, training job, stacked window array, or GPU allocation is created.
Run after ingest_dataset.py --splits configs/splits.yaml, on the CPU VM.
After pytest, use --record-validation to attach logs/windows-pytest.log.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import time

import holidays
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import sklearn

from smartgrid.data.scaling import fit_electrical_scaler, scaler_fit_coverage
from smartgrid.data.windows import eligible_origins, from_processed, split_ranges
from smartgrid.features.calendar import STATUS, academic_periods, tunisian_holidays, vacation_load_comparison, winter_weekday_profile
from smartgrid.features.calendar_features import ELECTRICAL, FEATURES, feature_table


def markdown(frame):
    def cell(value):
        if pd.isna(value):
            return "NA"
        if isinstance(value, (float,np.floating)):
            return f"{value:.6f}"
        return str(value).replace("|","/")
    lines = ["| "+" | ".join(map(str,frame.columns))+" |", "|"+"---|"*len(frame.columns)]
    lines.extend("| "+" | ".join(cell(v) for v in row)+" |" for row in frame.itertuples(index=False,name=None))
    return "\n".join(lines)


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            result.update(block)
    return result.hexdigest()


def gap_metadata(path):
    return json.loads(pq.ParquetFile(path).schema_arrow.metadata[b"supcom.imputation_gaps"])


def winter_dip_findings(winter):
    """Descriptive local dip screen only; never changes a calendar rule."""
    lines = ["For a transparent descriptive reading of 'clear', flag an adjacent two-week pair only when "
        "both week means are below BOTH immediately surrounding week means, and the pair's mean is at least 10% "
        "below the surrounding pair's mean. This is an exploratory screen, not a statistical test or calendar validation. "
        "The rule is unchanged regardless of this result. Weekly means use only the observed rows counted above.", ""]
    for year, group in winter.groupby("academic_year",sort=False):
        group = group.reset_index(drop=True)
        candidates = []
        for i in range(1,len(group)-2):
            four = group.iloc[i-1:i+3]
            values = four.mean_weekday_P_kW.to_numpy()
            if not np.isfinite(values).all():
                continue
            before, first, second, after = values
            around = (before+after)/2
            inside = (first+second)/2
            if max(first,second) < min(before,after) and around > 0 and inside <= .9*around:
                candidates.append((inside/around,i,first,second,around,int(four.excluded_imputed.sum())))
        if candidates:
            ratio,i,first,second,around,excluded = min(candidates)
            lines.append(f"- {year}: clear descriptive dip at **{group.iloc[i].iso_week} and {group.iloc[i+1].iso_week}** "
                f"({first:.3f}, {second:.3f} kW), {100*(1-ratio):.2f}% below the adjacent weeks' mean {around:.3f} kW. "
                f"Imputed exclusions across the four compared weeks: {excluded}. "
                "This may differ from the configured vacation weeks; no adjustment was made.")
        else:
            lines.append(f"- {year}: **no clear isolated two-week dip** under this descriptive screen. "
                "The printed weekday means do not establish the reconstructed winter dates; no adjustment was made.")
    return lines


def compare_reimputation(root):
    before = root/"cache/windows_before"
    current = root/"data/processed"
    old_gaps, new_gaps = gap_metadata(before/"em_virtual.parquet"), gap_metadata(current/"em_virtual.parquet")
    previous = {(g["meter"],g["start"],g["length"]):g for g in old_gaps}
    method_changes = []
    for gap in new_gaps:
        old = previous.get((gap["meter"],gap["start"],gap["length"]))
        if old and any(old.get(key) != gap.get(key) for key in ("method","reactive_method","donor_date")):
            method_changes.append(dict(meter=gap["meter"],start=gap["start"],length=gap["length"],
                old_method=old["method"],new_method=gap["method"],old_reactive=old["reactive_method"],
                new_reactive=gap["reactive_method"],old_donor=old["donor_date"],new_donor=gap["donor_date"]))
    records = []
    meters = pd.read_parquet(current/"all_meters.parquet",columns=["meter"])["meter"].unique()
    for meter in sorted(meters):
        # At most one meter's before/after data in memory at a time.
        old = pd.read_parquet(before/"all_meters.parquet",filters=[("meter","==",meter)]).set_index("timestamp")
        new = pd.read_parquet(current/"all_meters.parquet",filters=[("meter","==",meter)]).set_index("timestamp")
        if not old.index.equals(new.index):
            raise ValueError(f"Canonical timestamps changed for {meter}")
        impacted = old.is_imputed.to_numpy() | new.is_imputed.to_numpy()
        numeric = [c for c in new.columns if c not in ("meter","source_filename","source_sheet","is_imputed")]
        affected_rows = np.zeros(len(new),dtype=bool)
        imputed_cells = all_cells = 0
        for column in numeric:
            a,b = old[column].to_numpy(dtype=float),new[column].to_numpy(dtype=float)
            changed = ~np.isclose(a,b,rtol=1e-12,atol=1e-10,equal_nan=True)
            affected_rows |= changed
            imputed_cells += int((changed & impacted).sum())
            all_cells += int(changed.sum())
        records.append(dict(meter=meter,changed_numeric_cells=all_cells,changed_cells_on_old_or_new_imputed_rows=imputed_cells,
            changed_rows=int(affected_rows.sum()),old_imputed_rows=int(old.is_imputed.sum()),
            new_imputed_rows=int(new.is_imputed.sum()),changed_flags=int((old.is_imputed != new.is_imputed).sum()),
            old_missing_dEa=int(old.dEa.isna().sum()),new_missing_dEa=int(new.dEa.isna().sum())))
    changes = pd.DataFrame(method_changes,columns=["meter","start","length","old_method","new_method","old_reactive","new_reactive","old_donor","new_donor"])
    return pd.DataFrame(records),changes


def write_calendar_report(root, frame, config):
    public = tunisian_holidays(config)
    years = sorted({d.year for d in public})
    if years != sorted(config["holiday_years"]):
        raise ValueError(f"holidays/TN coverage mismatch: {years}")
    holiday_table = pd.DataFrame([dict(date=str(d),name=name) for d,name in sorted(public.items())])
    periods = academic_periods(config)
    comparison = vacation_load_comparison(frame,periods,public)
    winter = winter_weekday_profile(frame,config["academic_year_starts"])
    for name,table in (("calendar_periods",periods),("calendar_public_holidays",holiday_table),
                       ("calendar_vacation_load",comparison),("calendar_winter_weekday_load",winter)):
        table.to_csv(root/f"reports/{name}.csv",index=False)
    lines = ["# Academic calendar — RECONSTRUCTED, not official", "",
        "The user has only the official 2026/2027 calendar; it was not supplied to this run. "
        "The four earlier academic years below are reconstructed from the user-supplied structure, not verified institutional dates. "
        "Replace the rules when the supervisor provides the calendars. Every academic output is RECONSTRUCTED, not official.", "",
        "## Configurable rules", "", "[configs/calendar.yaml](../configs/calendar.yaml) uses JSON syntax valid in YAML 1.2. "
        "Winter starts on Monday of the week containing 25 December (weeks_before=0) and ends Sunday of the following week "
        "(weeks_after=1). Exams occupy the next two ISO weeks and are working periods. Spring is ISO week 14. "
        "Aid Al Fitr vacation is the ISO week containing the package's first Eid al-Fitr day. "
        "Overlapping vacations are unioned. Rentree is 1 September, fin d'annee is 10 July, closure is 11 July–31 August.", "",
        "## Every derived date for the four academic years", "", markdown(periods.loc[~periods.context_only]), "",
        "The initial July/August 2022 record also needs a closure mask. Apply the same rule to the preceding year's summer only; "
        "no other 2021/2022 dates are inferred:", "", markdown(periods.loc[periods.context_only]), "",
        "## Public holiday dates actually returned by holidays/TN", "",
        f"Package holidays {holidays.__version__}; country TN; English names. Returned years: {years}. "
        "Islamic dates are computed by the package, not hard-coded here. Estimated annotations are retained; "
        "these are package outputs, not independent official verification. "
        "[Package Tunisia documentation](https://holidays.readthedocs.io/en/latest/auto_gen_docs/tunisia/).", "",
        markdown(holiday_table), "", "## Observed load sanity comparison (not calendar validation)", "",
        "For each vacation: observed weekday P_avg vs weekday term slots in the 14 days before and 14 days after, "
        "excluding all reconstructed vacations and public holidays from the surrounding comparison. "
        "Means use is_imputed=False and finite P_avg only; excluded counts are alongside each result. "
        "NA means no observed coverage. Higher or lower vacation demand cannot validate reconstructed dates: weather and other loads confound occupancy.", "",
        markdown(comparison), "", "## Empirical winter weeks 49 through 03 (report only)", "",
        "All observed weekdays are retained, including holidays; no calendar-based trimming biases this comparison. "
        "This table does not change the configurable winter rule. Missing/imputed counts are explicit. "
        "Weekday means are descriptive, with no load assertions or fitted calendar.", "", markdown(winter), "",
        *winter_dip_findings(winter), ""]
    (root/"reports/CALENDAR.md").write_text("\n".join(lines),encoding="utf-8")
    print("PUBLIC_HOLIDAYS_ACTUALLY_RETURNED\n"+holiday_table.to_string(index=False),flush=True)
    print("WINTER_WEEKDAY_LOAD\n"+winter.to_string(index=False),flush=True)


def record_validation(root):
    """Attach actual completed pytest output without rerunning preprocessing."""
    log = (root/"logs/windows-pytest.log").read_text(encoding="utf-8").rstrip()
    path = root/"reports/WINDOWS.md"
    text = path.read_text(encoding="utf-8").split("\n## Pytest output\n")[0]
    text += "\n## Pytest output\n\n```text\n"+log+"\n```\n"
    ingestion = (root/"logs/windows-ingestion.log").read_text(encoding="utf-8")
    runtime = next(line for line in ingestion.splitlines() if line.startswith("RUNTIME_SECONDS "))
    text += "\nSplit-bounded ingestion execution: `"+runtime+"`.\n"
    path.write_text(text,encoding="utf-8")
    path = root/"reports/INGESTION.md"
    text = path.read_text(encoding="utf-8").split("\n## Validation after split-bounded ingestion\n")[0]
    path.write_text(text+"\n## Validation after split-bounded ingestion\n\n```text\n"+log+"\n```\n",encoding="utf-8")
    print("Attached actual pytest output to WINDOWS.md and INGESTION.md.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument("--record-validation",action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    root = args.root.resolve()
    if args.record_validation:
        record_validation(root)
        return
    output = root/"data/processed"
    calendar = json.loads((root/"configs/calendar.yaml").read_text(encoding="utf-8"))
    config = json.loads((root/"configs/splits.yaml").read_text(encoding="utf-8"))
    frame = pd.read_parquet(output/"em_virtual.parquet").set_index("timestamp")
    table = feature_table(frame,calendar)
    origins = eligible_origins(table,frame.is_imputed,config)
    _, coverage = scaler_fit_coverage(table,origins["train"],config)
    (root/"reports/windows_scaler_coverage.json").write_text(json.dumps(coverage,indent=2)+"\n",encoding="utf-8")
    print("SCALER_COVERAGE_BEFORE_FIT",json.dumps(coverage),flush=True)
    if coverage["excluded_pct"] >= 1:
        raise RuntimeError("At least 1% train rows excluded from scaler fit; STOP for user review before fitting")
    scaler, fit_mask, coverage = fit_electrical_scaler(table,origins["train"],config)
    scaler.save(output/"scaler.json")
    np.save(output/"features.npy",scaler.transform(table.to_numpy()),allow_pickle=False)
    pd.DataFrame(dict(timestamp=table.index,is_imputed=frame.is_imputed.to_numpy())).to_parquet(output/"feature_grid.parquet",index=False)
    origin_files = {}
    summary = []
    for name, positions in origins.items():
        origin_files[name] = f"{name}_origins.parquet"
        pd.DataFrame(dict(origin_index=positions,origin_timestamp=table.index[positions],
            target_start=table.index[positions+1],target_end=table.index[positions+config["horizon"]])).to_parquet(output/origin_files[name],index=False)
        start,end = split_ranges(config)[name]
        mask = (frame.index >= start) & (frame.index < end)
        observed = ~frame.is_imputed & frame.loc[:,ELECTRICAL].notna().all(axis=1)
        summary.append(dict(split=name,start=str(start.date()),end=str((end-pd.Timedelta(days=1)).date()),
            grid_rows=int(mask.sum()),complete_observed_rows=int((mask & observed).sum()),
            imputed_rows=int((mask & frame.is_imputed).sum()),
            incomplete_nonimputed_rows=int((mask & ~frame.is_imputed & ~observed).sum()),
            eligible_origins=len(positions),first_origin=str(table.index[positions[0]]) if len(positions) else "NA",
            last_origin=str(table.index[positions[-1]]) if len(positions) else "NA"))
    summary = pd.DataFrame(summary)
    summary.to_csv(root/"reports/windows_origin_counts.csv",index=False)
    metadata = dict(features=FEATURES,targets=ELECTRICAL,calendar_status=STATUS,context=config["context"],horizon=config["horizon"],
        shape=list(table.shape),dtype="float32",origin_semantics="last input timestamp",origin_files=origin_files,
        calendar_config=calendar,split_config=config,source_em_sha256=digest(output/"em_virtual.parquet"),
        features_sha256=digest(output/"features.npy"),scaler_sha256=digest(output/"scaler.json"))
    (output/"features.json").write_text(json.dumps(metadata,indent=2)+"\n",encoding="utf-8")
    # Verify the on-demand public loader on first/last origin of every split.
    for name in origins:
        windows = from_processed(output,name)
        for position in (0,len(windows)-1):
            x,y = windows[position]
            if x.shape != (672,11) or y.shape != (96,4) or not (np.isfinite(x).all() and np.isfinite(y).all()):
                raise ValueError(f"Invalid lazy window for {name}:{position}")
    comparison,changes = compare_reimputation(root)
    comparison.to_csv(root/"reports/windows_reimputation_changes.csv",index=False)
    changes.to_csv(root/"reports/windows_donor_changes.csv",index=False)
    write_calendar_report(root,frame,calendar)
    observed = frame.loc[~frame.is_imputed].dropna(subset=list(ELECTRICAL))
    mismatch = (observed.P_avg-4*observed.dEa).abs()
    observed_identity = pd.DataFrame([dict(comparable_observed_rows=len(observed),excluded_imputed=int(frame.is_imputed.sum()),
        other_missing_observed=int((~frame.is_imputed & frame.loc[:,ELECTRICAL].isna().any(axis=1)).sum()),
        median_abs_P_minus_4dEa_kW=mismatch.median(),max_abs_P_minus_4dEa_kW=mismatch.max(),
        rows_abs_difference_over_001kW=int((mismatch>.01).sum()),
        max_abs_S_minus_hypot_P_4dEr_kVA=float((observed.S_avg-np.hypot(observed.P_avg,4*observed.dEr)).abs().max()))])
    observed_identity.to_csv(root/"reports/windows_physical_diagnostics.csv",index=False)
    falls_back = int(((changes.old_method == "scaled_weekday") & (changes.new_method == "uniform")).sum())
    q_falls_back = int(((changes.old_reactive == "scaled_weekday") & (changes.new_reactive == "uniform")).sum())
    scaler_table = pd.DataFrame(dict(channel=ELECTRICAL,mean=scaler.mean,std=scaler.std,scale=scaler.scale))
    scaler_table.to_csv(root/"reports/windows_scaler_statistics.csv",index=False)
    lines = ["# Leakage-safe features and lazy windows", "",
        "Academic-calendar features: **RECONSTRUCTED, not official**. See [CALENDAR.md](CALENDAR.md). "
        "CPU-only preprocessing. No model, training, inference, or stacked window arrays were created.", "",
        "## Splits and eligibility", "",
        "[configs/splits.yaml](../configs/splits.yaml) replaces the EDA proposal. End dates are inclusive. "
        "Train: July 2022–August 2024 (26 months); validation: September 2024–May 2025 (9 months); "
        "test: June 2025–February 2026 (9 months). Test contains both meteorological summer and winter. "
        "Validation contains autumn/winter/spring, not a full summer.", "", markdown(summary), "",
        "Origin t is the last input timestamp. X = t-671..t, shape [672,11]; y = t+1..t+96, shape [96,4]. "
        "There is no overlap. All input rows must be present, consecutive and finite; imputed inputs are allowed. "
        "Every target must be observed, non-imputed and finite in all four channels. All targets stay inside their own split. "
        "Earlier partitions may supply historical input context. Therefore the first validation/test origin can precede its "
        "target partition by one slot. No labels or right anchors from later partitions are used for imputation.", "",
        "## Re-ingestion and split-bounded reconstruction", "",
        "Ran scripts/ingest_dataset.py --splits configs/splits.yaml, reading the raw exports afresh. "
        "All split starts/ends are enforced for both original counter anchors and earlier donors. "
        "Missing gaps that straddle a partition stay missing. Comparisons below use old/new is_imputed union and "
        "rtol=1e-12, atol=1e-10; NaN equals NaN. Numeric-cell counts include derived channels, not only raw filled cells.", "",
        markdown(comparison), "",
        f"Active donor-to-uniform fallback changes: **{falls_back}**; reactive: **{q_falls_back}**. "
        f"Method/donor changes: {len(changes)}.", "", markdown(changes), "",
        "The old EDA notebook/report remain the executed historical analysis of the preceding artifact. "
        "They were not rerun or silently rewritten; the current artifact is identified by hashes below.", "",
        "## Eleven features", "",
        "Order: `"+", ".join(FEATURES)+"`. Electrical channels are dEa (kWh/15 min), signed dEr (kvarh/15 min), "
        "P_avg (kW), S_avg (kVA). Fractional hour includes minutes, so 23:45 is adjacent to 00:00 in cyclic space. "
        "Weekday is Monday=0. Day-of-year uses period 365.25. Non-working is weekend OR TN public holiday OR "
        "RECONSTRUCTED academic vacation. Exams are working days unless another rule applies. Calendar channels are never scaled.", "",
        "## Scaler: unique training input OR target rows only", "",
        "StandardScaler is fitted once on the unique train-range rows touched by any eligible training input OR target. "
        "Overlapping windows do not repeat-weight observations. Imputed training inputs may enter the fit; "
        "imputed rows remain forbidden as labels. No validation/test row enters fit. Both X electrical channels and y "
        "use the same fitted transform. Population std (ddof=0); constant channels use scale 1.", "",
        markdown(pd.DataFrame([coverage])), "",
        "Excluded nonfinite rows cannot occur in any complete input/target. Excluded finite rows, if any, "
        "are not touched by any eligible training span. The excluded share is below 1%; the distinction from all train-range "
        "rows is immaterial at this scale, but the implemented fit policy remains exact. "
        "A >=1% exclusion would have stopped the builder before scaler fitting for user review.", "",
        markdown(scaler_table), "",
        f"Fitted rows: {scaler.n_rows}; first {scaler.fit_first}; last {scaler.fit_last}. "
        "Plain-number scaler is data/processed/scaler.json; it is not a pickle.", "",
        "## Lazy storage and use", "",
        f"One underlying [N,11] float32 array has shape {tuple(table.shape)} and {table.size*4:,} payload bytes. "
        "features.npy is memory-mapped by the loader. Origin Parquets contain only row indices and alignment timestamps, "
        "one file per split. feature_grid.parquet stores timestamps/flags; features.json pins order, dates and hashes. "
        "No [number_of_windows,672,11] array is written or retained.", "",
        "```python", "from smartgrid.data.windows import from_processed, torch_dataset",
        "train = from_processed('data/processed', 'train')", "X, y = train[0]  # read-only NumPy views; [672,11], [96,4]",
        "# Optional, only if torch is already installed:", "dataset = torch_dataset(train)  # genuine Dataset; one sample copied to CPU tensors on demand", "```", "",
        "Torch was not installed and was not added: only holidays/scikit-learn were authorized. "
        "The optional adapter source is provided; its real-Torch integration test is explicitly skipped in this environment. "
        "The NumPy lazy loader, storage round-trip, shapes and eligibility are tested. No GPU work occurs.", "",
        "## Four targets and physical consistency", "",
        "The intended interval energy/power relationship is P_avg = 4*dEa, while "
        "Q_avg = 4*dEr and S_avg = sqrt(P_avg^2+Q_avg^2). The four targets are therefore physically related. "
        "All four are retained because the specification requires joint dEa, dEr, Pmax, Smax prediction. "
        "The sequence head exposes dEa,dEr,P_avg,S_avg; Pmax and Smax for the PDE metric are the maxima of the "
        "96 predicted P_avg and S_avg values, after inverse normalization. Demand registers are cross-checks, never labels. "
        "At evaluation, compare predicted S against sqrt(predicted P^2+(4*predicted dEr)^2), in physical units. "
        "Also compare predicted P with 4*predicted dEa.", "",
        "Observed dEa is a counter difference, while observed P_avg is a separately exported power channel. "
        "The nominal P=4*dEa identity is not forced onto measured channels or assumed to hold exactly; "
        "the actual observed discrepancy is reported below rather than silently replacing measurements. "
        "S and signed dEr are derived in ingestion.", "", markdown(observed_identity), "",
        "## Provenance and execution", "",
        f"holidays {holidays.__version__}; scikit-learn {sklearn.__version__}. "
        "Only those two direct dependencies were added (their required dependencies may be installed by pip).", "",
        f"- EM_VIRTUAL SHA-256: `{metadata['source_em_sha256']}`",
        f"- Features SHA-256: `{metadata['features_sha256']}`",
        f"- Scaler SHA-256: `{metadata['scaler_sha256']}`",
        f"- Builder runtime: {time.monotonic()-started:.3f} seconds.", "",
        "## Pytest output", "", "<!-- PYTEST_OUTPUT -->", ""]
    (root/"reports/WINDOWS.md").write_text("\n".join(lines),encoding="utf-8")
    print("ORIGIN_COUNTS\n"+summary.to_string(index=False),flush=True)
    print("SCALER\n"+scaler_table.to_string(index=False),flush=True)
    print("REIMPUTATION\n"+comparison.to_string(index=False),flush=True)
    print("METHOD_CHANGES\n"+changes.to_string(index=False),flush=True)
    print("PHYSICAL_DIAGNOSTICS\n"+observed_identity.to_string(index=False),flush=True)


if __name__ == "__main__":
    main()
