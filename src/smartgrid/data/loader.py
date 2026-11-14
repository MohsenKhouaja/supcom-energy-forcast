"""Read untrusted SInERT exports without executing input code or formulas.

CSV rows and XLSX cells are streamed one file at a time. Only the six named
channels per meter are retained. The full raw row is inspected for missingness
and the deduplication completeness score; unused measurements are never stored.

Before constructing training windows, call windowing.eligible_target_origins:
all H=96 future targets must be observed (is_imputed=False). Imputed values may
inform inputs, never labels. Rerun imputation with the intended split boundaries
or separately within each split. Phase 5 PF alerts must compute statistics ONLY
on observed rows (is_imputed=False), never on reconstructed PF.
"""

from __future__ import annotations

from collections import Counter
import csv
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import hashlib
import math
from pathlib import Path
import re

import numpy as np
import pandas as pd

CHANNELS = {
    "Ea_counter": "kWh (kWh) [ABS]",
    "P_avg": "kW sys (kW) [AVG]",
    "Q_avg": "kvar sys (kvar) [AVG]",
    "Er_neg_counter": "kvarh (-) (kvarh) [ABS]",
    "Er_pos_counter": "kvarh (kvarh) [ABS]",
    "P_dmd_max": "kW dmd (kW) [MAX]",
    "S_dmd_max": "kVA dmd (kVA) [MAX]",
}
PROVENANCE = ["source_filename", "source_sheet"]


@dataclass
class LoadedDataset:
    frame: pd.DataFrame
    meters: tuple[str, ...]
    stats: dict
    coverage: pd.DataFrame


def parse_timestamp(day, clock) -> pd.Timestamp:
    """Interpret a separate export date and clock; 24:00 belongs to next day."""
    if isinstance(day, (pd.Timestamp, datetime, date)):
        base = pd.Timestamp(day).normalize()
    else:
        base = pd.Timestamp(datetime.strptime(str(day).strip(), "%d-%m-%Y"))
    if isinstance(clock, (datetime, pd.Timestamp)):
        clock = clock.time()
    if isinstance(clock, time):
        offset = timedelta(hours=clock.hour, minutes=clock.minute, seconds=clock.second)
    else:
        text = str(clock).strip()
        if text == "24:00:00":
            offset = timedelta(days=1)
        else:
            parsed = datetime.strptime(text, "%H:%M:%S")
            offset = timedelta(hours=parsed.hour, minutes=parsed.minute, seconds=parsed.second)
    result = base + offset
    if result.tzinfo is not None or result.minute % 15 or result.second or result.microsecond:
        raise ValueError(f"Timestamp is not a naive 15-minute grid point: {result}")
    return result


def missing(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() in ("", "---")) or (
        isinstance(value, (float, np.floating)) and math.isnan(value)
    )


def number(value) -> float:
    if missing(value):
        return np.nan
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Non-finite electrical value: {value!r}")
    return result


def normalize_header(values, *, xlsx=False) -> list[str]:
    """XLSX export suffix '[AVG] 2' becomes '[AVG]'; never map by position."""
    result = []
    for value in values:
        name = str(value).strip()
        if xlsx:
            name = re.sub(r"(\])\s+\d+$", r"\1", name)
        result.append(name)
    if len(result) != len(set(result)):
        raise ValueError("Duplicate column names after normalization")
    return result


def raw_name(meter: str, measure: str) -> str:
    return f"{meter} {CHANNELS[measure]}"


def meter_frame(wide: pd.DataFrame, meter: str) -> pd.DataFrame:
    result = wide[[raw_name(meter, field) for field in CHANNELS]].rename(
        columns={raw_name(meter, field): field for field in CHANNELS}
    ).copy()
    return result


def canonicalize(rows: pd.DataFrame, measures: list[str]) -> tuple[pd.DataFrame, dict]:
    """Sort, drop all-raw-missing rows, deduplicate, then create explicit holes."""
    if rows.empty:
        raise ValueError("No input rows")
    kept = rows.loc[rows["_non_null"] > 0].copy()
    if kept.empty:
        raise ValueError("All raw measurement rows are missing")
    kept = kept.sort_values(["timestamp", "_non_null"], ascending=[True, False], kind="stable")
    duplicates = int(kept.duplicated("timestamp").sum())
    kept = kept.drop_duplicates("timestamp", keep="first").set_index("timestamp").sort_index()
    grid = pd.date_range(kept.index[0], kept.index[-1], freq="15min", name="timestamp")
    stats = {"rows_in": len(rows), "all_missing_rows_dropped": int((rows["_non_null"] == 0).sum()),
             "duplicates_dropped": duplicates, "unique_observed_timestamps": len(kept),
             "grid_slots_created": len(grid)-len(kept), "rows_out_per_meter": len(grid)}
    return kept[measures + PROVENANCE].reindex(grid), stats


