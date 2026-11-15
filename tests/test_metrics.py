"""Synthetic-only checks for forecast alignment and physical-unit evaluation."""

import csv

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

from smartgrid.evaluation.benchmark import breakdown_metrics, predict_physical, timed_fit, write_predictions
from smartgrid.evaluation.metrics import BENCHMARK_COLUMNS, append_records, evaluate, inverse_predictions, normalize_electrical
from smartgrid.models.baselines import Persistence, SeasonalNaiveDaily, SeasonalNaiveWeekly


@pytest.fixture
def actual():
    energy = np.tile(np.linspace(1,4,96),(3,1))
    reactive = energy/3
    return np.stack([energy,reactive,4*energy,np.hypot(4*energy,4*reactive)],axis=-1)


@pytest.fixture
def scaler():
    return dict(channels=["dEa","dEr","P_avg","S_avg"],mean=[10.,-3.,40.,43.],scale=[2.,3.,8.,9.])


def test_perfect_prediction_all_errors_zero(actual):
    rows = evaluate(actual,actual.copy(),input_space="physical")
    for row in rows:
        assert row["mae"] == row["rmse"] == row["wape_pct"] == row["mape_pct"] == 0
        assert row["r2"] == 1
        assert row["pde_p_pct"] == row["pde_s_pct"] == 0
        assert row["consistency_p_median_kw"] == row["consistency_s_median_kva"] == 0


def test_constant_offset_has_exact_mae():
    actual = np.ones((2,96,4))*8
    rows = evaluate(actual,actual+2,input_space="physical")
    assert all(row["mae"] == row["rmse"] == 2 for row in rows)


def test_wape_zero_targets_and_signed_denominator_are_safe():
    actual = np.ones((1,3,4))
    actual[0,:,1] = [0.,-2.,2.]
    prediction = actual.copy()
    prediction[0,:,1] += 1
    reactive = evaluate(actual,prediction,input_space="physical")[1]
    assert reactive["wape_pct"] == 75
    assert np.isfinite(reactive["mape_pct"])
    assert reactive["mape_zero_targets"] == 1
    assert "unreliable_signed_near_zero" in reactive["mape_status"]
    assert "zero_targets_excluded" in reactive["mape_status"]


def test_all_zero_targets_are_explicitly_undefined():
    rows = evaluate(np.zeros((1,96,4)),np.ones((1,96,4)),input_space="physical")
    assert all(np.isnan(row["mape_pct"]) and np.isnan(row["wape_pct"]) for row in rows)
    assert all(row["wape_status"] == "undefined_all_targets_zero" for row in rows)
    assert rows[0]["pde_p_zero_windows"] == rows[0]["pde_s_zero_windows"] == 1
    assert np.isnan(rows[0]["pde_p_pct"])


def test_pde_uses_max_over_horizon_then_average_over_windows():
    actual = np.ones((2,2,4))
    actual[:,:,2] = [[10.,20.],[10.,100.]]
    actual[:,:,3] = actual[:,:,2]
    prediction = actual.copy()
    prediction[0,:,2:4] = [[20.,20.],[20.,20.]]
    prediction[1,:,2:4] = [[10.,10.],[80.,80.]]
    row = evaluate(actual,prediction,input_space="physical")[0]
    # First max is exactly right despite step-one error; second has20% peak error.
    assert row["pde_p_pct"] == pytest.approx(10)
    assert row["pde_s_pct"] == pytest.approx(10)


def test_inverse_transform_is_applied_before_metrics(actual,scaler):
    prediction = actual+2
    scaled_actual = normalize_electrical(actual,scaler)
    scaled_prediction = normalize_electrical(prediction,scaler)
    scored = evaluate(scaled_actual,scaled_prediction,input_space="scaled",scaler=scaler)
    wrong_units = evaluate(scaled_actual,scaled_prediction,input_space="physical")
    for i,row in enumerate(scored):
        assert row["mae"] == pytest.approx(2)
        assert row["mae"] != pytest.approx(wrong_units[i]["mae"])
    np.testing.assert_allclose(inverse_predictions(scaled_prediction,scaler),prediction)
    with pytest.raises(ValueError,match="scaler"):
        evaluate(scaled_actual,scaled_prediction,input_space="scaled")


@pytest.mark.parametrize("model_class,lag",[(SeasonalNaiveDaily,96),(SeasonalNaiveWeekly,672)])
def test_seasonal_naive_exact_on_matching_periodic_fixture(model_class,lag):
    n = 1800
    pattern = (np.arange(n)%lag).astype(float)+1
    history = np.stack([pattern,pattern/4,pattern*4,pattern*5],axis=-1)
    model = model_class(history,np.zeros(n,bool))
    origins = np.array([700,800,1000])
    assert timed_fit(model,np.array([700]),np.array([800])) >= 0
    np.testing.assert_array_equal(model.predict(origins),history[origins[:,None]+np.arange(1,97)])
    assert model.n_parameters == 0 and model.name == model_class.__name__


