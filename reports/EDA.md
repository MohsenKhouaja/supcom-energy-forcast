# EDA: SInERT observed behaviour

Read existing Parquets only; ingestion was not rerun. Canonical site grid: 2022-07-01 00:00:00 to 2026-02-28 23:45:00, 128,544 quarter-hours and 44 months. No models, features for models, or windows were created.

## Methods and exclusions

Every descriptive statistic masks is_imputed=True rows on the original grid. Lag pairs and consecutive runs never compress gaps. Tables list imputed exclusions separately from missing/undefined observed values. Timestamps are naive export local time; no timezone is inferred. Seasons are northern meteorological DJF winter, MAM spring, JJA summer and SON autumn. Max/min ties use the earliest observed timestamp; variability uses sample variance/std (ddof=1). The only explicit exception is split input-completeness counting: imputed inputs are allowed, but every future target must be observed.

The university academic calendar is unavailable. All vacation/term classifications below are PROVISIONAL data proxies, not facts about SUP'COM. Obtain the actual calendar from the supervisor and replace this proxy.

## 1. Active energy at four time scales

Excluded imputed rows: **377**; other missing/undefined observed rows for this parameter: **1**. Group-specific exclusions are included in the full CSV tables.

Observed active energy total: **1,939,539.100 kWh**. These are sums of observed dEa, not counter levels and not complete consumption estimates where intervals were excluded. Daily/weekly/monthly/annual CSVs include period totals, running totals, sample counts and exclusions. Weeks start Monday. 2022 and 2026 are partial calendar years.

| period | energy_kWh | observed_intervals | excluded_imputed | missing_observed | running_total_kWh |
|---|---|---|---|---|---|
| 2022-01-01 00:00 | 337484.0000 | 17626 | 37 | 1 | 337484.0000 |
| 2023-01-01 00:00 | 432871.0000 | 34881 | 159 | 0 | 770355.0000 |
| 2024-01-01 00:00 | 516093.2000 | 35012 | 124 | 0 | 1286448.2000 |
| 2025-01-01 00:00 | 581667.8000 | 35007 | 33 | 0 | 1868116.0000 |
| 2026-01-01 00:00 | 71423.1000 | 5640 | 24 | 0 | 1939539.1000 |

Daily energy distribution (kWh): count    1338.000000; mean     1449.580792; std       778.088901; min       349.600000; 25%       835.250000; 50%      1177.100000; 75%      1967.325000; max      4339.800000.

Full daily/weekly values: [daily](eda_energy_daily.csv), [weekly](eda_energy_weekly.csv). Figure: [energy_totals.png](figures/energy_totals.png).

## 2. Base load and occurrence hour

Excluded imputed rows: **377**; other missing/undefined observed rows for this parameter: **0**. Group-specific exclusions are included in the full CSV tables.

Daily minimum P_avg: median **35.375 kW**, range **6.300–136.830 kW**. Hour distribution counts the earliest occurrence per day.

| hour | days | excluded_imputed |
|---|---|---|
| 0 | 70 | 377 |
| 1 | 95 | 377 |
| 2 | 113 | 377 |
| 3 | 155 | 377 |
| 4 | 180 | 377 |
| 5 | 192 | 377 |
| 6 | 60 | 377 |
| 7 | 79 | 377 |
| 8 | 64 | 377 |
| 9 | 17 | 377 |
| 10 | 11 | 377 |
| 11 | 8 | 377 |
| 12 | 11 | 377 |
| 13 | 10 | 377 |
| 14 | 9 | 377 |
| 15 | 12 | 377 |
| 16 | 12 | 377 |
| 17 | 23 | 377 |
| 18 | 25 | 377 |
| 19 | 28 | 377 |
| 20 | 9 | 377 |
| 21 | 15 | 377 |
| 22 | 29 | 377 |
| 23 | 111 | 377 |

Daily values and timestamps: [table](eda_base_load_daily.csv). Figure: [base_load_and_hour.png](figures/base_load_and_hour.png).

## 3. Daily peak demand and duration

Excluded imputed rows: **377**; other missing/undefined observed rows for this parameter: **0**. Group-specific exclusions are included in the full CSV tables.

Peak duration is the LONGEST consecutive run of quarter-hours at or above 90% of that day's maximum, separately for P and S. Missing/imputed slots or a timestamp gap break a run; disconnected runs are never added. A day with no observed values has undefined peak/duration (NaN), not a measured zero. The maximum's earliest timestamp is also recorded.

| index | P_maximum | S_maximum | P_duration_hours | S_duration_hours |
|---|---|---|---|---|
| count | 1338.0000 | 1338.0000 | 1338.0000 | 1338.0000 |
| mean | 87.2409 | 91.6857 | 2.3451 | 2.4834 |
| std | 51.4043 | 53.5437 | 2.1708 | 2.5016 |
| min | 19.2800 | 21.6921 | 0.2500 | 0.2500 |
| 25% | 48.8900 | 52.3159 | 0.5000 | 0.5000 |
| 50% | 68.0400 | 70.4108 | 2.0000 | 2.0000 |
| 75% | 121.7175 | 126.8275 | 3.5000 | 3.5000 |
| max | 290.9200 | 303.2238 | 24.0000 | 24.0000 |

All daily peak times and durations: [table](eda_peaks_daily.csv). Figure: [daily_peaks_and_duration.png](figures/daily_peaks_and_duration.png).

## 4. Mean power comparisons

Excluded imputed rows: **377**; other missing/undefined observed rows for this parameter: **0**. Group-specific exclusions are included in the full CSV tables.

day_type:

| group | mean_kW | median_kW | observed_intervals | excluded_imputed | missing_observed |
|---|---|---|---|---|---|
| Weekday | 64.3082 | 53.9900 | 91585 | 191 | 0 |
| Weekend | 51.0899 | 39.4150 | 36582 | 186 | 0 |

PROVISIONAL academic proxy:

| group | mean_kW | median_kW | observed_intervals | excluded_imputed | missing_observed |
|---|---|---|---|---|---|
| Term-like PROVISIONAL | 57.7620 | 46.6600 | 77965 | 179 | 0 |
| Vacation-like PROVISIONAL | 64.8424 | 58.7200 | 50202 | 198 | 0 |

season:

| group | mean_kW | median_kW | observed_intervals | excluded_imputed | missing_observed |
|---|---|---|---|---|---|
| Autumn | 73.8273 | 67.8900 | 34898 | 46 | 0 |
| Spring | 37.6415 | 33.7100 | 26397 | 99 | 0 |
| Summer | 87.0033 | 85.2450 | 32274 | 174 | 0 |
| Winter | 39.9053 | 37.8900 | 34598 | 58 | 0 |

Boxplots suppress displayed outliers only; all observed measurements remain in the numerical results. The PROVISIONAL vacation-like mean is 64.8424 kW versus 57.7620 kW for the PROVISIONAL term-like group. Collapsed weekday/weekend contrast therefore does not mean low consumption; this proxy is confounded by seasonal operating patterns and is not an academic-calendar label. Figure: [mean_power_comparisons.png](figures/mean_power_comparisons.png).

