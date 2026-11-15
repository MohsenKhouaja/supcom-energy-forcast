# Leakage-safe features and lazy windows

Academic-calendar features: **RECONSTRUCTED, not official**. See [CALENDAR.md](CALENDAR.md). CPU-only preprocessing. No model, training, inference, or stacked window arrays were created.

## Splits and eligibility

[configs/splits.yaml](../configs/splits.yaml) replaces the EDA proposal. End dates are inclusive. Train: July 2022–August 2024 (26 months); validation: September 2024–May 2025 (9 months); test: June 2025–February 2026 (9 months). Test contains both meteorological summer and winter. Validation contains autumn/winter/spring, not a full summer.

| split | start | end | grid_rows | complete_observed_rows | imputed_rows | incomplete_nonimputed_rows | eligible_origins | first_origin | last_origin |
|---|---|---|---|---|---|---|---|---|---|
| train | 2022-07-01 | 2024-08-31 | 76128 | 75832 | 295 | 1 | 73640 | 2022-07-08 00:00:00 | 2024-08-30 23:45:00 |
| val | 2024-09-01 | 2025-05-31 | 26208 | 26169 | 39 | 0 | 25124 | 2024-08-31 23:45:00 | 2025-05-30 23:45:00 |
| test | 2025-06-01 | 2026-02-28 | 26208 | 26165 | 43 | 0 | 25500 | 2025-05-31 23:45:00 | 2026-02-27 23:45:00 |

Origin t is the last input timestamp. X = t-671..t, shape [672,11]; y = t+1..t+96, shape [96,4]. There is no overlap. All input rows must be present, consecutive and finite; imputed inputs are allowed. Every target must be observed, non-imputed and finite in all four channels. All targets stay inside their own split. Earlier partitions may supply historical input context. Therefore the first validation/test origin can precede its target partition by one slot. No labels or right anchors from later partitions are used for imputation.

## Re-ingestion and split-bounded reconstruction

Ran scripts/ingest_dataset.py --splits configs/splits.yaml, reading the raw exports afresh. All split starts/ends are enforced for both original counter anchors and earlier donors. Missing gaps that straddle a partition stay missing. Comparisons below use old/new is_imputed union and rtol=1e-12, atol=1e-10; NaN equals NaN. Numeric-cell counts include derived channels, not only raw filled cells.

| meter | changed_numeric_cells | changed_cells_on_old_or_new_imputed_rows | changed_rows | old_imputed_rows | new_imputed_rows | changed_flags | old_missing_dEa | new_missing_dEa |
|---|---|---|---|---|---|---|---|---|
| CLIM_SALLE_IT_(TGBT_D1) | 0 | 0 | 0 | 377 | 377 | 0 | 1 | 1 |
| CLIM_TOUR_A_(TGBT_D6) | 0 | 0 | 0 | 377 | 377 | 0 | 1 | 1 |
| EM_VIRTUAL | 0 | 0 | 0 | 377 | 377 | 0 | 1 | 1 |
| ONDULEUR_1_(TGBT_DXX) | 0 | 0 | 0 | 510 | 510 | 0 | 4452 | 4452 |
| ONDULEUR_2_(TGBT_DXX) | 0 | 0 | 0 | 502 | 502 | 0 | 223 | 223 |
| PV_(CHAUFFERIE_PROV.) | 0 | 0 | 0 | 377 | 377 | 0 | 1 | 1 |
| SALLE_B101_(A._MEZAN_TOUR_B) | 0 | 0 | 0 | 415 | 415 | 0 | 1 | 1 |
| SALLE_B112_(A._MEZAN_TOUR_B) | 0 | 0 | 0 | 415 | 415 | 0 | 1 | 1 |
| SALLE_B201_(A_1_ETAGE_TOUR_B) | 0 | 0 | 0 | 415 | 415 | 0 | 1 | 1 |
| TGBT_TR1 | 0 | 0 | 0 | 377 | 377 | 0 | 1 | 1 |
| TGBT_TR2 | 0 | 0 | 0 | 377 | 377 | 0 | 1 | 1 |
| TOUR_A_(TGBT_D14) | 0 | 0 | 0 | 369 | 369 | 0 | 2786 | 2786 |
| TOUR_C_(TGBT_D10) | 0 | 0 | 0 | 369 | 369 | 0 | 2786 | 2786 |
| Tour_B_(TGBT_D5) | 0 | 0 | 0 | 377 | 377 | 0 | 1 | 1 |

Active donor-to-uniform fallback changes: **0**; reactive: **0**. Method/donor changes: 0.

| meter | start | length | old_method | new_method | old_reactive | new_reactive | old_donor | new_donor |
|---|---|---|---|---|---|---|---|---|

The old EDA notebook/report remain the executed historical analysis of the preceding artifact. They were not rerun or silently rewritten; the current artifact is identified by hashes below.

## Eleven features

Order: `dEa, dEr, P_avg, S_avg, hour_sin, hour_cos, weekday_sin, weekday_cos, doy_sin, doy_cos, is_non_working_day`. Electrical channels are dEa (kWh/15 min), signed dEr (kvarh/15 min), P_avg (kW), S_avg (kVA). Fractional hour includes minutes, so 23:45 is adjacent to 00:00 in cyclic space. Weekday is Monday=0. Day-of-year uses period 365.25. Non-working is weekend OR TN public holiday OR RECONSTRUCTED academic vacation. Exams are working days unless another rule applies. Calendar channels are never scaled.

