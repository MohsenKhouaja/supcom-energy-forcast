# SInERT dataset audit

VM working folder: `/home/khalifa/supcom-energy-forcast`. CSV audit only; no training or pipeline ingestion.

Observed runtime environment: host `ubuntu-gpu`, Python 3.12.3, Ubuntu 24.04.3 LTS.

Audit script SHA-256: `9e73f26041fa4f98997d82789bfc867a17d4c41c553de5eba8d98acf365cd37a`.

Inspected 670 CSV files in 44 month folders, 1,134,338,350 CSV bytes, 126,718 raw rows. 14 non-CSV files were not parsed. Audit runtime: 68.32 seconds.

## Definitions and limits

One process, one CSV row at a time; retain 198 selected numerical channels for one month. All [ABS] channels are checked for decreases. No timezone is encoded, so timestamps remain naive local times. Normalized 670 occurrences of 24:00:00 to the next day; 0 timestamps are off the 15-minute grid.

Monthly counts use calendar timestamps [month start, next month start), not source folder membership. Inventory month records the source folder. Files are processed by their first valid timestamp; misplaced copies participate in duplicate detection and are not counted twice. Duplicate timestamps use the whole row with the most finite selected values; ties retain the first row. No values are interpolated. A meter interval is present when at least one of its main kWh counter, P or Q is finite; energy/PF completeness can be lower. All measurement fields beyond Date/Time are checked for an entirely --- row.

dEa = kWh counter(t) minus kWh counter(t-15 min), only when both readings exist at consecutive timestamps. It is assigned to the month of the ending timestamp; negative changes remain in signed totals and are separately flagged. The first reading and gaps do not create energy estimates. Thus totals describe observed valid pairs, not full-month consumption. dEr = sum of signed kvar sys [AVG] times 0.25 h over observed rows. Derived S = sqrt(P²+Q²); derived PF = P/S for S>0, unweighted mean (signed if P is negative). Reactive counter change is last minus first finite in-month reading, including decreases; endpoint timestamps are in meters.csv. These counter changes and integrated Q are different quantities and are not assumed equal.

## 1. Coverage and 5/9. Monthly EM_VIRTUAL active energy and derived PF

Coverage folders: 2022-06 through 2026-01. Missing whole month folders: none. Months without any CSV starting in that actual month: 2025-08. Complete CSV timestamp coverage requires every expected calendar quarter-hour; usable rows additionally exclude entirely --- rows.