## 5. Activity proxies and variability

Excluded imputed rows: **377**; other missing/undefined observed rows for this parameter: **0**. Group-specific exclusions are included in the full CSV tables.

Activation/deactivation are the first/last observed interval with P_avg >1.5 times that day's observed minimum. A flat day with no crossing returns None. This is a descriptive site-activity proxy, not an equipment switching log.

| index | quantity | value |
|---|---|---|
| 0 | activation median hour | 6.7500 |
| 1 | deactivation median hour | 20.5000 |
| 2 | observed days with no crossing | 210.0000 |
| 3 | days with no observed P | 1.0000 |

Monthly P_avg standard deviation and variance:

| group | std_kW | variance_kW2 | observed_intervals | excluded_imputed | missing_observed |
|---|---|---|---|---|---|
| 2022-07-01 00:00 | 22.2185 | 493.6601 | 2946 | 30 | 0 |
| 2022-08-01 00:00 | 41.2025 | 1697.6439 | 2974 | 2 | 0 |
| 2022-09-01 00:00 | 37.6155 | 1414.9265 | 2875 | 5 | 0 |
| 2022-10-01 00:00 | 22.9771 | 527.9488 | 2976 | 0 | 0 |
| 2022-11-01 00:00 | 10.4341 | 108.8706 | 2880 | 0 | 0 |
| 2022-12-01 00:00 | 9.2190 | 84.9895 | 2976 | 0 | 0 |
| 2023-01-01 00:00 | 11.2223 | 125.9409 | 2976 | 0 | 0 |
| 2023-02-01 00:00 | 16.3894 | 268.6114 | 2688 | 0 | 0 |
| 2023-03-01 00:00 | 13.9484 | 194.5568 | 2974 | 2 | 0 |
| 2023-04-01 00:00 | 7.6882 | 59.1091 | 2783 | 97 | 0 |
| 2023-05-01 00:00 | 11.6562 | 135.8674 | 2976 | 0 | 0 |
| 2023-06-01 00:00 | 28.1830 | 794.2840 | 2852 | 28 | 0 |
| 2023-07-01 00:00 | 28.9665 | 839.0587 | 2972 | 4 | 0 |
| 2023-08-01 00:00 | 28.0749 | 788.1976 | 2970 | 6 | 0 |
| 2023-09-01 00:00 | 27.9307 | 780.1233 | 2858 | 22 | 0 |
| 2023-10-01 00:00 | 25.3162 | 640.9114 | 2976 | 0 | 0 |
| 2023-11-01 00:00 | 13.3526 | 178.2908 | 2880 | 0 | 0 |
| 2023-12-01 00:00 | 11.6357 | 135.3893 | 2976 | 0 | 0 |
| 2024-01-01 00:00 | 16.2146 | 262.9117 | 2976 | 0 | 0 |
| 2024-02-01 00:00 | 13.7086 | 187.9255 | 2784 | 0 | 0 |
| 2024-03-01 00:00 | 11.1718 | 124.8094 | 2976 | 0 | 0 |
| 2024-04-01 00:00 | 8.7858 | 77.1910 | 2880 | 0 | 0 |
| 2024-05-01 00:00 | 13.7835 | 189.9841 | 2976 | 0 | 0 |
| 2024-06-01 00:00 | 21.5760 | 465.5256 | 2880 | 0 | 0 |
| 2024-07-01 00:00 | 28.1808 | 794.1572 | 2971 | 5 | 0 |
| 2024-08-01 00:00 | 49.2006 | 2420.6972 | 2882 | 94 | 0 |
| 2024-09-01 00:00 | 42.2604 | 1785.9374 | 2867 | 13 | 0 |
| 2024-10-01 00:00 | 22.7264 | 516.4877 | 2974 | 2 | 0 |
| 2024-11-01 00:00 | 21.8287 | 476.4941 | 2878 | 2 | 0 |
| 2024-12-01 00:00 | 15.8955 | 252.6661 | 2968 | 8 | 0 |
| 2025-01-01 00:00 | 11.0473 | 122.0426 | 2966 | 10 | 0 |
| 2025-02-01 00:00 | 10.5146 | 110.5562 | 2684 | 4 | 0 |
| 2025-03-01 00:00 | 6.0981 | 37.1866 | 2976 | 0 | 0 |
| 2025-04-01 00:00 | 9.8283 | 96.5955 | 2880 | 0 | 0 |
| 2025-05-01 00:00 | 23.1141 | 534.2612 | 2976 | 0 | 0 |
| 2025-06-01 00:00 | 25.9753 | 674.7180 | 2880 | 0 | 0 |
| 2025-07-01 00:00 | 41.8425 | 1750.7915 | 2974 | 2 | 0 |
| 2025-08-01 00:00 | 36.2755 | 1315.9104 | 2973 | 3 | 0 |
| 2025-09-01 00:00 | 42.8573 | 1836.7495 | 2878 | 2 | 0 |
| 2025-10-01 00:00 | 24.3713 | 593.9616 | 2976 | 0 | 0 |
| 2025-11-01 00:00 | 16.5691 | 274.5364 | 2880 | 0 | 0 |
| 2025-12-01 00:00 | 9.7536 | 95.1330 | 2964 | 12 | 0 |
| 2026-01-01 00:00 | 10.7856 | 116.3295 | 2965 | 11 | 0 |
| 2026-02-01 00:00 | 8.4314 | 71.0886 | 2675 | 13 | 0 |

By weekday (0=Monday, 6=Sunday):

| group | std_kW | variance_kW2 | observed_intervals | excluded_imputed | missing_observed |
|---|---|---|---|---|---|
| 0 | 38.7278 | 1499.8396 | 18314 | 22 | 0 |
| 1 | 37.6868 | 1420.2961 | 18253 | 83 | 0 |
| 2 | 37.3935 | 1398.2722 | 18272 | 64 | 0 |
| 3 | 37.1917 | 1383.2201 | 18325 | 11 | 0 |
| 4 | 36.5642 | 1336.9401 | 18421 | 11 | 0 |
| 5 | 31.3347 | 981.8637 | 18317 | 115 | 0 |
| 6 | 29.7560 | 885.4220 | 18265 | 71 | 0 |

Daily times: [table](eda_activity_daily.csv). Figure: [activity_and_variability.png](figures/activity_and_variability.png).

## B. PROVISIONAL vacation-like weeks

Excluded imputed rows: **377**; other missing/undefined observed rows for this parameter: **0**. Group-specific exclusions are included in the full CSV tables.

PROVISIONAL rule: abs(weekday_mean - weekend_mean) <=0.20*abs(weekend_mean). Saturday/Sunday are weekend. Both means must exist. A zero/zero week has collapsed contrast; positive weekday with zero weekend does not. Partial boundary weeks use the same rule and are explicitly flagged; their classification is less supported. This PROVISIONAL rule can also reflect holidays, outages or operational changes and does not establish university vacations.

