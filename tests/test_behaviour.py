"""Synthetic-only EDA tests: no real files, Parquets, ingestion or windows."""

import numpy as np
import pandas as pd
import pytest

from smartgrid.features.behaviour import (
    autocorrelation, base_load, cumulative_energy, demand_divergence, load_duration,
    meter_contributions, peak_demand, power_comparisons, power_factor,
    provisional_vacation_weeks, seasonality, site_behaviour, split_coverage,
    weekday_weekend,
)


def synthetic(days=28, start="2022-07-04"):
    index = pd.date_range(start, periods=days*96, freq="15min", name="timestamp")
    daytime = (index.hour >= 8) & (index.hour < 18)
    p = 10+np.asarray(daytime, float)*np.where(index.day_of_week < 5, 20, 3)
    q = -p/4
    return pd.DataFrame({"P_avg": p, "Q_avg": q, "S_avg": np.hypot(p, q),
                         "dEa": p*.25, "dEr": q*.25, "PF": p/np.hypot(p,q),
                         "S_dmd_max": np.hypot(p,q)*1.02, "is_imputed": False}, index=index)


def test_peak_duration_is_consecutive_not_sum_of_disconnected_bands():
    data = synthetic(1).iloc[:7].copy()
    data["P_avg"] = [100., 95., 0., 95., 96., 100., 0.]
    data["S_avg"] = data.P_avg
    daily = peak_demand(data).tables["daily"].iloc[0]
    assert daily.P_maximum == 100
    assert daily.P_duration_intervals == 3
    assert daily.P_duration_hours == .75
    assert daily.P_time == data.index[0]


def test_imputed_interval_and_timestamp_hole_break_peak_runs():
    data = synthetic(1).iloc[:5].copy()
    data[["P_avg", "S_avg"]] = 100.
    data.loc[data.index[2], "is_imputed"] = True
    assert peak_demand(data).tables["daily"].iloc[0].P_duration_intervals == 2
    data = data.drop(data.index[2])
    assert peak_demand(data).tables["daily"].iloc[0].P_duration_intervals == 2


def test_entirely_imputed_day_has_undefined_peak_duration_not_zero():
    data = synthetic(1)
    data["is_imputed"] = True
    result = peak_demand(data).tables["daily"].iloc[0]
    assert pd.isna(result.P_maximum)
    assert pd.isna(result.P_duration_intervals)
    assert result.observed_intervals == 0
    assert result.excluded_imputed == 96


def test_flat_day_has_none_activation_and_deactivation():
    data = synthetic(1)
    data["P_avg"] = 10.
    result = site_behaviour(data).tables["daily"].iloc[0]
    assert result.activation is None
    assert result.deactivation is None


def test_activity_uses_first_and_last_observed_15x_minimum_crossing():
    data = synthetic(1).iloc[:6].copy()
    data["P_avg"] = [10., 16., 20., 14., 16., 10.]
    data.loc[data.index[1], "is_imputed"] = True
    result = site_behaviour(data).tables["daily"].iloc[0]
    assert result.activation == data.index[2]
    assert result.deactivation == data.index[4]


def test_saturday_sunday_are_weekend_and_friday_monday_are_weekday():
    index = pd.to_datetime(["2024-01-05", "2024-01-06", "2024-01-07", "2024-01-08"])
    assert weekday_weekend(index).tolist() == ["Weekday", "Weekend", "Weekend", "Weekday"]


def test_PROVISIONAL_flat_week_is_flagged_but_normal_week_is_not():
    flat = synthetic(7, "2024-01-01")
    flat["P_avg"] = 10.
    normal = flat.copy()
    normal.loc[normal.index.day_of_week < 5, "P_avg"] = 30.
    assert provisional_vacation_weeks(flat).tables["weeks"].iloc[0].PROVISIONAL_vacation_like == True
    assert provisional_vacation_weeks(normal).tables["weeks"].iloc[0].PROVISIONAL_vacation_like == False
    assert "Vacation-like PROVISIONAL" in power_comparisons(flat).tables["academic_PROXY_PROVISIONAL"].index
    assert "Term-like PROVISIONAL" in power_comparisons(normal).tables["academic_PROXY_PROVISIONAL"].index


def test_PROVISIONAL_week_rule_inclusive_20_percent_boundary():
    data = synthetic(7, "2024-01-01")
    data["P_avg"] = np.where(data.index.day_of_week < 5, 12., 10.)
    assert provisional_vacation_weeks(data).tables["weeks"].iloc[0].PROVISIONAL_vacation_like == True


FUNCTIONS = [cumulative_energy, base_load, peak_demand, power_comparisons, site_behaviour,
             provisional_vacation_weeks, seasonality, autocorrelation, power_factor,
             load_duration, demand_divergence, split_coverage]


@pytest.mark.parametrize("function", FUNCTIONS, ids=[f.__name__ for f in FUNCTIONS])
def test_every_parameter_ignores_imputed_measurements(function):
    data = synthetic()
    excluded = data.index[[3, 100, 500, 1500]]
    data.loc[excluded, "is_imputed"] = True
    corrupted = data.copy()
    columns = corrupted.select_dtypes(include="number").columns
    corrupted.loc[excluded, columns] = 1e12
    before, after = function(data), function(corrupted)
    assert before.excluded_imputed == after.excluded_imputed == 4
    assert before.missing_observed == after.missing_observed
    for name in before.tables:
        pd.testing.assert_frame_equal(before.tables[name], after.tables[name])
    assert before.findings == after.findings


def test_meter_contribution_ignores_imputed_measurements():
    site = synthetic()
    site.loc[site.index[[100, 1000]], "is_imputed"] = True
    long = site.reset_index().assign(meter="A")
    changed = long.copy()
    changed.loc[changed.is_imputed, ["dEa", "P_avg"]] = 1e12
    before, after = meter_contributions(site, long), meter_contributions(site, changed)
    for name in before.tables:
        pd.testing.assert_frame_equal(before.tables[name], after.tables[name])
    assert before.excluded_imputed == after.excluded_imputed == 2


def test_acf_keeps_original_lag_positions_and_reports_pair_exclusions():
    data = synthetic(1).iloc[:7].copy()
    data["dEa"] = [1., 4., 2., 9., 3., 8., 5.]
    data.loc[data.index[2], "is_imputed"] = True
    actual = autocorrelation(data, max_lag=1).tables["lags"].loc[1]
    expected = np.corrcoef([1., 9., 3., 8.], [4., 3., 8., 5.])[0, 1]
    assert actual.observed_pairs == 4
    assert actual.excluded_imputed_pairs == 2
    assert actual.correlation == pytest.approx(expected)


def test_observed_energy_sums_match_every_temporal_scale():
    data = synthetic()
    data.loc[data.index[[0, 500]], "is_imputed"] = True
    result = cumulative_energy(data)
    expected = data.loc[~data.is_imputed, "dEa"].sum()
    for name in ("daily", "weekly", "monthly", "annual"):
        assert result.tables[name].energy_kWh.sum() == pytest.approx(expected)
        assert result.tables[name].excluded_imputed.sum() == 2


def test_split_counts_require_observed_labels_and_do_not_create_windows():
    data = synthetic(14)
    baseline = split_coverage(data).tables["splits"].loc["train"]
    data.loc[data.index[800], "is_imputed"] = True
    changed = split_coverage(data).tables["splits"].loc["train"]
    assert changed.eligible_origins_prior_context < baseline.eligible_origins_prior_context
    assert changed.excluded_imputed == 1
    assert changed.eligible_origins_prior_context == changed.eligible_origins_strict_context
