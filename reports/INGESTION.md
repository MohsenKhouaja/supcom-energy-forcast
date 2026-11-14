# SInERT ingestion

Validation status: pytest exit code 0. All requested tests passed.

VM project: `/home/khalifa/supcom-energy-forcast`. CPU-only; no modeling, feature engineering or notebooks.

## Sources and schema

The update contains 30 CSVs: 16 August 2025 and 14 February 2026 files, 51,535,457 extracted bytes. Every CSV is required to have raw header MD5 `ae7740e6f10914f7aa4b2fa665f0baa0` and the same header bytes as the baseline.

Read 700 CSVs and 14 XLSX workbooks. The November 2023 XLSX workbooks supplied 2702 raw rows and 2688 additional EM_VIRTUAL observed intervals beyond the original CSVs.

XLSX measurement headers have numerical suffixes (for example `[ABS] 1`); these are removed by name, and the resulting entire header must equal the CSV schema. Excel dates are native datetime cells. Workbooks are streamed read-only, cached values only; formulas and macros are never executed.

Both reactive counters are retained: the forward counter is not assumed frozen. Net reactive anchor energy is delta(Er_pos_counter) minus delta(Er_neg_counter). Observed dEr always uses signed Q_avg * 0.25.

## Row accounting

| Item | Count |
|---|---:|
| rows_in | 135114 |
| all_missing_rows_dropped | 3556 |
| duplicates_dropped | 3072 |
| unique_observed_timestamps | 128486 |
| startup_observed_rows_dropped | 284 |
| startup_grid_slots_dropped | 288 |
| retained_observed_timestamps | 128202 |
| grid_slots_created | 342 |
| rows_out_per_meter | 128544 |
| Meters | 14 |
| Long output rows | 1799616 |

Grid: 2022-07-01 00:00:00 through 2026-02-28 23:45:00, every 15 minutes. The July 1 cutoff removes 288 grid slots, including 284 observed timestamps; the difference is explicit missing grid slots. Startup is removed before imputation and derivation. No leading/trailing extrapolation is performed. Duplicates use the entire raw row's non-null measurement count, with stable first-row ties; the misplaced original August 2025 copies of May are deduplicated by actual timestamps.

## Monthly observed coverage before imputation

Counts are unique EM_VIRTUAL timestamps with at least one observed Ea_counter/P_avg/Q_avg. This source-inventory table includes June 2022 for provenance; June is excluded from the canonical outputs.

| Month | Original CSV | With November XLSX | With update | Calendar expected |
|---|---:|---:|---:|---:|
| 2022-06 | 284 | 284 | 284 | 2880 |
| 2022-07 | 2948 | 2948 | 2948 | 2976 |
| 2022-08 | 2975 | 2975 | 2975 | 2976 |
| 2022-09 | 2876 | 2876 | 2876 | 2880 |
| 2022-10 | 2976 | 2976 | 2976 | 2976 |
| 2022-11 | 2880 | 2880 | 2880 | 2880 |
| 2022-12 | 2976 | 2976 | 2976 | 2976 |
| 2023-01 | 2976 | 2976 | 2976 | 2976 |
| 2023-02 | 2688 | 2688 | 2688 | 2688 |
| 2023-03 | 2975 | 2975 | 2975 | 2976 |
| 2023-04 | 2784 | 2784 | 2784 | 2880 |
| 2023-05 | 2976 | 2976 | 2976 | 2976 |
| 2023-06 | 2854 | 2854 | 2854 | 2880 |
| 2023-07 | 2973 | 2973 | 2973 | 2976 |
| 2023-08 | 2972 | 2972 | 2972 | 2976 |
| 2023-09 | 2860 | 2860 | 2860 | 2880 |
| 2023-10 | 2976 | 2976 | 2976 | 2976 |
| 2023-11 | 192 | 2880 | 2880 | 2880 |
| 2023-12 | 2976 | 2976 | 2976 | 2976 |
| 2024-01 | 2976 | 2976 | 2976 | 2976 |
| 2024-02 | 2784 | 2784 | 2784 | 2784 |
| 2024-03 | 2976 | 2976 | 2976 | 2976 |
| 2024-04 | 2880 | 2880 | 2880 | 2880 |
| 2024-05 | 2976 | 2976 | 2976 | 2976 |
| 2024-06 | 2880 | 2880 | 2880 | 2880 |
| 2024-07 | 2972 | 2972 | 2972 | 2976 |
| 2024-08 | 2883 | 2883 | 2883 | 2976 |
| 2024-09 | 2868 | 2868 | 2868 | 2880 |
| 2024-10 | 2975 | 2975 | 2975 | 2976 |
| 2024-11 | 2879 | 2879 | 2879 | 2880 |
| 2024-12 | 2971 | 2971 | 2971 | 2976 |
| 2025-01 | 2969 | 2969 | 2969 | 2976 |
| 2025-02 | 2686 | 2686 | 2686 | 2688 |
| 2025-03 | 2976 | 2976 | 2976 | 2976 |
| 2025-04 | 2880 | 2880 | 2880 | 2880 |
| 2025-05 | 2976 | 2976 | 2976 | 2976 |
| 2025-06 | 2880 | 2880 | 2880 | 2880 |
| 2025-07 | 2975 | 2975 | 2975 | 2976 |
| 2025-08 | 0 | 0 | 2974 | 2976 |
| 2025-09 | 2879 | 2879 | 2879 | 2880 |
| 2025-10 | 2976 | 2976 | 2976 | 2976 |
| 2025-11 | 2880 | 2880 | 2880 | 2880 |
| 2025-12 | 2965 | 2965 | 2965 | 2976 |
| 2026-01 | 2966 | 2966 | 2966 | 2976 |
| 2026-02 | 0 | 0 | 2676 | 2688 |

## Imputation and leakage policy

Thresholds live in configs/data.yaml (valid YAML 1.2 expressed with JSON syntax, parsed without another package). A gap is a consecutive run with any primary Ea/P/Q channel missing, per meter. Unbounded gaps and runs longer than 96 slots stay missing. Short runs up to 4 slots interpolate missing counter/P/Q cells linearly between original anchors, only with a same-day right anchor; dEa is then re-differenced.

For 5–96 missing slots there are L+1 increments between the observed anchors. The nearest wholly observed, non-imputed same-weekday window within the earlier 8 weeks supplies the shape. Negative donor active increments are clipped to zero. Scale active increments to the exact active counter change, and signed net reactive increments independently to the change of both reactive counters. A missing/zero-sum donor uses uniform increments. Existing active-counter observations, including internal anchors in a partially missing run, are preserved. P_avg and Q_avg are reconstructed over all L+1 slots, including the closing slot, replacing those readings and flagging them; original values remain in the raw selected-channel cache. S_avg and PF are derived anew. Reactive counters remain observed-only cross-checks.

Independent k/k_q preserve the two gap totals but generally change PF. Anchoring fixes total energy across the gap; allocation between months remains estimated if the anchors straddle a month boundary. Warnings do not alter observations or suppress tests.

Right counter anchors are lookahead within an analysis partition. No imputation or donor crosses configured split boundaries. No train/test split has been chosen here: before modeling, rerun with actual boundaries or per split. The windowing eligibility function excludes any origin whose next H=96 labels contain an imputed row, including the reconstructed closing increment. Imputed data may inform inputs, never targets. Phase 5 PF alerts must use is_imputed=False rows only. Monthly observed PF ranges are used only for diagnostic warnings, never to choose a fill.

is_imputed is a row boolean: true if any electrical value was filled/reconstructed or dEa depends on a filled previous counter. Per-method counts below include reconstructed closing P/Q readings, not only previously NaN cells.

| Method | Channel | Reconstructed values, all meters |
|---|---|---:|
| linear | Ea_counter | 561 |
| linear | P_avg | 561 |
| linear | Q_avg | 561 |
| scaled_weekday | Ea_counter | 3548 |
| scaled_weekday | P_avg | 3681 |
| scaled_weekday | Q_avg | 3640 |
| uniform | Ea_counter | 1062 |
| uniform | P_avg | 1101 |
| uniform | Q_avg | 1142 |

| Measure | All meters | EM_VIRTUAL |
|---|---:|---:|
| Imputed rows | 5634 | 377 |
| Newly filled primary NaN cells | 15511 | 1036 |
| Changed observed primary cells | 280 | 26 |

| Column | Remaining NaNs, all meters | Remaining NaNs, EM_VIRTUAL |
|---|---:|---:|
| Ea_counter | 10232 | 0 |
| dEa | 10257 | 1 |
| P_avg | 10232 | 0 |
| Q_avg | 10232 | 0 |
| dEr | 10232 | 0 |
| S_avg | 10232 | 0 |
| PF | 425736 | 0 |
| P_dmd_max | 16014 | 407 |
| S_dmd_max | 16014 | 407 |
| Er_pos_counter | 15403 | 346 |
| Er_neg_counter | 15403 | 346 |

## Medium-gap reconstruction provenance