PROVISIONAL vacation-like weeks: **75 / 192**; flagged partial among those: **0**.

| week_start | weekday_mean_kW | weekend_mean_kW | contrast | partial_week | observed_intervals | excluded_imputed |
|---|---|---|---|---|---|---|
| 2022-07-11 00:00 | 110.7666 | 100.0293 | 0.1073 | False | 672 | 0 |
| 2022-07-18 00:00 | 109.3886 | 99.3364 | 0.1012 | False | 657 | 15 |
| 2022-07-25 00:00 | 106.5329 | 95.5590 | 0.1148 | False | 657 | 15 |
| 2022-08-01 00:00 | 98.9199 | 92.3965 | 0.0706 | False | 672 | 0 |
| 2022-08-08 00:00 | 96.3952 | 88.1129 | 0.0940 | False | 672 | 0 |
| 2022-08-29 00:00 | 110.1315 | 95.0534 | 0.1586 | False | 672 | 0 |
| 2022-09-26 00:00 | 90.0901 | 77.4392 | 0.1634 | False | 667 | 5 |
| 2022-10-17 00:00 | 75.9223 | 69.5198 | 0.0921 | False | 672 | 0 |
| 2022-10-31 00:00 | 40.9140 | 35.8906 | 0.1400 | False | 672 | 0 |
| 2022-12-05 00:00 | 33.2837 | 27.7522 | 0.1993 | False | 672 | 0 |
| 2023-03-06 00:00 | 36.7025 | 30.6517 | 0.1974 | False | 672 | 0 |
| 2023-03-20 00:00 | 21.9806 | 18.8748 | 0.1646 | False | 670 | 2 |
| 2023-03-27 00:00 | 23.4782 | 21.4835 | 0.0928 | False | 672 | 0 |
| 2023-04-17 00:00 | 23.7455 | 20.4019 | 0.1639 | False | 672 | 0 |
| 2023-05-08 00:00 | 52.8659 | 51.5348 | 0.0258 | False | 672 | 0 |
| 2023-05-22 00:00 | 43.0594 | 45.8459 | 0.0608 | False | 672 | 0 |
| 2023-05-29 00:00 | 53.8150 | 46.8103 | 0.1496 | False | 672 | 0 |
| 2023-06-19 00:00 | 87.2306 | 87.6614 | 0.0049 | False | 672 | 0 |
| 2023-06-26 00:00 | 71.8551 | 70.0296 | 0.0261 | False | 672 | 0 |
| 2023-07-03 00:00 | 89.0054 | 81.3891 | 0.0936 | False | 672 | 0 |
| 2023-07-10 00:00 | 95.1496 | 84.2833 | 0.1289 | False | 672 | 0 |
| 2023-07-31 00:00 | 27.9036 | 25.7439 | 0.0839 | False | 668 | 4 |
| 2023-08-07 00:00 | 28.2439 | 23.5561 | 0.1990 | False | 672 | 0 |
| 2023-08-14 00:00 | 77.3224 | 74.5445 | 0.0373 | False | 670 | 2 |
| 2023-08-21 00:00 | 84.1647 | 75.5243 | 0.1144 | False | 672 | 0 |
| 2023-08-28 00:00 | 78.4203 | 66.4576 | 0.1800 | False | 668 | 4 |
| 2023-09-18 00:00 | 84.8942 | 71.6954 | 0.1841 | False | 650 | 22 |
| 2024-03-18 00:00 | 29.4008 | 26.1258 | 0.1254 | False | 672 | 0 |
| 2024-03-25 00:00 | 29.4453 | 25.8898 | 0.1373 | False | 672 | 0 |
| 2024-04-08 00:00 | 27.5030 | 26.7035 | 0.0299 | False | 672 | 0 |
| 2024-04-15 00:00 | 37.0057 | 30.8603 | 0.1991 | False | 672 | 0 |
| 2024-05-06 00:00 | 36.6861 | 31.2851 | 0.1726 | False | 672 | 0 |
| 2024-05-13 00:00 | 41.9416 | 37.3264 | 0.1236 | False | 672 | 0 |
| 2024-05-27 00:00 | 58.8915 | 63.2748 | 0.0693 | False | 672 | 0 |
| 2024-06-03 00:00 | 74.3903 | 67.9011 | 0.0956 | False | 672 | 0 |
| 2024-06-10 00:00 | 74.5043 | 62.8041 | 0.1863 | False | 672 | 0 |
| 2024-06-17 00:00 | 79.8589 | 72.4117 | 0.1028 | False | 672 | 0 |
| 2024-06-24 00:00 | 92.1250 | 77.9207 | 0.1823 | False | 672 | 0 |
| 2024-07-15 00:00 | 82.2807 | 72.1711 | 0.1401 | False | 672 | 0 |
| 2024-08-05 00:00 | 35.6679 | 32.7409 | 0.0894 | False | 578 | 94 |
| 2024-08-12 00:00 | 91.8474 | 89.1416 | 0.0304 | False | 672 | 0 |
| 2024-08-19 00:00 | 108.7963 | 126.2510 | 0.1383 | False | 672 | 0 |
| 2024-08-26 00:00 | 144.8255 | 152.1693 | 0.0483 | False | 672 | 0 |
| 2024-10-21 00:00 | 76.9442 | 67.6072 | 0.1381 | False | 672 | 0 |
| 2024-10-28 00:00 | 80.1880 | 71.9434 | 0.1146 | False | 672 | 0 |
| 2024-12-09 00:00 | 55.4468 | 47.2978 | 0.1723 | False | 668 | 4 |
| 2024-12-16 00:00 | 54.9026 | 55.4112 | 0.0092 | False | 672 | 0 |
| 2024-12-30 00:00 | 23.1995 | 22.2742 | 0.0415 | False | 672 | 0 |
| 2025-01-06 00:00 | 34.5919 | 29.9090 | 0.1566 | False | 672 | 0 |
| 2025-01-27 00:00 | 50.2466 | 43.9155 | 0.1442 | False | 670 | 2 |
| 2025-02-03 00:00 | 53.2771 | 45.8744 | 0.1614 | False | 672 | 0 |
| 2025-03-17 00:00 | 31.5748 | 27.4294 | 0.1511 | False | 672 | 0 |
| 2025-03-24 00:00 | 31.9184 | 29.5235 | 0.0811 | False | 672 | 0 |
| 2025-03-31 00:00 | 27.5415 | 28.3662 | 0.0291 | False | 672 | 0 |
| 2025-04-07 00:00 | 34.4510 | 32.3607 | 0.0646 | False | 672 | 0 |
| 2025-04-14 00:00 | 43.8107 | 38.3605 | 0.1421 | False | 672 | 0 |
| 2025-04-28 00:00 | 43.6978 | 41.9853 | 0.0408 | False | 672 | 0 |
| 2025-05-05 00:00 | 45.2403 | 42.2634 | 0.0704 | False | 672 | 0 |
| 2025-05-19 00:00 | 78.6756 | 77.4801 | 0.0154 | False | 672 | 0 |
| 2025-05-26 00:00 | 80.5848 | 74.6699 | 0.0792 | False | 672 | 0 |
| 2025-06-02 00:00 | 83.4648 | 80.4598 | 0.0373 | False | 672 | 0 |
| 2025-06-16 00:00 | 100.1749 | 91.4991 | 0.0948 | False | 672 | 0 |
| 2025-06-23 00:00 | 123.1978 | 111.0053 | 0.1098 | False | 672 | 0 |
| 2025-06-30 00:00 | 129.3253 | 133.9660 | 0.0346 | False | 670 | 2 |
| 2025-07-07 00:00 | 127.3985 | 113.3670 | 0.1238 | False | 672 | 0 |
| 2025-07-14 00:00 | 129.5855 | 112.0198 | 0.1568 | False | 672 | 0 |
| 2025-07-28 00:00 | 34.4239 | 36.8663 | 0.0663 | False | 672 | 0 |
| 2025-08-11 00:00 | 108.9776 | 100.8141 | 0.0810 | False | 669 | 3 |
| 2025-10-27 00:00 | 68.5577 | 75.5422 | 0.0925 | False | 672 | 0 |
| 2025-12-15 00:00 | 46.4412 | 41.6073 | 0.1162 | False | 672 | 0 |
| 2025-12-29 00:00 | 36.1897 | 31.7444 | 0.1400 | False | 672 | 0 |
| 2026-01-26 00:00 | 50.0341 | 50.1049 | 0.0014 | False | 648 | 24 |
| 2026-02-02 00:00 | 60.1675 | 60.4232 | 0.0042 | False | 672 | 0 |
| 2026-02-09 00:00 | 62.7575 | 56.8628 | 0.1037 | False | 672 | 0 |
| 2026-02-16 00:00 | 61.1086 | 54.9868 | 0.1113 | False | 672 | 0 |

