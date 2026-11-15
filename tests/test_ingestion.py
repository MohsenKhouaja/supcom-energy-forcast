"""Synthetic policy tests plus explicit checks against the VM output artifacts."""

from pathlib import Path

import numpy as np
import json
import pandas as pd
import pyarrow.parquet as pq
import pytest

from smartgrid.data.derive import derive, clean_demand_registers
from smartgrid.data.impute import impute
from smartgrid.data.loader import CHANNELS, canonicalize, load_dataset, normalize_header, parse_timestamp
from smartgrid.data.windowing import eligible_target_origins
from smartgrid.evaluation.demand import demand_diagnostics

POLICY = {"short_gap_max_intervals": 4, "medium_gap_max_intervals": 96,
          "donor_lookback_weeks": 8, "split_boundaries": []}
ROOT = Path(__file__).resolve().parents[1]


def fixture(n=1800):
    index = pd.date_range("2024-01-01", periods=n, freq="15min", name="timestamp")
    return pd.DataFrame({"Ea_counter": 100+np.arange(n)*.5, "P_avg": 2., "Q_avg": -1.,
        "Er_pos_counter": 0., "Er_neg_counter": 50+np.arange(n)*.25,
        "P_dmd_max": 2.1, "S_dmd_max": np.sqrt(5)}, index=index)


def medium_fixture():
    frame = fixture()
    start, length = 800, 5
    stop = start+length
    frame.loc[frame.index[stop:], "Ea_counter"] += 3
    frame.loc[frame.index[stop:], "Er_neg_counter"] += 1.5
    frame.loc[frame.index[start:stop], list(CHANNELS)] = np.nan
    return frame, start, stop


def test_24_hour_rollover_and_leap_day():
    assert parse_timestamp("29-02-2024", "24:00:00") == pd.Timestamp("2024-03-01")
    assert parse_timestamp("31-12-2023", "24:00:00") == pd.Timestamp("2024-01-01")


def test_duplicate_collapse_and_explicit_grid():
    rows = pd.DataFrame({"timestamp": pd.to_datetime(["2024-01-01", "2024-01-01", "2024-01-01 00:30"], format="mixed"),
                         "Ea_counter": [1., 2., 3.], "_non_null": [1, 2, 2],
                         "source_filename": ["a", "b", "c"], "source_sheet": ["", "", ""]})
    result, stats = canonicalize(rows, ["Ea_counter"])
    assert len(result) == 3
    assert result.index.is_unique
    assert result["Ea_counter"].iloc[0] == 2
    assert pd.isna(result["Ea_counter"].iloc[1])
    assert stats["duplicates_dropped"] == 1
    assert stats["grid_slots_created"] == 1


def test_startup_cutoff_trims_observed_and_explicit_missing_slots():
    rows = pd.DataFrame({"timestamp": pd.to_datetime(["2022-06-30 23:30", "2022-07-01 00:00", "2022-07-01 00:30"]),
                         "Ea_counter": [1., 2., 3.], "_non_null": [1, 1, 1],
                         "source_filename": ["a", "b", "c"], "source_sheet": ["", "", ""]})
    result, stats = canonicalize(rows, ["Ea_counter"], canonical_start="2022-07-01 00:00")
    assert result.index[0] == pd.Timestamp("2022-07-01 00:00")
    assert stats["startup_grid_slots_dropped"] == 2
    assert stats["startup_observed_rows_dropped"] == 1
    assert result["Ea_counter"].isna().sum() == 1


def test_failed_demand_zeros_are_missing_but_idle_and_one_kva_zeros_remain():
    frame = pd.DataFrame({"S_avg": [0., 1., 1.0001, 295., 2., np.nan],
                          "P_dmd_max": [0., 0., 0., 5., 0., 0.],
                          "S_dmd_max": [0., 0., 9., 0., 0., 0.], "is_imputed": False})
    cleaned, counts = clean_demand_registers(frame)
    assert counts == {"P_dmd_max": 2, "S_dmd_max": 2}
    assert cleaned["P_dmd_max"].isna().tolist() == [False, False, True, False, True, False]
    assert cleaned["S_dmd_max"].isna().tolist() == [False, False, False, True, True, False]
    assert cleaned.loc[0, ["P_dmd_max", "S_dmd_max"]].eq(0).all()
    assert not cleaned["is_imputed"].any()
    assert not frame["P_dmd_max"].isna().any()  # Input is preserved.