Length counts missing slots; allocation spans length+1 intervals. Dates are naive export local time. NA scale/ratio means uniform fallback or an undefined ratio. Warning bounds: k outside [0.5,2], k_q/k outside [0.8,1.25], or reconstructed PF outside the observed surrounding-month range.

| Meter | Start | L | Active / reactive method | Donor date | k | k_q | k_q/k | PF min / max | Warnings |
|---|---|---:|---|---|---:|---:|---:|---|---|
| CLIM_SALLE_IT_(TGBT_D1) | 2022-07-24 02:30:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-17 | 0.0468 | 0.0469 | 1.0020 | 0.9569 / 0.9950 | k outside [0.5, 2] |
| CLIM_SALLE_IT_(TGBT_D1) | 2022-07-26 15:15:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-19 | 0.0000 | 0.0000 | NA | NA / NA | k outside [0.5, 2] |
| CLIM_SALLE_IT_(TGBT_D1) | 2023-04-29 00:00:00 | 96 | uniform / uniform | 2023-04-22 | NA | NA | NA | NA / NA | none |
| CLIM_SALLE_IT_(TGBT_D1) | 2023-06-11 09:00:00 | 16 | uniform / uniform | 2023-06-04 | NA | NA | NA | NA / NA | none |
| CLIM_SALLE_IT_(TGBT_D1) | 2023-06-17 15:30:00 | 10 | uniform / uniform | 2023-06-10 | NA | NA | NA | NA / NA | none |
| CLIM_SALLE_IT_(TGBT_D1) | 2023-09-20 01:30:00 | 16 | uniform / uniform | 2023-09-13 | NA | NA | NA | NA / NA | none |
| CLIM_SALLE_IT_(TGBT_D1) | 2024-08-06 10:15:00 | 93 | uniform / uniform | 2024-07-23 | NA | NA | NA | NA / NA | none |
| CLIM_SALLE_IT_(TGBT_D1) | 2024-09-08 08:45:00 | 12 | uniform / uniform | 2024-09-01 | NA | NA | NA | NA / NA | none |
| CLIM_SALLE_IT_(TGBT_D1) | 2025-12-07 09:15:00 | 11 | uniform / uniform | 2025-11-30 | NA | NA | NA | NA / NA | none |
| CLIM_SALLE_IT_(TGBT_D1) | 2026-01-30 04:45:00 | 10 | uniform / uniform | 2026-01-23 | NA | NA | NA | NA / NA | none |
| CLIM_SALLE_IT_(TGBT_D1) | 2026-02-01 04:45:00 | 12 | uniform / uniform | 2026-01-25 | NA | NA | NA | NA / NA | none |
| CLIM_TOUR_A_(TGBT_D6) | 2022-07-24 02:30:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-17 | 0.0870 | 0.0811 | 0.9324 | 0.7314 / 0.9549 | k outside [0.5, 2] |
| CLIM_TOUR_A_(TGBT_D6) | 2022-07-26 15:15:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-19 | 0.2105 | 0.1860 | 0.8837 | 0.7493 / 0.9147 | k outside [0.5, 2] |
| CLIM_TOUR_A_(TGBT_D6) | 2023-04-29 00:00:00 | 96 | uniform / uniform | 2023-04-22 | NA | NA | NA | 0.7786 / 0.7786 | none |
| CLIM_TOUR_A_(TGBT_D6) | 2023-06-11 09:00:00 | 16 | scaled_weekday / scaled_weekday | 2023-06-04 | 0.0959 | 0.0678 | 0.7070 | 0.6860 / 0.9206 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| CLIM_TOUR_A_(TGBT_D6) | 2023-06-17 15:30:00 | 10 | scaled_weekday / scaled_weekday | 2023-06-10 | 0.0000 | 0.0000 | NA | NA / NA | k outside [0.5, 2] |
| CLIM_TOUR_A_(TGBT_D6) | 2023-09-20 01:30:00 | 16 | scaled_weekday / scaled_weekday | 2023-09-13 | 0.1233 | 0.0862 | 0.6992 | 0.8195 / 0.9064 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| CLIM_TOUR_A_(TGBT_D6) | 2024-08-06 10:15:00 | 93 | scaled_weekday / uniform | 2024-07-23 | 0.0000 | NA | NA | NA / NA | k outside [0.5, 2] |
| CLIM_TOUR_A_(TGBT_D6) | 2024-09-08 08:45:00 | 12 | scaled_weekday / scaled_weekday | 2024-09-01 | 0.0318 | 0.0258 | 0.8111 | 0.8544 / 0.8855 | k outside [0.5, 2] |
| CLIM_TOUR_A_(TGBT_D6) | 2025-12-07 09:15:00 | 11 | uniform / uniform | 2025-11-30 | NA | NA | NA | NA / NA | none |
| CLIM_TOUR_A_(TGBT_D6) | 2026-01-30 04:45:00 | 10 | uniform / uniform | 2026-01-23 | NA | NA | NA | NA / NA | none |
| CLIM_TOUR_A_(TGBT_D6) | 2026-02-01 04:45:00 | 12 | uniform / uniform | 2026-01-25 | NA | NA | NA | NA / NA | none |
| EM_VIRTUAL | 2022-07-24 02:30:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-17 | 0.0649 | 0.0581 | 0.8953 | 0.9389 / 0.9621 | k outside [0.5, 2] |
| EM_VIRTUAL | 2022-07-26 15:15:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-19 | 0.1185 | 0.1350 | 1.1385 | 0.9196 / 0.9422 | k outside [0.5, 2] |
| EM_VIRTUAL | 2023-04-29 00:00:00 | 96 | scaled_weekday / scaled_weekday | 2023-04-22 | 1.7867 | 0.6239 | 0.3492 | 0.9274 / 0.9706 | k_q/k outside [0.8, 1.25] |
| EM_VIRTUAL | 2023-06-11 09:00:00 | 16 | scaled_weekday / scaled_weekday | 2023-06-04 | 0.1410 | 0.1235 | 0.8758 | 0.9725 / 0.9946 | k outside [0.5, 2] |
| EM_VIRTUAL | 2023-06-17 15:30:00 | 10 | scaled_weekday / scaled_weekday | 2023-06-10 | 0.0661 | -0.0585 | -0.8849 | 0.9807 / 0.9987 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| EM_VIRTUAL | 2023-09-20 01:30:00 | 16 | scaled_weekday / scaled_weekday | 2023-09-13 | 0.0516 | 0.0490 | 0.9510 | 0.9645 / 0.9937 | k outside [0.5, 2] |
| EM_VIRTUAL | 2024-08-06 10:15:00 | 93 | scaled_weekday / scaled_weekday | 2024-07-23 | 0.4525 | -0.2046 | -0.4520 | 0.9854 / 0.9990 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| EM_VIRTUAL | 2024-09-08 08:45:00 | 12 | scaled_weekday / scaled_weekday | 2024-09-01 | 0.0557 | 0.0409 | 0.7340 | 0.9587 / 0.9747 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| EM_VIRTUAL | 2025-01-25 13:15:00 | 7 | scaled_weekday / scaled_weekday | 2025-01-18 | 0.1576 | 0.4245 | 2.6931 | 0.8981 / 0.9164 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| EM_VIRTUAL | 2025-12-07 09:15:00 | 11 | scaled_weekday / scaled_weekday | 2025-11-30 | 0.0812 | 0.0812 | 1.0009 | 0.8115 / 0.8376 | k outside [0.5, 2] |
| EM_VIRTUAL | 2026-01-30 04:45:00 | 10 | scaled_weekday / scaled_weekday | 2026-01-23 | 0.9590 | 1.0273 | 1.0713 | 0.9283 / 0.9924 | none |
| EM_VIRTUAL | 2026-02-01 04:45:00 | 12 | scaled_weekday / scaled_weekday | 2026-01-25 | 1.4611 | -1.3827 | -0.9463 | 0.9466 / 0.9935 | k_q/k outside [0.8, 1.25] |
| ONDULEUR_1_(TGBT_DXX) | 2022-07-24 02:30:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-17 | 1.0220 | 1.0517 | 1.0291 | 0.9459 / 0.9685 | none |
| ONDULEUR_1_(TGBT_DXX) | 2022-07-26 15:15:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-19 | 0.0753 | 0.0508 | 0.6755 | 0.9756 / 0.9860 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| ONDULEUR_1_(TGBT_DXX) | 2023-04-29 00:00:00 | 96 | scaled_weekday / scaled_weekday | 2023-04-22 | 1.0297 | 1.0000 | 0.9712 | 0.8744 / 0.9396 | none |
| ONDULEUR_1_(TGBT_DXX) | 2023-06-11 09:00:00 | 16 | scaled_weekday / scaled_weekday | 2023-06-04 | 0.0794 | 0.0615 | 0.7754 | 0.9143 / 0.9602 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| ONDULEUR_1_(TGBT_DXX) | 2023-06-17 15:30:00 | 10 | scaled_weekday / scaled_weekday | 2023-06-10 | 0.4337 | 0.4091 | 0.9432 | 0.8803 / 0.9045 | k outside [0.5, 2] |
| ONDULEUR_1_(TGBT_DXX) | 2023-09-20 01:30:00 | 16 | scaled_weekday / scaled_weekday | 2023-09-13 | 1.0317 | 1.0615 | 1.0289 | 0.8620 / 0.9330 | PF outside observed surrounding-month range |
| ONDULEUR_1_(TGBT_DXX) | 2024-08-06 10:15:00 | 93 | scaled_weekday / scaled_weekday | 2024-07-23 | 0.9435 | 1.0000 | 1.0598 | 0.8836 / 0.9752 | PF outside observed surrounding-month range |
| ONDULEUR_1_(TGBT_DXX) | 2024-09-08 08:45:00 | 12 | scaled_weekday / scaled_weekday | 2024-09-01 | 1.0484 | 1.0600 | 1.0111 | 0.9121 / 0.9569 | none |
| ONDULEUR_1_(TGBT_DXX) | 2024-12-28 02:30:00 | 28 | scaled_weekday / scaled_weekday | 2024-12-21 | 0.0538 | 0.0273 | 0.5068 | 0.9605 / 0.9824 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| ONDULEUR_1_(TGBT_DXX) | 2025-02-01 21:45:00 | 38 | scaled_weekday / scaled_weekday | 2025-01-25 | 0.0129 | -0.0000 | -0.0000 | 1.0000 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| ONDULEUR_1_(TGBT_DXX) | 2025-02-03 02:00:00 | 17 | scaled_weekday / scaled_weekday | 2025-01-27 | 0.0000 | -0.0000 | NA | NA / NA | k outside [0.5, 2] |
| ONDULEUR_1_(TGBT_DXX) | 2025-02-08 07:30:00 | 21 | scaled_weekday / scaled_weekday | 2025-02-01 | 0.0064 | -0.0000 | -0.0000 | 1.0000 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| ONDULEUR_1_(TGBT_DXX) | 2025-08-22 04:00:00 | 7 | scaled_weekday / scaled_weekday | 2025-08-15 | 0.0781 | 0.0323 | 0.4129 | 0.9733 / 0.9847 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| ONDULEUR_1_(TGBT_DXX) | 2025-12-07 09:15:00 | 11 | scaled_weekday / scaled_weekday | 2025-11-30 | 0.3085 | 0.2667 | 0.8644 | 0.8966 / 0.9513 | k outside [0.5, 2] |
| ONDULEUR_1_(TGBT_DXX) | 2026-01-30 04:45:00 | 10 | scaled_weekday / scaled_weekday | 2026-01-23 | 0.8257 | 0.9762 | 1.1823 | 0.8852 / 0.9425 | none |
| ONDULEUR_1_(TGBT_DXX) | 2026-02-01 04:45:00 | 12 | scaled_weekday / scaled_weekday | 2026-01-25 | 1.1215 | 1.0417 | 0.9288 | 0.8833 / 0.9553 | PF outside observed surrounding-month range |
| ONDULEUR_1_(TGBT_DXX) | 2026-02-19 12:30:00 | 15 | scaled_weekday / scaled_weekday | 2026-02-12 | 0.0519 | 0.0323 | 0.6210 | 0.9640 / 0.9831 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| ONDULEUR_2_(TGBT_DXX) | 2022-07-24 02:30:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-17 | 1.0000 | 1.0351 | 1.0351 | 0.2348 / 0.5415 | PF outside observed surrounding-month range |
| ONDULEUR_2_(TGBT_DXX) | 2022-07-26 15:15:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-19 | 0.1538 | 0.0517 | 0.3362 | 0.5967 / 0.8929 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| ONDULEUR_2_(TGBT_DXX) | 2023-04-29 00:00:00 | 96 | scaled_weekday / scaled_weekday | 2023-04-22 | 1.0352 | 0.9896 | 0.9560 | 0.8258 / 0.9253 | PF outside observed surrounding-month range |
| ONDULEUR_2_(TGBT_DXX) | 2023-06-11 09:00:00 | 16 | scaled_weekday / scaled_weekday | 2023-06-04 | 0.0684 | 0.0735 | 1.0754 | 0.8127 / 0.8520 | k outside [0.5, 2] |
| ONDULEUR_2_(TGBT_DXX) | 2023-06-17 15:30:00 | 10 | scaled_weekday / scaled_weekday | 2023-06-10 | 0.4342 | 0.4091 | 0.9421 | 0.8468 / 0.8805 | k outside [0.5, 2] |
| ONDULEUR_2_(TGBT_DXX) | 2023-09-20 01:30:00 | 16 | scaled_weekday / scaled_weekday | 2023-09-13 | 1.0259 | 1.0441 | 1.0178 | 0.8275 / 0.8644 | PF outside observed surrounding-month range |
| ONDULEUR_2_(TGBT_DXX) | 2024-08-06 10:15:00 | 93 | scaled_weekday / scaled_weekday | 2024-07-23 | 0.9394 | 0.9948 | 1.0589 | 0.8556 / 0.9624 | PF outside observed surrounding-month range |
| ONDULEUR_2_(TGBT_DXX) | 2024-09-08 08:45:00 | 12 | scaled_weekday / scaled_weekday | 2024-09-01 | 1.0603 | 1.0385 | 0.9794 | 0.8981 / 0.9169 | none |
| ONDULEUR_2_(TGBT_DXX) | 2024-12-27 15:15:00 | 12 | scaled_weekday / scaled_weekday | 2024-12-20 | 0.0286 | 0.0192 | 0.6731 | 0.9333 / 0.9581 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| ONDULEUR_2_(TGBT_DXX) | 2024-12-28 02:30:00 | 28 | scaled_weekday / scaled_weekday | 2024-12-21 | 0.0493 | 0.0261 | 0.5296 | 0.9571 / 0.9752 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| ONDULEUR_2_(TGBT_DXX) | 2025-02-01 18:00:00 | 53 | scaled_weekday / scaled_weekday | 2025-01-25 | 0.0075 | -0.0000 | -0.0000 | 1.0000 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| ONDULEUR_2_(TGBT_DXX) | 2025-02-03 02:00:00 | 17 | scaled_weekday / scaled_weekday | 2025-01-27 | 0.0929 | 0.0282 | 0.3034 | 0.9802 / 0.9917 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| ONDULEUR_2_(TGBT_DXX) | 2025-08-22 04:00:00 | 7 | scaled_weekday / scaled_weekday | 2025-08-15 | 0.0833 | 0.0313 | 0.3750 | 0.9778 / 0.9864 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| ONDULEUR_2_(TGBT_DXX) | 2025-12-07 09:15:00 | 11 | scaled_weekday / scaled_weekday | 2025-11-30 | 0.3068 | 0.2553 | 0.8322 | 0.9031 / 0.9419 | k outside [0.5, 2] |
| ONDULEUR_2_(TGBT_DXX) | 2026-01-30 04:45:00 | 10 | scaled_weekday / scaled_weekday | 2026-01-23 | 1.0000 | 1.0233 | 1.0233 | 0.8633 / 0.9158 | none |
| ONDULEUR_2_(TGBT_DXX) | 2026-02-01 04:45:00 | 12 | scaled_weekday / scaled_weekday | 2026-01-25 | 0.9900 | 1.0196 | 1.0299 | 0.8618 / 0.9328 | PF outside observed surrounding-month range |
| PV_(CHAUFFERIE_PROV.) | 2022-07-24 02:30:00 | 14 | uniform / uniform | 2022-07-17 | NA | NA | NA | NA / NA | none |
| PV_(CHAUFFERIE_PROV.) | 2022-07-26 15:15:00 | 14 | uniform / uniform | 2022-07-19 | NA | NA | NA | NA / NA | none |
| PV_(CHAUFFERIE_PROV.) | 2023-04-29 00:00:00 | 96 | uniform / uniform | 2023-04-22 | NA | NA | NA | NA / NA | none |
| PV_(CHAUFFERIE_PROV.) | 2023-06-11 09:00:00 | 16 | uniform / uniform | 2023-06-04 | NA | NA | NA | NA / NA | none |
| PV_(CHAUFFERIE_PROV.) | 2023-06-17 15:30:00 | 10 | uniform / uniform | 2023-06-10 | NA | NA | NA | NA / NA | none |
| PV_(CHAUFFERIE_PROV.) | 2023-09-20 01:30:00 | 16 | uniform / uniform | 2023-09-13 | NA | NA | NA | NA / NA | none |
| PV_(CHAUFFERIE_PROV.) | 2024-08-06 10:15:00 | 93 | uniform / uniform | 2024-07-23 | NA | NA | NA | NA / NA | none |
| PV_(CHAUFFERIE_PROV.) | 2024-09-08 08:45:00 | 12 | uniform / uniform | 2024-09-01 | NA | NA | NA | NA / NA | none |
| PV_(CHAUFFERIE_PROV.) | 2025-12-07 09:15:00 | 11 | uniform / uniform | 2025-11-30 | NA | NA | NA | 0.7071 / 0.7071 | none |
| PV_(CHAUFFERIE_PROV.) | 2026-01-30 04:45:00 | 10 | uniform / uniform | 2026-01-23 | NA | NA | NA | NA / NA | none |
| PV_(CHAUFFERIE_PROV.) | 2026-02-01 04:45:00 | 12 | uniform / uniform | 2026-01-25 | NA | NA | NA | NA / NA | none |
| SALLE_B101_(A._MEZAN_TOUR_B) | 2022-07-24 02:30:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-17 | 0.0370 | -0.0000 | -0.0000 | 1.0000 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| SALLE_B101_(A._MEZAN_TOUR_B) | 2022-07-26 15:15:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-19 | 0.0357 | -0.0000 | -0.0000 | 1.0000 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| SALLE_B101_(A._MEZAN_TOUR_B) | 2023-04-29 00:00:00 | 96 | scaled_weekday / scaled_weekday | 2023-04-22 | 1.0055 | 0.9818 | 0.9765 | 0.7155 / 1.0000 | PF outside observed surrounding-month range |
| SALLE_B101_(A._MEZAN_TOUR_B) | 2023-06-11 09:00:00 | 16 | scaled_weekday / scaled_weekday | 2023-06-04 | 0.0625 | 0.1250 | 2.0000 | 0.4472 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| SALLE_B101_(A._MEZAN_TOUR_B) | 2023-06-17 15:30:00 | 10 | scaled_weekday / scaled_weekday | 2023-06-10 | 0.0952 | 0.1667 | 1.7500 | 0.4961 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| SALLE_B101_(A._MEZAN_TOUR_B) | 2023-09-20 01:30:00 | 16 | scaled_weekday / scaled_weekday | 2023-09-13 | 0.0625 | 0.1111 | 1.7778 | 0.4903 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| SALLE_B101_(A._MEZAN_TOUR_B) | 2024-07-13 08:45:00 | 14 | scaled_weekday / scaled_weekday | 2024-07-06 | 0.0357 | -0.0000 | -0.0000 | 1.0000 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| SALLE_B101_(A._MEZAN_TOUR_B) | 2024-07-20 09:15:00 | 18 | scaled_weekday / scaled_weekday | 2024-07-06 | 0.0278 | -0.0000 | -0.0000 | 1.0000 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| SALLE_B101_(A._MEZAN_TOUR_B) | 2024-08-06 10:15:00 | 93 | scaled_weekday / scaled_weekday | 2024-07-23 | 0.9832 | 1.0400 | 1.0577 | 0.6870 / 1.0000 | PF outside observed surrounding-month range |
| SALLE_B101_(A._MEZAN_TOUR_B) | 2024-09-08 08:45:00 | 12 | scaled_weekday / scaled_weekday | 2024-09-01 | 0.0417 | -0.0000 | -0.0000 | 1.0000 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| SALLE_B101_(A._MEZAN_TOUR_B) | 2025-12-07 09:15:00 | 11 | scaled_weekday / scaled_weekday | 2025-11-30 | 0.0909 | 0.1667 | 1.8333 | 0.4789 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| SALLE_B101_(A._MEZAN_TOUR_B) | 2026-01-30 04:45:00 | 10 | scaled_weekday / scaled_weekday | 2026-01-23 | 1.0000 | 1.0000 | 1.0000 | 0.7071 / 1.0000 | PF outside observed surrounding-month range |
| SALLE_B101_(A._MEZAN_TOUR_B) | 2026-02-01 04:45:00 | 12 | scaled_weekday / scaled_weekday | 2026-01-25 | 0.9583 | 1.1429 | 1.1925 | 0.6425 / 1.0000 | PF outside observed surrounding-month range |
| SALLE_B112_(A._MEZAN_TOUR_B) | 2022-07-24 02:30:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-17 | 0.0000 | -0.0000 | NA | NA / NA | k outside [0.5, 2] |
| SALLE_B112_(A._MEZAN_TOUR_B) | 2022-07-26 15:15:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-19 | 0.0000 | -0.0000 | NA | NA / NA | k outside [0.5, 2] |
| SALLE_B112_(A._MEZAN_TOUR_B) | 2023-04-29 00:00:00 | 96 | scaled_weekday / scaled_weekday | 2023-04-22 | 1.3333 | 1.0000 | 0.7500 | 0.0000 / 1.0000 | k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| SALLE_B112_(A._MEZAN_TOUR_B) | 2023-06-11 09:00:00 | 16 | scaled_weekday / scaled_weekday | 2023-06-04 | 0.0000 | 0.5000 | NA | 0.0000 / 0.0000 | k outside [0.5, 2]; k=0 but k_q!=0: ratio undefined; PF outside observed surrounding-month range |
| SALLE_B112_(A._MEZAN_TOUR_B) | 2023-06-17 15:30:00 | 10 | uniform / scaled_weekday | 2023-06-10 | NA | -0.0000 | NA | NA / NA | none |
| SALLE_B112_(A._MEZAN_TOUR_B) | 2023-09-20 01:30:00 | 16 | uniform / scaled_weekday | 2023-09-13 | NA | -0.0000 | NA | 1.0000 / 1.0000 | none |
| SALLE_B112_(A._MEZAN_TOUR_B) | 2024-07-13 08:45:00 | 14 | scaled_weekday / scaled_weekday | 2024-07-06 | 0.0000 | -0.0000 | NA | NA / NA | k outside [0.5, 2] |
| SALLE_B112_(A._MEZAN_TOUR_B) | 2024-07-20 08:15:00 | 22 | scaled_weekday / scaled_weekday | 2024-07-06 | 0.0000 | -0.0000 | NA | NA / NA | k outside [0.5, 2] |
| SALLE_B112_(A._MEZAN_TOUR_B) | 2024-08-06 10:15:00 | 93 | scaled_weekday / scaled_weekday | 2024-07-23 | 1.0000 | 0.9167 | 0.9167 | 0.0000 / 1.0000 | PF outside observed surrounding-month range |
| SALLE_B112_(A._MEZAN_TOUR_B) | 2024-09-08 08:45:00 | 12 | uniform / scaled_weekday | 2024-09-01 | NA | -0.0000 | NA | NA / NA | none |
| SALLE_B112_(A._MEZAN_TOUR_B) | 2025-12-07 09:15:00 | 11 | uniform / scaled_weekday | 2025-11-30 | NA | 1.0000 | NA | 0.0000 / 0.0000 | PF outside observed surrounding-month range |
| SALLE_B112_(A._MEZAN_TOUR_B) | 2026-01-30 04:45:00 | 10 | scaled_weekday / scaled_weekday | 2026-01-23 | 0.0000 | 1.0000 | NA | 0.0000 / 0.0000 | k outside [0.5, 2]; k=0 but k_q!=0: ratio undefined; PF outside observed surrounding-month range |
| SALLE_B112_(A._MEZAN_TOUR_B) | 2026-02-01 04:45:00 | 12 | scaled_weekday / scaled_weekday | 2026-01-25 | 1.0000 | 1.0000 | 1.0000 | 0.0000 / 1.0000 | PF outside observed surrounding-month range |
| SALLE_B201_(A_1_ETAGE_TOUR_B) | 2022-07-24 02:30:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-17 | 0.0588 | 0.0667 | 1.1333 | 0.8700 / 0.9355 | k outside [0.5, 2]; PF outside observed surrounding-month range |
| SALLE_B201_(A_1_ETAGE_TOUR_B) | 2022-07-26 15:15:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-19 | 0.0588 | -0.0000 | -0.0000 | 1.0000 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| SALLE_B201_(A_1_ETAGE_TOUR_B) | 2023-04-29 00:00:00 | 96 | scaled_weekday / scaled_weekday | 2023-04-22 | 1.2202 | 1.2800 | 1.0490 | 0.6900 / 0.9440 | PF outside observed surrounding-month range |
| SALLE_B201_(A_1_ETAGE_TOUR_B) | 2023-06-11 09:00:00 | 16 | scaled_weekday / scaled_weekday | 2023-06-04 | 0.0937 | 0.0667 | 0.7111 | 0.8150 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| SALLE_B201_(A_1_ETAGE_TOUR_B) | 2023-06-17 15:30:00 | 10 | scaled_weekday / scaled_weekday | 2023-06-10 | 0.0909 | 0.0833 | 0.9167 | 0.7372 / 0.9091 | k outside [0.5, 2]; PF outside observed surrounding-month range |
| SALLE_B201_(A_1_ETAGE_TOUR_B) | 2023-09-20 01:30:00 | 16 | scaled_weekday / scaled_weekday | 2023-09-13 | 0.0294 | -0.0000 | -0.0000 | 1.0000 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| SALLE_B201_(A_1_ETAGE_TOUR_B) | 2024-07-13 08:45:00 | 14 | scaled_weekday / scaled_weekday | 2024-07-06 | 0.0294 | -0.0000 | -0.0000 | 1.0000 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| SALLE_B201_(A_1_ETAGE_TOUR_B) | 2024-07-20 08:15:00 | 22 | scaled_weekday / scaled_weekday | 2024-07-06 | 0.0192 | -0.0000 | -0.0000 | 1.0000 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| SALLE_B201_(A_1_ETAGE_TOUR_B) | 2024-08-06 10:15:00 | 93 | scaled_weekday / scaled_weekday | 2024-07-23 | 1.0166 | 1.0000 | 0.9837 | 0.7129 / 1.0000 | PF outside observed surrounding-month range |
| SALLE_B201_(A_1_ETAGE_TOUR_B) | 2024-09-08 08:45:00 | 12 | scaled_weekday / scaled_weekday | 2024-09-01 | 0.0400 | 0.0909 | 2.2727 | 0.6606 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| SALLE_B201_(A_1_ETAGE_TOUR_B) | 2025-12-07 09:15:00 | 11 | scaled_weekday / scaled_weekday | 2025-11-30 | 0.0800 | 0.0667 | 0.8333 | 0.7682 / 0.9635 | k outside [0.5, 2]; PF outside observed surrounding-month range |
| SALLE_B201_(A_1_ETAGE_TOUR_B) | 2026-01-30 04:45:00 | 10 | scaled_weekday / scaled_weekday | 2026-01-23 | 1.0000 | 1.0000 | 1.0000 | 0.7071 / 0.8944 | PF outside observed surrounding-month range |
| SALLE_B201_(A_1_ETAGE_TOUR_B) | 2026-02-01 04:45:00 | 12 | scaled_weekday / scaled_weekday | 2026-01-25 | 1.0000 | 1.0000 | 1.0000 | 0.7071 / 0.8944 | PF outside observed surrounding-month range |
| TGBT_TR1 | 2022-07-24 02:30:00 | 14 | uniform / uniform | 2022-07-17 | NA | NA | NA | NA / NA | none |
| TGBT_TR1 | 2022-07-26 15:15:00 | 14 | uniform / uniform | 2022-07-19 | NA | NA | NA | NA / NA | none |
| TGBT_TR1 | 2023-04-29 00:00:00 | 96 | uniform / uniform | 2023-04-22 | NA | NA | NA | NA / NA | none |
| TGBT_TR1 | 2023-06-11 09:00:00 | 16 | uniform / uniform | 2023-06-04 | NA | NA | NA | 0.9548 / 0.9548 | PF outside observed surrounding-month range |
| TGBT_TR1 | 2023-06-17 15:30:00 | 10 | uniform / uniform | 2023-06-10 | NA | NA | NA | NA / NA | none |
| TGBT_TR1 | 2023-09-20 01:30:00 | 16 | scaled_weekday / scaled_weekday | 2023-09-13 | 0.0500 | 0.0461 | 0.9221 | 0.9666 / 0.9940 | k outside [0.5, 2] |
| TGBT_TR1 | 2024-08-06 10:15:00 | 93 | uniform / uniform | 2024-07-23 | NA | NA | NA | NA / NA | none |
| TGBT_TR1 | 2024-09-08 08:45:00 | 12 | uniform / uniform | 2024-09-01 | NA | NA | NA | NA / NA | none |
| TGBT_TR1 | 2025-12-07 09:15:00 | 11 | uniform / uniform | 2025-11-30 | NA | NA | NA | 0.8437 / 0.8437 | none |
| TGBT_TR1 | 2026-01-30 04:45:00 | 10 | scaled_weekday / scaled_weekday | 2026-01-23 | 0.9590 | 1.0273 | 1.0713 | 0.9283 / 0.9924 | none |
| TGBT_TR1 | 2026-02-01 04:45:00 | 12 | scaled_weekday / scaled_weekday | 2026-01-25 | 1.4611 | -1.3827 | -0.9463 | 0.9466 / 0.9935 | k_q/k outside [0.8, 1.25] |
| TGBT_TR2 | 2022-07-24 02:30:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-17 | 0.0649 | 0.0581 | 0.8953 | 0.9389 / 0.9621 | k outside [0.5, 2] |
| TGBT_TR2 | 2022-07-26 15:15:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-19 | 0.1185 | 0.1350 | 1.1385 | 0.9196 / 0.9422 | k outside [0.5, 2] |
| TGBT_TR2 | 2023-04-29 00:00:00 | 96 | scaled_weekday / scaled_weekday | 2023-04-22 | 1.7867 | 0.6239 | 0.3492 | 0.9274 / 0.9706 | k_q/k outside [0.8, 1.25] |
| TGBT_TR2 | 2023-06-11 09:00:00 | 16 | scaled_weekday / scaled_weekday | 2023-06-04 | 0.0621 | 0.0097 | 0.1559 | 0.9991 / 0.9998 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| TGBT_TR2 | 2023-06-17 15:30:00 | 10 | scaled_weekday / scaled_weekday | 2023-06-10 | 0.0661 | -0.0585 | -0.8849 | 0.9807 / 0.9987 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| TGBT_TR2 | 2023-09-20 01:30:00 | 16 | uniform / uniform | 2023-09-13 | NA | NA | NA | 0.9285 / 0.9285 | PF outside observed surrounding-month range |
| TGBT_TR2 | 2024-08-06 10:15:00 | 93 | scaled_weekday / scaled_weekday | 2024-07-23 | 0.4525 | -0.2046 | -0.4520 | 0.9854 / 0.9990 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| TGBT_TR2 | 2024-09-08 08:45:00 | 12 | scaled_weekday / scaled_weekday | 2024-09-01 | 0.0557 | 0.0409 | 0.7340 | 0.9587 / 0.9747 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| TGBT_TR2 | 2025-12-07 09:15:00 | 11 | scaled_weekday / scaled_weekday | 2025-11-30 | 0.0705 | 0.0714 | 1.0127 | 0.8082 / 0.8346 | k outside [0.5, 2] |
| TGBT_TR2 | 2026-01-30 04:45:00 | 10 | uniform / uniform | 2026-01-23 | NA | NA | NA | NA / NA | none |
| TGBT_TR2 | 2026-02-01 04:45:00 | 12 | uniform / uniform | 2026-01-25 | NA | NA | NA | NA / NA | none |
| TOUR_A_(TGBT_D14) | 2022-07-24 02:30:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-17 | 0.0530 | 0.0506 | 0.9548 | 0.8130 / 0.8834 | k outside [0.5, 2] |
| TOUR_A_(TGBT_D14) | 2022-07-26 15:15:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-19 | 0.1478 | 0.0845 | 0.5717 | 0.9258 / 0.9615 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| TOUR_A_(TGBT_D14) | 2023-04-29 00:00:00 | 96 | scaled_weekday / scaled_weekday | 2023-04-22 | 1.2689 | 1.0922 | 0.8608 | 0.6808 / 0.8673 | none |
| TOUR_A_(TGBT_D14) | 2023-06-11 09:00:00 | 16 | scaled_weekday / scaled_weekday | 2023-06-04 | 0.2246 | 0.1667 | 0.7419 | 0.9530 / 0.9832 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| TOUR_A_(TGBT_D14) | 2023-06-17 15:30:00 | 10 | scaled_weekday / scaled_weekday | 2023-06-10 | 0.0458 | 0.0323 | 0.7043 | 0.9350 / 0.9735 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| TOUR_A_(TGBT_D14) | 2023-09-20 01:30:00 | 16 | scaled_weekday / scaled_weekday | 2023-09-13 | 0.1122 | 0.0641 | 0.5711 | 0.8684 / 0.9346 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| TOUR_A_(TGBT_D14) | 2024-08-06 10:15:00 | 93 | scaled_weekday / scaled_weekday | 2024-07-23 | 0.6171 | 0.6741 | 1.0923 | 0.7229 / 0.9057 | PF outside observed surrounding-month range |
| TOUR_A_(TGBT_D14) | 2024-09-08 08:45:00 | 12 | scaled_weekday / scaled_weekday | 2024-09-01 | 0.0864 | 0.0577 | 0.6676 | 0.9136 / 0.9486 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| TOUR_A_(TGBT_D14) | 2025-12-07 09:15:00 | 11 | scaled_weekday / scaled_weekday | 2025-11-30 | 0.0602 | 0.0556 | 0.9222 | 0.6808 / 0.8664 | k outside [0.5, 2] |
| TOUR_A_(TGBT_D14) | 2026-01-30 04:45:00 | 10 | scaled_weekday / scaled_weekday | 2026-01-23 | 1.0000 | 1.0377 | 1.0377 | 0.6105 / 0.7694 | none |
| TOUR_A_(TGBT_D14) | 2026-02-01 04:45:00 | 12 | scaled_weekday / scaled_weekday | 2026-01-25 | 1.0000 | 1.0167 | 1.0167 | 0.5936 / 0.7012 | PF outside observed surrounding-month range |
| TOUR_C_(TGBT_D10) | 2022-07-24 02:30:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-17 | 0.0938 | -0.0000 | -0.0000 | 1.0000 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| TOUR_C_(TGBT_D10) | 2022-07-26 15:15:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-19 | 0.1538 | 0.1250 | 0.8125 | 0.8539 / 0.9652 | k outside [0.5, 2] |
| TOUR_C_(TGBT_D10) | 2023-04-29 00:00:00 | 96 | scaled_weekday / scaled_weekday | 2023-04-22 | 2.5568 | 1.4000 | 0.5476 | 0.0000 / 0.9645 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| TOUR_C_(TGBT_D10) | 2023-06-11 09:00:00 | 16 | scaled_weekday / scaled_weekday | 2023-06-04 | 0.0588 | 0.0465 | 0.7907 | 0.5345 / 0.8846 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| TOUR_C_(TGBT_D10) | 2023-06-17 15:30:00 | 10 | scaled_weekday / scaled_weekday | 2023-06-10 | 0.0417 | 0.0175 | 0.4211 | 0.8186 / 0.9216 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| TOUR_C_(TGBT_D10) | 2023-09-20 01:30:00 | 16 | scaled_weekday / scaled_weekday | 2023-09-13 | 0.0870 | 0.0769 | 0.8846 | 0.4921 / 0.9145 | k outside [0.5, 2] |
| TOUR_C_(TGBT_D10) | 2024-08-06 10:15:00 | 93 | scaled_weekday / scaled_weekday | 2024-07-23 | 0.0042 | -0.0000 | -0.0000 | 1.0000 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| TOUR_C_(TGBT_D10) | 2024-09-08 08:45:00 | 12 | scaled_weekday / scaled_weekday | 2024-09-01 | 0.4615 | -0.0000 | -0.0000 | 1.0000 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| TOUR_C_(TGBT_D10) | 2025-12-07 09:15:00 | 11 | scaled_weekday / scaled_weekday | 2025-11-30 | 0.0833 | 0.1250 | 1.5000 | 0.3162 / 0.9363 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| TOUR_C_(TGBT_D10) | 2026-01-30 04:45:00 | 10 | scaled_weekday / scaled_weekday | 2026-01-23 | 0.5000 | -0.0000 | -0.0000 | 1.0000 / 1.0000 | k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| TOUR_C_(TGBT_D10) | 2026-02-01 04:45:00 | 12 | scaled_weekday / scaled_weekday | 2026-01-25 | 0.3000 | 0.1765 | 0.5882 | 0.0000 / 0.8619 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| Tour_B_(TGBT_D5) | 2022-07-24 02:30:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-17 | 0.0619 | 0.0429 | 0.6918 | 0.8965 / 0.9451 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| Tour_B_(TGBT_D5) | 2022-07-26 15:15:00 | 14 | scaled_weekday / scaled_weekday | 2022-07-19 | 0.0791 | 0.0541 | 0.6830 | 0.9197 / 0.9569 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| Tour_B_(TGBT_D5) | 2023-04-29 00:00:00 | 96 | scaled_weekday / scaled_weekday | 2023-04-22 | 1.2158 | 1.1155 | 0.9175 | 0.7369 / 0.9089 | none |
| Tour_B_(TGBT_D5) | 2023-06-11 09:00:00 | 16 | scaled_weekday / scaled_weekday | 2023-06-04 | 0.0663 | 0.0795 | 1.2004 | 0.7808 / 0.8574 | k outside [0.5, 2] |
| Tour_B_(TGBT_D5) | 2023-06-17 15:30:00 | 10 | scaled_weekday / scaled_weekday | 2023-06-10 | 0.1084 | 0.0758 | 0.6987 | 0.8579 / 0.8858 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| Tour_B_(TGBT_D5) | 2023-09-20 01:30:00 | 16 | scaled_weekday / scaled_weekday | 2023-09-13 | 0.0787 | 0.0562 | 0.7135 | 0.8531 / 0.9419 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25] |
| Tour_B_(TGBT_D5) | 2024-08-06 10:15:00 | 93 | scaled_weekday / scaled_weekday | 2024-07-23 | 0.8609 | 0.8979 | 1.0430 | 0.8019 / 0.9350 | none |
| Tour_B_(TGBT_D5) | 2024-09-08 08:45:00 | 12 | scaled_weekday / scaled_weekday | 2024-09-01 | 0.0290 | 0.0893 | 3.0804 | 0.2567 / 1.0000 | k outside [0.5, 2]; k_q/k outside [0.8, 1.25]; PF outside observed surrounding-month range |
| Tour_B_(TGBT_D5) | 2025-12-07 09:15:00 | 11 | scaled_weekday / scaled_weekday | 2025-11-30 | 0.0909 | 0.0777 | 0.8544 | 0.6732 / 0.7603 | k outside [0.5, 2] |
| Tour_B_(TGBT_D5) | 2026-01-30 04:45:00 | 10 | scaled_weekday / scaled_weekday | 2026-01-23 | 1.0222 | 0.9900 | 0.9685 | 0.6369 / 0.7183 | none |
| Tour_B_(TGBT_D5) | 2026-02-01 04:45:00 | 12 | scaled_weekday / scaled_weekday | 2026-01-25 | 0.9901 | 1.0000 | 1.0100 | 0.5696 / 0.7036 | none |

