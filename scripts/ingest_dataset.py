#!/usr/bin/env python3
"""CPU-only ingestion entrypoint. Author locally; run from the VM project root."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from smartgrid.data.derive import derive
from smartgrid.data.loader import LoadedDataset, load_dataset, meter_frame, raw_name
from smartgrid.data.windowing import eligible_target_origins

OUTPUT = ["Ea_counter", "dEa", "P_avg", "Q_avg", "dEr", "S_avg", "PF", "P_dmd_max", "S_dmd_max", "is_imputed"]


def input_fingerprint(root, config):
    records = []
    for tree in config["raw_trees"]:
        for path in sorted((root/tree).rglob("*")):
            if path.is_file() and path.suffix.lower() in (".csv", ".xlsx"):
                info = path.stat()
                records.append((str(path.relative_to(root)), info.st_size, info.st_mtime_ns))
    records.append(("loader_sha256", hashlib.sha256((root/"src/smartgrid/data/loader.py").read_bytes()).hexdigest()))
    records.append(("config", config))
    return hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()


def load_or_resume(root, config, resume):
    cache = root/"cache/ingestion"
    cache.mkdir(parents=True, exist_ok=True)
    fingerprint = input_fingerprint(root, config)
    if resume:
        meta = json.loads((cache/"metadata.json").read_text())
        if meta["fingerprint"] != fingerprint:
            raise ValueError("Raw files, loader or configuration changed; rerun without --resume")
        return LoadedDataset(pd.read_parquet(cache/"raw_selected.parquet"), tuple(meta["meters"]),
                             meta["stats"], pd.DataFrame.from_dict(meta["coverage"], orient="index"))
    loaded = load_dataset(root, config["raw_trees"], expected_header_md5=config["csv_header_md5"],
                          expected_meter_count=config["expected_meter_count"])
    loaded.frame.to_parquet(cache/"raw_selected.parquet", engine="pyarrow")
    (cache/"metadata.json").write_text(json.dumps({"fingerprint": fingerprint, "meters": loaded.meters,
        "stats": loaded.stats, "coverage": loaded.coverage.to_dict(orient="index")}, indent=2), encoding="utf-8")
    return loaded


def provenance_runs(wide):
    source = wide[["source_filename", "source_sheet"]].fillna("")
    changed = source.ne(source.shift()).any(axis=1)
    result = []
    for _, group in source.groupby(changed.cumsum()):
        if group["source_filename"].iloc[0]:
            result.append({"first": str(group.index[0]), "last": str(group.index[-1]), "rows": len(group),
                           "filename": group["source_filename"].iloc[0], "sheet": group["source_sheet"].iloc[0]})
    return result


def write_outputs(root, loaded, frames, gap_logs):
    output = root/"data/processed"
    output.mkdir(parents=True, exist_ok=True)
    em = frames["EM_VIRTUAL"][OUTPUT].reset_index()
    table = pa.Table.from_pandas(em, preserve_index=False)
    metadata = dict(table.schema.metadata or {})
    metadata[b"supcom.source_provenance_runs"] = json.dumps(provenance_runs(loaded.frame)).encode()
    metadata[b"supcom.imputation_gaps"] = json.dumps(gap_logs).encode()
    metadata[b"supcom.reactive_convention"] = b"net kvarh = positive counter change minus negative counter change; signed Q"
    pq.write_table(table.replace_schema_metadata(metadata), output/"em_virtual.parquet", compression="snappy")
    writer = None
    try:
        for month in loaded.frame.index.to_period("M").unique():
            mask = loaded.frame.index.to_period("M") == month
            chunks = []
            for meter in loaded.meters:
                chunk = frames[meter].loc[mask, OUTPUT+["Er_pos_counter", "Er_neg_counter"]].copy()
                chunk.insert(0, "meter", meter)
                chunk["source_filename"] = loaded.frame.loc[mask, "source_filename"].astype("string")
                chunk["source_sheet"] = loaded.frame.loc[mask, "source_sheet"].astype("string")
                chunks.append(chunk.reset_index())
            long = pd.concat(chunks, ignore_index=True).sort_values(["timestamp", "meter"], kind="stable")
            block = pa.Table.from_pandas(long, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(output/"all_meters.parquet", block.schema, compression="snappy")
            writer.write_table(block)
    finally:
        if writer is not None:
            writer.close()
    return {name: {"bytes": (output/name).stat().st_size, "rows": pq.ParquetFile(output/name).metadata.num_rows}
            for name in ("em_virtual.parquet", "all_meters.parquet")}


def demand_agreement(frame):
    finite = frame[["S_avg", "S_dmd_max"]].notna().all(axis=1) & ~frame["is_imputed"]
    check = frame.loc[finite]
    within = (check["S_avg"]-check["S_dmd_max"]).abs() <= .05*check["S_dmd_max"].abs()
    return int(finite.sum()), float(within.mean()) if len(within) else None


def f(value, digits=4):
    return "NA" if value is None or pd.isna(value) else f"{value:.{digits}f}"


def report(root, loaded, frames, stats, gaps, files, runtime):
    em = frames["EM_VIRTUAL"]
    lines = ["# SInERT ingestion", "", f"VM project: `{root}`. CPU-only; no modeling, feature engineering or notebooks.", "",
        "## Sources and schema", "",
        "The update contains 30 CSVs: 16 August 2025 and 14 February 2026 files, 51,535,457 extracted bytes. "
        f"Every CSV is required to have raw header MD5 `{ 'ae7740e6f10914f7aa4b2fa665f0baa0' }` and the same header bytes as the baseline.", "",
        f"Read {loaded.stats['csv_files']} CSVs and {loaded.stats['xlsx_files']} XLSX workbooks. "
        f"The November 2023 XLSX workbooks supplied {loaded.stats['xlsx_rows_in']} raw rows and "
        f"{loaded.stats['xlsx_new_em_intervals']} additional EM_VIRTUAL observed intervals beyond the original CSVs.", "",
        "XLSX measurement headers have numerical suffixes (for example `[ABS] 1`); these are removed by name, "
        "and the resulting entire header must equal the CSV schema. Excel dates are native datetime cells. "
        "Workbooks are streamed read-only, cached values only; formulas and macros are never executed.", "",
        "Both reactive counters are retained: the forward counter is not assumed frozen. Net reactive anchor energy is "
        "delta(Er_pos_counter) minus delta(Er_neg_counter). Observed dEr always uses signed Q_avg * 0.25.", "",
        "## Row accounting", "", "| Item | Count |", "|---|---:|"]
    for key in ("rows_in", "all_missing_rows_dropped", "duplicates_dropped", "unique_observed_timestamps", "grid_slots_created", "rows_out_per_meter"):
        lines.append(f"| {key} | {loaded.stats[key]} |")
    lines += [f"| Meters | {len(loaded.meters)} |", f"| Long output rows | {len(em)*len(loaded.meters)} |", "",
        f"Grid: {em.index[0]} through {em.index[-1]}, every 15 minutes. It starts after the entirely missing opening rows "
        "were dropped. No leading/trailing extrapolation is performed. Duplicates use the entire raw row's non-null measurement count, "
        "with stable first-row ties; the misplaced original August 2025 copies of May are deduplicated by actual timestamps.", "",
        "## Monthly observed coverage before imputation", "",
        "Counts are unique EM_VIRTUAL timestamps with at least one observed Ea_counter/P_avg/Q_avg. "
        "Calendar expected counts include the missing opening portion of June 2022.", "",
        "| Month | Original CSV | With November XLSX | With update | Calendar expected |", "|---|---:|---:|---:|---:|"]
    for month, row in loaded.coverage.sort_index().iterrows():
        lines.append(f"| {month} | {int(row['original_csv'])} | {int(row['with_xlsx'])} | {int(row['with_update'])} | {int(row['expected_calendar_slots'])} |")
    lines += ["", "## Imputation and leakage policy", "",
        "Thresholds live in configs/data.yaml (valid YAML 1.2 expressed with JSON syntax, parsed without another package). "
        "A gap is a consecutive run with any primary Ea/P/Q channel missing, per meter. Unbounded gaps and runs longer than 96 slots stay missing. "
        "Short runs up to 4 slots interpolate missing counter/P/Q cells linearly between original anchors, only with a same-day right anchor; "
        "dEa is then re-differenced.", "",
        "For 5–96 missing slots there are L+1 increments between the observed anchors. The nearest wholly observed, non-imputed "
        "same-weekday window within the earlier 8 weeks supplies the shape. Negative donor active increments are clipped to zero. "
        "Scale active increments to the exact active counter change, and signed net reactive increments independently to the change "
        "of both reactive counters. A missing/zero-sum donor uses uniform increments. Existing active-counter observations, including "
        "internal anchors in a partially missing run, are preserved. P_avg and Q_avg are reconstructed over all L+1 slots, "
        "including the closing slot, replacing those readings and flagging them; original values remain in the raw selected-channel cache. "
        "S_avg and PF are derived anew. Reactive counters remain observed-only cross-checks.", "",
        "Independent k/k_q preserve the two gap totals but generally change PF. Anchoring fixes total energy across the gap; "
        "allocation between months remains estimated if the anchors straddle a month boundary. Warnings do not alter observations or suppress tests.", "",
        "Right counter anchors are lookahead within an analysis partition. No imputation or donor crosses configured split boundaries. "
        "No train/test split has been chosen here: before modeling, rerun with actual boundaries or per split. "
        "The windowing eligibility function excludes any origin whose next H=96 labels contain an imputed row, including the "
        "reconstructed closing increment. Imputed data may inform inputs, never targets. Phase 5 PF alerts must use is_imputed=False rows only. "
        "Monthly observed PF ranges are used only for diagnostic warnings, never to choose a fill.", "",
        "is_imputed is a row boolean: true if any electrical value was filled/reconstructed or dEa depends on a filled previous counter. "
        "Per-method counts below include reconstructed closing P/Q readings, not only previously NaN cells.", "",
        "| Method | Channel | Reconstructed values, all meters |", "|---|---|---:|"]
    method_counts = Counter()
    for item in stats.values():
        method_counts.update(item["methods"])
    for name, count in sorted(method_counts.items()):
        method, channel = name.split(":", 1)
        lines.append(f"| {method} | {channel} | {count} |")
    lines += ["", "| Measure | All meters | EM_VIRTUAL |", "|---|---:|---:|",
        f"| Imputed rows | {sum(s['imputed_rows'] for s in stats.values())} | {stats['EM_VIRTUAL']['imputed_rows']} |",
        f"| Newly filled primary NaN cells | {sum(s['newly_filled_primary_cells'] for s in stats.values())} | {stats['EM_VIRTUAL']['newly_filled_primary_cells']} |",
        f"| Changed observed primary cells | {sum(s['replaced_observed_primary_cells'] for s in stats.values())} | {stats['EM_VIRTUAL']['replaced_observed_primary_cells']} |"]
    lines += ["", "| Column | Remaining NaNs, all meters | Remaining NaNs, EM_VIRTUAL |", "|---|---:|---:|"]
    for col in [c for c in OUTPUT if c != "is_imputed"] + ["Er_pos_counter", "Er_neg_counter"]:
        lines.append(f"| {col} | {sum(s['remaining_nan'][col] for s in stats.values())} | {stats['EM_VIRTUAL']['remaining_nan'][col]} |")
    lines += ["", "## Medium-gap reconstruction provenance", "",
        "Length counts missing slots; allocation spans length+1 intervals. Dates are naive export local time. "
        "NA scale/ratio means uniform fallback or an undefined ratio. Warning bounds: k outside [0.5,2], k_q/k outside [0.8,1.25], "
        "or reconstructed PF outside the observed surrounding-month range.", "",
        "| Meter | Start | L | Active / reactive method | Donor date | k | k_q | k_q/k | PF min / max | Warnings |",
        "|---|---|---:|---|---|---:|---:|---:|---|---|"]
    for gap in gaps:
        lines.append(f"| {gap['meter']} | {gap['start']} | {gap['length']} | {gap['method']} / {gap['reactive_method']} | {gap['donor_date'] or 'NA'} | {f(gap['k'])} | {f(gap['k_q'])} | {f(gap['kq_over_k'])} | {f(gap['min_PF'])} / {f(gap['max_PF'])} | {'; '.join(gap['warnings']) or 'none'} |")
    lines += ["", "## Longest remaining primary-channel gaps", "",
        "| Meter | Channel | First missing | Last missing | Slots |", "|---|---|---|---|---:|"]
    from smartgrid.data.impute import missing_runs
    longest = []
    for meter, frame in frames.items():
        for col in ("Ea_counter", "P_avg", "Q_avg", "dEa"):
            for start, stop in missing_runs(frame[col].isna()):
                longest.append((int(stop-start), meter, col, str(frame.index[start]), str(frame.index[stop-1])))
    for length, meter, col, start, stop in sorted(longest, reverse=True)[:12]:
        lines.append(f"| {meter} | {col} | {start} | {stop} | {length} |")
    lines += ["", "## EM_VIRTUAL monthly totals and peaks", "",
        "Totals include flagged reconstructions and exclude remaining NaNs. They are not full consumption estimates where gaps remain.", "",
        "| Month | Total dEa kWh | Max P_avg kW | Max S_avg kVA | Imputed rows |", "|---|---:|---:|---:|---:|"]
    for month, group in em.groupby(em.index.to_period("M")):
        lines.append(f"| {month} | {f(group['dEa'].sum(min_count=1),3)} | {f(group['P_avg'].max(),3)} | {f(group['S_avg'].max(),3)} | {int(group['is_imputed'].sum())} |")
    lines += ["", "## Validation measurements and contradictions", "",
        "S_avg derives from interval-average P/Q; S_dmd_max is a separate maximum-demand channel. "
        "The requested 5%-on-95% agreement check is measured and tested, without relabeling either channel.", "",
        "| Meter | Observed comparable S rows | Fraction within 5% of S_dmd_max |", "|---|---:|---:|"]
    for meter, frame in frames.items():
        count, fraction = demand_agreement(frame)
        lines.append(f"| {meter} | {count} | {f(fraction,6)} |")
    positive_q = sum(int((meter_frame(loaded.frame, meter)["Q_avg"] > 0).sum()) for meter in loaded.meters)
    lines += ["", f"Observed positive-Q meter intervals: {positive_q}; the site must not be assumed capacitive at every interval. "
        f"Medium-gap warnings: {sum(bool(g['warnings']) for g in gaps)} of {len(gaps)} reported bounded/medium cases. "
        "Uniform fallback is an estimate of interval shape, not a measured profile.", "",
        f"EM_VIRTUAL H=96 origins passing the imputed-label exclusion: {int(eligible_target_origins(em['is_imputed']).sum())}. "
        "This eligibility check does not yet reject other missing targets or define forecasting splits; no training windows were materialized.", "",
        "## Outputs and provenance", "",
        "em_virtual.parquet has exactly the requested timestamp plus ten measure/flag columns. Its Arrow metadata records "
        "source filename/sheet runs and imputation gap provenance. all_meters.parquet is timestamp/meter-sorted long format, "
        "with the same measures plus both reactive cross-check counters and source_filename/source_sheet. "
        "Grid-only rows have null source provenance. No raw files were modified.", "",
        "| VM output under data/processed/ | Data rows | Bytes |", "|---|---:|---:|"]
    for name, info in files.items():
        lines.append(f"| {name} | {info['rows']} | {info['bytes']} |")
    lines += ["", f"Pipeline runtime for this invocation: {runtime:.2f} seconds.", ""]
    (root/"reports").mkdir(exist_ok=True)
    (root/"reports/INGESTION.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--load-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--record-validation", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    root = args.root.resolve()
    if args.record_validation:
        path = root/"reports/INGESTION.md"
        body = path.read_text(encoding="utf-8").split("\n## Pytest result\n")[0]
        body = "\n".join(line for line in body.splitlines() if not line.startswith("Validation status:"))
        status = (root/"logs/ingestion-pytest.exit").read_text().strip()
        log = (root/"logs/ingestion-pytest.log").read_text(encoding="utf-8")
        statement = f"Validation status: pytest exit code {status}. " + (
            "All requested tests passed." if status == "0" else
            "Validation has failures; the requested assertions and thresholds remain unchanged.")
        body = body.replace("# SInERT ingestion\n", "# SInERT ingestion\n\n"+statement+"\n", 1)
        path.write_text(body+"\n\n## Pytest result\n\n```text\n"+log.rstrip()+"\n```\n", encoding="utf-8")
        print(statement, flush=True)
        return
    config = json.loads((root/"configs/data.yaml").read_text(encoding="utf-8"))
    loaded = load_or_resume(root, config, args.resume)
    print(json.dumps({k: v for k, v in loaded.stats.items() if k != "source_sheets"}, indent=2), flush=True)
    if args.load_only:
        print("LOAD_ONLY_DONE", time.monotonic()-started, flush=True)
        return
    from smartgrid.data.impute import impute
    frames, stats, gaps = {}, {}, []
    for meter in loaded.meters:
        frames[meter], stats[meter], log = impute(meter_frame(loaded.frame, meter), config["imputation"])
        gaps.extend({"meter": meter, **gap} for gap in log)
        print("IMPUTED", meter, json.dumps(stats[meter]), flush=True)
    files = write_outputs(root, loaded, frames, gaps)
    report(root, loaded, frames, stats, gaps, files, time.monotonic()-started)
    print("OUTPUTS", json.dumps(files), flush=True)
    print("RUNTIME_SECONDS", time.monotonic()-started, flush=True)


if __name__ == "__main__":
    main()