Full PROVISIONAL weekly table: [table](eda_PROVISIONAL_calendar_weeks.csv). PROVISIONAL timeline: [PROVISIONAL_vacation_timeline.png](figures/PROVISIONAL_vacation_timeline.png).

## 6. Seasonality

Excluded imputed rows: **377**; other missing/undefined observed rows for this parameter: **1**. Group-specific exclusions are included in the full CSV tables.

Summer/winter energy-rate ratio: **2.1802** using mean observed dEa ×96 (coverage-normalized daily equivalents). Ratio of mean monthly observed totals: **2.2185**. These avoid confusing unequal numbers of summer/winter months with higher consumption.

| season | total_kWh | observed_daily_equivalent_kWh | mean_monthly_observed_kWh | month_count | observed_intervals | excluded_imputed | missing_observed |
|---|---|---|---|---|---|---|---|
| Autumn | 644079.7000 | 1771.7821 | 53673.3083 | 12 | 34898 | 46 | 0 |
| Spring | 248379.7000 | 903.3016 | 27597.7444 | 9 | 26397 | 99 | 0 |
| Summer | 701924.8000 | 2087.9615 | 63811.3455 | 11 | 32273 | 174 | 1 |
| Winter | 345154.9000 | 957.7106 | 28762.9083 | 12 | 34598 | 58 | 0 |

All monthly totals:

| period | energy_kWh | observed_intervals | excluded_imputed | missing_observed | running_total_kWh |
|---|---|---|---|---|---|
| 2022-07-01 00:00 | 74975.8000 | 2945 | 30 | 1 | 74975.8000 |
| 2022-08-01 00:00 | 84218.3000 | 2974 | 2 | 0 | 159194.1000 |
| 2022-09-01 00:00 | 79296.5000 | 2875 | 5 | 0 | 238490.6000 |
| 2022-10-01 00:00 | 51190.0000 | 2976 | 0 | 0 | 289680.6000 |
| 2022-11-01 00:00 | 26114.9000 | 2880 | 0 | 0 | 315795.5000 |
| 2022-12-01 00:00 | 21688.5000 | 2976 | 0 | 0 | 337484.0000 |
| 2023-01-01 00:00 | 22378.7000 | 2976 | 0 | 0 | 359862.7000 |
| 2023-02-01 00:00 | 24601.2000 | 2688 | 0 | 0 | 384463.9000 |
| 2023-03-01 00:00 | 23097.3000 | 2974 | 2 | 0 | 407561.2000 |
| 2023-04-01 00:00 | 17923.7000 | 2783 | 97 | 0 | 425484.9000 |
| 2023-05-01 00:00 | 34839.3000 | 2976 | 0 | 0 | 460324.2000 |
| 2023-06-01 00:00 | 43836.6000 | 2852 | 28 | 0 | 504160.8000 |
| 2023-07-01 00:00 | 63227.3000 | 2972 | 4 | 0 | 567388.1000 |
| 2023-08-01 00:00 | 42393.9000 | 2970 | 6 | 0 | 609782.0000 |
| 2023-09-01 00:00 | 57198.9000 | 2858 | 22 | 0 | 666980.9000 |
| 2023-10-01 00:00 | 52987.0000 | 2976 | 0 | 0 | 719967.9000 |
| 2023-11-01 00:00 | 27010.4000 | 2880 | 0 | 0 | 746978.3000 |
| 2023-12-01 00:00 | 23376.7000 | 2976 | 0 | 0 | 770355.0000 |
| 2024-01-01 00:00 | 30289.3000 | 2976 | 0 | 0 | 800644.3000 |
| 2024-02-01 00:00 | 27969.9000 | 2784 | 0 | 0 | 828614.2000 |
| 2024-03-01 00:00 | 25194.7000 | 2976 | 0 | 0 | 853808.9000 |
| 2024-04-01 00:00 | 24094.7000 | 2880 | 0 | 0 | 877903.6000 |
| 2024-05-01 00:00 | 28556.1000 | 2976 | 0 | 0 | 906459.7000 |
| 2024-06-01 00:00 | 55029.4000 | 2880 | 0 | 0 | 961489.1000 |
| 2024-07-01 00:00 | 55353.2000 | 2971 | 5 | 0 | 1016842.3000 |
| 2024-08-01 00:00 | 64477.8000 | 2882 | 94 | 0 | 1081320.1000 |
| 2024-09-01 00:00 | 74663.7000 | 2867 | 13 | 0 | 1155983.8000 |
| 2024-10-01 00:00 | 62759.9000 | 2974 | 2 | 0 | 1218743.7000 |
| 2024-11-01 00:00 | 35919.9000 | 2878 | 2 | 0 | 1254663.6000 |
| 2024-12-01 00:00 | 31784.6000 | 2968 | 8 | 0 | 1286448.2000 |
| 2025-01-01 00:00 | 26408.5000 | 2966 | 10 | 0 | 1312856.7000 |
| 2025-02-01 00:00 | 33300.1000 | 2684 | 4 | 0 | 1346156.8000 |
| 2025-03-01 00:00 | 23840.3000 | 2976 | 0 | 0 | 1369997.1000 |
| 2025-04-01 00:00 | 27222.5000 | 2880 | 0 | 0 | 1397219.6000 |
| 2025-05-01 00:00 | 43611.1000 | 2976 | 0 | 0 | 1440830.7000 |
| 2025-06-01 00:00 | 69384.4000 | 2880 | 0 | 0 | 1510215.1000 |
| 2025-07-01 00:00 | 81146.2000 | 2974 | 2 | 0 | 1591361.3000 |
| 2025-08-01 00:00 | 67881.9000 | 2973 | 3 | 0 | 1659243.2000 |
| 2025-09-01 00:00 | 88389.9000 | 2878 | 2 | 0 | 1747633.1000 |
| 2025-10-01 00:00 | 51023.6000 | 2976 | 0 | 0 | 1798656.7000 |
| 2025-11-01 00:00 | 37525.0000 | 2880 | 0 | 0 | 1836181.7000 |
| 2025-12-01 00:00 | 31934.3000 | 2964 | 12 | 0 | 1868116.0000 |
| 2026-01-01 00:00 | 32353.1000 | 2965 | 11 | 0 | 1900469.1000 |
| 2026-02-01 00:00 | 39070.0000 | 2675 | 13 | 0 | 1939539.1000 |