| Month | CSVs folder/dated | Grid rows / expected | Usable rows | EM present missing % | dEa kWh | dEa pairs | EM mean PF | EM min PF |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2022-06 | 15/15 | 2880/2880 | 284 | 90.139 | 8772.700 | 282 | 0.942327 | 0.915471 |
| 2022-07 | 16/16 | 2976/2976 | 2948 | 0.941 | 74999.400 | 2946 | 0.945172 | 0.902919 |
| 2022-08 | 16/16 | 2976/2976 | 2975 | 0.034 | 84218.300 | 2974 | 0.939686 | 0.901541 |
| 2022-09 | 15/15 | 2880/2880 | 2876 | 0.139 | 79296.500 | 2875 | 0.944662 | 0.902411 |
| 2022-10 | 16/16 | 2976/2976 | 2976 | 0.000 | 51190.000 | 2976 | 0.961695 | 0.914075 |
| 2022-11 | 15/15 | 2880/2880 | 2880 | 0.000 | 26114.900 | 2880 | 0.944929 | 0.856058 |
| 2022-12 | 16/16 | 2976/2976 | 2976 | 0.000 | 21688.500 | 2976 | 0.933709 | 0.869783 |
| 2023-01 | 16/16 | 2976/2976 | 2976 | 0.000 | 22378.700 | 2976 | 0.929931 | 0.869994 |
| 2023-02 | 14/14 | 2688/2688 | 2688 | 0.000 | 24601.200 | 2688 | 0.947389 | 0.877130 |
| 2023-03 | 16/16 | 2976/2976 | 2975 | 0.034 | 23097.300 | 2974 | 0.939122 | 0.855141 |
| 2023-04 | 15/15 | 2785/2880 | 2784 | 3.333 | 17923.700 | 2783 | 0.881731 | 0.631682 |
| 2023-05 | 16/16 | 2976/2976 | 2976 | 0.000 | 34839.300 | 2976 | 0.951417 | 0.792197 |
| 2023-06 | 15/15 | 2880/2880 | 2854 | 0.903 | 43836.600 | 2852 | 0.968211 | 0.906262 |
| 2023-07 | 16/16 | 2976/2976 | 2973 | 0.101 | 63227.300 | 2972 | 0.952189 | 0.912689 |
| 2023-08 | 16/16 | 2976/2976 | 2972 | 0.134 | 42393.900 | 2970 | 0.979683 | 0.919292 |
| 2023-09 | 15/15 | 2880/2880 | 2860 | 0.694 | 57198.900 | 2858 | 0.976008 | 0.927973 |
| 2023-10 | 16/16 | 2976/2976 | 2976 | 0.000 | 52987.000 | 2976 | 0.968907 | 0.762898 |
| 2023-11 | 1/1 | 194/2880 | 192 | 93.333 | 1617.700 | 191 | 0.974403 | 0.937525 |
| 2023-12 | 16/16 | 2976/2976 | 2976 | 0.000 | 23370.300 | 2975 | 0.946810 | 0.716861 |
| 2024-01 | 16/16 | 2976/2976 | 2976 | 0.000 | 30289.300 | 2976 | 0.962197 | 0.876184 |
| 2024-02 | 15/15 | 2784/2784 | 2784 | 0.000 | 27969.900 | 2784 | 0.968046 | 0.884078 |
| 2024-03 | 16/16 | 2976/2976 | 2976 | 0.000 | 25194.700 | 2976 | 0.963337 | 0.892466 |
| 2024-04 | 15/15 | 2880/2880 | 2880 | 0.000 | 24094.700 | 2880 | 0.946965 | 0.824118 |
| 2024-05 | 16/16 | 2976/2976 | 2976 | 0.000 | 28556.100 | 2976 | 0.931658 | 0.768796 |
| 2024-06 | 15/15 | 2880/2880 | 2880 | 0.000 | 55029.400 | 2880 | 0.953094 | 0.908900 |
| 2024-07 | 16/16 | 2976/2976 | 2972 | 0.134 | 55353.200 | 2971 | 0.966167 | 0.908590 |
| 2024-08 | 16/16 | 2976/2976 | 2883 | 3.125 | 64477.800 | 2882 | 0.968061 | 0.912658 |
| 2024-09 | 15/15 | 2880/2880 | 2868 | 0.417 | 74663.700 | 2867 | 0.980938 | 0.923014 |
| 2024-10 | 16/16 | 2976/2976 | 2975 | 0.034 | 62759.900 | 2974 | 0.989852 | 0.953835 |
| 2024-11 | 15/15 | 2880/2880 | 2879 | 0.035 | 35919.900 | 2878 | 0.873026 | 0.620154 |
| 2024-12 | 16/16 | 2976/2976 | 2971 | 0.168 | 31784.600 | 2968 | 0.883100 | 0.622060 |
| 2025-01 | 16/16 | 2976/2976 | 2972 | 0.235 | 26408.500 | 2966 | 0.939729 | 0.747516 |
| 2025-02 | 14/14 | 2688/2688 | 2686 | 0.074 | 33300.100 | 2684 | 0.952108 | 0.769795 |
| 2025-03 | 16/16 | 2976/2976 | 2976 | 0.000 | 23840.300 | 2976 | 0.818669 | 0.720684 |
| 2025-04 | 15/15 | 2880/2880 | 2880 | 0.000 | 27222.500 | 2880 | 0.818480 | 0.633309 |
| 2025-05 | 16/32 | 2976/2976 | 2976 | 0.000 | 43611.100 | 2976 | 0.900407 | 0.759650 |
| 2025-06 | 15/15 | 2880/2880 | 2880 | 0.000 | 69384.400 | 2880 | 0.976477 | 0.940184 |
| 2025-07 | 16/16 | 2976/2976 | 2975 | 0.034 | 81146.200 | 2974 | 0.946110 | 0.794944 |
| 2025-08 | 16/0 | 1/2976 | 0 | 100.000 | NA | 0 | NA | NA |
| 2025-09 | 15/15 | 2880/2880 | 2879 | 0.035 | 88363.400 | 2877 | 0.977176 | 0.944997 |
| 2025-10 | 16/16 | 2976/2976 | 2976 | 0.000 | 51023.600 | 2976 | 0.949540 | 0.804996 |
| 2025-11 | 15/15 | 2880/2880 | 2880 | 0.000 | 37525.000 | 2880 | 0.885110 | 0.788640 |
| 2025-12 | 16/16 | 2976/2976 | 2965 | 0.370 | 31934.300 | 2964 | 0.871550 | 0.608863 |
| 2026-01 | 16/16 | 2976/2976 | 2966 | 0.336 | 32353.100 | 2965 | 0.933963 | 0.852194 |