def test_named_csv_selection_with_reordered_columns(tmp_path):
    import csv
    header = ["M " + suffix for suffix in reversed(list(CHANNELS.values()))] + ["Time", "Date"]
    values = {"M " + suffix: i+1 for i, suffix in enumerate(CHANNELS.values())}
    values.update({"Time": "00:00:00", "Date": "01-01-2024"})
    (tmp_path/"raw").mkdir()
    with (tmp_path/"raw/input.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header, delimiter=";")
        writer.writeheader()
        writer.writerow(values)
    loaded = load_dataset(tmp_path, ["raw"], expected_meter_count=1)
    assert loaded.frame["M kWh (kWh) [ABS]"].iloc[0] == 1
    assert loaded.frame["M kvarh (kvarh) [ABS]"].iloc[0] == 5
    with pytest.raises(ValueError, match="CSV HEADER MISMATCH"):
        load_dataset(tmp_path, ["raw"], expected_meter_count=1, expected_header_md5="different")


def test_xlsx_export_suffix_normalization_is_name_based():
    assert normalize_header(["Date", "M kWh (kWh) [ABS] 137"], xlsx=True) == ["Date", "M kWh (kWh) [ABS]"]


def test_short_gap_and_long_gap():
    raw = fixture()
    raw.loc[raw.index[100:103], ["Ea_counter", "P_avg", "Q_avg"]] = np.nan
    raw.loc[raw.index[300:500], ["Ea_counter", "P_avg", "Q_avg"]] = np.nan
    out, _, _ = impute(raw, POLICY)
    assert out.loc[raw.index[100:103], ["Ea_counter", "P_avg", "Q_avg"]].notna().all().all()
    assert out["is_imputed"].iloc[100:104].all()
    assert out.loc[raw.index[300:500], ["Ea_counter", "P_avg", "Q_avg"]].isna().all().all()
    assert not out["is_imputed"].iloc[300:500].any()
    assert pd.isna(out["dEa"].iloc[500])


def test_medium_gap_has_L_plus_one_flagged_increments_and_conserves_energy():
    raw, start, stop = medium_fixture()
    c0, c1 = raw["Ea_counter"].iloc[start-1], raw["Ea_counter"].iloc[stop]
    q_total = (raw["Er_pos_counter"].iloc[stop]-raw["Er_pos_counter"].iloc[start-1]
               - raw["Er_neg_counter"].iloc[stop]+raw["Er_neg_counter"].iloc[start-1])
    out, _, logs = impute(raw, POLICY)
    increments = out["dEa"].iloc[start:stop+1]
    assert len(increments) == stop-start+1
    assert increments.notna().all()
    assert (increments > 0).all()  # This donor has no zero increments and total>0.
    assert out["is_imputed"].iloc[start:stop+1].all()
    assert out["is_imputed"].sum() == stop-start+1
    assert increments.sum() == pytest.approx(c1-c0)
    assert out["dEr"].iloc[start:stop+1].sum() == pytest.approx(q_total)
    assert out["Ea_counter"].iloc[start-1] == c0
    assert out["Ea_counter"].iloc[stop] == c1
    assert logs[0]["method"] == "scaled_weekday"
    assert logs[0]["k"] == pytest.approx(2)
    assert out["Q_avg"].iloc[start:stop+1].lt(0).all()


def test_both_reactive_counters_and_independent_PF_scale_warnings():
    raw, start, stop = medium_fixture()
    raw.loc[raw.index[stop:], "Ea_counter"] -= 1.5  # k=1.5
    raw.loc[raw.index[stop:], "Er_pos_counter"] += 1.5
    raw.loc[raw.index[stop:], "Er_neg_counter"] += 4.5  # net target -6, k_q=4
    out, _, logs = impute(raw, POLICY)
    observed_total = ((raw["Er_pos_counter"]-raw["Er_neg_counter"]).iloc[stop]
                      -(raw["Er_pos_counter"]-raw["Er_neg_counter"]).iloc[start-1])
    assert out["dEr"].iloc[start:stop+1].sum() == pytest.approx(observed_total)
    assert logs[0]["kq_over_k"] == pytest.approx(logs[0]["k_q"]/logs[0]["k"])
    assert "k_q/k outside [0.8, 1.25]" in logs[0]["warnings"]
    assert "PF outside observed surrounding-month range" in logs[0]["warnings"]


def test_uniform_fallback_and_no_imputed_donor():
    raw, start, stop = medium_fixture()
    raw["is_imputed"] = False
    raw.loc[raw.index[start-672-1:stop-672+1], "is_imputed"] = True
    out, _, logs = impute(raw, POLICY)
    assert logs[0]["method"] == "uniform"
    assert logs[0]["reactive_method"] == "uniform"
    assert logs[0]["donor_date"] == ""
    assert np.ptp(out["dEa"].iloc[start:stop+1].to_numpy()) < 1e-9


def test_nearest_earlier_wholly_observed_donor():
    raw = fixture(2400)
    start, stop = 1700, 1705
    raw.loc[raw.index[start:stop], list(CHANNELS)] = np.nan
    raw.loc[raw.index[start-672], "P_avg"] = np.nan
    _, _, logs = impute(raw, POLICY)
    selected = next(g for g in logs if g["start"] == str(raw.index[start]))
    assert selected["donor_date"] == str(raw.index[start-2*672].date())


def test_donor_search_never_exceeds_eight_weeks():
    raw = fixture(7200)
    start, stop = 7000, 7005
    raw.loc[raw.index[start:stop], list(CHANNELS)] = np.nan
    for week in range(1, 9):
        raw.loc[raw.index[start-week*672], "P_avg"] = np.nan
    _, _, logs = impute(raw, POLICY)
    selected = next(g for g in logs if g["start"] == str(raw.index[start]))
    assert selected["method"] == "uniform"
    assert selected["donor_date"] == ""


def test_unbounded_gaps_stay_nan_and_short_gap_cannot_cross_day():
    raw = fixture()
    for interval in (slice(0, 3), slice(95, 98), slice(len(raw)-3, len(raw))):
        raw.loc[raw.index[interval], ["Ea_counter", "P_avg", "Q_avg"]] = np.nan
    out, _, _ = impute(raw, POLICY)
    for interval in (slice(0, 3), slice(95, 98), slice(len(raw)-3, len(raw))):
        assert out["Ea_counter"].iloc[interval].isna().all()
        assert not out["is_imputed"].iloc[interval].any()


def test_no_read_across_explicit_split_boundary():
    raw, start, stop = medium_fixture()
    policy = {**POLICY, "split_boundaries": [str(raw.index[start+2])]}
    out, stats, _ = impute(raw, policy)
    assert out["Ea_counter"].iloc[start:stop].isna().all()
    assert stats["unfilled_reasons"]["split_boundary"] == 1


def test_derived_energy_does_not_bridge_a_missing_grid_slot():
    raw = fixture(10)
    raw.loc[raw.index[4], "Ea_counter"] = np.nan
    out = derive(raw)
    assert out["dEa"].iloc[4:6].isna().all()


def test_H96_targets_exclude_every_imputed_label_including_closing_increment():
    flags = pd.Series(False, index=pd.date_range("2024-01-01", periods=300, freq="15min"))
    flags.iloc[100:106] = True
    mask = eligible_target_origins(flags, 96)
    assert not mask.iloc[4:105].any()
    assert mask.iloc[105]  # The closing imputed row may be an INPUT, not a label.
    assert not mask.iloc[-96:].any()
    assert mask.iloc[3]  # t+96 ends just before the first imputed row.


@pytest.fixture(scope="module")
def output():
    path = ROOT/"data/processed/em_virtual.parquet"
    if not path.exists():
        pytest.skip("VM ingestion output required for real-data checks")
    return pd.read_parquet(path).set_index("timestamp")


@pytest.fixture(scope="module")
def all_output():
    path = ROOT/"data/processed/all_meters.parquet"
    if not path.exists():
        pytest.skip("VM ingestion output required for real-data checks")
    data = pd.read_parquet(path, columns=["timestamp", "meter", "Ea_counter", "dEa", "P_avg", "Q_avg", "dEr", "S_avg", "PF", "P_dmd_max", "S_dmd_max", "is_imputed"])
    return {meter: group.drop(columns="meter").set_index("timestamp") for meter, group in data.groupby("meter", sort=False)}


def test_output_has_no_duplicate_timestamps_and_requested_columns(output):
    assert output.index.is_unique
    assert list(output.columns) == ["Ea_counter", "dEa", "P_avg", "Q_avg", "dEr", "S_avg", "PF", "P_dmd_max", "S_dmd_max", "is_imputed"]


def test_output_complete_strictly_increasing_grid(all_output):
    for output in all_output.values():
        assert output.index[0] == pd.Timestamp("2022-07-01 00:00")
        assert output.index.is_monotonic_increasing
        assert output.index.equals(pd.date_range(output.index[0], output.index[-1], freq="15min", name="timestamp"))


def test_observed_counter_never_decreases(all_output):
    for meter, output in all_output.items():
        observed = ~output["is_imputed"] & ~output["is_imputed"].shift(1, fill_value=True)
        assert not output["Ea_counter"].diff().loc[observed].lt(-1e-8).any(), meter
        assert not output["Ea_counter"].diff().lt(-1e-8).any(), meter


def test_dEa_stays_nan_after_a_missing_unimputed_slot(all_output):
    raw = pd.read_parquet(ROOT/"cache/ingestion/raw_selected.parquet", columns=[f"{m} kWh (kWh) [ABS]" for m in all_output])
    for meter, output in all_output.items():
        originally_missing_previous = raw[f"{meter} kWh (kWh) [ABS]"].shift().isna()
        not_imputed_previous = ~output["is_imputed"].shift(1, fill_value=False)
        assert output.loc[originally_missing_previous & not_imputed_previous, "dEa"].isna().all(), meter


def test_no_growing_odometer_column_except_counters(all_output):
    # Constants are not growing odometers; empty channels carry no evidence.
    for meter, output in all_output.items():
        for col in ["dEa", "P_avg", "Q_avg", "dEr", "S_avg", "PF", "P_dmd_max", "S_dmd_max"]:
            changes = output[col].dropna().diff().dropna()
            assert not (len(changes) and changes.ge(-1e-10).all() and changes.gt(1e-10).any()), f"{meter} {col} grows monotonically like a counter"


def test_apparent_power_bound(all_output):
    for meter, output in all_output.items():
        good = output[["S_avg", "P_avg"]].notna().all(axis=1)
        assert output.loc[good, "S_avg"].ge(output.loc[good, "P_avg"].abs()-1e-10).all(), meter


def test_power_factor_bounds(all_output):
    for meter, output in all_output.items():
        assert output["PF"].dropna().between(-1, 1).all(), meter


def test_output_has_no_failed_zero_demand_registers_under_load(all_output):
    for meter, output in all_output.items():
        loaded = output["S_avg"] > 1.0
        for column in ("P_dmd_max", "S_dmd_max"):
            assert not output.loc[loaded, column].eq(0).any(), (meter, column)


@pytest.fixture(scope="module")
def demand_results(all_output):
    return {meter: demand_diagnostics(frame, meter) for meter, frame in all_output.items()}


def test_high_load_median_demand_deviation_below_10_percent(demand_results):
    failures = {meter: {"median_deviation": stats["high_quartile_median_relative"], "rows": stats["high_quartile_relative_rows"]}
                for meter, (stats, _) in demand_results.items()
                if not stats["high_quartile_median_relative"] < .10}
    assert not failures, f"For S_avg > meter P75, median relative deviation must be <0.10; {failures}"


def test_demand_diagnostics_exclude_imputed_rows_and_separate_quartile_from_halves():
    index = pd.date_range("2024-01-01", periods=101, freq="15min", name="timestamp")
    s = np.arange(1., 102.)
    frame = pd.DataFrame({"S_avg": s, "S_dmd_max": s*1.05, "is_imputed": False}, index=index)
    frame.loc[index[-1], ["S_avg", "S_dmd_max", "is_imputed"]] = [1e9, -1e9, True]
    frame.loc[index[0], "S_dmd_max"] = .9
    stats, failed = demand_diagnostics(frame, "synthetic")
    assert stats["comparable_rows"] == 100
    assert stats["invariant_fraction"] == pytest.approx(.99)
    assert failed["timestamp"].tolist() == [index[0]]
    assert stats["p75_load_kVA"] == pytest.approx(75.25)
    assert stats["high_quartile_rows"] == 25
    assert stats["low_half_rows"] == stats["high_half_rows"] == 50
    assert stats["high_half_median_relative"] == pytest.approx(.05/1.05)
    assert stats["high_half_p90_relative"] == pytest.approx(.05/1.05)


def test_zero_demand_ratios_and_idle_load_ties_are_explicit():
    index = pd.date_range("2024-01-01", periods=5, freq="15min", name="timestamp")
    frame = pd.DataFrame({"S_avg": [0., 0., 0., 1., 2.], "S_dmd_max": [0., 0., 0., .99, 1.98], "is_imputed": False}, index=index)
    stats, failed = demand_diagnostics(frame, "idle")
    assert stats["comparable_rows"] == 5
    assert stats["zero_demand_rows"] == 3
    assert stats["low_half_rows"] == 3
    assert stats["low_half_relative_rows"] == 0
    assert np.isnan(stats["low_half_median_relative"])
    assert len(failed) == 1
    assert failed["timestamp"].iloc[0] == index[-1]


def test_all_real_medium_gap_energy_totals_and_closing_flags(all_output):
    metadata = pq.ParquetFile(ROOT/"data/processed/em_virtual.parquet").schema_arrow.metadata
    gaps = json.loads(metadata[b"supcom.imputation_gaps"])
    checked = 0
    for gap in gaps:
        if gap["method"] == "unfilled":
            continue
        frame = all_output[gap["meter"]]
        start = pd.Timestamp(gap["start"])
        close = start+pd.Timedelta(minutes=15*gap["length"])
        span = frame.loc[start:close]
        assert len(span) == gap["length"]+1
        assert span["is_imputed"].all()
        assert span["dEa"].sum() == pytest.approx(gap["active_total_kWh"], abs=1e-7)
        assert span["dEr"].sum() == pytest.approx(gap["net_reactive_total_kvarh"], abs=1e-7)
        checked += 1
    assert checked > 0


def test_long_format_grid_and_provenance():
    path = ROOT/"data/processed/all_meters.parquet"
    if not path.exists():
        pytest.skip("VM ingestion output required")
    table = pq.read_table(path, columns=["timestamp", "meter"])
    data = table.to_pandas()
    assert not data.duplicated(["timestamp", "meter"]).any()
    assert data["meter"].nunique() == 14
    sizes = data.groupby("timestamp").size()
    assert sizes.eq(14).all()
    assert data.equals(data.sort_values(["timestamp", "meter"], ignore_index=True))
    for _, group in data.groupby("meter"):
        index = pd.DatetimeIndex(group["timestamp"])
        assert (index[1:]-index[:-1] == pd.Timedelta(minutes=15)).all()
    assert "source_filename" in pq.ParquetFile(path).schema.names
    metadata = pq.ParquetFile(ROOT/"data/processed/em_virtual.parquet").schema_arrow.metadata
    assert b"supcom.source_provenance_runs" in metadata