## Longest remaining primary-channel gaps

| Meter | Channel | First missing | Last missing | Slots |
|---|---|---|---|---:|
| TOUR_C_(TGBT_D10) | dEa | 2024-12-27 15:00:00 | 2025-01-25 15:00:00 | 2785 |
| TOUR_A_(TGBT_D14) | dEa | 2024-12-27 15:00:00 | 2025-01-25 15:00:00 | 2785 |
| TOUR_C_(TGBT_D10) | Q_avg | 2024-12-27 15:00:00 | 2025-01-25 14:45:00 | 2784 |
| TOUR_C_(TGBT_D10) | P_avg | 2024-12-27 15:00:00 | 2025-01-25 14:45:00 | 2784 |
| TOUR_C_(TGBT_D10) | Ea_counter | 2024-12-27 15:00:00 | 2025-01-25 14:45:00 | 2784 |
| TOUR_A_(TGBT_D14) | Q_avg | 2024-12-27 15:00:00 | 2025-01-25 14:45:00 | 2784 |
| TOUR_A_(TGBT_D14) | P_avg | 2024-12-27 15:00:00 | 2025-01-25 14:45:00 | 2784 |
| TOUR_A_(TGBT_D14) | Ea_counter | 2024-12-27 15:00:00 | 2025-01-25 14:45:00 | 2784 |
| ONDULEUR_1_(TGBT_DXX) | dEa | 2025-02-20 09:30:00 | 2025-03-08 17:30:00 | 1569 |
| ONDULEUR_1_(TGBT_DXX) | Q_avg | 2025-02-20 09:30:00 | 2025-03-08 17:15:00 | 1568 |
| ONDULEUR_1_(TGBT_DXX) | P_avg | 2025-02-20 09:30:00 | 2025-03-08 17:15:00 | 1568 |
| ONDULEUR_1_(TGBT_DXX) | Ea_counter | 2025-02-20 09:30:00 | 2025-03-08 17:15:00 | 1568 |