def load_dataset(root: Path, raw_trees, *, expected_header_md5=None,
                 expected_meter_count=None) -> LoadedDataset:
    root = Path(root).resolve()
    paths = sorted(p for tree in raw_trees for p in (root/tree).rglob("*")
                   if p.is_file() and p.suffix.lower() in (".csv", ".xlsx"))
    csv_paths = [p for p in paths if p.suffix.lower() == ".csv"]
    if not csv_paths:
        raise ValueError("No input CSV files")
    with csv_paths[0].open("rb") as f:
        baseline_bytes = f.readline()
    baseline = normalize_header(next(csv.reader([baseline_bytes.decode("utf-8-sig")], delimiter=";")))
    suffix = " " + CHANNELS["Ea_counter"]
    meters = tuple(sorted(c[:-len(suffix)] for c in baseline if c.endswith(suffix)))
    if expected_meter_count is not None and len(meters) != expected_meter_count:
        raise ValueError(f"Expected {expected_meter_count} meters, found {len(meters)}")
    if not meters:
        raise ValueError("No named active energy channels")
    measures = [raw_name(m, field) for m in meters for field in CHANNELS]
    for name in ["Date", "Time", *measures]:
        if name not in baseline:
            raise ValueError(f"Required named column missing: {name}")
    chunks, file_stats = [], []
    csv.field_size_limit(1024*1024)

    def consume(path, sheet, header_values, iterator):
        header = normalize_header(header_values, xlsx=bool(sheet))
        if header != baseline:
            different = [(a, b) for a, b in zip(baseline, header) if a != b]
            raise ValueError(f"Normalized header mismatch in {path}:{sheet}: {different[:5]}")
        values, dates, scores = [], [], []
        rel = path.relative_to(root).as_posix()
        for line_no, row_values in enumerate(iterator, 2):
            if len(row_values) != len(header):
                raise ValueError(f"Row width mismatch in {rel}:{sheet}:{line_no}")
            row = dict(zip(header, row_values))
            score = sum(not missing(value) for name, value in row.items() if name not in ("Date", "Time"))
            if missing(row["Date"]) and missing(row["Time"]) and score == 0:
                continue  # Empty worksheet padding is not a timestamped observation.
            dates.append(parse_timestamp(row["Date"], row["Time"]))
            values.append([number(row[name]) for name in measures])
            scores.append(score)
        if not dates:
            return
        chunk = pd.DataFrame(np.asarray(values, dtype=float), columns=measures)
        chunk["timestamp"] = dates
        chunk["_non_null"] = scores
        chunk["source_filename"] = rel
        chunk["source_sheet"] = sheet or ""
        chunk["_format"] = path.suffix.lower()[1:]
        chunk["_tree"] = "update" if path.is_relative_to(root/raw_trees[-1]) and len(raw_trees)>1 else "original"
        chunks.append(chunk)
        file_stats.append({"filename": rel, "sheet": sheet or "", "rows": len(chunk),
                           "all_missing": int((chunk["_non_null"] == 0).sum())})

    for i, path in enumerate(paths, 1):
        if path.suffix.lower() == ".csv":
            with path.open("rb") as f:
                line = f.readline()
            if expected_header_md5 is not None:
                digest = hashlib.md5(line).hexdigest()
                if digest != expected_header_md5 or line != baseline_bytes:
                    raise ValueError(f"CSV HEADER MISMATCH: {path}; actual={digest}; expected={expected_header_md5}")
            with path.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f, delimiter=";")
                consume(path, None, next(reader), reader)
        else:
            from openpyxl import load_workbook
            workbook = load_workbook(path, read_only=True, data_only=True, keep_links=False)
            try:
                for sheet in workbook:
                    rows = sheet.iter_rows(values_only=True)
                    header = next(rows, None)
                    if header is not None:
                        consume(path, sheet.title, header, rows)
            finally:
                workbook.close()
        if i % 25 == 0 or i == len(paths):
            print(f"READ {i}/{len(paths)} files: {path.name}", flush=True)
    rows = pd.concat(chunks, ignore_index=True)
    del chunks
    em_columns = [raw_name("EM_VIRTUAL", k) for k in ("Ea_counter", "P_avg", "Q_avg")]
    if "EM_VIRTUAL" not in meters:
        em_columns = [raw_name(meters[0], k) for k in ("Ea_counter", "P_avg", "Q_avg")]
    observed = rows.loc[rows[em_columns].notna().any(axis=1)]
    def observed_times(frame):
        return pd.DatetimeIndex(frame["timestamp"].drop_duplicates()).sort_values()
    before = observed_times(observed.loc[(observed["_tree"] == "original") & (observed["_format"] == "csv")])
    recovered = observed_times(observed.loc[observed["_tree"] == "original"])
    after = observed_times(observed)
    xlsx_times = observed_times(observed.loc[observed["_format"] == "xlsx"])
    month_range = pd.period_range(min(rows["timestamp"]).to_period("M"), max(after).to_period("M"), freq="M")
    coverage = pd.DataFrame(index=month_range.astype(str))
    for label, times in (("original_csv", before), ("with_xlsx", recovered), ("with_update", after)):
        coverage[label] = pd.Series(Counter(times.strftime("%Y-%m"))).reindex(coverage.index, fill_value=0)
    coverage["expected_calendar_slots"] = [p.days_in_month*96 for p in month_range]
    frame, stats = canonicalize(rows, measures)
    stats.update({"csv_files": len(csv_paths), "xlsx_files": len(paths)-len(csv_paths),
                  "source_sheets": file_stats, "xlsx_new_em_intervals": len(xlsx_times.difference(before)),
                  "xlsx_em_intervals": len(xlsx_times), "xlsx_rows_in": sum(f["rows"] for f in file_stats if f["sheet"]),
                  "normalized_xlsx_numeric_suffixes": True})
    return LoadedDataset(frame, meters, stats, coverage)