Months with incomplete usable CSV coverage: 2022-06, 2022-07, 2022-08, 2022-09, 2023-03, 2023-04, 2023-06, 2023-07, 2023-08, 2023-09, 2023-11, 2024-07, 2024-08, 2024-09, 2024-10, 2024-11, 2024-12, 2025-01, 2025-02, 2025-07, 2025-08, 2025-09, 2025-12, 2026-01.

Misplaced files: 16, of which 16 have a byte-identical SHA-256 match in the folder matching their actual month. Details and matching original paths are in anomalies.csv.
- Folder month 2025-08 contains 16 files whose actual first timestamp month is 2025-05.

EM_VIRTUAL monthly mean derived PF ranges from 0.818480 (2025-04) to 0.989852 (2024-10). Missing months have no PF estimate; every observed monthly value is in the table above.

## 2. Header identity

1 raw header MD5 variant(s). Majority `ae7740e6f10914f7aa4b2fa665f0baa0` occurs in 670/670 files and has 1501 columns. MD5 includes the exact header bytes including line ending.
All CSV header lines are byte-identical.

## 3. Meter activity

Active means observed nonzero P or Q; a fixed nonzero cumulative counter alone is not activity.

| Meter | Nonzero intervals | Active month periods | First nonzero timestamp | Last nonzero timestamp |
|---|---:|---|---|---|
| CLIM_SALLE_IT_(TGBT_D1) | 16155 | 2022-06 to 2022-09; 2023-06 to 2023-07; 2024-12 to 2025-01; 2025-05 to 2025-07; 2025-09 to 2025-11 | 2022-06-28 00:00:00 | 2025-11-07 12:30:00 |
| CLIM_TOUR_A_(TGBT_D6) | 54246 | 2022-06 to 2022-10; 2023-04 to 2023-10; 2024-04 to 2024-11; 2025-05 to 2025-07; 2025-09 to 2025-11 | 2022-06-28 00:00:00 | 2025-11-07 12:15:00 |
| EM_VIRTUAL | 120145 | 2022-06 to 2025-07; 2025-09 to 2026-01 | 2022-06-28 00:00:00 | 2026-01-31 23:45:00 |
| ONDULEUR_1_(TGBT_DXX) | 115597 | 2022-06 to 2025-07; 2025-09 to 2026-01 | 2022-06-28 00:00:00 | 2026-01-31 23:45:00 |
| ONDULEUR_2_(TGBT_DXX) | 120032 | 2022-06 to 2025-07; 2025-09 to 2026-01 | 2022-06-28 00:00:00 | 2026-01-31 23:45:00 |
| PV_(CHAUFFERIE_PROV.) | 21312 | 2022-09; 2022-12 to 2023-04; 2023-06 to 2023-07; 2023-09 to 2024-04; 2024-06 to 2025-01; 2025-07; 2025-09 to 2026-01 | 2022-09-19 10:45:00 | 2026-01-12 14:30:00 |
| SALLE_B101_(A._MEZAN_TOUR_B) | 120110 | 2022-06 to 2025-07; 2025-09 to 2026-01 | 2022-06-28 00:00:00 | 2026-01-31 23:45:00 |
| SALLE_B112_(A._MEZAN_TOUR_B) | 120109 | 2022-06 to 2025-07; 2025-09 to 2026-01 | 2022-06-28 00:00:00 | 2026-01-31 23:45:00 |
| SALLE_B201_(A_1_ETAGE_TOUR_B) | 120109 | 2022-06 to 2025-07; 2025-09 to 2026-01 | 2022-06-28 00:00:00 | 2026-01-31 23:45:00 |
| TGBT_TR1 | 44817 | 2023-06 to 2024-02; 2024-11 to 2025-07; 2025-12 to 2026-01 | 2023-06-11 13:00:00 | 2026-01-31 23:45:00 |
| TGBT_TR2 | 77848 | 2022-06 to 2023-07; 2023-09 to 2023-10; 2024-02 to 2024-11; 2025-07; 2025-09 to 2025-12 | 2022-06-28 00:00:00 | 2025-12-07 09:00:00 |
| TOUR_A_(TGBT_D14) | 117286 | 2022-06 to 2025-07; 2025-09 to 2026-01 | 2022-06-28 00:00:00 | 2026-01-31 23:45:00 |
| TOUR_C_(TGBT_D10) | 117367 | 2022-06 to 2025-07; 2025-09 to 2026-01 | 2022-06-28 00:00:00 | 2026-01-31 23:45:00 |
| Tour_B_(TGBT_D5) | 120107 | 2022-06 to 2025-07; 2025-09 to 2026-01 | 2022-06-28 00:00:00 | 2026-01-31 23:45:00 |