Figures: [monthly_energy_seasonality.png](figures/monthly_energy_seasonality.png), [seasonal_daily_profiles.png](figures/seasonal_daily_profiles.png).

## 7. Autocorrelation and later baseline/context choices

Excluded imputed rows: **377**; other missing/undefined observed rows for this parameter: **1**. Group-specific exclusions are included in the full CSV tables.

ACF uses pairwise Pearson correlation of dEa at original grid lags 0–700; both endpoints must be observed and finite. Pair-specific excluded counts are listed below and in the full CSV. It is not an ACF of a compressed observed-only sequence.

| lag | correlation | observed_pairs | excluded_imputed_pairs | other_missing_pairs |
|---|---|---|---|---|
| 0 | 1.0000 | 128166 | 377 | 1 |
| 96 | 0.8622 | 127694 | 753 | 1 |
| 672 | 0.7856 | 127120 | 751 | 1 |
| 700 | 0.6324 | 127094 | 749 | 1 |

Observed daily lag-96 correlation is **0.8622**; weekly lag-672 is **0.7856**. These positive correlations provide empirical evidence for evaluating daily/weekly seasonal-naive baselines and the proposed 672-step input context. They do not prove that 672 is optimal; trend/annual seasonality can contribute. No baseline or model was fitted.

Figure: [energy_autocorrelation.png](figures/energy_autocorrelation.png).

## 8. Power factor, inductive intervals and Phase 5 screening

Excluded imputed rows: **377**; other missing/undefined observed rows for this parameter: **0**. Group-specific exclusions are included in the full CSV tables.

Counts use strict PF<0.90 and PF<0.80. For EDA screening only, any such observed interval makes the month a warning/severe Phase 5 interval candidate, respectively. A separate monthly-mean candidate applies the same cutoffs to mean PF. An official persistence/duration alert policy was not supplied; these are candidates, not deployed alerts. PF alerts must exclude reconstructed data. Positive Q is the inductive share of finite observed Q intervals.