def test_persistence_uses_t_not_first_target_or_last_nonimputed_search():
    history = np.arange(1200*4,dtype=float).reshape(1200,4)
    model = Persistence(history,np.zeros(1200,bool))
    predicted = model.predict(np.array([700]))
    np.testing.assert_array_equal(predicted,np.broadcast_to(history[700],(1,96,4)))
    flags = np.zeros(1200,bool)
    flags[700] = True
    assert np.isnan(Persistence(history,flags).predict(np.array([700]))).all()


def test_imputed_lag_excludes_entire_window_without_zero_fill():
    history = np.ones((1200,4))
    flags = np.zeros(1200,bool)
    flags[610] = True
    prediction = SeasonalNaiveDaily(history,flags).predict(np.array([700,900]))
    assert np.isnan(prediction[0,5]).all()  #700+6-96=610
    assert np.isfinite(prediction[0,0]).all()
    rows = evaluate(np.ones((2,96,4)),prediction,input_space="physical")
    assert all(row["n_origins"] == 2 and row["n_scored_windows"] == 1 and row["n_excluded_windows"] == 1 for row in rows)


def test_missing_lag_and_out_of_bounds_never_wrap_or_read_future():
    history = np.arange(1200*4,dtype=float).reshape(1200,4)
    history[610,0] = np.nan
    predicted = SeasonalNaiveDaily(history,np.zeros(1200,bool)).predict(np.array([700]))
    assert np.isnan(predicted[0,5]).all()
    predicted = SeasonalNaiveWeekly(history,np.zeros(1200,bool)).predict(np.array([100]))
    assert np.isnan(predicted).all()
    original = history.copy()
    history[701:] = 1e9
    np.testing.assert_allclose(predicted,SeasonalNaiveWeekly(history,np.zeros(1200,bool)).predict(np.array([100])),equal_nan=True)
    model = SeasonalNaiveDaily(original,np.zeros(1200,bool))
    np.testing.assert_array_equal(model.predict(np.array([700]))[0,-1],original[700])


def test_horizon_breakdowns_keep_whole_window_exclusion():
    truth = np.ones((2,96,4))
    prediction = truth.copy()
    prediction[0,95] = np.nan
    starts = pd.DatetimeIndex(["2024-02-02","2024-02-03"])
    groups = list(breakdown_metrics(truth,prediction,starts,[0,1]))
    first_step = next(rows for dimension,label,rows in groups if dimension == "horizon" and label == "1")
    assert first_step[0]["n_scored_windows"] == 1
    weekend = next(rows for dimension,label,rows in groups if dimension == "day_type" and label == "weekend")
    assert weekend[0]["n_scored_windows"] == 1


def test_prediction_export_preserves_all_origins_nan_steps_and_physical_values(tmp_path,actual):
    index = pd.date_range("2024-01-01",periods=1200,freq="15min")
    origins = np.array([700,701,702])
    prediction = actual.copy()
    prediction[0,10] = np.nan
    path = write_predictions(tmp_path,"Synthetic","val","run1",origins,index,actual,prediction,{"units":"physical"})
    saved = pq.read_table(path)
    assert saved.num_rows == 3 and saved.schema.field("pred_dEa").type.list_size == 96
    assert saved["is_scored"].to_pylist() == [False,True,True]
    assert np.isnan(saved["pred_dEa"][0].as_py()[10])
    assert saved["true_P_avg"][0].as_py() == actual[0,:,2].tolist()
    assert (tmp_path/"Synthetic_val.parquet").exists()
    with pytest.raises(FileExistsError):
        write_predictions(tmp_path,"Synthetic","val","run1",origins,index,actual,prediction,{})


def test_benchmark_append_has_fixed_schema_and_preserves_old_rows(tmp_path):
    path = tmp_path/"benchmark.csv"
    row = dict.fromkeys(BENCHMARK_COLUMNS,"")
    row.update(model="Synthetic",mae=0.)
    append_records(path,[row])
    append_records(path,[row])
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        assert tuple(reader.fieldnames) == BENCHMARK_COLUMNS
        assert len(list(reader)) == 2
    with pytest.raises(ValueError,match="Schema mismatch"):
        append_records(path,[{**row,"extra":1}])


def test_predict_contract_and_inverse_physical_timing(scaler):
    physical = np.ones((1200,4))
    model = Persistence(normalize_electrical(physical,scaler),np.zeros(1200,bool))
    predicted,seconds = predict_physical(model,np.array([700]),scaler)
    np.testing.assert_allclose(predicted,np.ones((1,96,4)))
    assert seconds >= 0