## EM_VIRTUAL monthly totals and peaks

Totals include flagged reconstructions and exclude remaining NaNs. They are not full consumption estimates where gaps remain.

| Month | Total dEa kWh | Max P_avg kW | Max S_avg kVA | Imputed rows |
|---|---:|---:|---:|---:|
| 2022-07 | 75049.800 | 202.950 | 212.917 | 30 |
| 2022-08 | 84223.700 | 284.950 | 302.538 | 2 |
| 2022-09 | 79320.000 | 223.240 | 238.059 | 5 |
| 2022-10 | 51190.000 | 136.230 | 144.666 | 0 |
| 2022-11 | 26114.900 | 63.620 | 65.849 | 0 |
| 2022-12 | 21688.500 | 60.050 | 62.340 | 0 |
| 2023-01 | 22378.700 | 64.840 | 67.300 | 0 |
| 2023-02 | 24601.200 | 91.650 | 92.440 | 0 |
| 2023-03 | 23108.900 | 71.830 | 72.639 | 2 |
| 2023-04 | 18861.200 | 66.400 | 66.594 | 97 |
| 2023-05 | 34839.300 | 104.640 | 110.140 | 0 |
| 2023-06 | 43871.700 | 197.120 | 210.934 | 28 |
| 2023-07 | 63234.500 | 214.360 | 225.070 | 4 |
| 2023-08 | 42535.500 | 129.390 | 136.667 | 6 |
| 2023-09 | 57225.200 | 193.410 | 201.808 | 22 |
| 2023-10 | 52987.000 | 169.160 | 177.750 | 0 |
| 2023-11 | 27010.400 | 125.660 | 131.855 | 0 |
| 2023-12 | 23376.700 | 71.310 | 72.147 | 0 |
| 2024-01 | 30289.300 | 87.540 | 88.804 | 0 |
| 2024-02 | 27969.900 | 74.020 | 74.640 | 0 |
| 2024-03 | 25194.700 | 66.610 | 67.191 | 0 |
| 2024-04 | 24094.700 | 95.310 | 98.112 | 0 |
| 2024-05 | 28556.100 | 131.240 | 139.612 | 0 |
| 2024-06 | 55029.400 | 209.170 | 224.040 | 0 |
| 2024-07 | 55405.800 | 209.820 | 217.303 | 5 |
| 2024-08 | 65305.100 | 248.740 | 262.112 | 94 |
| 2024-09 | 74688.900 | 290.920 | 303.224 | 13 |
| 2024-10 | 62789.500 | 177.330 | 180.987 | 2 |
| 2024-11 | 35935.700 | 133.830 | 137.134 | 2 |
| 2024-12 | 31825.200 | 88.160 | 91.241 | 8 |
| 2025-01 | 26449.900 | 70.860 | 73.101 | 10 |
| 2025-02 | 33366.700 | 74.370 | 76.178 | 4 |
| 2025-03 | 23840.300 | 61.350 | 63.093 | 0 |
| 2025-04 | 27222.500 | 68.230 | 76.632 | 0 |
| 2025-05 | 43611.100 | 228.320 | 241.044 | 0 |
| 2025-06 | 69384.400 | 241.130 | 256.206 | 0 |
| 2025-07 | 81181.700 | 227.010 | 238.127 | 2 |
| 2025-08 | 67893.800 | 176.300 | 184.376 | 3 |
| 2025-09 | 88480.000 | 290.300 | 299.362 | 2 |
| 2025-10 | 51023.600 | 173.490 | 177.235 | 0 |
| 2025-11 | 37525.000 | 133.810 | 136.096 | 0 |
| 2025-12 | 31942.700 | 76.330 | 82.691 | 12 |
| 2026-01 | 32472.300 | 77.840 | 85.208 | 11 |
| 2026-02 | 39239.200 | 83.400 | 84.567 | 13 |