TGBT_TR1 additionally has 120,093 nonzero cumulative kWh readings in 2022-06 to 2025-07; 2025-09 to 2026-01; first 2022-06-28 14:00:00, last 2026-01-31 23:45:00. This distinguishes retained historical counters from observed load activity.

## 4. EM_VIRTUAL versus TGBT_TR1 + TGBT_TR2

The additive channels do NOT equal the transformer sum in every observed month.

- P: 639 unequal readings; first 2023-09-20 08:00:00, last 2023-10-16 11:30:00; residual (virtual minus transformer sum) among affected months ranges -0.010000 to 0.010000; maximum absolute residual 0.010000.
- Q: 601 unequal readings; first 2023-09-20 06:00:00, last 2023-10-16 11:45:00; residual (virtual minus transformer sum) among affected months ranges -0.010000 to 0.010000; maximum absolute residual 0.010000.
- cumulative kWh: 32,649 unequal readings; first 2025-01-25 15:15:00, last 2026-01-31 23:45:00; residual (virtual minus transformer sum) among affected months ranges -0.000000 to 8.700000; maximum absolute residual 8.700000.
- cumulative kvarh (-): 32,649 unequal readings; first 2025-01-25 15:15:00, last 2026-01-31 23:45:00; residual (virtual minus transformer sum) among affected months ranges -0.000000 to 0.900000; maximum absolute residual 0.900000.

Compare simultaneous finite readings at stored precision, numeric tolerance 0.000001 in the channel's units. Missing comparisons cannot establish equality. Test P, Q, cumulative kWh and both cumulative kvarh counters separately; voltages, frequency and PF are not additive. The following are mismatches/compared rows; kWh offset is maximum absolute residual.