| month | mean_PF | minimum_PF | PF_intervals | below_090 | below_080 | Phase5_screening_candidate | Phase5_monthly_mean_candidate | positive_Q_intervals | Q_intervals | positive_Q_share | observed_intervals | excluded_imputed | missing_observed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022-07-01 00:00 | 0.9452 | 0.9029 | 2946 | 0 | 0 | none | none | 2946 | 2946 | 1.0000 | 2946 | 30 | 0 |
| 2022-08-01 00:00 | 0.9397 | 0.9015 | 2974 | 0 | 0 | none | none | 2974 | 2974 | 1.0000 | 2974 | 2 | 0 |
| 2022-09-01 00:00 | 0.9447 | 0.9024 | 2875 | 0 | 0 | none | none | 2875 | 2875 | 1.0000 | 2875 | 5 | 0 |
| 2022-10-01 00:00 | 0.9617 | 0.9141 | 2976 | 0 | 0 | none | none | 2334 | 2976 | 0.7843 | 2976 | 0 | 0 |
| 2022-11-01 00:00 | 0.9449 | 0.8561 | 2880 | 24 | 0 | warning | none | 1 | 2880 | 0.0003 | 2880 | 0 | 0 |
| 2022-12-01 00:00 | 0.9337 | 0.8698 | 2976 | 181 | 0 | warning | none | 0 | 2976 | 0.0000 | 2976 | 0 | 0 |
| 2023-01-01 00:00 | 0.9299 | 0.8700 | 2976 | 122 | 0 | warning | none | 0 | 2976 | 0.0000 | 2976 | 0 | 0 |
| 2023-02-01 00:00 | 0.9474 | 0.8771 | 2688 | 41 | 0 | warning | none | 719 | 2688 | 0.2675 | 2688 | 0 | 0 |
| 2023-03-01 00:00 | 0.9391 | 0.8551 | 2974 | 256 | 0 | warning | none | 736 | 2974 | 0.2475 | 2974 | 2 | 0 |
| 2023-04-01 00:00 | 0.8817 | 0.6317 | 2783 | 965 | 571 | severe | warning | 7 | 2783 | 0.0025 | 2783 | 97 | 0 |
| 2023-05-01 00:00 | 0.9514 | 0.7922 | 2976 | 613 | 4 | severe | none | 359 | 2976 | 0.1206 | 2976 | 0 | 0 |
| 2023-06-01 00:00 | 0.9682 | 0.9063 | 2852 | 0 | 0 | none | none | 2649 | 2852 | 0.9288 | 2852 | 28 | 0 |
| 2023-07-01 00:00 | 0.9522 | 0.9127 | 2972 | 0 | 0 | none | none | 2773 | 2972 | 0.9330 | 2972 | 4 | 0 |
| 2023-08-01 00:00 | 0.9797 | 0.9193 | 2970 | 0 | 0 | none | none | 1895 | 2970 | 0.6380 | 2970 | 6 | 0 |
| 2023-09-01 00:00 | 0.9760 | 0.9280 | 2858 | 0 | 0 | none | none | 2414 | 2858 | 0.8446 | 2858 | 22 | 0 |
| 2023-10-01 00:00 | 0.9689 | 0.7629 | 2976 | 140 | 2 | severe | none | 2513 | 2976 | 0.8444 | 2976 | 0 | 0 |
| 2023-11-01 00:00 | 0.9658 | 0.8942 | 2880 | 6 | 0 | warning | none | 430 | 2880 | 0.1493 | 2880 | 0 | 0 |
| 2023-12-01 00:00 | 0.9468 | 0.7169 | 2976 | 137 | 38 | severe | none | 576 | 2976 | 0.1935 | 2976 | 0 | 0 |
| 2024-01-01 00:00 | 0.9622 | 0.8762 | 2976 | 6 | 0 | warning | none | 1207 | 2976 | 0.4056 | 2976 | 0 | 0 |
| 2024-02-01 00:00 | 0.9680 | 0.8841 | 2784 | 21 | 0 | warning | none | 1685 | 2784 | 0.6052 | 2784 | 0 | 0 |
| 2024-03-01 00:00 | 0.9633 | 0.8925 | 2976 | 9 | 0 | warning | none | 1054 | 2976 | 0.3542 | 2976 | 0 | 0 |
| 2024-04-01 00:00 | 0.9470 | 0.8241 | 2880 | 15 | 0 | warning | none | 150 | 2880 | 0.0521 | 2880 | 0 | 0 |
| 2024-05-01 00:00 | 0.9317 | 0.7688 | 2976 | 630 | 12 | severe | none | 396 | 2976 | 0.1331 | 2976 | 0 | 0 |
| 2024-06-01 00:00 | 0.9531 | 0.9089 | 2880 | 0 | 0 | none | none | 2880 | 2880 | 1.0000 | 2880 | 0 | 0 |
| 2024-07-01 00:00 | 0.9662 | 0.9086 | 2971 | 0 | 0 | none | none | 2472 | 2971 | 0.8320 | 2971 | 5 | 0 |
| 2024-08-01 00:00 | 0.9681 | 0.9127 | 2882 | 0 | 0 | none | none | 1882 | 2882 | 0.6530 | 2882 | 94 | 0 |
| 2024-09-01 00:00 | 0.9810 | 0.9230 | 2867 | 0 | 0 | none | none | 2699 | 2867 | 0.9414 | 2867 | 13 | 0 |
| 2024-10-01 00:00 | 0.9899 | 0.9538 | 2974 | 0 | 0 | none | none | 2446 | 2974 | 0.8225 | 2974 | 2 | 0 |
| 2024-11-01 00:00 | 0.8731 | 0.6202 | 2878 | 1495 | 983 | severe | warning | 600 | 2878 | 0.2085 | 2878 | 2 | 0 |
| 2024-12-01 00:00 | 0.8830 | 0.6221 | 2968 | 1267 | 714 | severe | warning | 15 | 2968 | 0.0051 | 2968 | 8 | 0 |
| 2025-01-01 00:00 | 0.9397 | 0.7475 | 2966 | 639 | 158 | severe | none | 118 | 2966 | 0.0398 | 2966 | 10 | 0 |
| 2025-02-01 00:00 | 0.9521 | 0.7698 | 2684 | 281 | 81 | severe | none | 30 | 2684 | 0.0112 | 2684 | 4 | 0 |
| 2025-03-01 00:00 | 0.8187 | 0.7207 | 2976 | 2857 | 984 | severe | warning | 0 | 2976 | 0.0000 | 2976 | 0 | 0 |
| 2025-04-01 00:00 | 0.8185 | 0.6333 | 2880 | 2787 | 916 | severe | warning | 0 | 2880 | 0.0000 | 2880 | 0 | 0 |
| 2025-05-01 00:00 | 0.9004 | 0.7596 | 2976 | 1830 | 20 | severe | none | 1097 | 2976 | 0.3686 | 2976 | 0 | 0 |
| 2025-06-01 00:00 | 0.9765 | 0.9402 | 2880 | 0 | 0 | none | none | 2826 | 2880 | 0.9812 | 2880 | 0 | 0 |
| 2025-07-01 00:00 | 0.9461 | 0.7949 | 2974 | 500 | 2 | severe | none | 2446 | 2974 | 0.8225 | 2974 | 2 | 0 |
| 2025-08-01 00:00 | 0.9432 | 0.7479 | 2973 | 708 | 25 | severe | none | 2264 | 2973 | 0.7615 | 2973 | 3 | 0 |
| 2025-09-01 00:00 | 0.9772 | 0.9450 | 2878 | 0 | 0 | none | none | 2842 | 2878 | 0.9875 | 2878 | 2 | 0 |
| 2025-10-01 00:00 | 0.9495 | 0.8050 | 2976 | 591 | 0 | warning | none | 998 | 2976 | 0.3353 | 2976 | 0 | 0 |
| 2025-11-01 00:00 | 0.8851 | 0.7886 | 2880 | 1955 | 5 | severe | warning | 254 | 2880 | 0.0882 | 2880 | 0 | 0 |
| 2025-12-01 00:00 | 0.8716 | 0.6089 | 2964 | 2097 | 84 | severe | warning | 0 | 2964 | 0.0000 | 2964 | 12 | 0 |
| 2026-01-01 00:00 | 0.9340 | 0.8522 | 2965 | 638 | 0 | warning | none | 54 | 2965 | 0.0182 | 2965 | 11 | 0 |
| 2026-02-01 00:00 | 0.9823 | 0.9162 | 2675 | 0 | 0 | none | none | 2374 | 2675 | 0.8875 | 2675 | 13 | 0 |

Figure: [monthly_power_factor.png](figures/monthly_power_factor.png).

## 9. Apparent-load duration and the supplied 600 kVA subscription

Excluded imputed rows: **377**; other missing/undefined observed rows for this parameter: **0**. Group-specific exclusions are included in the full CSV tables.

Maximum observed S_avg: **303.2238 kVA**, or **50.537%** of the supplied 600 kVA reference.

| index | fraction_of_subscription | threshold_kVA | intervals_above | percent_above | observed_intervals | excluded_imputed | missing_observed |
|---|---|---|---|---|---|---|---|
| 0 | 0.5000 | 300.0000 | 3 | 0.0023 | 128167 | 377 | 0 |
| 1 | 0.6000 | 360.0000 | 0 | 0.0000 | 128167 | 377 | 0 |
| 2 | 0.7000 | 420.0000 | 0 | 0.0000 | 128167 | 377 | 0 |
| 3 | 0.8000 | 480.0000 | 0 | 0.0000 | 128167 | 377 | 0 |

These measured exceedances are evidence for evaluating subscription headroom. They do not select a new subscription: excluded observations and interval-average peaks do not establish unobserved/transient demand, and no tariff calculation was performed.

Figure: [apparent_load_duration.png](figures/apparent_load_duration.png).

## 10. Demand-channel divergence: test the seasonal pattern

Excluded imputed rows: **377**; other missing/undefined observed rows for this parameter: **40**. Group-specific exclusions are included in the full CSV tables.

Demand-minus-average is a diagnostic, not an ordering invariant. Report both signed and absolute differences so sign changes are not hidden.

