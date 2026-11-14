"""Synthetic window/calendar/scaler fixtures; never read the real dataset."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from smartgrid.data.scaling import ElectricalScaler, fit_electrical_scaler, scaler_fit_coverage
from smartgrid.data.impute import impute
from smartgrid.data.windows import LazyWindows, eligible_origins, from_processed, split_ranges, touched_train_rows, torch_dataset, window_at
from smartgrid.features.calendar import academic_periods, tunisian_holidays, vacation_mask, vacation_load_comparison, winter_weekday_profile
from smartgrid.features.calendar_features import CALENDAR, ELECTRICAL, FEATURES, calendar_features, feature_table

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def calendar_config():
    return json.loads((ROOT/"configs/calendar.yaml").read_text(encoding="utf-8"))


@pytest.fixture
def fixture():
    index = pd.date_range("2024-01-01", periods=20*96, freq="15min", name="timestamp")
    table = pd.DataFrame(np.arange(len(index)*11).reshape(-1,11), columns=FEATURES, index=index, dtype=np.float32)
    flags = pd.Series(False, index=index)
    config = dict(context=672, horizon=96, splits=dict(
        train=dict(start="2024-01-01",end="2024-01-12"),
        val=dict(start="2024-01-13",end="2024-01-16"),
        test=dict(start="2024-01-17",end="2024-01-20")))
    return table, flags, config


def test_exact_shapes_alignment_and_views(fixture):
    table, flags, config = fixture
    origins = eligible_origins(table, flags, config)
    values = table.to_numpy()
    x,y = window_at(values, origins["train"][0])
    assert x.shape == (672,11) and y.shape == (96,4)
    np.testing.assert_array_equal(x[-1], values[671])
    np.testing.assert_array_equal(y[0], values[672,:4])
    assert table.index[672]-table.index[671] == pd.Timedelta(minutes=15)
    assert np.shares_memory(x,values) and np.shares_memory(y,values)
    assert not x.flags.writeable and not y.flags.writeable


def test_hand_computed_counts_and_target_boundaries(fixture):
    table, flags, config = fixture
    origins = eligible_origins(table,flags,config)
    assert {name:len(o) for name,o in origins.items()} == dict(train=385,val=289,test=289)
    assert origins["train"][0] == 671
    assert origins["val"][0] == 1151  # first target is the split's first row
    for name,(start,end) in split_ranges(config).items():
        for origin in origins[name]:
            target = table.index[origin+1:origin+97]
            assert len(target) == 96 and target.min() >= start and target.max() < end


def test_no_imputed_targets_but_imputed_inputs_allowed(fixture):
    table, flags, config = fixture
    flags.iloc[800] = True
    origins = eligible_origins(table,flags,config)
    assert len(origins["train"]) == 385-96
    assert 800 in origins["train"]  # imputed LAST input is permitted
    for positions in origins.values():
        for origin in positions:
            assert not flags.iloc[origin+1:origin+97].any()


def test_nonfinite_inputs_and_targets_excluded(fixture):
    table, flags, config = fixture
    table.iloc[800,0] = np.nan
    origins = eligible_origins(table, flags, config)
    for positions in origins.values():
        for origin in positions:
            assert np.isfinite(table.iloc[origin-671:origin+97].to_numpy()).all()


def test_missing_timestamp_fails_instead_of_compressing_grid(fixture):
    table,flags,config = fixture
    with pytest.raises(ValueError,match="consecutive"):
        eligible_origins(table.drop(table.index[100]), flags.drop(flags.index[100]), config)


def test_flags_must_align(fixture):
    table,flags,config = fixture
    with pytest.raises(ValueError,match="align"):
        eligible_origins(table,flags.iloc[::-1],config)


def test_fit_includes_unique_input_and_target_rows_only_in_train(fixture):
    table, flags, config = fixture
    origins = eligible_origins(table,flags,config)
    scaler,mask,coverage = fit_electrical_scaler(table,origins["train"],config)
    assert mask[:1152].all() and not mask[1152:].any()
    assert coverage["excluded_rows"] == 0 and scaler.n_rows == 1152
    # The last 96 training rows appear only as targets, but MUST be in the fit.
    assert mask[origins["train"][-1]+1:1152].all()
    np.testing.assert_allclose(scaler.mean,table.iloc[:1152,:4].mean().to_numpy(),rtol=1e-6)
    table.iloc[1152:,:4] = 1e9
    again,_,_ = fit_electrical_scaler(table,origins["train"],config)
    np.testing.assert_array_equal(scaler.mean,again.mean)


def test_fit_unique_rows_not_overlap_weighted_and_reports_exclusions(fixture):
    table,flags,config = fixture
    origins = np.array([700,800])
    mask, coverage = scaler_fit_coverage(table,origins,config)
    expected = np.zeros(len(table),bool)
    expected[29:897] = True
    np.testing.assert_array_equal(mask,expected)
    assert coverage["excluded_rows"] == 1152-868
    scaler,_,_ = fit_electrical_scaler(table,origins,config)
    np.testing.assert_allclose(scaler.mean,table.iloc[29:897,:4].to_numpy(dtype=float).mean(axis=0))


def test_scaler_rejects_validation_origins(fixture):
    table,flags,config = fixture
    with pytest.raises(ValueError,match="Non-training"):
        touched_train_rows(table.index,eligible_origins(table,flags,config)["val"],config)


def test_calendar_passes_through_and_scaler_json_roundtrip(fixture,tmp_path):
    table,flags,config = fixture
    scaler,_,_ = fit_electrical_scaler(table,eligible_origins(table,flags,config)["train"],config)
    transformed = scaler.transform(table.to_numpy())
    np.testing.assert_array_equal(transformed[:,4:],table.to_numpy()[:,4:])
    np.testing.assert_allclose(scaler.inverse_electrical(transformed[:,:4]),table.to_numpy()[:,:4],rtol=1e-5,atol=.01)
    path = tmp_path/"scaler.json"
    scaler.save(path)
    restored = ElectricalScaler.load(path)
    np.testing.assert_array_equal(restored.transform(table.to_numpy()),transformed)
    assert json.loads(path.read_text())["calendar_scaled"] is False


def test_constant_channel_uses_unit_scale(fixture):
    table, flags, config = fixture
    table["dEr"] = 7.
    scaler,_,_ = fit_electrical_scaler(table,eligible_origins(table,flags,config)["train"],config)
    assert scaler.std[1] == 0 and scaler.scale[1] == 1


def test_midnight_cyclic_distance(calendar_config):
    index = pd.DatetimeIndex(["2024-02-01 23:45","2024-02-02 00:00"])
    features = calendar_features(index,calendar_config)
    distance = np.linalg.norm(features.loc[:,["hour_sin","hour_cos"]].to_numpy()[0]-features.loc[:,["hour_sin","hour_cos"]].to_numpy()[1])
    assert 0 < distance < .07
    assert tuple(features.columns) == CALENDAR
    assert np.abs(features.to_numpy()).max() <= 1


def test_tunisian_holiday_vacation_weekend_and_term_day(calendar_config):
    index = pd.DatetimeIndex(["2024-03-20","2024-04-02","2024-02-03","2024-02-06"])
    assert "Independence" in tunisian_holidays(calendar_config)[index[0].date()]
    assert calendar_features(index,calendar_config).is_non_working_day.tolist() == [1,1,1,0]


def test_winter_rule_is_configurable_and_exams_not_vacation(calendar_config):
    periods = academic_periods(calendar_config)
    winter = periods.query("academic_year == '2023/2024' and period == 'vacances hiver'").iloc[0]
    assert winter.start == pd.Timestamp("2023-12-25") and winter.end == pd.Timestamp("2024-01-07")
    assert not vacation_mask(pd.DatetimeIndex(["2024-01-09"]),periods)[0]
    calendar_config["winter_vacation"]["weeks_before"] = 1
    changed = academic_periods(calendar_config)
    assert vacation_mask(pd.DatetimeIndex(["2023-12-18"]),changed)[0]
    assert not vacation_mask(pd.DatetimeIndex(["2023-12-18"]),periods)[0]


def test_initial_summer_is_covered_without_extending_july_first(calendar_config):
    features = calendar_features(pd.DatetimeIndex(["2022-07-04","2022-07-11"]),calendar_config)
    assert features.is_non_working_day.tolist() == [0,1]


def test_calendar_reports_ignore_imputed_rows(calendar_config):
    index = pd.date_range("2023-12-01", "2024-01-31 23:45", freq="15min")
    frame = pd.DataFrame(dict(P_avg=10.,is_imputed=False), index=index)
    frame.loc["2023-12-26", "is_imputed"] = True
    before = winter_weekday_profile(frame,[2023])
    frame.loc[frame.is_imputed,"P_avg"] = 1e9
    pd.testing.assert_frame_equal(before,winter_weekday_profile(frame,[2023]))
    comparison = vacation_load_comparison(frame,academic_periods(calendar_config),tunisian_holidays(calendar_config))
    values = comparison.filter(like="mean_kW").stack().dropna()
    assert values.eq(10).all()


def test_persisted_lazy_loader_uses_memmap(fixture,tmp_path):
    table,flags,config = fixture
    origins = eligible_origins(table,flags,config)["train"]
    np.save(tmp_path/"features.npy",table.to_numpy(),allow_pickle=False)
    pd.DataFrame(dict(origin_index=origins)).to_parquet(tmp_path/"train_origins.parquet")
    (tmp_path/"features.json").write_text(json.dumps(dict(features=FEATURES,context=672,horizon=96,
        origin_files=dict(train="train_origins.parquet"))))
    windows = from_processed(tmp_path,"train")
    assert np.shares_memory(windows.values,windows.values.base)
    assert len(windows) == 385
    assert windows[0][0].shape == (672,11)


@pytest.fixture
def raw_counter_fixture():
    index = pd.date_range("2024-08-25", periods=14*96, freq="15min", name="timestamp").as_unit("ns")
    n = len(index)
    frame = pd.DataFrame(dict(Ea_counter=np.arange(n,dtype=float)*2, P_avg=8., Q_avg=-4.,
        Er_pos_counter=0., Er_neg_counter=np.arange(n,dtype=float)), index=index)
    policy = dict(short_gap_max_intervals=4,medium_gap_max_intervals=96,donor_lookback_weeks=8,
        split_boundaries=["2024-09-01"])
    return frame,policy


def test_reimputation_never_anchors_across_split_with_mixed_timestamp_units(raw_counter_fixture):
    frame,policy = raw_counter_fixture
    frame.loc["2024-08-31 23:45",["Ea_counter","P_avg","Q_avg"]] = np.nan
    filled,stats,_ = impute(frame,policy)
    assert pd.isna(filled.loc["2024-08-31 23:45","P_avg"])
    assert stats["unfilled_reasons"]["split_boundary"] == 1


def test_reimputation_prior_partition_donor_falls_back_to_uniform(raw_counter_fixture):
    frame,policy = raw_counter_fixture
    frame.loc["2024-09-02 10:00":"2024-09-02 11:00",["Ea_counter","P_avg","Q_avg"]] = np.nan
    _,_,unbounded = impute(frame,{**policy,"split_boundaries":[]})
    _,_,bounded = impute(frame,policy)
    assert unbounded[0]["method"] == "scaled_weekday"
    assert bounded[0]["method"] == "uniform" and bounded[0]["donor_date"] == ""


@pytest.mark.skipif(importlib.util.find_spec("torch") is None, reason="Torch not installed; only holidays/scikit-learn additions authorized")
def test_optional_torch_dataset_cpu_and_lazy(fixture):
    from torch.utils.data import Dataset
    table,flags,config = fixture
    dataset = torch_dataset(LazyWindows(table.to_numpy(),eligible_origins(table,flags,config)["train"]))
    assert isinstance(dataset,Dataset)
    x,y = dataset[0]
    assert tuple(x.shape) == (672,11) and tuple(y.shape) == (96,4)
    assert x.device.type == y.device.type == "cpu"