| Month | P | Q | kWh counter | kvarh counter | kvarh (-) counter | Max abs kWh offset |
|---|---:|---:|---:|---:|---:|---:|
| 2022-06 | 0/284 | 0/284 | 0/284 | 0/284 | 0/284 | 0.000 |
| 2022-07 | 0/2948 | 0/2948 | 0/2948 | 0/2948 | 0/2948 | 0.000 |
| 2022-08 | 0/2975 | 0/2975 | 0/2975 | 0/2975 | 0/2975 | 0.000 |
| 2022-09 | 0/2876 | 0/2876 | 0/2876 | 0/2876 | 0/2876 | 0.000 |
| 2022-10 | 0/2976 | 0/2976 | 0/2976 | 0/2976 | 0/2976 | 0.000 |
| 2022-11 | 0/2880 | 0/2880 | 0/2880 | 0/2880 | 0/2880 | 0.000 |
| 2022-12 | 0/2976 | 0/2976 | 0/2976 | 0/2976 | 0/2976 | 0.000 |
| 2023-01 | 0/2976 | 0/2976 | 0/2976 | 0/2976 | 0/2976 | 0.000 |
| 2023-02 | 0/2688 | 0/2688 | 0/2688 | 0/2688 | 0/2688 | 0.000 |
| 2023-03 | 0/2975 | 0/2975 | 0/2975 | 0/2975 | 0/2975 | 0.000 |
| 2023-04 | 0/2784 | 0/2784 | 0/2784 | 0/2784 | 0/2784 | 0.000 |
| 2023-05 | 0/2976 | 0/2976 | 0/2976 | 0/2976 | 0/2976 | 0.000 |
| 2023-06 | 0/2854 | 0/2854 | 0/2854 | 0/2854 | 0/2854 | 0.000 |
| 2023-07 | 0/2973 | 0/2973 | 0/2973 | 0/2973 | 0/2973 | 0.000 |
| 2023-08 | 0/2972 | 0/2972 | 0/2972 | 0/2972 | 0/2972 | 0.000 |
| 2023-09 | 254/2860 | 237/2860 | 0/2860 | 0/2860 | 0/2860 | 0.000 |
| 2023-10 | 385/2976 | 364/2976 | 0/2976 | 0/2976 | 0/2976 | 0.000 |
| 2023-11 | 0/192 | 0/192 | 0/192 | 0/192 | 0/192 | 0.000 |
| 2023-12 | 0/2976 | 0/2976 | 0/2976 | 0/2976 | 0/2976 | 0.000 |
| 2024-01 | 0/2976 | 0/2976 | 0/2976 | 0/2976 | 0/2976 | 0.000 |
| 2024-02 | 0/2784 | 0/2784 | 0/2784 | 0/2784 | 0/2784 | 0.000 |
| 2024-03 | 0/2976 | 0/2976 | 0/2976 | 0/2976 | 0/2976 | 0.000 |
| 2024-04 | 0/2880 | 0/2880 | 0/2880 | 0/2880 | 0/2880 | 0.000 |
| 2024-05 | 0/2976 | 0/2976 | 0/2976 | 0/2976 | 0/2976 | 0.000 |
| 2024-06 | 0/2880 | 0/2880 | 0/2880 | 0/2880 | 0/2880 | 0.000 |
| 2024-07 | 0/2972 | 0/2972 | 0/2972 | 0/2972 | 0/2972 | 0.000 |
| 2024-08 | 0/2883 | 0/2883 | 0/2883 | 0/2883 | 0/2883 | 0.000 |
| 2024-09 | 0/2868 | 0/2868 | 0/2868 | 0/2868 | 0/2868 | 0.000 |
| 2024-10 | 0/2975 | 0/2975 | 0/2975 | 0/2975 | 0/2975 | 0.000 |
| 2024-11 | 0/2879 | 0/2879 | 0/2879 | 0/2879 | 0/2879 | 0.000 |
| 2024-12 | 0/2971 | 0/2971 | 0/2971 | 0/2971 | 0/2971 | 0.000 |
| 2025-01 | 0/2969 | 0/2969 | 610/2968 | 0/2968 | 610/2968 | 8.700 |
| 2025-02 | 0/2686 | 0/2686 | 2686/2686 | 0/2686 | 2686/2686 | 8.700 |
| 2025-03 | 0/2976 | 0/2976 | 2976/2976 | 0/2976 | 2976/2976 | 8.700 |
| 2025-04 | 0/2880 | 0/2880 | 2880/2880 | 0/2880 | 2880/2880 | 8.700 |
| 2025-05 | 0/2976 | 0/2976 | 2976/2976 | 0/2976 | 2976/2976 | 8.700 |
| 2025-06 | 0/2880 | 0/2880 | 2880/2880 | 0/2880 | 2880/2880 | 8.700 |
| 2025-07 | 0/2975 | 0/2975 | 2975/2975 | 0/2975 | 2975/2975 | 8.700 |
| 2025-08 | 0/0 | 0/0 | 0/0 | 0/0 | 0/0 | NA |
| 2025-09 | 0/2879 | 0/2879 | 2879/2879 | 0/2879 | 2879/2879 | 8.700 |
| 2025-10 | 0/2976 | 0/2976 | 2976/2976 | 0/2976 | 2976/2976 | 8.700 |
| 2025-11 | 0/2880 | 0/2880 | 2880/2880 | 0/2880 | 2880/2880 | 8.700 |
| 2025-12 | 0/2965 | 0/2965 | 2965/2965 | 0/2965 | 2965/2965 | 8.700 |
| 2026-01 | 0/2966 | 0/2966 | 2966/2966 | 0/2966 | 2966/2966 | 8.700 |