| season | mean_gap_kVA | mean_absolute_gap_kVA | observed_intervals | excluded_imputed | missing_observed |
|---|---|---|---|---|---|
| Autumn | 0.2905 | 8.1221 | 34888 | 46 | 10 |
| Spring | 0.1157 | 1.9763 | 26391 | 99 | 6 |
| Summer | 0.1184 | 11.1187 | 32262 | 174 | 12 |
| Winter | 0.0317 | 1.0856 | 34586 | 58 | 12 |

Summer mean absolute gap **11.1187 kVA** versus winter **1.0856 kVA**. The proposed summer-widening pattern is SUPPORTED in mean absolute gap. This seasonal association alone cannot establish air-conditioning as its cause; meter changes below provide separate descriptive evidence. No result is assumed from the equipment names.

Full monthly aggregation: [table](eda_demand_divergence_monthly.csv). Figure: [monthly_demand_gap.png](figures/monthly_demand_gap.png).

## 11. Meter contributions and the summer rise

Excluded imputed rows: **5,634**; other missing/undefined observed rows for this parameter: **10,257**. Group-specific exclusions are included in the full CSV tables.

Shares use each meter's observed monthly dEa divided by EM_VIRTUAL observed monthly dEa. Transformer and downstream meters overlap; do not add their shares. Different missing/imputed coverage also affects these ratios. For seasonal attribution the table compares mean observed P rather than sums over unequal season lengths. These are descriptive contributors, not a validated disjoint electrical topology.

| meter | Summer_mean_kW | Summer_excluded_imputed | Summer_observed_intervals | Winter_mean_kW | Winter_excluded_imputed | Winter_observed_intervals | summer_minus_winter_kW |
|---|---|---|---|---|---|---|---|
| TGBT_TR2 | 72.9718 | 174 | 32274 | 10.1138 | 58 | 34598 | 62.8580 |
| EM_VIRTUAL | 87.0033 | 174 | 32274 | 39.9053 | 58 | 34598 | 47.0980 |
| CLIM_SALLE_IT_(TGBT_D1) | 4.3291 | 174 | 32274 | 0.0456 | 58 | 34598 | 4.2835 |
| CLIM_TOUR_A_(TGBT_D6) | 1.8337 | 174 | 32274 | 0.0000 | 58 | 34598 | 1.8337 |
| ONDULEUR_1_(TGBT_DXX) | 3.6845 | 184 | 32264 | 3.6065 | 179 | 32058 | 0.0780 |
| SALLE_B112_(A._MEZAN_TOUR_B) | 0.0129 | 212 | 32236 | 0.0229 | 58 | 34598 | -0.0100 |
| SALLE_B201_(A_1_ETAGE_TOUR_B) | 0.7838 | 212 | 32236 | 0.7982 | 58 | 34598 | -0.0144 |
| SALLE_B101_(A._MEZAN_TOUR_B) | 0.6868 | 212 | 32236 | 0.7458 | 58 | 34598 | -0.0590 |
| ONDULEUR_2_(TGBT_DXX) | 2.8819 | 181 | 32046 | 3.0354 | 174 | 34482 | -0.1535 |
| TOUR_A_(TGBT_D14) | 2.9200 | 174 | 32274 | 3.3889 | 50 | 31822 | -0.4689 |
| TOUR_C_(TGBT_D10) | 1.3661 | 174 | 32274 | 1.8906 | 50 | 31822 | -0.5246 |
| Tour_B_(TGBT_D5) | 3.4112 | 174 | 32274 | 4.0110 | 58 | 34598 | -0.5998 |
| PV_(CHAUFFERIE_PROV.) | 0.0140 | 174 | 32274 | 3.4481 | 58 | 34598 | -3.4341 |
| TGBT_TR1 | 14.0315 | 174 | 32274 | 29.7915 | 58 | 34598 | -15.7600 |

Among downstream meter names, the two CLIM channels have the largest positive summer-minus-winter mean-power changes. Their tabled increases are only a partial explanation of the site's summer rise, not a complete air-conditioning allocation. At transformer level, TGBT_TR2's increase is partly offset by TGBT_TR1's decrease; do not count these again as downstream contributions.

All meter/month shares: [table](eda_meter_contributions_monthly.csv). Figures: [monthly_meter_shares.png](figures/monthly_meter_shares.png), [summer_meter_changes.png](figures/summer_meter_changes.png).

## D. Proposed split validation — counts only

Excluded imputed rows: **377**; other missing/undefined observed rows for this parameter: **1**. Group-specific exclusions are included in the full CSV tables.

Train/val/test boundaries are exactly the proposal, with end dates inclusive by calendar day. Eligibility requires 672 consecutive finite input slots and 96 following observed, finite target slots (dEa,dEr,P_avg,S_avg). Imputed INPUTS are permitted; imputed labels are not. Targets stay inside their split. Both strict within-split history and prior-split historical context counts are shown. No window arrays, labels or model features were created.

| split | start | end_exclusive | grid_rows | observed_complete_rows | excluded_imputed | missing_observed | eligible_origins_prior_context | eligible_origins_strict_context | history_unavailable_origins | target_boundary_origins | target_unobserved_origins |
|---|---|---|---|---|---|---|---|---|---|---|---|
| train | 2022-07-01 00:00 | 2025-03-01 00:00 | 93504 | 93169 | 334 | 1 | 90027 | 90027 | 672 | 96 | 2709 |
| val | 2025-03-01 00:00 | 2025-09-01 00:00 | 17664 | 17659 | 5 | 0 | 17373 | 16702 | 0 | 96 | 195 |
| test | 2025-09-01 00:00 | 2026-03-01 00:00 | 17376 | 17338 | 38 | 0 | 16862 | 16191 | 0 | 96 | 418 |

All three partitions have nonzero, workable counts of eligible overlapping origins for later sample construction. These counts do not imply independent samples or prove statistical adequacy. The initial unavailable-history range and all target-imputation/boundary exclusions are recorded below.

The claim that EACH validation/test period spans both meteorological summer and winter is false: validation (March–August 2025) contains spring and summer, with NO DJF winter; test (September 2025–February 2026) contains autumn and winter, with NO JJA summer. September may have high measured load, but that does not make it a meteorological summer month. Thus these are populated chronological splits, not demonstrated season-balanced validation/test sets.

Both validation and test nevertheless contain measured high- and low-load months; the table distinguishes energy-regime coverage from meteorological season labels:

| split | high_load_month | high_month_observed_kWh | high_month_excluded_imputed | low_load_month | low_month_observed_kWh | low_month_excluded_imputed |
|---|---|---|---|---|---|---|
| train | 2022-08-01 00:00 | 84218.3000 | 2 | 2023-04-01 00:00 | 17923.7000 | 97 |
| val | 2025-07-01 00:00 | 81146.2000 | 2 | 2025-03-01 00:00 | 23840.3000 | 0 |
| test | 2025-09-01 00:00 | 88389.9000 | 2 | 2025-12-01 00:00 | 31934.3000 | 12 |

Longest blocked-origin runs per split (all ranges are in eda_splits_blocked_origin_runs.csv):

