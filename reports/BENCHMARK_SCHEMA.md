# Benchmark contract, version 1

`reports/benchmark.csv` is append-only: exactly four rows per successful
(run, model, split), one for each channel in this order: dEa, dEr, P_avg, S_avg.
The header below is fixed. Later models use the same interface, evaluator and
schema. A changed header requires an explicit versioned migration; extra or
missing fields are rejected. A run_id identifies a comparison cohort. An
explicitly requested extension may reuse the baseline run_id for new model
families; run_utc records that extension's actual invocation time. Duplicate
(run_id, model, split, channel) entries are refused by the ML runner. Use the
chosen run_id when ranking; do not mix unrelated cohorts.

All metrics and persisted predictions are in **physical units**. Model.predict
returns normalized channels; the harness applies the saved train-only scaler
before scoring. The scorer requires an explicit input-space declaration.

| Column, in CSV order | Type / meaning |
|---|---|
| schema_version | int, 1 |
| run_id | string, unique invocation identifier |
| run_utc | string, UTC ISO timestamp of invocation |
| git_commit | string, local source revision before the run; working changes are additionally hashed in the run manifest |
| model | stable model.name string |
| split | val or test for this benchmark |
| channel | dEa, dEr, P_avg, S_avg |
| unit | kWh, kvarh, kW, kVA respectively |
| n_origins | int, eligible candidate windows before model-specific exclusions |
| n_scored_windows | int, complete finite truth/prediction windows |
| n_excluded_windows | int, n_origins minus n_scored_windows |
| n_pairs | int, scored windows times retained horizon length |
| mae | float, mean absolute error, channel unit |
| rmse | float, root mean square error, channel unit |
| r2 | float, pooled R-squared; constant truth: 1 if perfect, otherwise 0; fewer than 2 pairs: undefined |
| mape_pct | float, 100 times mean(abs(error)/abs(truth)) on nonzero targets only |
| mape_status | string, ok / zero_targets_excluded / undefined_all_targets_zero / undefined_no_scored_windows; dEr prefixes unreliable_signed_near_zero |
| mape_zero_targets | int, omitted exact-zero target denominators |
| wape_pct | float, 100 times sum(abs(error))/sum(abs(truth)); primary percentage metric for dEr |
| wape_status | string, ok / undefined_all_targets_zero / undefined_no_scored_windows |
| pde_p_pct | float, 100 times mean over windows of abs(max(pred_P)-max(true_P))/max(true_P) |
| pde_s_pct | float, same definition for S_avg |
| pde_p_zero_windows | int, windows with nonpositive true P maximum, omitted from PDE_P |
| pde_s_zero_windows | int, windows with nonpositive true S maximum, omitted from PDE_S |
| consistency_p_median_kw | float, median abs(pred_P-4*pred_dEa) over scored forecast pairs |
| consistency_s_median_kva | float, median abs(pred_S-hypot(pred_P,4*pred_dEr)) over scored forecast pairs |
| n_parameters | int, fitted model parameters; 0 for these baselines; excludes data and the shared scaler |
| fit_seconds | float, wall-clock time of the actual fit(train_origins,val_origins) call |
| predict_seconds | float, wall-clock time of predict(origins), excluding inverse transform, scoring and export |
| peak_rss_mb | float, isolated worker's lifetime peak resident memory, decimal MB; Linux ru_maxrss KiB times 1024/1e6 |
| predictions_path | string, immutable project-relative run-versioned prediction Parquet |
| source_sha256 | string, SHA-256 of physical em_virtual.parquet |
| origins_sha256 | string, SHA-256 of the split origin-index Parquet |
| scaler_sha256 | string, SHA-256 of scaler.json |
| calendar_status | string, RECONSTRUCTED, not official |

Undefined floating metrics are empty CSV cells, never infinity. Timing, counts,
PDE, physical consistency and cost describe the run and repeat on its four
channel rows. Channel errors are pooled across all scored origin/horizon pairs.
Overlapping rolling forecasts are counted repeatedly as distinct forecast
cases; n_pairs is not a count of independent observations.

A budget-censored model retains rows with n_scored_windows=0 and undefined
errors. Such rows are unavailable for numeric accuracy ranking; an empty error
is never zero. Its manifest/prediction metadata records the cause. Zero usable
parameters in that case does not make it a successful zero-parameter baseline.
If no completed model.predict call occurred, predict_seconds is empty, not a
claimed zero-time prediction.
For multi-stage ML, peak RSS is the maximum across its fitting/evaluation
workers; wasted fit attempts are charged and disclosed in the run report.

A whole window is excluded if **any** channel at **any** forecast step is
non-finite. All calendar/horizon breakdowns keep that same exclusion mask.
The baselines emit a NaN four-channel vector whenever the required historical
row is missing or imputed. Persistence uses exactly t, not a backward search
for an earlier usable reading. Lagged observations may belong to an earlier
split; they are past information, never future targets.

`reports/baseline_breakdowns.csv` uses exactly the benchmark columns followed
by `breakdown,group`. Dimensions: month (YYYY-MM), season (DJF/MAM/JJA/SON),
day_type (weekday/weekend), is_non_working_day (0/1), horizon (1..96).
Calendar cohorts are assigned by the **first target timestamp**, retaining
the entire 96-step forecast and its horizon-max PDE. Horizon-only slices retain
one step: their PDE is a single-step relative error, not the headline 24-hour
peak error. Horizon figures plot MAE in physical units.

Non-working labels come from the existing saved calendar feature and remain
**RECONSTRUCTED, not official**. They are not re-inferred from electricity use.

## Prediction Parquet contract

Latest aliases: `data/predictions/<model>_<split>.parquet`.
Immutable versions: `data/predictions/runs/<run_id>/<model>_<split>.parquet`.
On the VM the alias is a hard link, so it does not duplicate payload storage.
Benchmark rows point to the immutable version to preserve append-only history.

One row per candidate origin, including excluded windows:

| Field | Arrow type / meaning |
|---|---|
| run_id, model, split | string identifiers |
| origin_index | int64, last input row t on the canonical 15-minute grid |
| origin_timestamp | timestamp[ns], t |
| target_start, target_end | timestamp[ns], t+1 and t+96 |
| is_scored | bool, complete window included in metrics |
| exclusion_reason | string, empty or nonfinite_truth_or_prediction |
| true_dEa, true_dEr, true_P_avg, true_S_avg | fixed_size_list<float64>[96], observed physical targets |
| pred_dEa, pred_dEr, pred_P_avg, pred_S_avg | fixed_size_list<float64>[96], physical forecasts in h=1..96 order |

NaN steps remain IEEE NaNs inside lists; excluded windows are never zero-filled.
Parquet schema metadata pins version, source/scaler/origin hashes, units and
calendar status. Writes use bounded row groups. Only predictions/targets are
assembled; no [n,672,11] input-window array is materialized.

## Selection and resource comparison

Use validation for selecting references and later models. Test is descriptive
held-out reporting, not selection. All model-specific exclusion counts must be
shown: metrics on different supports are not strictly paired comparisons.
The report identifies the lowest validation PDE_S as the peak-demand reference
and separately reports channel winners; it does not claim one universal winner.

Each (model, split) runs in a fresh CPU worker, sequentially, with numerical
threads limited to 1. Peak RSS includes data loading, forecast arrays, metrics
and Parquet serialization, not merely the model's parameter storage. Fit time
is measured even for the baseline no-op. Zero parameters do not mean zero
process memory. Required libraries were already installed; no packages added.