## 6. Missing data and longest gaps

Entirely --- raw measurement rows: 3,498. Missing CSV grid slots: 5,756/128,736. Grid slots without a usable measurement row: 8,588. Meter missing percentages include absent timestamps and missing main channels; zero is a valid observation.

Worst EM_VIRTUAL months by missing main-channel observations:
- 2025-08: 2976/2976 missing (100.000%).
- 2023-11: 2688/2880 missing (93.333%).
- 2022-06: 2596/2880 missing (90.139%).
- 2023-04: 96/2880 missing (3.333%).
- 2024-08: 93/2976 missing (3.125%).
- 2022-07: 28/2976 missing (0.941%).
- 2023-06: 26/2880 missing (0.903%).
- 2023-09: 20/2880 missing (0.694%).

Longest gaps between observed CSV timestamps (leading/trailing calendar holes are included in monthly missing counts):
- 2025-08-01 00:00:00 to 2025-09-01 00:00:00: 44640 minutes; 2975 missing slots.
- 2023-11-01 00:00:00 to 2023-11-17 00:00:00: 23040 minutes; 1535 missing slots.
- 2023-11-19 00:00:00 to 2023-12-01 00:00:00: 17280 minutes; 1151 missing slots.
- 2023-04-29 00:00:00 to 2023-04-30 00:00:00: 1440 minutes; 95 missing slots.

Longest gaps between finite main-channel observations for EM_VIRTUAL:
- 2025-07-31 23:45:00 to 2025-09-01 00:00:00: 44655 minutes; 2976 missing slots.
- 2023-10-31 23:45:00 to 2023-11-17 00:00:00: 23055 minutes; 1536 missing slots.
- 2023-11-18 23:45:00 to 2023-12-01 00:00:00: 17295 minutes; 1152 missing slots.
- 2023-04-28 23:45:00 to 2023-04-30 00:00:00: 1455 minutes; 96 missing slots.
- 2024-08-06 10:00:00 to 2024-08-07 09:30:00: 1410 minutes; 93 missing slots.

Longest EM_VIRTUAL missing calendar runs, including leading/trailing holes (end exclusive):
- 2025-08-01 00:00:00 to 2025-09-01 00:00:00: 2,976 missing quarter-hours (44,640 minutes).
- 2022-06-01 00:00:00 to 2022-06-28 00:00:00: 2,592 missing quarter-hours (38,880 minutes).
- 2023-11-01 00:00:00 to 2023-11-17 00:00:00: 1,536 missing quarter-hours (23,040 minutes).
- 2023-11-19 00:00:00 to 2023-12-01 00:00:00: 1,152 missing quarter-hours (17,280 minutes).
- 2023-04-29 00:00:00 to 2023-04-30 00:00:00: 96 missing quarter-hours (1,440 minutes).

The archive also contains 14 XLSX files. They are listed below but were not parsed (only pandas, pyarrow and numpy were authorized; the requested inventory is CSV-only). CSV absence in those periods must not be described as absence from the archive:
- `data/raw/sinert/SINERT_DATA_CONCENTRATOR/November2023/2023-11-01_2023-11-02_Daily Report_Main AC meter.xlsx`
- `data/raw/sinert/SINERT_DATA_CONCENTRATOR/November2023/2023-11-03_2023-11-04_Daily Report_Main AC meter.xlsx`
- `data/raw/sinert/SINERT_DATA_CONCENTRATOR/November2023/2023-11-05_2023-11-06_Daily Report_Main AC meter.xlsx`
- `data/raw/sinert/SINERT_DATA_CONCENTRATOR/November2023/2023-11-07_2023-11-08_Daily Report_Main AC meter.xlsx`
- `data/raw/sinert/SINERT_DATA_CONCENTRATOR/November2023/2023-11-09_2023-11-10_Daily Report_Main AC meter.xlsx`
- `data/raw/sinert/SINERT_DATA_CONCENTRATOR/November2023/2023-11-11_2023-11-12_Daily Report_Main AC meter.xlsx`
- `data/raw/sinert/SINERT_DATA_CONCENTRATOR/November2023/2023-11-13_2023-11-14_Daily Report_Main AC meter.xlsx`
- `data/raw/sinert/SINERT_DATA_CONCENTRATOR/November2023/2023-11-15_2023-11-16_Daily Report_Main AC meter.xlsx`
- `data/raw/sinert/SINERT_DATA_CONCENTRATOR/November2023/2023-11-19_2023-11-20_Daily Report_Main AC meter.xlsx`
- `data/raw/sinert/SINERT_DATA_CONCENTRATOR/November2023/2023-11-21_2023-11-22_Daily Report_Main AC meter.xlsx`
- `data/raw/sinert/SINERT_DATA_CONCENTRATOR/November2023/2023-11-23_2023-11-24_Daily Report_Main AC meter.xlsx`
- `data/raw/sinert/SINERT_DATA_CONCENTRATOR/November2023/2023-11-25_2023-11-26_Daily Report_Main AC meter.xlsx`
- `data/raw/sinert/SINERT_DATA_CONCENTRATOR/November2023/2023-11-27_2023-11-28_Daily Report_Main AC meter.xlsx`
- `data/raw/sinert/SINERT_DATA_CONCENTRATOR/November2023/2023-11-29_2023-11-30_Daily Report_Main AC meter.xlsx`

