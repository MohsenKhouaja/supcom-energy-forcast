"""Physical-unit forecast metrics and the version-1 benchmark CSV contract.

Every metric excludes an ENTIRE window if any truth/prediction is non-finite.
MAPE omits exact-zero denominators and flags that omission; dEr MAPE is always
flagged unreliable because it is signed and crosses/approaches zero. WAPE
uses sum(abs(truth)), not abs(sum(truth)). Percentage metrics are in percent.
PDE is the per-window relative error of the horizon maximum, then the mean.
Zero true maxima make that window's PDE undefined; counts are reported.
"""

import csv
from pathlib import Path

import numpy as np

from smartgrid.models.base import CHANNELS, UNITS

SCHEMA_VERSION = 1
BENCHMARK_COLUMNS = (
    "schema_version", "run_id", "run_utc", "git_commit", "model", "split", "channel", "unit",
    "n_origins", "n_scored_windows", "n_excluded_windows", "n_pairs", "mae", "rmse", "r2",
    "mape_pct", "mape_status", "mape_zero_targets", "wape_pct", "wape_status",
    "pde_p_pct", "pde_s_pct", "pde_p_zero_windows", "pde_s_zero_windows",
    "consistency_p_median_kw", "consistency_s_median_kva", "n_parameters", "fit_seconds",
    "predict_seconds", "peak_rss_mb", "predictions_path", "source_sha256", "origins_sha256",
    "scaler_sha256", "calendar_status",
)
BREAKDOWN_COLUMNS = BENCHMARK_COLUMNS + ("breakdown", "group")


def _scale_arrays(scaler):
    if scaler is None or tuple(scaler["channels"]) != CHANNELS:
        raise ValueError("Scaled inputs require the fitted four-channel scaler")
    mean,scale = np.asarray(scaler["mean"],dtype=float),np.asarray(scaler["scale"],dtype=float)
    if mean.shape != (4,) or scale.shape != (4,) or not np.isfinite([mean,scale]).all() or (scale <= 0).any():
        raise ValueError("Invalid scaler mean/scale")
    return mean,scale


def inverse_predictions(values, scaler):
    """Inverse-transform all four channels, preserving NaNs and array shape."""
    mean,scale = _scale_arrays(scaler)
    values = np.asarray(values,dtype=np.float64)
    if values.shape[-1:] != (4,):
        raise ValueError("Expected four electrical channels on the last axis")
    return values*scale+mean


def normalize_electrical(values, scaler):
    mean,scale = _scale_arrays(scaler)
    values = np.asarray(values,dtype=np.float64)
    if values.shape[-1:] != (4,):
        raise ValueError("Expected four electrical channels on the last axis")
    return (values-mean)/scale


def scored_window_mask(y_true, y_pred):
    truth,pred = np.asarray(y_true,dtype=float),np.asarray(y_pred,dtype=float)
    if truth.ndim != 3 or truth.shape[-1] != 4 or truth.shape != pred.shape or truth.shape[1] == 0:
        raise ValueError("Expected matching [n_windows,horizon,4] truth/predictions")
    return np.isfinite(truth).all(axis=(1,2)) & np.isfinite(pred).all(axis=(1,2))


def _pde(truth,pred,channel):
    actual = truth[:,:,channel].max(axis=1)
    predicted = pred[:,:,channel].max(axis=1)
    valid = actual > 0
    value = float(np.mean(np.abs(predicted[valid]-actual[valid])/actual[valid])*100) if valid.any() else np.nan
    return value,int((~valid).sum())