## Failed-zero demand-register cleanup

After P/Q reconstruction, a P_dmd_max or S_dmd_max reading equal to zero is independently set to NaN where the same row has S_avg > 1.0 kVA. Counts below cover the retained canonical grid, including flagged rows. Idle S_avg == 0 readings remain valid zeros. This cleanup does not set is_imputed.

| Meter | P_dmd_max zeros to NaN | S_dmd_max zeros to NaN |
|---|---:|---:|
| CLIM_SALLE_IT_(TGBT_D1) | 20 | 20 |
| CLIM_TOUR_A_(TGBT_D6) | 24 | 24 |
| EM_VIRTUAL | 62 | 62 |
| ONDULEUR_1_(TGBT_DXX) | 119 | 119 |
| ONDULEUR_2_(TGBT_DXX) | 112 | 112 |
| PV_(CHAUFFERIE_PROV.) | 51 | 51 |
| SALLE_B101_(A._MEZAN_TOUR_B) | 0 | 0 |
| SALLE_B112_(A._MEZAN_TOUR_B) | 0 | 0 |
| SALLE_B201_(A_1_ETAGE_TOUR_B) | 9 | 9 |
| TGBT_TR1 | 30 | 30 |
| TGBT_TR2 | 38 | 38 |
| TOUR_A_(TGBT_D14) | 49 | 49 |
| TOUR_C_(TGBT_D10) | 47 | 47 |
| Tour_B_(TGBT_D5) | 51 | 51 |