## Scaler: unique training input OR target rows only

StandardScaler is fitted once on the unique train-range rows touched by any eligible training input OR target. Overlapping windows do not repeat-weight observations. Imputed training inputs may enter the fit; imputed rows remain forbidden as labels. No validation/test row enters fit. Both X electrical channels and y use the same fitted transform. Population std (ddof=0); constant channels use scale 1.

| train_range_rows | fitted_rows | excluded_rows | excluded_pct | excluded_nonfinite_electrical | excluded_finite_not_touched |
|---|---|---|---|---|---|
| 76128 | 76127 | 1 | 0.001314 | 1 | 0 |

Excluded nonfinite rows cannot occur in any complete input/target. Excluded finite rows, if any, are not touched by any eligible training span. The excluded share is below 1%; the distinction from all train-range rows is immaterial at this scale, but the implemented fit policy remains exact. A >=1% exclusion would have stopped the builder before scaler fitting for user review.

| channel | mean | std | scale |
|---|---|---|---|
| dEa | 14.232299 | 8.819300 | 8.819300 |
| dEr | 1.659972 | 5.108594 | 5.108594 |
| P_avg | 56.947430 | 35.274722 | 35.274722 |
| S_avg | 59.732148 | 37.162319 | 37.162319 |

Fitted rows: 76127; first 2022-07-01 00:15:00; last 2024-08-31 23:45:00. Plain-number scaler is data/processed/scaler.json; it is not a pickle.

## Lazy storage and use

One underlying [N,11] float32 array has shape (128544, 11) and 5,655,936 payload bytes. features.npy is memory-mapped by the loader. Origin Parquets contain only row indices and alignment timestamps, one file per split. feature_grid.parquet stores timestamps/flags; features.json pins order, dates and hashes. No [number_of_windows,672,11] array is written or retained.

```python
from smartgrid.data.windows import from_processed, torch_dataset
train = from_processed('data/processed', 'train')
X, y = train[0]  # read-only NumPy views; [672,11], [96,4]
# Optional, only if torch is already installed:
dataset = torch_dataset(train)  # genuine Dataset; one sample copied to CPU tensors on demand
```

Torch was not installed and was not added: only holidays/scikit-learn were authorized. The optional adapter source is provided; its real-Torch integration test is explicitly skipped in this environment. The NumPy lazy loader, storage round-trip, shapes and eligibility are tested. No GPU work occurs.

## Four targets and physical consistency

The intended interval energy/power relationship is P_avg = 4*dEa, while Q_avg = 4*dEr and S_avg = sqrt(P_avg^2+Q_avg^2). The four targets are therefore physically related. All four are retained because the specification requires joint dEa, dEr, Pmax, Smax prediction. The sequence head exposes dEa,dEr,P_avg,S_avg; Pmax and Smax for the PDE metric are the maxima of the 96 predicted P_avg and S_avg values, after inverse normalization. Demand registers are cross-checks, never labels. At evaluation, compare predicted S against sqrt(predicted P^2+(4*predicted dEr)^2), in physical units. Also compare predicted P with 4*predicted dEa.

Observed dEa is a counter difference, while observed P_avg is a separately exported power channel. The nominal P=4*dEa identity is not forced onto measured channels or assumed to hold exactly; the actual observed discrepancy is reported below rather than silently replacing measurements. S and signed dEr are derived in ingestion.

| comparable_observed_rows | excluded_imputed | other_missing_observed | median_abs_P_minus_4dEa_kW | max_abs_P_minus_4dEa_kW | rows_abs_difference_over_001kW | max_abs_S_minus_hypot_P_4dEr_kVA |
|---|---|---|---|---|---|---|
| 128166 | 377 | 1 | 0.250000 | 34.950000 | 125511 | 0.000000 |

## Provenance and execution

holidays 0.108; scikit-learn 1.9.1. Only those two direct dependencies were added (their required dependencies may be installed by pip).

- EM_VIRTUAL SHA-256: `6c45c14bcab15a45bf8ebe2f88329de121e4e137774fe8f316bb6f7dd6b05bbe`
- Features SHA-256: `732d734a0dd0be7435c1b03e159f3636e1a350e8035e79c9b5eb6b681d528856`
- Scaler SHA-256: `cbd34d6eaeff8b71ffb1e77df8406f6d6ec2d362b7c039a76b7ea11ad05e85a5`
- Builder runtime: 13.603 seconds.

## Pytest output

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.2.0, pluggy-1.7.0
rootdir: /home/khalifa/supcom-energy-forcast
plugins: platformdirs-4.14.5, anyio-4.16.0
collected 77 items

tests/test_behaviour.py ........................                         [ 31%]
tests/test_contracts.py ....                                             [ 36%]
tests/test_ingestion.py .............................                    [ 74%]
tests/test_windows.py ...................s                               [100%]

=========================== short test summary info ============================
SKIPPED [1] tests/test_windows.py:230: Torch not installed; only holidays/scikit-learn additions authorized
======================== 76 passed, 1 skipped in 7.65s =========================
```

Split-bounded ingestion execution: `RUNTIME_SECONDS 140.17424774891697`.
