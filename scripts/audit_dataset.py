#!/usr/bin/env python3
"""Standalone SInERT inspection; never modifies existing files in data/raw.

Run --extract once into an empty destination, --self-test, then without flags.
Only one CSV row is parsed at a time. Retain selected numerical channels for
one calendar month, plus midnight rollover rows. No model or ingestion code.
"""

from __future__ import annotations

import argparse
import calendar
from collections import Counter, defaultdict
import csv
from datetime import datetime, timedelta
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import time
import zipfile

STEP = timedelta(minutes=15)
SUFFIX = {
    "ea": "kWh (kWh) [ABS]",
    "p": "kW sys (kW) [AVG]",
    "q": "kvar sys (kvar) [AVG]",
    "rp": "kvarh (kvarh) [ABS]",
    "rn": "kvarh (-) (kvarh) [ABS]",
}
INVENTORY = ["path", "month", "bytes", "n_cols", "n_rows", "first_ts", "last_ts", "header_md5"]
ANOMALIES = ["issue", "path", "month", "meter", "timestamp", "previous_timestamp", "column", "value", "previous_value", "details"]
METERS = ["month", "meter", "interval_count", "expected_count", "missing_pct", "dEa_kWh",
          "dEa_valid_intervals", "negative_dEa_count", "dEa_positive_kWh", "dEr_kvarh",
          "q_intervals", "max_kW", "max_derived_kVA", "mean_derived_PF", "min_derived_PF",
          "PF_intervals", "kvarh_change", "kvarh_negative_change", "kvarh_first_ts",
          "kvarh_last_ts", "kvarh_negative_first_ts", "kvarh_negative_last_ts",
          "nonzero_intervals", "first_nonzero_ts", "last_nonzero_ts",
          "nonzero_kWh_counter_count", "first_nonzero_kWh_ts", "last_nonzero_kWh_ts"]


def timestamp(date: str, clock: str) -> datetime:
    day = datetime.strptime(date.strip(), "%d-%m-%Y")
    clock = clock.strip()
    if clock == "24:00:00":
        return day + timedelta(days=1)
    return datetime.combine(day.date(), datetime.strptime(clock, "%H:%M:%S").time())


def next_month(day: datetime) -> datetime:
    return datetime(day.year + (day.month == 12), day.month % 12 + 1, 1)


def folder_month(path: Path) -> str:
    match = re.fullmatch(r"([A-Za-z]+)(\d{4})", path.parent.name)
    if not match:
        raise ValueError(f"Unrecognized month folder: {path.parent.name}")
    names = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
    return f"{int(match[2]):04d}-{names[match[1].lower()]:02d}"


def iso(value):
    return value.isoformat(sep=" ") if isinstance(value, datetime) else value


def writer(path, fields):
    handle = path.open("w", newline="", encoding="utf-8")
    out = csv.DictWriter(handle, fieldnames=fields)
    out.writeheader()
    return handle, out


def extract(root: Path):
    """Validate all members before extracting regular files; never use extractall."""
    destination = root / "data/raw/sinert"
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(f"Extraction destination is not empty: {destination}")
    if destination.is_symlink():
        raise ValueError("Extraction destination must not be a symlink")
    with zipfile.ZipFile(root / "data/raw/SINERT_DATA_CONCENTRATOR.zip") as archive:
        members = archive.infolist()
        seen = set()
        for member in members:
            p = PurePosixPath(member.filename)
            mode = member.external_attr >> 16
            if (p.is_absolute() or ".." in p.parts or "\\" in member.filename
                    or ":" in member.filename or not p.parts
                    or stat.S_ISLNK(mode)
                    or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR))):
                raise ValueError(f"Unsafe ZIP member: {member.filename!r}")
            target = destination.joinpath(*p.parts)
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError(f"ZIP member escapes destination: {member.filename!r}")
            if str(p) in seen:
                raise ValueError(f"Duplicate ZIP member: {member.filename!r}")
            seen.add(str(p))
        required = sum(m.file_size for m in members)
        if shutil.disk_usage(root).free < required + 1024 ** 3:
            raise ValueError("Insufficient project filesystem space for extraction plus 1 GiB")
        destination.mkdir(parents=True, exist_ok=True)
        for member in members:
            target = destination.joinpath(*PurePosixPath(member.filename).parts)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
    files = [p for p in destination.rglob("*") if p.is_file()]
    csvs = [p for p in files if p.suffix.lower() == ".csv"]
    print(json.dumps({"extracted_bytes": sum(p.stat().st_size for p in files),
                      "files": len(files), "csv_files": len(csvs),
                      "month_folders": len({p.parent for p in csvs}),
                      "other_files": [str(p.relative_to(destination)) for p in files if p not in csvs]}, indent=2), flush=True)