## Final target definition

For the H=96 future slots t+1 through t+96: Pmax = max(P_avg), Smax = max(S_avg). Both targets are derived from the canonical interval-average channels. P_dmd_max and S_dmd_max remain cross-check columns in the Parquets and are NEVER used as labels. The registers aggregate on different clocks and include startup/failed reads, so ordering and correlation are EDA diagnostics, not invariants. The high-load median-deviation <0.10 test is retained. Imputed target regions remain excluded as documented above.


## Validation measurements and load-dependent demand diagnostics

Observed rows only (is_imputed == False), with finite S_avg and S_dmd_max. S_avg derives from interval-average P/Q; S_dmd_max aggregates on a different clock. Ordering and Pearson correlation are EDA diagnostics ONLY, with no asserted thresholds. The CSV schema, including legacy invariant_fraction/invariant_violations column names, is retained unchanged. An ordering exception below means S_dmd_max < S_avg - 0.01; it is not an invariant failure.

The retained check is median (S_dmd_max-S_avg)/S_dmd_max < 0.10 for S_avg strictly above the meter's observed 75th percentile.

| Meter | Comparable rows | Ordering fraction % | Ordering exceptions | P75 S_avg kVA | Upper-quartile rows | Upper-quartile median deviation | Pearson r |
|---|---:|---:|---:|---:|---:|---:|---:|
| CLIM_SALLE_IT_(TGBT_D1) | 128148 | 94.1201 | 7535 | 0.000000 | 18114 | 0.007098 | 0.947491 |
| CLIM_TOUR_A_(TGBT_D6) | 128148 | 84.0965 | 20380 | 1.798777 | 32035 | -0.035085 | 0.905209 |
| EM_VIRTUAL | 128127 | 53.3088 | 59824 | 82.102613 | 32032 | -0.017453 | 0.961508 |
| ONDULEUR_1_(TGBT_DXX) | 123491 | 72.4012 | 34082 | 4.033417 | 30873 | 0.000126 | 0.992014 |
| ONDULEUR_2_(TGBT_DXX) | 127728 | 72.8540 | 34673 | 3.645888 | 31911 | 0.000033 | 0.994434 |
| PV_(CHAUFFERIE_PROV.) | 128120 | 96.3128 | 4724 | 0.000000 | 21608 | -0.000726 | 0.995626 |
| SALLE_B101_(A._MEZAN_TOUR_B) | 128129 | 99.6207 | 486 | 0.791202 | 23428 | -0.005114 | 0.995347 |
| SALLE_B112_(A._MEZAN_TOUR_B) | 128129 | 99.2351 | 980 | 0.063246 | 28517 | -0.030776 | 0.956575 |
| SALLE_B201_(A_1_ETAGE_TOUR_B) | 128121 | 90.9788 | 11558 | 1.037304 | 31967 | -0.000409 | 0.988668 |
| TGBT_TR1 | 128147 | 82.1143 | 22920 | 41.172349 | 32037 | 0.001229 | 0.986570 |
| TGBT_TR2 | 128143 | 70.2809 | 38083 | 72.100003 | 32036 | -0.009658 | 0.981842 |
| TOUR_A_(TGBT_D14) | 125354 | 67.4745 | 40772 | 4.249841 | 31339 | 0.000371 | 0.986170 |
| TOUR_C_(TGBT_D10) | 125355 | 66.1418 | 42443 | 2.866025 | 31335 | 0.000114 | 0.985390 |
| Tour_B_(TGBT_D5) | 128130 | 63.2725 | 47059 | 5.416512 | 32032 | 0.000354 | 0.952728 |