| split | first_origin | last_origin | intervals |
|---|---|---|---|
| train | 2022-07-01 00:00 | 2022-07-07 23:45 | 672 |
| train | 2023-04-28 00:00 | 2023-04-29 23:45 | 192 |
| train | 2024-08-05 10:15 | 2024-08-07 09:15 | 189 |
| test | 2026-01-31 04:45 | 2026-02-01 07:30 | 108 |
| test | 2025-12-06 09:15 | 2025-12-07 11:45 | 107 |
| test | 2026-01-29 04:45 | 2026-01-30 07:00 | 106 |
| val | 2025-08-10 09:15 | 2025-08-11 09:30 | 98 |
| val | 2025-06-30 09:00 | 2025-07-01 09:00 | 97 |
| val | 2025-08-31 00:00 | 2025-08-31 23:45 | 96 |

Split counts are provisional feasibility checks on the existing analysis artifact. Before modeling, actual split boundaries and the imputation leakage policy must be enforced; ingestion/imputation was not rerun here.

## Three findings for the modelling phase

1. Seasonal load differs: summer/winter observed daily-energy rate ratio 2.1802. Use calendar/season-aware comparisons and chronological evaluation, not random splits.
2. Observed lag correlations at 96/672 are 0.8622/0.7856; evaluate both seasonal-naive baselines and the proposed week-long context without assuming an optimal model.
3. The proposed split season-balance claim fails. Eligible prior-context origins are train=90027, val=17373, test=16862; keep imputed targets excluded and review seasonal coverage with the supervisor.

## Figures (all PNG, 150 dpi)

| Figure | Parameter | Excluded imputed rows | Other missing observed |
|---|---|---:|---:|
| [energy_totals.png](figures/energy_totals.png) | energy | 377 | 1 |
| [base_load_and_hour.png](figures/base_load_and_hour.png) | base_load | 377 | 0 |
| [daily_peaks_and_duration.png](figures/daily_peaks_and_duration.png) | peaks | 377 | 0 |
| [mean_power_comparisons.png](figures/mean_power_comparisons.png) | power_comparisons | 377 | 0 |
| [activity_and_variability.png](figures/activity_and_variability.png) | activity | 377 | 0 |
| [PROVISIONAL_vacation_timeline.png](figures/PROVISIONAL_vacation_timeline.png) | PROVISIONAL_calendar | 377 | 0 |
| [monthly_energy_seasonality.png](figures/monthly_energy_seasonality.png) | seasonality | 377 | 1 |
| [seasonal_daily_profiles.png](figures/seasonal_daily_profiles.png) | seasonality | 377 | 1 |
| [energy_autocorrelation.png](figures/energy_autocorrelation.png) | autocorrelation | 377 | 1 |
| [monthly_power_factor.png](figures/monthly_power_factor.png) | power_factor | 377 | 0 |
| [apparent_load_duration.png](figures/apparent_load_duration.png) | load_duration | 377 | 0 |
| [monthly_demand_gap.png](figures/monthly_demand_gap.png) | demand_divergence | 377 | 40 |
| [monthly_meter_shares.png](figures/monthly_meter_shares.png) | meter_contributions | 5634 | 10257 |
| [summer_meter_changes.png](figures/summer_meter_changes.png) | meter_contributions | 5634 | 10257 |

## Input provenance

Input SHA-256 hashes were checked unchanged after EDA:

- `em_virtual.parquet`: `6c45c14bcab15a45bf8ebe2f88329de121e4e137774fe8f316bb6f7dd6b05bbe`
- `all_meters.parquet`: `e3f44ae7b5170bb9bab158c51a3d24054ef974cc7883a4c29d280949d748033e`

## Synthetic pytest output

```text
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.2.0, pluggy-1.7.0 -- /home/khalifa/supcom-energy-forcast/envs/main/bin/python
cachedir: cache/pytest-eda
rootdir: /home/khalifa/supcom-energy-forcast
plugins: platformdirs-4.14.5, anyio-4.16.0
collecting ... collected 24 items

tests/test_behaviour.py::test_peak_duration_is_consecutive_not_sum_of_disconnected_bands PASSED [  4%]
tests/test_behaviour.py::test_imputed_interval_and_timestamp_hole_break_peak_runs PASSED [  8%]
tests/test_behaviour.py::test_entirely_imputed_day_has_undefined_peak_duration_not_zero PASSED [ 12%]
tests/test_behaviour.py::test_flat_day_has_none_activation_and_deactivation PASSED [ 16%]
tests/test_behaviour.py::test_activity_uses_first_and_last_observed_15x_minimum_crossing PASSED [ 20%]
tests/test_behaviour.py::test_saturday_sunday_are_weekend_and_friday_monday_are_weekday PASSED [ 25%]
tests/test_behaviour.py::test_PROVISIONAL_flat_week_is_flagged_but_normal_week_is_not PASSED [ 29%]
tests/test_behaviour.py::test_PROVISIONAL_week_rule_inclusive_20_percent_boundary PASSED [ 33%]
tests/test_behaviour.py::test_every_parameter_ignores_imputed_measurements[cumulative_energy] PASSED [ 37%]
tests/test_behaviour.py::test_every_parameter_ignores_imputed_measurements[base_load] PASSED [ 41%]
tests/test_behaviour.py::test_every_parameter_ignores_imputed_measurements[peak_demand] PASSED [ 45%]
tests/test_behaviour.py::test_every_parameter_ignores_imputed_measurements[power_comparisons] PASSED [ 50%]
tests/test_behaviour.py::test_every_parameter_ignores_imputed_measurements[site_behaviour] PASSED [ 54%]
tests/test_behaviour.py::test_every_parameter_ignores_imputed_measurements[provisional_vacation_weeks] PASSED [ 58%]
tests/test_behaviour.py::test_every_parameter_ignores_imputed_measurements[seasonality] PASSED [ 62%]
tests/test_behaviour.py::test_every_parameter_ignores_imputed_measurements[autocorrelation] PASSED [ 66%]
tests/test_behaviour.py::test_every_parameter_ignores_imputed_measurements[power_factor] PASSED [ 70%]
tests/test_behaviour.py::test_every_parameter_ignores_imputed_measurements[load_duration] PASSED [ 75%]
tests/test_behaviour.py::test_every_parameter_ignores_imputed_measurements[demand_divergence] PASSED [ 79%]
tests/test_behaviour.py::test_every_parameter_ignores_imputed_measurements[split_coverage] PASSED [ 83%]
tests/test_behaviour.py::test_meter_contribution_ignores_imputed_measurements PASSED [ 87%]
tests/test_behaviour.py::test_acf_keeps_original_lag_positions_and_reports_pair_exclusions PASSED [ 91%]
tests/test_behaviour.py::test_observed_energy_sums_match_every_temporal_scale PASSED [ 95%]
tests/test_behaviour.py::test_split_counts_require_observed_labels_and_do_not_create_windows PASSED [100%]

============================== 24 passed in 3.23s ==============================
```