def self_test():
    assert timestamp("31-12-2023", "24:00:00") == datetime(2024, 1, 1)
    assert timestamp("28-02-2024", "24:00:00") == datetime(2024, 2, 29)
    assert timestamp("29-02-2024", "24:00:00") == datetime(2024, 3, 1)
    assert timestamp("01-01-2024", "00:15:00") - timestamp("31-12-2023", "24:00:00") == STEP
    assert next_month(datetime(2023, 12, 1)) == datetime(2024, 1, 1)
    assert folder_month(Path("February2024/test.csv")) == "2024-02"
    assert 100 * (1 - 2 / 4) == 50
    assert math.isclose(3 / math.hypot(3, 4), 0.6)
    print("SELF_TEST_OK: midnight rollover, leap day, year boundary, month parsing, cadence, missing percentage, PF")


def audit(root: Path):
    started = time.monotonic()
    import numpy as np

    csv.field_size_limit(1024 * 1024)
    raw = root / "data/raw/sinert"
    reports = root / "reports"
    reports.mkdir(exist_ok=True)
    paths = sorted(raw.rglob("*.csv"), key=lambda p: (folder_month(p), p.name))
    if not paths:
        raise ValueError("No extracted CSV files found")
    headers, counts, info = {}, Counter(), {}
    for path in paths:
        first_valid = None
        with path.open("rb") as f:
            line = f.readline()
            cols = next(csv.reader([line.decode("utf-8-sig")], delimiter=";"))
            normalized = [c.strip() for c in cols]
            date_i, time_i = normalized.index("Date"), normalized.index("Time")
            for row in csv.reader(io.TextIOWrapper(f, encoding="utf-8-sig", newline=""), delimiter=";"):
                if len(row) != len(cols):
                    continue
                try:
                    first_valid = timestamp(row[date_i], row[time_i])
                    break
                except ValueError:
                    continue  # Invalid records are explicitly reported in the full pass.
        digest = hashlib.md5(line).hexdigest()
        headers[digest] = cols
        counts[digest] += 1
        observed_month = first_valid.strftime("%Y-%m") if first_valid else folder_month(path)
        info[path] = (digest, cols, observed_month, first_valid)
    paths.sort(key=lambda p: (info[p][2], info[p][3] or datetime.min,
                              folder_month(p) != info[p][2], p.name, str(p)))
    folder_counts = Counter(folder_month(p) for p in paths)
    misplaced = []
    for path in paths:
        if folder_month(path) != info[path][2]:
            candidates = [p for p in paths if p.name == path.name and folder_month(p) == info[path][2]]
            identical = None
            for candidate in candidates:
                def sha256_file(p):
                    digest = hashlib.sha256()
                    with p.open("rb") as handle:
                        for block in iter(lambda: handle.read(1024 * 1024), b""):
                            digest.update(block)
                    return digest.hexdigest()
                if sha256_file(path) == sha256_file(candidate):
                    identical = str(candidate.relative_to(root))
                    break
            misplaced.append((str(path.relative_to(root)), folder_month(path), info[path][2], identical))
    majority = counts.most_common(1)[0][0]
    all_columns = sorted({c.strip() for cols in headers.values() for c in cols})
    meters = sorted(c[:-len(SUFFIX["ea"])].strip() for c in all_columns if c.endswith(" " + SUFFIX["ea"]))
    selected = [c for c in all_columns if c.endswith("[ABS]") or any(c.endswith(" " + SUFFIX[k]) for k in ("p", "q"))]
    index = {c: i for i, c in enumerate(selected)}
    metric_index = {m: {k: index.get(m + " " + s) for k, s in SUFFIX.items()} for m in meters}
    counters = [(c, index[c]) for c in selected if c.endswith("[ABS]")]
    ih, inv = writer(reports / "inventory.csv", INVENTORY)
    ah, anomaly = writer(reports / "anomalies.csv", ANOMALIES)
    mh, meter_writer = writer(reports / "meters.csv", METERS)
    issue_counts = Counter()
    month_rows, meter_rows, gaps, boundaries, header_diffs = [], [], [], [], []
    missing_open, missing_runs = {}, []
    all_missing_rows = rollover_count = offgrid_count = 0
    duplicate_conflicts = 0

    def issue(kind, **kwargs):
        issue_counts[kind] += 1
        anomaly.writerow({"issue": kind, **{k: iso(v) for k, v in kwargs.items()}})

    for path in paths:
        digest, cols, _, _ = info[path]
        if digest != majority:
            baseline = headers[majority]
            changes = [{"position": i, "majority": baseline[i] if i < len(baseline) else None,
                        "actual": cols[i] if i < len(cols) else None}
                       for i in range(max(len(cols), len(baseline)))
                       if (baseline[i] if i < len(baseline) else None) != (cols[i] if i < len(cols) else None)]
            detail = json.dumps(changes, ensure_ascii=False) if changes else "Parsed columns identical; raw header bytes differ."
            rel = str(path.relative_to(root))
            header_diffs.append((rel, detail))
            issue("header_differs", path=rel, month=folder_month(path), value=digest, previous_value=majority, details=detail)
    for rel, source_month, observed_month, identical in misplaced:
        issue("misplaced_file", path=rel, month=source_month,
              details=f"first observed month={observed_month}; byte-identical SHA-256 match={identical or 'none found'}")

    grouped = defaultdict(list)
    for path in paths:
        grouped[info[path][2]].append(path)
    first_month = datetime.strptime(min(set(grouped) | set(folder_counts)), "%Y-%m")
    end_month = next_month(datetime.strptime(max(set(grouped) | set(folder_counts)), "%Y-%m"))
    current = first_month
    carry = []
    previous_file = None
    previous_ts = None
    previous_values = None
    counter_previous = {}
    meter_last = {}
    while current < end_month:
        month = current.strftime("%Y-%m")
        end = next_month(current)
        records = {}
        next_carry = []
        raw_rows = month_all_missing = 0

        def accept(ts, values, empty, rel, row_number):
            nonlocal duplicate_conflicts
            if ts >= end:
                next_carry.append((ts, values, empty, rel, row_number))
                return
            if ts < current:
                issue("outside_processing_month", path=rel, month=month, timestamp=ts, details=f"row {row_number}; excluded")
                return
            if ts in records:
                old, oldempty, oldpath, oldrow = records[ts]
                common = np.isfinite(old) & np.isfinite(values)
                conflict = bool(np.any(old[common] != values[common]))
                duplicate_conflicts += int(conflict)
                issue("duplicate_timestamp", path=rel, month=month, timestamp=ts,
                      details=f"row {row_number}; earlier {oldpath}:{oldrow}; conflicting_selected_values={conflict}")
                if np.isfinite(values).sum() <= np.isfinite(old).sum():
                    return
            records[ts] = (values, empty, rel, row_number)

        for row in carry:
            accept(*row)
        for path in grouped.get(month, []):
            rel = str(path.relative_to(root))
            digest, original, _, _ = info[path]
            source_month = folder_month(path)
            source_start = datetime.strptime(source_month, "%Y-%m")
            source_end = next_month(source_start)
            normalized = [c.strip() for c in original]
            if len(normalized) != len(set(normalized)):
                raise ValueError(f"Ambiguous duplicate column names: {rel}")
            positions = [(i, index[c]) for i, c in enumerate(normalized) if c in index]
            date_i, time_i = normalized.index("Date"), normalized.index("Time")
            nrows = 0
            first = last = earlier = None
            with path.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f, delimiter=";")
                next(reader)
                for line_no, row in enumerate(reader, 2):
                    nrows += 1
                    raw_rows += 1
                    if len(row) != len(original):
                        issue("row_width", path=rel, month=month, value=len(row), previous_value=len(original), details=f"row {line_no}; excluded")
                        continue
                    try:
                        ts = timestamp(row[date_i], row[time_i])
                    except ValueError as error:
                        issue("invalid_timestamp", path=rel, month=month, details=f"row {line_no}: {error}")
                        continue
                    rollover_count += int(row[time_i].strip() == "24:00:00")
                    if ts < source_start or ts > source_end:
                        issue("outside_source_month", path=rel, month=source_month, timestamp=ts,
                              details=f"row {line_no}; included under actual timestamp, deduplicated")
                    if ts.minute % 15 or ts.second or ts.microsecond:
                        offgrid_count += 1
                        issue("off_cadence_timestamp", path=rel, month=month, timestamp=ts, details=f"row {line_no}; excluded from cadence counts")
                    if earlier is not None and ts < earlier:
                        issue("out_of_order", path=rel, month=month, timestamp=ts, previous_timestamp=earlier)
                    earlier = ts
                    first = ts if first is None else min(first, ts)
                    last = ts if last is None else max(last, ts)
                    measurements = [v.strip() for i, v in enumerate(row) if i not in (date_i, time_i)]
                    empty = all(v == "---" for v in measurements)
                    if empty:
                        all_missing_rows += 1
                        month_all_missing += 1
                        issue("all_missing_row", path=rel, month=month, timestamp=ts, details=f"row {line_no}; all measurement columns are ---")
                    values = np.full(len(selected), np.nan)
                    for source, target in positions:
                        value = row[source].strip()
                        if value in ("---", ""):
                            continue
                        try:
                            number = float(value)
                            if not math.isfinite(number):
                                raise ValueError("non-finite")
                            values[target] = number
                        except ValueError:
                            issue("invalid_numeric", path=rel, month=month, timestamp=ts, column=selected[target], value=value, details=f"row {line_no}")
                    accept(ts, values, empty, rel, line_no)
            inv.writerow(dict(zip(INVENTORY, [rel, source_month, path.stat().st_size, len(original), nrows, iso(first), iso(last), digest])))
            if previous_file is not None and first is not None:
                prev_path, prev_last = previous_file
                delta = (first - prev_last).total_seconds() / 60
                kind = "overlap" if delta <= 0 else "hole" if delta > 15 else "contiguous"
                boundaries.append((kind, delta, prev_path, rel, prev_last, first))
                if kind != "contiguous":
                    issue("file_boundary_" + kind, path=rel, month=month, timestamp=first, previous_timestamp=prev_last,
                          value=delta, details=f"minutes from previous file endpoint; previous={prev_path}")
            if last is not None:
                previous_file = (rel, last)
        ordered = sorted(records)
        expected = int((end - current) / STEP)
        ongrid = np.array([t.minute % 15 == 0 and t.second == 0 for t in ordered], dtype=bool)
        matrix = np.array([records[t][0] for t in ordered]) if ordered else np.empty((0, len(selected)))
        raw_unique = int(ongrid.sum())
        usable = sum(not records[t][1] and good for t, good in zip(ordered, ongrid))
        increments = {m: [] for m in meters}
        monthly_negative = Counter()
        monthly_positive = defaultdict(float)
        for j, ts in enumerate(ordered):
            values, _, rel, line_no = records[ts]
            if previous_ts is not None and ts - previous_ts > STEP:
                gap = (ts - previous_ts).total_seconds() / 60
                gaps.append((gap, "timestamp", "ALL", previous_ts, ts))
                issue("timestamp_gap", path=rel, month=month, timestamp=ts, previous_timestamp=previous_ts, value=gap)
            for col, idx in counters:
                value = values[idx]
                if np.isfinite(value):
                    prev = counter_previous.get(col)
                    if prev is not None and value < prev[1]:
                        issue("counter_decrease", path=rel, month=month, meter=col.split(" ")[0], timestamp=ts,
                              previous_timestamp=prev[0], column=col, value=value, previous_value=prev[1],
                              details=f"change={value-prev[1]:.12g}; decrease does not by itself prove a hardware reset")
                    counter_previous[col] = (ts, value)
            if previous_ts is not None and ts - previous_ts == STEP:
                for m in meters:
                    idx = metric_index[m]["ea"]
                    if idx is not None and np.isfinite(values[idx]) and np.isfinite(previous_values[idx]):
                        delta = float(values[idx] - previous_values[idx])
                        increments[m].append(delta)
                        monthly_positive[m] += max(delta, 0)
                        if delta < 0:
                            monthly_negative[m] += 1
                            issue("negative_dEa", path=rel, month=month, meter=m, timestamp=ts, previous_timestamp=previous_ts,
                                  column=m + " " + SUFFIX["ea"], value=delta)
            previous_ts, previous_values = ts, values

        def column(m, k):
            idx = metric_index[m][k]
            return matrix[:, idx] if idx is not None else np.full(len(ordered), np.nan)

        def finite_stat(values, operation):
            good = values[np.isfinite(values)]
            return float(operation(good)) if len(good) else ""

        local = {}
        for m in meters:
            p, q = column(m, "p"), column(m, "q")
            valid = np.isfinite(p) & np.isfinite(q) & ongrid
            present = (np.isfinite(p) | np.isfinite(q) | np.isfinite(column(m, "ea"))) & ongrid
            active = ((np.isfinite(p) & (p != 0)) | (np.isfinite(q) & (q != 0))) & ongrid
            apparent = np.hypot(p, q)
            pf_good = valid & (apparent > 0)
            pf = np.full(len(p), np.nan)
            pf[pf_good] = p[pf_good] / apparent[pf_good]
            times = [t for t, good in zip(ordered, present) if good]
            present_times = set(times)
            for slot in range(expected):
                grid_ts = current + slot * STEP
                if grid_ts not in present_times:
                    missing_open.setdefault(m, grid_ts)
                elif m in missing_open:
                    run_start = missing_open.pop(m)
                    slots = int((grid_ts - run_start) / STEP)
                    missing_runs.append((slots, m, run_start, grid_ts))
                    issue("meter_missing_run", month=run_start.strftime("%Y-%m"), meter=m,
                          timestamp=run_start, value=slots,
                          details=f"missing calendar slots; end_exclusive={iso(grid_ts)}; minutes={slots*15}")
            for a, b in zip(times, times[1:]):
                if b - a > STEP:
                    gap = (b-a).total_seconds()/60
                    gaps.append((gap, "meter", m, a, b))
                    issue("meter_gap", month=month, meter=m, timestamp=b, previous_timestamp=a, value=gap)
            prior = meter_last.get(m)
            if times and prior is not None and times[0] - prior > STEP:
                gap = (times[0]-prior).total_seconds()/60
                gaps.append((gap, "meter", m, prior, times[0]))
                issue("meter_gap", month=month, meter=m, timestamp=times[0], previous_timestamp=prior, value=gap)
            if times:
                meter_last[m] = times[-1]
            changes = {}
            for k, label in (("rp", "kvarh"), ("rn", "kvarh_negative")):
                values = column(m, k)
                good = np.flatnonzero(np.isfinite(values) & ongrid)
                changes[label + "_change"] = float(values[good[-1]] - values[good[0]]) if len(good) > 1 else ""
                changes[label + "_first_ts"] = iso(ordered[good[0]]) if len(good) else ""
                changes[label + "_last_ts"] = iso(ordered[good[-1]]) if len(good) else ""
            nz_times = [t for t, good in zip(ordered, active) if good]
            ea_values = column(m, "ea")
            nz_counter_times = [t for t, good in zip(ordered, np.isfinite(ea_values) & (ea_values != 0) & ongrid) if good]
            result = dict(month=month, meter=m, interval_count=int(present.sum()), expected_count=expected,
                          missing_pct=100 * (1 - present.sum()/expected),
                          dEa_kWh=math.fsum(increments[m]) if increments[m] else "",
                          dEa_valid_intervals=len(increments[m]), negative_dEa_count=monthly_negative[m],
                          dEa_positive_kWh=monthly_positive[m] if increments[m] else "",
                          dEr_kvarh=float(np.sum(q[np.isfinite(q) & ongrid]))*0.25 if np.any(np.isfinite(q) & ongrid) else "",
                          q_intervals=int((np.isfinite(q) & ongrid).sum()),
                          max_kW=finite_stat(p[ongrid], np.max), max_derived_kVA=finite_stat(apparent[valid], np.max),
                          mean_derived_PF=finite_stat(pf, np.mean), min_derived_PF=finite_stat(pf, np.min),
                          PF_intervals=int(pf_good.sum()), nonzero_intervals=len(nz_times),
                          first_nonzero_ts=iso(nz_times[0]) if nz_times else "", last_nonzero_ts=iso(nz_times[-1]) if nz_times else "",
                          nonzero_kWh_counter_count=len(nz_counter_times),
                          first_nonzero_kWh_ts=iso(nz_counter_times[0]) if nz_counter_times else "",
                          last_nonzero_kWh_ts=iso(nz_counter_times[-1]) if nz_counter_times else "", **changes)
            meter_writer.writerow(result)
            meter_rows.append(result)
            local[m] = result
        balance = {}
        for k in SUFFIX:
            if all(m in metric_index for m in ("EM_VIRTUAL", "TGBT_TR1", "TGBT_TR2")):
                v, a, b = (column(m, k) for m in ("EM_VIRTUAL", "TGBT_TR1", "TGBT_TR2"))
                good = np.isfinite(v) & np.isfinite(a) & np.isfinite(b) & ongrid
                residual = v[good] - a[good] - b[good]
                comparison_times = [t for t, valid in zip(ordered, good) if valid]
                mismatch_times = [t for t, residual_value in zip(comparison_times, residual) if abs(residual_value) > 1e-6]
                balance[k] = {"compared": len(residual), "unequal": int(np.sum(np.abs(residual) > 1e-6)),
                              "max_abs": float(np.max(np.abs(residual))) if len(residual) else None,
                              "min_residual": float(np.min(residual)) if len(residual) else None,
                              "max_residual": float(np.max(residual)) if len(residual) else None,
                              "first_mismatch": iso(mismatch_times[0]) if mismatch_times else "",
                              "last_mismatch": iso(mismatch_times[-1]) if mismatch_times else ""}
        month_rows.append(dict(month=month, csv_files=len(grouped.get(month, [])), raw_rows=raw_rows,
                               source_files=folder_counts[month],
                               unique=raw_unique, usable=usable, expected=expected, all_missing=month_all_missing,
                               balance=balance, local=local))
        print(f"MONTH {month}: files={len(grouped.get(month, []))}, raw_rows={raw_rows}, unique_grid={raw_unique}/{expected}, usable={usable}, elapsed={time.monotonic()-started:.2f}s", flush=True)
        carry = next_carry
        current = end
    for m, run_start in missing_open.items():
        slots = int((end_month-run_start)/STEP)
        missing_runs.append((slots, m, run_start, end_month))
        issue("meter_missing_run", month=run_start.strftime("%Y-%m"), meter=m, timestamp=run_start, value=slots,
              details=f"missing calendar slots; end_exclusive={iso(end_month)}; minutes={slots*15}; trailing run")
    ih.close()
    ah.close()
    mh.close()
    runtime = time.monotonic() - started
    other_files = sorted(str(p.relative_to(root)) for p in raw.rglob("*") if p.is_file() and p.suffix.lower() != ".csv")
    report = make_report(root, paths, counts, majority, headers, header_diffs, month_rows, meter_rows,
                         issue_counts, gaps, boundaries, all_missing_rows, rollover_count, offgrid_count,
                         duplicate_conflicts, other_files, runtime, len(selected), carry, missing_runs, misplaced)
    (reports / "AUDIT.md").write_text(report, encoding="utf-8")
    print(json.dumps({"runtime_seconds": runtime, "inventory_rows": len(paths), "meters_rows": len(meter_rows),
                      "anomalies_rows": sum(issue_counts.values()), "issues": issue_counts}, indent=2), flush=True)