def evaluate(y_true, y_pred, *, input_space, scaler=None):
    """Return four channel records, always scored in physical units.

    Explicit input_space is mandatory. For 'scaled', BOTH truth and predictions
    are inverse-transformed using the train-only scaler before any calculation.
    For 'physical', callers certify physical-unit inputs. h-only breakdowns may
    have horizon=1; their PDE then uses the max over that one retained step.
    R2 uses the standard finite convention for constant truth: 1 if perfect,
    otherwise 0. Fewer than two pairs -> undefined R2 (NaN).
    """
    truth,pred = np.asarray(y_true,dtype=np.float64),np.asarray(y_pred,dtype=np.float64)
    if input_space == "scaled":
        truth,pred = inverse_predictions(truth,scaler),inverse_predictions(pred,scaler)
    elif input_space != "physical":
        raise ValueError("input_space must explicitly be 'physical' or 'scaled'")
    good = scored_window_mask(truth,pred)
    n_origins = len(truth)
    truth,pred = truth[good],pred[good]
    n = len(truth)
    shared = dict(n_origins=n_origins,n_scored_windows=n,n_excluded_windows=n_origins-n)
    if n:
        pde_p,p_zero = _pde(truth,pred,2)
        pde_s,s_zero = _pde(truth,pred,3)
        consistency_p = float(np.median(np.abs(pred[:,:,2]-4*pred[:,:,0])))
        consistency_s = float(np.median(np.abs(pred[:,:,3]-np.hypot(pred[:,:,2],4*pred[:,:,1]))))
    else:
        pde_p=pde_s=consistency_p=consistency_s=np.nan
        p_zero=s_zero=0
    shared.update(pde_p_pct=pde_p,pde_s_pct=pde_s,pde_p_zero_windows=p_zero,pde_s_zero_windows=s_zero,
                  consistency_p_median_kw=consistency_p,consistency_s_median_kva=consistency_s)
    rows = []
    for i,(channel,unit) in enumerate(zip(CHANNELS,UNITS)):
        actual,forecast = truth[:,:,i].reshape(-1),pred[:,:,i].reshape(-1)
        error = forecast-actual
        absolute = np.abs(error)
        count = len(actual)
        if count:
            mae = float(absolute.mean())
            rmse = float(np.sqrt(np.mean(error**2)))
            sst = float(np.sum((actual-actual.mean())**2))
            sse = float(np.sum(error**2))
            r2 = float(1-sse/sst) if sst > 0 else float(sse == 0)
            if count < 2:
                r2 = np.nan
            nonzero = actual != 0
            mape = float(np.mean(absolute[nonzero]/np.abs(actual[nonzero]))*100) if nonzero.any() else np.nan
            denom = float(np.abs(actual).sum())
            wape = float(absolute.sum()/denom*100) if denom > 0 else np.nan
            zero_count = int((~nonzero).sum())
            mape_status = "ok" if not zero_count else "zero_targets_excluded"
            if not nonzero.any():
                mape_status = "undefined_all_targets_zero"
            if channel == "dEr":
                mape_status = "unreliable_signed_near_zero;"+mape_status
            wape_status = "ok" if denom > 0 else "undefined_all_targets_zero"
        else:
            mae=rmse=r2=mape=wape=np.nan
            zero_count=0
            mape_status=wape_status="undefined_no_scored_windows"
        rows.append(dict(shared,channel=channel,unit=unit,n_pairs=count,mae=mae,rmse=rmse,r2=r2,
                         mape_pct=mape,mape_status=mape_status,mape_zero_targets=zero_count,
                         wape_pct=wape,wape_status=wape_status))
    return rows


def append_records(path, rows, *, columns=BENCHMARK_COLUMNS):
    """Append only exact-schema records. Never silently change an old header."""
    path = Path(path)
    rows = list(rows)
    for row in rows:
        if set(row) != set(columns):
            raise ValueError(f"Schema mismatch: missing={set(columns)-set(row)}, extra={set(row)-set(columns)}")
    if path.exists() and path.stat().st_size:
        with path.open(newline="",encoding="utf-8") as stream:
            if tuple(next(csv.reader(stream))) != tuple(columns):
                raise ValueError("Existing CSV schema differs; explicit schema migration required")
    path.parent.mkdir(parents=True,exist_ok=True)
    existed = path.exists() and path.stat().st_size > 0
    with path.open("a",newline="",encoding="utf-8") as stream:
        writer = csv.DictWriter(stream,fieldnames=columns,extrasaction="raise")
        if not existed:
            writer.writeheader()
        for row in rows:
            writer.writerow({key:("" if isinstance(value,(float,np.floating)) and not np.isfinite(value) else value)
                             for key,value in row.items()})