## 7. Counter decreases

Observed 0 decreases across all [ABS] channels, comparing consecutive finite readings even across gaps. Observed 0 negative main-kWh increments across consecutive 15-minute readings. A decrease is consistent with a reset, rollover or correction; the CSV alone does not identify the cause. Each event, channel, old/new reading and timestamps is in anomalies.csv.

## 8. File boundaries and duplicates

Among 669 consecutive file boundaries: 665 overlap/touch at the same timestamp or earlier, 4 leave more than 15 minutes, 0 are exactly 15 minutes apart. Duplicate timestamps: 3,737; 0 duplicate rows conflict on at least one finite selected channel. Equal midnight endpoints are counted as overlaps. Each exceptional boundary is in anomalies.csv.
- Boundary hole: 2025-08-01 00:00:00 to 2025-09-01 00:00:00, 44640 minutes; `data/raw/sinert/SINERT_DATA_CONCENTRATOR/July2025/2025-07-31_Daily Report_Main AC meter.csv` -> `data/raw/sinert/SINERT_DATA_CONCENTRATOR/September2025/2025-09-01_2025-09-02_Daily Report_Main AC meter.csv`.
- Boundary hole: 2023-11-01 00:00:00 to 2023-11-17 00:00:00, 23040 minutes; `data/raw/sinert/SINERT_DATA_CONCENTRATOR/October2023/2023-10-31_Daily Report_Main AC meter.csv` -> `data/raw/sinert/SINERT_DATA_CONCENTRATOR/November2023/2023-11-17_2023-11-18_Daily Report_Main AC meter.csv`.
- Boundary hole: 2023-11-19 00:00:00 to 2023-12-01 00:00:00, 17280 minutes; `data/raw/sinert/SINERT_DATA_CONCENTRATOR/November2023/2023-11-17_2023-11-18_Daily Report_Main AC meter.csv` -> `data/raw/sinert/SINERT_DATA_CONCENTRATOR/December2023/2023-12-01_2023-12-02_Daily Report_Main AC meter.csv`.
- Boundary hole: 2023-04-29 00:00:00 to 2023-04-30 00:00:00, 1440 minutes; `data/raw/sinert/SINERT_DATA_CONCENTRATOR/April2023/2023-04-27_2023-04-28_Daily Report_Main AC meter.csv` -> `data/raw/sinert/SINERT_DATA_CONCENTRATOR/April2023/2023-04-30_Daily Report_Main AC meter.csv`.

1 normalized endpoint rows at/after the final calendar month were excluded from monthly totals; 0 of those contain a measurement. No extra month is inferred from an empty final endpoint.

## Output counts and anomaly types

inventory.csv: 670 data rows. meters.csv: 616 data rows. anomalies.csv: 12026 data rows. CSV row counts exclude headers.

- all_missing_row: 3498
- duplicate_timestamp: 3737
- file_boundary_hole: 4
- file_boundary_overlap: 665
- meter_gap: 500
- meter_missing_run: 514
- misplaced_file: 16
- outside_source_month: 3088
- timestamp_gap: 4