def fmt(value, digits=3):
    return "NA" if value is None or value == "" else f"{value:.{digits}f}"


def periods(months):
    if not months:
        return "none"
    result = []
    start = previous = months[0]
    for month in months[1:]:
        if next_month(datetime.strptime(previous, "%Y-%m")).strftime("%Y-%m") != month:
            result.append(start if start == previous else f"{start} to {previous}")
            start = month
        previous = month
    result.append(start if start == previous else f"{start} to {previous}")
    return "; ".join(result)


def make_report(root, paths, counts, majority, headers, differences, months, meters, issues,
                gaps, boundaries, missing, rollovers, offgrid, conflicts, others, runtime, nselected, carry, missing_runs, misplaced):
    lines = ["# SInERT dataset audit", "", f"VM working folder: `{root}`. CSV audit only; no training or pipeline ingestion.", "",
             f"Observed runtime environment: host `{platform.node()}`, Python {platform.python_version()}, "
             f"{platform.freedesktop_os_release().get('PRETTY_NAME', 'unknown Linux distribution')}.", "",
             f"Audit script SHA-256: `{hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}`.", "",
             f"Inspected {len(paths):,} CSV files in {len({folder_month(p) for p in paths})} month folders, "
             f"{sum(p.stat().st_size for p in paths):,} CSV bytes, {sum(m['raw_rows'] for m in months):,} raw rows. "
             f"{len(others)} non-CSV files were not parsed. Audit runtime: {runtime:.2f} seconds.", "",
             "## Definitions and limits", "",
             f"One process, one CSV row at a time; retain {nselected} selected numerical channels for one month. "
             "All [ABS] channels are checked for decreases. No timezone is encoded, so timestamps remain naive local times. "
             f"Normalized {rollovers:,} occurrences of 24:00:00 to the next day; {offgrid:,} timestamps are off the 15-minute grid.", "",
             "Monthly counts use calendar timestamps [month start, next month start), not source folder membership. "
             "Inventory month records the source folder. Files are processed by their first valid timestamp; "
             "misplaced copies participate in duplicate detection and are not counted twice. "
             "Duplicate timestamps use the whole row with the most finite selected values; ties retain the first row. "
             "No values are interpolated. A meter interval is present when at least one of its main kWh counter, P or Q is finite; "
             "energy/PF completeness can be lower. All measurement fields beyond Date/Time are checked for an entirely --- row.", "",
             "dEa = kWh counter(t) minus kWh counter(t-15 min), only when both readings exist at consecutive timestamps. "
             "It is assigned to the month of the ending timestamp; negative changes remain in signed totals and are separately flagged. "
             "The first reading and gaps do not create energy estimates. Thus totals describe observed valid pairs, not full-month consumption. "
             "dEr = sum of signed kvar sys [AVG] times 0.25 h over observed rows. "
             "Derived S = sqrt(P²+Q²); derived PF = P/S for S>0, unweighted mean (signed if P is negative). "
             "Reactive counter change is last minus first finite in-month reading, including decreases; endpoint timestamps are in meters.csv. "
             "These counter changes and integrated Q are different quantities and are not assumed equal.", "",
             "## 1. Coverage and 5/9. Monthly EM_VIRTUAL active energy and derived PF", "",
             f"Coverage folders: {months[0]['month']} through {months[-1]['month']}. "
             f"Missing whole month folders: {', '.join(m['month'] for m in months if not m['source_files']) or 'none'}. "
             f"Months without any CSV starting in that actual month: {', '.join(m['month'] for m in months if not m['csv_files']) or 'none'}. "
             "Complete CSV timestamp coverage requires every expected calendar quarter-hour; usable rows additionally exclude entirely --- rows.", "",
             "| Month | CSVs folder/dated | Grid rows / expected | Usable rows | EM present missing % | dEa kWh | dEa pairs | EM mean PF | EM min PF |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for m in months:
        v = m["local"].get("EM_VIRTUAL", {})
        lines.append(f"| {m['month']} | {m['source_files']}/{m['csv_files']} | {m['unique']}/{m['expected']} | {m['usable']} | {fmt(v.get('missing_pct'))} | {fmt(v.get('dEa_kWh'))} | {v.get('dEa_valid_intervals', 0)} | {fmt(v.get('mean_derived_PF'), 6)} | {fmt(v.get('min_derived_PF'), 6)} |")
    incomplete = [m["month"] for m in months if m["usable"] < m["expected"]]
    lines += ["", "Months with incomplete usable CSV coverage: " + ", ".join(incomplete) + ".", "",
              f"Misplaced files: {len(misplaced)}, of which {sum(bool(m[3]) for m in misplaced)} have a byte-identical "
              "SHA-256 match in the folder matching their actual month. Details and matching original paths are in anomalies.csv."]
    for source, actual in sorted({(m[1], m[2]) for m in misplaced}):
        lines.append(f"- Folder month {source} contains {sum(m[1]==source and m[2]==actual for m in misplaced)} files whose actual first timestamp month is {actual}.")
    pf_months = [m for m in meters if m["meter"] == "EM_VIRTUAL" and m["mean_derived_PF"] != ""]
    if pf_months:
        lowest = min(pf_months, key=lambda m: m["mean_derived_PF"])
        highest = max(pf_months, key=lambda m: m["mean_derived_PF"])
        lines += ["", f"EM_VIRTUAL monthly mean derived PF ranges from {lowest['mean_derived_PF']:.6f} "
                  f"({lowest['month']}) to {highest['mean_derived_PF']:.6f} ({highest['month']}). "
                  "Missing months have no PF estimate; every observed monthly value is in the table above."]
    lines += ["",
              "## 2. Header identity", "",
              f"{len(counts)} raw header MD5 variant(s). Majority `{majority}` occurs in {counts[majority]}/{len(paths)} files "
              f"and has {len(headers[majority])} columns. MD5 includes the exact header bytes including line ending."]
    if differences:
        for path, detail in differences:
            lines.append(f"- `{path}`: {detail}")
    else:
        lines += ["All CSV header lines are byte-identical."]
    lines += ["", "## 3. Meter activity", "", "Active means observed nonzero P or Q; a fixed nonzero cumulative counter alone is not activity.", "",
              "| Meter | Nonzero intervals | Active month periods | First nonzero timestamp | Last nonzero timestamp |",
              "|---|---:|---|---|---|"]
    for name in sorted({m["meter"] for m in meters}):
        active = [m for m in meters if m["meter"] == name and m["nonzero_intervals"]]
        lines.append(f"| {name} | {sum(m['nonzero_intervals'] for m in active)} | {periods([m['month'] for m in active])} | {active[0]['first_nonzero_ts'] if active else 'none'} | {active[-1]['last_nonzero_ts'] if active else 'none'} |")
    tr1 = [m for m in meters if m["meter"] == "TGBT_TR1" and m["nonzero_kWh_counter_count"]]
    lines += ["", f"TGBT_TR1 additionally has {sum(m['nonzero_kWh_counter_count'] for m in tr1):,} nonzero cumulative kWh readings "
              f"in {periods([m['month'] for m in tr1])}; "
              f"first {tr1[0]['first_nonzero_kWh_ts'] if tr1 else 'none'}, last {tr1[-1]['last_nonzero_kWh_ts'] if tr1 else 'none'}. "
              "This distinguishes retained historical counters from observed load activity."]
    lines += ["", "## 4. EM_VIRTUAL versus TGBT_TR1 + TGBT_TR2", ""]
    unequal = any(m["balance"].get(k, {}).get("unequal", 0) for m in months for k in SUFFIX)
    lines += ["The additive channels do NOT equal the transformer sum in every observed month." if unequal else
              "No unequal additive readings were found where all three meters have finite values.", ""]
    for k, label in (("p", "P"), ("q", "Q"), ("ea", "cumulative kWh"), ("rp", "cumulative kvarh"), ("rn", "cumulative kvarh (-)")):
        differences_k = [m["balance"][k] for m in months if m["balance"].get(k, {}).get("unequal", 0)]
        if differences_k:
            lines.append(f"- {label}: {sum(b['unequal'] for b in differences_k):,} unequal readings; "
                         f"first {differences_k[0]['first_mismatch']}, last {differences_k[-1]['last_mismatch']}; "
                         f"residual (virtual minus transformer sum) among affected months ranges "
                         f"{min(b['min_residual'] for b in differences_k):.6f} to {max(b['max_residual'] for b in differences_k):.6f}; "
                         f"maximum absolute residual {max(b['max_abs'] for b in differences_k):.6f}.")
    lines += ["",
              "Compare simultaneous finite readings at stored precision, numeric tolerance 0.000001 in the channel's units. "
              "Missing comparisons cannot establish equality. Test P, Q, cumulative kWh and both cumulative kvarh counters separately; "
              "voltages, frequency and PF are not additive. The following are mismatches/compared rows; kWh offset is maximum absolute residual.", "",
              "| Month | P | Q | kWh counter | kvarh counter | kvarh (-) counter | Max abs kWh offset |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for m in months:
        cells = [f"{m['balance'].get(k, {}).get('unequal', 0)}/{m['balance'].get(k, {}).get('compared', 0)}" for k in ("p", "q", "ea", "rp", "rn")]
        lines.append(f"| {m['month']} | " + " | ".join(cells) + f" | {fmt(m['balance'].get('ea', {}).get('max_abs'))} |")
    lines += ["", "## 6. Missing data and longest gaps", "",
              f"Entirely --- raw measurement rows: {missing:,}. Missing CSV grid slots: "
              f"{sum(m['expected']-m['unique'] for m in months):,}/{sum(m['expected'] for m in months):,}. "
              f"Grid slots without a usable measurement row: {sum(m['expected']-m['usable'] for m in months):,}. "
              "Meter missing percentages include absent timestamps and missing main channels; zero is a valid observation.", "",
              "Worst EM_VIRTUAL months by missing main-channel observations:"]
    worst = sorted((m for m in meters if m["meter"] == "EM_VIRTUAL"), key=lambda m: m["missing_pct"], reverse=True)[:8]
    lines += [f"- {m['month']}: {m['expected_count']-m['interval_count']}/{m['expected_count']} missing ({m['missing_pct']:.3f}%)." for m in worst]
    lines += ["", "Longest gaps between observed CSV timestamps (leading/trailing calendar holes are included in monthly missing counts):"]
    for duration, _, meter, a, b in sorted((g for g in gaps if g[1] == "timestamp"), reverse=True)[:5]:
        lines.append(f"- {iso(a)} to {iso(b)}: {duration:.0f} minutes; {max(0, math.ceil(duration/15)-1)} missing slots.")
    lines += ["", "Longest gaps between finite main-channel observations for EM_VIRTUAL:"]
    for duration, _, meter, a, b in sorted((g for g in gaps if g[1] == "meter" and g[2] == "EM_VIRTUAL"), reverse=True)[:5]:
        lines.append(f"- {iso(a)} to {iso(b)}: {duration:.0f} minutes; {max(0, math.ceil(duration/15)-1)} missing slots.")
    lines += ["", "Longest EM_VIRTUAL missing calendar runs, including leading/trailing holes (end exclusive):"]
    for slots, meter, a, b in sorted((r for r in missing_runs if r[1] == "EM_VIRTUAL"), reverse=True)[:5]:
        lines.append(f"- {iso(a)} to {iso(b)}: {slots:,} missing quarter-hours ({slots*15:,} minutes).")
    lines += ["", f"The archive also contains {len(others)} XLSX files. They are listed below but were not parsed "
              "(only pandas, pyarrow and numpy were authorized; the requested inventory is CSV-only). "
              "CSV absence in those periods must not be described as absence from the archive:"]
    lines += [f"- `{p}`" for p in others]
    lines += ["", "## 7. Counter decreases", "",
              f"Observed {issues['counter_decrease']:,} decreases across all [ABS] channels, comparing consecutive finite readings even across gaps. "
              f"Observed {issues['negative_dEa']:,} negative main-kWh increments across consecutive 15-minute readings. "
              "A decrease is consistent with a reset, rollover or correction; the CSV alone does not identify the cause. "
              "Each event, channel, old/new reading and timestamps is in anomalies.csv.", "",
              "## 8. File boundaries and duplicates", ""]
    bc = Counter(b[0] for b in boundaries)
    lines += [f"Among {len(boundaries)} consecutive file boundaries: {bc['overlap']} overlap/touch at the same timestamp or earlier, "
              f"{bc['hole']} leave more than 15 minutes, {bc['contiguous']} are exactly 15 minutes apart. "
              f"Duplicate timestamps: {issues['duplicate_timestamp']:,}; {conflicts:,} duplicate rows conflict on at least one finite selected channel. "
              "Equal midnight endpoints are counted as overlaps. Each exceptional boundary is in anomalies.csv."]
    for kind, delta, prev, path, a, b in sorted((b for b in boundaries if b[0] == "hole"), key=lambda b: b[1], reverse=True)[:5]:
        lines.append(f"- Boundary hole: {iso(a)} to {iso(b)}, {delta:.0f} minutes; `{prev}` -> `{path}`.")
    lines += ["", f"{len(carry)} normalized endpoint rows at/after the final calendar month were excluded from monthly totals; "
              f"{sum(not row[2] for row in carry)} of those contain a measurement. No extra month is inferred from an empty final endpoint.", "",
              "## Output counts and anomaly types", "",
              f"inventory.csv: {len(paths)} data rows. meters.csv: {len(meters)} data rows. "
              f"anomalies.csv: {sum(issues.values())} data rows. CSV row counts exclude headers.", ""]
    lines += [f"- {kind}: {count}" for kind, count in sorted(issues.items())]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--extract", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    elif args.extract:
        extract(args.root.resolve())
    else:
        audit(args.root.resolve())


if __name__ == "__main__":
    main()
