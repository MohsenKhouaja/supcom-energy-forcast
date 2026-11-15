"""Synthetic-only causal-feature and classical-model interface checks."""

import copy

import numpy as np
import pytest

from smartgrid.features.tabular import CALENDAR, FEATURE_NAMES, FEATURE_SPECS, LAGS, ROLLING, TabularFeatures, capped_training_pairs, complete_pairs
from smartgrid.models.classical import RandomForestForecaster, SVRForecaster, XGBoostForecaster


@pytest.fixture(scope="module")
def causal_fixture():
    n=1500
    history = np.arange(n,dtype=float)[:,None]+1000*np.arange(4)[None,:]
    calendar = np.sin(np.arange(n)[:,None]/30+np.arange(7)).astype(np.float32)
    flags = np.zeros(n,bool)
    original = TabularFeatures(history,calendar,flags)
    changed = history.copy()
    changed[1001:] = 1e12
    mutated = TabularFeatures(changed,calendar,flags)
    return original,mutated,history,calendar


@pytest.mark.parametrize("column,spec",list(enumerate(FEATURE_SPECS)),ids=FEATURE_NAMES)
def test_every_feature_only_reads_past_electricity_or_known_calendar(column,spec,causal_fixture):
    original,mutated,history,calendar = causal_fixture
    origins=np.array([1000])
    h=np.array([37])
    before=original.build(origins,h)
    after=mutated.build(origins,h)
    assert before[0,column] == after[0,column]
    if spec.kind == "electrical_history":
        assert spec.earliest_relative_row <= spec.latest_relative_row <= 0
    elif spec.kind == "known_future_calendar":
        assert before[0,column] == calendar[1037,CALENDAR.index(spec.name.removeprefix("target_"))]
    else:
        assert spec.name == "h" and before[0,column] == 37


def test_lags_and_rolling_statistics_match_synthetic_ramp(causal_fixture):
    builder,_,history,_=causal_fixture
    values=builder.build(np.array([1000]),np.array([1]))[0]
    assert len(values) == len(FEATURE_NAMES) == 64
    for channel,name in enumerate(("dEa","dEr","P_avg","S_avg")):
        for lag in LAGS:
            assert values[FEATURE_NAMES.index(f"{name}_lag_{lag}")] == history[1000-lag,channel]
        for width in ROLLING:
            trailing=history[1001-width:1001,channel]
            assert values[FEATURE_NAMES.index(f"{name}_rolling_mean_{width}")] == pytest.approx(trailing.mean())
            assert values[FEATURE_NAMES.index(f"{name}_rolling_std_{width}")] == pytest.approx(trailing.std(ddof=0),rel=1e-5)


def test_horizon_is_exactly_1_through_96(causal_fixture):
    builder,_,_,_=causal_fixture
    origin,h=complete_pairs(np.array([1000]))
    assert builder.build(origin,h)[:,-1].tolist() == list(range(1,97))


def test_target_guard_and_imputed_inputs_are_distinct(causal_fixture):
    _,_,history,calendar=causal_fixture
    flags=np.zeros(len(history),bool)
    flags[1000]=True  # allowed input
    flags[1037]=True  # forbidden label
    builder=TabularFeatures(history,calendar,flags)
    assert np.isfinite(builder.build(np.array([1000]),np.array([37]))).all()
    with pytest.raises(ValueError,match="Imputed"):
        builder.targets(np.array([1000]),np.array([37]))
    assert np.isfinite(builder.targets(np.array([1000]),np.array([36]))).all()


def test_exact_week_lag_requires_one_extra_reading(causal_fixture):
    _,_,history,calendar=causal_fixture
    history=history.copy()
    history[0,0]=np.nan
    builder=TabularFeatures(history,calendar,np.zeros(len(history),bool))
    assert builder.usable_origins(np.array([672,673])).tolist() == [False,True]


def test_svr_training_cap_is_deterministic_and_never_used_for_evaluation():
    origins=np.arange(1000,90000,7)
    left,h=capped_training_pairs(origins,20000)
    again=capped_training_pairs(origins,20000)
    assert len(left) == 20000 and np.unique(h).tolist() == list(range(1,97))
    np.testing.assert_array_equal(left,again[0])
    np.testing.assert_array_equal(h,again[1])
    assert len(np.unique(np.column_stack([left,h]),axis=0)) == 20000
    assert len(complete_pairs(origins)[0]) == len(origins)*96


def test_half_retry_pattern_retains_all_quarter_hour_phases():
    selected=np.arange(673,673+10520*7,7)
    half=selected[np.arange(len(selected))%8 < 4]
    assert len(half) == 5260
    assert set(half%4) == {0,1,2,3}


@pytest.mark.parametrize("model_class,half_sample",[(RandomForestForecaster,False),(RandomForestForecaster,True),(XGBoostForecaster,False),(SVRForecaster,False)])
def test_fixture_model_implements_full_forecast_shape(model_class,half_sample):
    n=1200
    t=np.arange(n,dtype=float)
    history=np.column_stack([np.sin(t/96),np.cos(t/96),np.sin(t/96)*4,np.ones(n)])
    calendar=np.column_stack([np.sin(t/96+i) for i in range(7)])
    builder=TabularFeatures(history,calendar,np.zeros(n,bool))
    config=dict(training_origin_stride=7,random_seed=1,svr_training_rows=20000,
        rf=dict(n_estimators=2,max_depth_grid=[2,3],n_jobs=1,max_features=.5),
        xgb=dict(n_estimators=2,max_depth_grid=[2],n_jobs=1,tree_method="hist",device="cpu"),
        svr=dict(kernel="rbf",C_grid=[1.],epsilon=.1,gamma="scale",cache_size=32))
    scaler=dict(channels=["dEa","dEr","P_avg","S_avg"],mean=[0.]*4,scale=[1.]*4)
    model=model_class(builder,scaler,config,half_sample=half_sample)
    assert model.fit(np.arange(700,715),np.arange(800,805)) is None
    result=model.predict(np.array([900,901]))
    assert result.shape == (2,96,4) and np.isfinite(result).all()
    assert len(model.estimators) == 4 and model.n_parameters > 0
    if half_sample:
        assert len(model.selection) == 5
        assert len({estimator.max_depth for estimator in model.estimators}) == 1