Descriptive load halves (REPORT ONLY; no assertions): low means S_avg <= the meter's median, high means S_avg > median. Ties remain low, so idle-meter halves may have unequal sizes. Deviations are ratios, not percentages. S_dmd_max == 0 has an undefined relative deviation and is excluded only from ratio summaries; those rows remain in the ordering diagnostics, quantiles and correlations. The ratio sample counts make this exclusion explicit.

| Meter | Median S_avg kVA | Low rows / ratios | Low median deviation | Low P90 deviation | High rows / ratios | High median deviation | High P90 deviation | Zero-demand rows |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| CLIM_SALLE_IT_(TGBT_D1) | 0.000000 | 110034/41 | 1.000000 | 1.000000 | 18114/18099 | 0.007098 | 0.321814 | 110008 |
| CLIM_TOUR_A_(TGBT_D6) | 0.000000 | 71662/29 | 1.000000 | 1.000000 | 56486/56467 | 0.000000 | 0.490828 | 71652 |
| EM_VIRTUAL | 53.738308 | 64064/64064 | 0.002731 | 0.054485 | 64063/64063 | -0.001510 | 0.171687 | 0 |
| ONDULEUR_1_(TGBT_DXX) | 3.592130 | 61913/61909 | 0.000421 | 0.009476 | 61578/61578 | 0.000108 | 0.014386 | 4 |
| ONDULEUR_2_(TGBT_DXX) | 3.337664 | 64004/64004 | 0.000230 | 0.007388 | 63724/63724 | 0.000187 | 0.017585 | 0 |
| PV_(CHAUFFERIE_PROV.) | 0.000000 | 106512/548 | 1.000000 | 1.000000 | 21608/21321 | -0.000726 | 0.013596 | 106251 |
| SALLE_B101_(A._MEZAN_TOUR_B) | 0.781089 | 64344/64330 | 0.002633 | 0.010939 | 63785/63782 | -0.000078 | 0.006994 | 17 |
| SALLE_B112_(A._MEZAN_TOUR_B) | 0.053852 | 76494/76483 | -0.030776 | 0.175379 | 51635/51629 | -0.030776 | 0.083754 | 17 |
| SALLE_B201_(A_1_ETAGE_TOUR_B) | 0.962549 | 64152/64138 | 0.003185 | 0.017573 | 63969/63969 | 0.000072 | 0.014432 | 14 |
| TGBT_TR1 | 0.000000 | 78004/11 | 1.000000 | 1.000000 | 50143/50143 | 0.001799 | 0.079758 | 77993 |
| TGBT_TR2 | 31.241975 | 64072/16434 | 0.001592 | 0.035254 | 64071/64071 | 0.001396 | 0.162203 | 47638 |
| TOUR_A_(TGBT_D14) | 3.182994 | 62677/62600 | 0.001031 | 0.020806 | 62677/62677 | 0.000585 | 0.057062 | 77 |
| TOUR_C_(TGBT_D10) | 1.760824 | 62687/62683 | 0.004538 | 0.062765 | 62668/62668 | 0.000900 | 0.064091 | 4 |
| Tour_B_(TGBT_D5) | 4.286269 | 64068/64032 | 0.000685 | 0.016036 | 64062/64062 | 0.000417 | 0.065804 | 36 |

Ordering exceptions (diagnostic only): 365519. Every meter/timestamp, S_avg, S_dmd_max and shortfall is listed in `outputs/demand_invariant_violations.csv` (generated measurement dump, excluded from Git). Per-meter statistics are also saved in `reports/demand_diagnostics.csv`. These diagnostics do not alter the dataset.

Largest observed ordering difference per meter (diagnostic only; complete timestamp list in CSV above):

| Meter | Timestamp | S_avg kVA | S_dmd_max kVA | Shortfall kVA |
|---|---|---:|---:|---:|
| CLIM_SALLE_IT_(TGBT_D1) | 2022-08-22 08:45:00 | 54.624461 | 5.470000 | 49.154461 |
| CLIM_TOUR_A_(TGBT_D6) | 2024-08-15 10:15:00 | 13.143124 | 3.220000 | 9.923124 |
| EM_VIRTUAL | 2025-05-19 15:00:00 | 241.044023 | 108.290000 | 132.754023 |
| ONDULEUR_1_(TGBT_DXX) | 2022-08-27 10:00:00 | 12.791267 | 3.130000 | 9.661267 |
| ONDULEUR_2_(TGBT_DXX) | 2024-08-12 11:30:00 | 4.298802 | 1.600000 | 2.698802 |
| PV_(CHAUFFERIE_PROV.) | 2025-12-18 13:00:00 | 28.043830 | 8.000000 | 20.043830 |
| SALLE_B101_(A._MEZAN_TOUR_B) | 2023-03-25 08:45:00 | 0.791202 | 0.000000 | 0.791202 |
| SALLE_B112_(A._MEZAN_TOUR_B) | 2022-12-02 14:45:00 | 1.345362 | 0.370000 | 0.975362 |
| SALLE_B201_(A_1_ETAGE_TOUR_B) | 2025-01-27 11:15:00 | 0.843090 | 0.000000 | 0.843090 |
| TGBT_TR1 | 2025-05-19 15:00:00 | 241.044023 | 108.290000 | 132.754023 |
| TGBT_TR2 | 2022-08-25 14:00:00 | 300.665104 | 193.190000 | 107.475104 |
| TOUR_A_(TGBT_D14) | 2023-10-24 09:15:00 | 12.899353 | 4.610000 | 8.289353 |
| TOUR_C_(TGBT_D10) | 2024-08-26 09:30:00 | 4.770168 | 0.630000 | 4.140168 |
| Tour_B_(TGBT_D5) | 2024-08-30 13:45:00 | 68.719660 | 31.510000 | 37.209660 |


Observed positive-Q meter intervals: 208774; the site must not be assumed capacitive at every interval. Medium-gap warnings: 122 of 172 reported bounded/medium cases. Uniform fallback is an estimate of interval shape, not a measured profile.

EM_VIRTUAL H=96 origins passing the imputed-label exclusion: 125126. This eligibility check does not yet reject other missing targets or define forecasting splits; no training windows were materialized.

## Outputs and provenance

em_virtual.parquet has exactly the requested timestamp plus ten measure/flag columns. Its Arrow metadata records source filename/sheet runs and imputation gap provenance. all_meters.parquet is timestamp/meter-sorted long format, with the same measures plus both reactive cross-check counters and source_filename/source_sheet. Grid-only rows have null source provenance. No raw files were modified.

| VM output under data/processed/ | Data rows | Bytes |
|---|---:|---:|
| em_virtual.parquet | 128544 | 6642859 |
| all_meters.parquet | 1799616 | 47964943 |

Pipeline runtime for this invocation: 129.18 seconds.

## Pytest result

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.2.0, pluggy-1.7.0 -- /home/khalifa/supcom-energy-forcast/envs/main/bin/python
cachedir: cache/pytest
rootdir: /home/khalifa/supcom-energy-forcast
collecting ... collected 33 items

tests/test_contracts.py::ProjectContractTests::test_canonical_columns_keep_timestamp_and_four_electrical_values PASSED [  3%]
tests/test_contracts.py::ProjectContractTests::test_contract_rejects_inconsistent_cadence PASSED [  6%]
tests/test_contracts.py::ProjectContractTests::test_contract_rejects_wrong_calendar_feature_count PASSED [  9%]
tests/test_contracts.py::ProjectContractTests::test_official_dimensions PASSED [ 12%]
tests/test_ingestion.py::test_24_hour_rollover_and_leap_day PASSED       [ 15%]
tests/test_ingestion.py::test_duplicate_collapse_and_explicit_grid PASSED [ 18%]
tests/test_ingestion.py::test_startup_cutoff_trims_observed_and_explicit_missing_slots PASSED [ 21%]
tests/test_ingestion.py::test_failed_demand_zeros_are_missing_but_idle_and_one_kva_zeros_remain PASSED [ 24%]
tests/test_ingestion.py::test_named_csv_selection_with_reordered_columns PASSED [ 27%]
tests/test_ingestion.py::test_xlsx_export_suffix_normalization_is_name_based PASSED [ 30%]
tests/test_ingestion.py::test_short_gap_and_long_gap PASSED              [ 33%]
tests/test_ingestion.py::test_medium_gap_has_L_plus_one_flagged_increments_and_conserves_energy PASSED [ 36%]
tests/test_ingestion.py::test_both_reactive_counters_and_independent_PF_scale_warnings PASSED [ 39%]
tests/test_ingestion.py::test_uniform_fallback_and_no_imputed_donor PASSED [ 42%]
tests/test_ingestion.py::test_nearest_earlier_wholly_observed_donor PASSED [ 45%]
tests/test_ingestion.py::test_donor_search_never_exceeds_eight_weeks PASSED [ 48%]
tests/test_ingestion.py::test_unbounded_gaps_stay_nan_and_short_gap_cannot_cross_day PASSED [ 51%]
tests/test_ingestion.py::test_no_read_across_explicit_split_boundary PASSED [ 54%]
tests/test_ingestion.py::test_derived_energy_does_not_bridge_a_missing_grid_slot PASSED [ 57%]
tests/test_ingestion.py::test_H96_targets_exclude_every_imputed_label_including_closing_increment PASSED [ 60%]
tests/test_ingestion.py::test_output_has_no_duplicate_timestamps_and_requested_columns PASSED [ 63%]
tests/test_ingestion.py::test_output_complete_strictly_increasing_grid PASSED [ 66%]
tests/test_ingestion.py::test_observed_counter_never_decreases PASSED    [ 69%]
tests/test_ingestion.py::test_dEa_stays_nan_after_a_missing_unimputed_slot PASSED [ 72%]
tests/test_ingestion.py::test_no_growing_odometer_column_except_counters PASSED [ 75%]
tests/test_ingestion.py::test_apparent_power_bound PASSED                [ 78%]
tests/test_ingestion.py::test_power_factor_bounds PASSED                 [ 81%]
tests/test_ingestion.py::test_output_has_no_failed_zero_demand_registers_under_load PASSED [ 84%]
tests/test_ingestion.py::test_high_load_median_demand_deviation_below_10_percent PASSED [ 87%]
tests/test_ingestion.py::test_demand_diagnostics_exclude_imputed_rows_and_separate_quartile_from_halves PASSED [ 90%]
tests/test_ingestion.py::test_zero_demand_ratios_and_idle_load_ties_are_explicit PASSED [ 93%]
tests/test_ingestion.py::test_all_real_medium_gap_energy_totals_and_closing_flags PASSED [ 96%]
tests/test_ingestion.py::test_long_format_grid_and_provenance PASSED     [100%]

============================== 33 passed in 4.36s ==============================
```
