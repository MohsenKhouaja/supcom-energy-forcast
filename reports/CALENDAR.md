# Academic calendar — RECONSTRUCTED, not official

The user has only the official 2026/2027 calendar; it was not supplied to this run. The four earlier academic years below are reconstructed from the user-supplied structure, not verified institutional dates. Replace the rules when the supervisor provides the calendars. Every academic output is RECONSTRUCTED, not official.

## Configurable rules

[configs/calendar.yaml](../configs/calendar.yaml) uses JSON syntax valid in YAML 1.2. Winter starts on Monday of the week containing 25 December (weeks_before=0) and ends Sunday of the following week (weeks_after=1). Exams occupy the next two ISO weeks and are working periods. Spring is ISO week 14. Aid Al Fitr vacation is the ISO week containing the package's first Eid al-Fitr day. Overlapping vacations are unioned. Rentree is 1 September, fin d'annee is 10 July, closure is 11 July–31 August.

## Every derived date for the four academic years

| academic_year | period | start | end | is_vacation | context_only | status |
|---|---|---|---|---|---|---|
| 2022/2023 | rentree | 2022-09-01 00:00:00 | 2022-09-01 00:00:00 | False | False | RECONSTRUCTED, not official |
| 2022/2023 | vacances hiver | 2022-12-19 00:00:00 | 2023-01-01 00:00:00 | True | False | RECONSTRUCTED, not official |
| 2022/2023 | exams Sem 1 | 2023-01-02 00:00:00 | 2023-01-15 00:00:00 | False | False | RECONSTRUCTED, not official |
| 2022/2023 | vacances printemps | 2023-04-03 00:00:00 | 2023-04-09 00:00:00 | True | False | RECONSTRUCTED, not official |
| 2022/2023 | vacances Aid Al Fitr | 2023-04-17 00:00:00 | 2023-04-23 00:00:00 | True | False | RECONSTRUCTED, not official |
| 2022/2023 | fin annee | 2023-07-10 00:00:00 | 2023-07-10 00:00:00 | False | False | RECONSTRUCTED, not official |
| 2022/2023 | summer closure | 2023-07-11 00:00:00 | 2023-08-31 00:00:00 | True | False | RECONSTRUCTED, not official |
| 2023/2024 | rentree | 2023-09-01 00:00:00 | 2023-09-01 00:00:00 | False | False | RECONSTRUCTED, not official |
| 2023/2024 | vacances hiver | 2023-12-25 00:00:00 | 2024-01-07 00:00:00 | True | False | RECONSTRUCTED, not official |
| 2023/2024 | exams Sem 1 | 2024-01-08 00:00:00 | 2024-01-21 00:00:00 | False | False | RECONSTRUCTED, not official |
| 2023/2024 | vacances printemps | 2024-04-01 00:00:00 | 2024-04-07 00:00:00 | True | False | RECONSTRUCTED, not official |
| 2023/2024 | vacances Aid Al Fitr | 2024-04-08 00:00:00 | 2024-04-14 00:00:00 | True | False | RECONSTRUCTED, not official |
| 2023/2024 | fin annee | 2024-07-10 00:00:00 | 2024-07-10 00:00:00 | False | False | RECONSTRUCTED, not official |
| 2023/2024 | summer closure | 2024-07-11 00:00:00 | 2024-08-31 00:00:00 | True | False | RECONSTRUCTED, not official |
| 2024/2025 | rentree | 2024-09-01 00:00:00 | 2024-09-01 00:00:00 | False | False | RECONSTRUCTED, not official |
| 2024/2025 | vacances hiver | 2024-12-23 00:00:00 | 2025-01-05 00:00:00 | True | False | RECONSTRUCTED, not official |
| 2024/2025 | exams Sem 1 | 2025-01-06 00:00:00 | 2025-01-19 00:00:00 | False | False | RECONSTRUCTED, not official |
| 2024/2025 | vacances printemps | 2025-03-31 00:00:00 | 2025-04-06 00:00:00 | True | False | RECONSTRUCTED, not official |
| 2024/2025 | vacances Aid Al Fitr | 2025-03-24 00:00:00 | 2025-03-30 00:00:00 | True | False | RECONSTRUCTED, not official |
| 2024/2025 | fin annee | 2025-07-10 00:00:00 | 2025-07-10 00:00:00 | False | False | RECONSTRUCTED, not official |
| 2024/2025 | summer closure | 2025-07-11 00:00:00 | 2025-08-31 00:00:00 | True | False | RECONSTRUCTED, not official |
| 2025/2026 | rentree | 2025-09-01 00:00:00 | 2025-09-01 00:00:00 | False | False | RECONSTRUCTED, not official |
| 2025/2026 | vacances hiver | 2025-12-22 00:00:00 | 2026-01-04 00:00:00 | True | False | RECONSTRUCTED, not official |
| 2025/2026 | exams Sem 1 | 2026-01-05 00:00:00 | 2026-01-18 00:00:00 | False | False | RECONSTRUCTED, not official |
| 2025/2026 | vacances printemps | 2026-03-30 00:00:00 | 2026-04-05 00:00:00 | True | False | RECONSTRUCTED, not official |
| 2025/2026 | vacances Aid Al Fitr | 2026-03-16 00:00:00 | 2026-03-22 00:00:00 | True | False | RECONSTRUCTED, not official |
| 2025/2026 | fin annee | 2026-07-10 00:00:00 | 2026-07-10 00:00:00 | False | False | RECONSTRUCTED, not official |
| 2025/2026 | summer closure | 2026-07-11 00:00:00 | 2026-08-31 00:00:00 | True | False | RECONSTRUCTED, not official |

The initial July/August 2022 record also needs a closure mask. Apply the same rule to the preceding year's summer only; no other 2021/2022 dates are inferred:

| academic_year | period | start | end | is_vacation | context_only | status |
|---|---|---|---|---|---|---|
| 2021/2022 | summer closure (initial-record context) | 2022-07-11 00:00:00 | 2022-08-31 00:00:00 | True | True | RECONSTRUCTED, not official |

## Public holiday dates actually returned by holidays/TN

Package holidays 0.108; country TN; English names. Returned years: [2022, 2023, 2024, 2025, 2026]. Islamic dates are computed by the package, not hard-coded here. Estimated annotations are retained; these are package outputs, not independent official verification. [Package Tunisia documentation](https://holidays.readthedocs.io/en/latest/auto_gen_docs/tunisia/).

| date | name |
|---|---|
| 2022-01-01 | New Year's Day |
| 2022-01-14 | Revolution and Youth Day |
| 2022-03-20 | Independence Day |
| 2022-04-09 | Martyrs' Day |
| 2022-05-01 | Labor Day |
| 2022-05-02 | Eid al-Fitr (estimated) |
| 2022-05-03 | Eid al-Fitr Holiday (estimated) |
| 2022-05-04 | Eid al-Fitr Holiday (estimated) |
| 2022-07-08 | Day of Arafah (estimated) |
| 2022-07-09 | Eid al-Adha (estimated) |
| 2022-07-10 | Eid al-Adha Holiday (estimated) |
| 2022-07-11 | Eid al-Adha Holiday (estimated) |
| 2022-07-25 | Republic Day |
| 2022-07-30 | Islamic New Year (estimated) |
| 2022-08-13 | Women's Day |
| 2022-10-08 | Prophet's Birthday (estimated) |
| 2022-10-15 | Evacuation Day |
| 2023-01-01 | New Year's Day |
| 2023-01-14 | Revolution and Youth Day |
| 2023-03-20 | Independence Day |
| 2023-04-09 | Martyrs' Day |
| 2023-04-21 | Eid al-Fitr (estimated) |
| 2023-04-22 | Eid al-Fitr Holiday (estimated) |
| 2023-04-23 | Eid al-Fitr Holiday (estimated) |
| 2023-05-01 | Labor Day |
| 2023-06-27 | Day of Arafah (estimated) |
| 2023-06-28 | Eid al-Adha (estimated) |
| 2023-06-29 | Eid al-Adha Holiday (estimated) |
| 2023-06-30 | Eid al-Adha Holiday (estimated) |
| 2023-07-19 | Islamic New Year (estimated) |
| 2023-07-25 | Republic Day |
| 2023-08-13 | Women's Day |
| 2023-09-27 | Prophet's Birthday (estimated) |
| 2023-10-15 | Evacuation Day |
| 2024-01-01 | New Year's Day |
| 2024-01-14 | Revolution and Youth Day |
| 2024-03-20 | Independence Day |
| 2024-04-09 | Martyrs' Day |
| 2024-04-10 | Eid al-Fitr (estimated) |
| 2024-04-11 | Eid al-Fitr Holiday (estimated) |
| 2024-04-12 | Eid al-Fitr Holiday (estimated) |
| 2024-05-01 | Labor Day |
| 2024-06-15 | Day of Arafah (estimated) |
| 2024-06-16 | Eid al-Adha (estimated) |
| 2024-06-17 | Eid al-Adha Holiday (estimated) |
| 2024-06-18 | Eid al-Adha Holiday (estimated) |
| 2024-07-07 | Islamic New Year (estimated) |
| 2024-07-25 | Republic Day |
| 2024-08-13 | Women's Day |
| 2024-09-15 | Prophet's Birthday (estimated) |
| 2024-10-15 | Evacuation Day |
| 2025-01-01 | New Year's Day |
| 2025-01-14 | Revolution and Youth Day |
| 2025-03-20 | Independence Day |
| 2025-03-30 | Eid al-Fitr (estimated) |
| 2025-03-31 | Eid al-Fitr Holiday (estimated) |
| 2025-04-01 | Eid al-Fitr Holiday (estimated) |
| 2025-04-09 | Martyrs' Day |
| 2025-05-01 | Labor Day |
| 2025-06-05 | Day of Arafah (estimated) |
| 2025-06-06 | Eid al-Adha (estimated) |
| 2025-06-07 | Eid al-Adha Holiday (estimated) |
| 2025-06-08 | Eid al-Adha Holiday (estimated) |
| 2025-06-26 | Islamic New Year (estimated) |
| 2025-07-25 | Republic Day |
| 2025-08-13 | Women's Day |
| 2025-09-04 | Prophet's Birthday (estimated) |
| 2025-10-15 | Evacuation Day |
| 2026-01-01 | New Year's Day |
| 2026-01-14 | Revolution and Youth Day |
| 2026-03-20 | Eid al-Fitr (estimated); Independence Day |
| 2026-03-21 | Eid al-Fitr Holiday (estimated) |
| 2026-03-22 | Eid al-Fitr Holiday (estimated) |
| 2026-04-09 | Martyrs' Day |
| 2026-05-01 | Labor Day |
| 2026-05-26 | Day of Arafah (estimated) |
| 2026-05-27 | Eid al-Adha (estimated) |
| 2026-05-28 | Eid al-Adha Holiday (estimated) |
| 2026-05-29 | Eid al-Adha Holiday (estimated) |
| 2026-06-16 | Islamic New Year (estimated) |
| 2026-07-25 | Republic Day |
| 2026-08-13 | Women's Day |
| 2026-08-25 | Prophet's Birthday (estimated) |
| 2026-10-15 | Evacuation Day |

## Observed load sanity comparison (not calendar validation)

For each vacation: observed weekday P_avg vs weekday term slots in the 14 days before and 14 days after, excluding all reconstructed vacations and public holidays from the surrounding comparison. Means use is_imputed=False and finite P_avg only; excluded counts are alongside each result. NA means no observed coverage. Higher or lower vacation demand cannot validate reconstructed dates: weather and other loads confound occupancy.

| academic_year | period | status | vacation_weekday_mean_kW | vacation_observed_rows | vacation_excluded_imputed | vacation_other_missing | surrounding_term_weekday_mean_kW | surrounding_term_observed_rows | surrounding_term_excluded_imputed | surrounding_term_other_missing |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022/2023 | vacances hiver | RECONSTRUCTED, not official | 26.321854 | 960 | 0 | 0 | 33.555521 | 1920 | 0 | 0 |
| 2022/2023 | vacances printemps | RECONSTRUCTED, not official | 27.347521 | 480 | 0 | 0 | 24.497034 | 1342 | 2 | 0 |
| 2022/2023 | vacances Aid Al Fitr | RECONSTRUCTED, not official | 23.745521 | 480 | 0 | 0 | 34.932798 | 1344 | 0 | 0 |
| 2022/2023 | summer closure | RECONSTRUCTED, not official | 72.333496 | 3638 | 10 | 0 | 87.463001 | 1536 | 0 | 0 |
| 2023/2024 | vacances hiver | RECONSTRUCTED, not official | 36.913177 | 960 | 0 | 0 | 42.073745 | 1920 | 0 | 0 |
| 2023/2024 | vacances printemps | RECONSTRUCTED, not official | 32.579479 | 480 | 0 | 0 | 32.392746 | 1344 | 0 | 0 |
| 2023/2024 | vacances Aid Al Fitr | RECONSTRUCTED, not official | 27.502979 | 480 | 0 | 0 | 36.425236 | 1440 | 0 | 0 |
| 2023/2024 | summer closure | RECONSTRUCTED, not official | 83.560553 | 3453 | 99 | 0 | 113.123484 | 1920 | 0 | 0 |
| 2024/2025 | vacances hiver | RECONSTRUCTED, not official | 33.211559 | 956 | 4 | 0 | 46.280192 | 1820 | 4 | 0 |
| 2024/2025 | vacances printemps | RECONSTRUCTED, not official | 27.541542 | 480 | 0 | 0 | 38.099647 | 1248 | 0 | 0 |
| 2024/2025 | vacances Aid Al Fitr | RECONSTRUCTED, not official | 31.918437 | 480 | 0 | 0 | 34.217676 | 1248 | 0 | 0 |
| 2024/2025 | summer closure | RECONSTRUCTED, not official | 96.734199 | 3453 | 3 | 0 | 135.238277 | 1822 | 2 | 0 |
| 2025/2026 | vacances hiver | RECONSTRUCTED, not official | 38.266479 | 960 | 0 | 0 | 47.840175 | 1824 | 0 | 0 |
| 2025/2026 | vacances printemps | RECONSTRUCTED, not official | NA | 0 | 0 | 0 | NA | 0 | 0 | 0 |
| 2025/2026 | vacances Aid Al Fitr | RECONSTRUCTED, not official | NA | 0 | 0 | 0 | NA | 0 | 0 | 0 |
| 2025/2026 | summer closure | RECONSTRUCTED, not official | NA | 0 | 0 | 0 | NA | 0 | 0 | 0 |
| 2021/2022 | summer closure (initial-record context) | RECONSTRUCTED, not official | 114.141451 | 3631 | 17 | 0 | 124.431007 | 1440 | 0 | 0 |

## Empirical winter weeks 49 through 03 (report only)

All observed weekdays are retained, including holidays; no calendar-based trimming biases this comparison. This table does not change the configurable winter rule. Missing/imputed counts are explicit. Weekday means are descriptive, with no load assertions or fitted calendar.

| academic_year | iso_week | start | mean_weekday_P_kW | observed_rows | excluded_imputed | other_missing | status |
|---|---|---|---|---|---|---|---|
| 2022/2023 | 2022-W49 | 2022-12-05 | 33.283687 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2022/2023 | 2022-W50 | 2022-12-12 | 37.227167 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2022/2023 | 2022-W51 | 2022-12-19 | 28.218417 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2022/2023 | 2022-W52 | 2022-12-26 | 24.425292 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2022/2023 | 2023-W01 | 2023-01-02 | 29.888604 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2022/2023 | 2023-W02 | 2023-01-09 | 33.822625 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2022/2023 | 2023-W03 | 2023-01-16 | 33.343875 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2023/2024 | 2023-W49 | 2023-12-04 | 34.611625 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2023/2024 | 2023-W50 | 2023-12-11 | 37.265687 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2023/2024 | 2023-W51 | 2023-12-18 | 34.409229 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2023/2024 | 2023-W52 | 2023-12-25 | 35.853729 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2023/2024 | 2024-W01 | 2024-01-01 | 37.972625 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2023/2024 | 2024-W02 | 2024-01-08 | 47.214604 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2023/2024 | 2024-W03 | 2024-01-15 | 49.405458 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2024/2025 | 2024-W49 | 2024-12-02 | 39.445875 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2024/2025 | 2024-W50 | 2024-12-09 | 55.446807 | 476 | 4 | 0 | RECONSTRUCTED, not official |
| 2024/2025 | 2024-W51 | 2024-12-16 | 54.902625 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2024/2025 | 2024-W52 | 2024-12-23 | 43.307794 | 476 | 4 | 0 | RECONSTRUCTED, not official |
| 2024/2025 | 2025-W01 | 2024-12-30 | 23.199458 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2024/2025 | 2025-W02 | 2025-01-06 | 34.591917 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2024/2025 | 2025-W03 | 2025-01-13 | 39.058896 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2025/2026 | 2025-W49 | 2025-12-01 | 50.659500 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2025/2026 | 2025-W50 | 2025-12-08 | 47.587604 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2025/2026 | 2025-W51 | 2025-12-15 | 46.441167 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2025/2026 | 2025-W52 | 2025-12-22 | 40.343271 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2025/2026 | 2026-W01 | 2025-12-29 | 36.189688 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2025/2026 | 2026-W02 | 2026-01-05 | 47.246917 | 480 | 0 | 0 | RECONSTRUCTED, not official |
| 2025/2026 | 2026-W03 | 2026-01-12 | 50.627313 | 480 | 0 | 0 | RECONSTRUCTED, not official |

For a transparent descriptive reading of 'clear', flag an adjacent two-week pair only when both week means are below BOTH immediately surrounding week means, and the pair's mean is at least 10% below the surrounding pair's mean. This is an exploratory screen, not a statistical test or calendar validation. The rule is unchanged regardless of this result. Weekly means use only the observed rows counted above.

- 2022/2023: clear descriptive dip at **2022-W51 and 2022-W52** (28.218, 24.425 kW), 21.56% below the adjacent weeks' mean 33.558 kW. Imputed exclusions across the four compared weeks: 0. This may differ from the configured vacation weeks; no adjustment was made.
- 2023/2024: **no clear isolated two-week dip** under this descriptive screen. The printed weekday means do not establish the reconstructed winter dates; no adjustment was made.
- 2024/2025: clear descriptive dip at **2025-W01 and 2025-W02** (23.199, 34.592 kW), 29.84% below the adjacent weeks' mean 41.183 kW. Imputed exclusions across the four compared weeks: 4. This may differ from the configured vacation weeks; no adjustment was made.
- 2025/2026: clear descriptive dip at **2025-W52 and 2026-W01** (40.343, 36.190 kW), 18.31% below the adjacent weeks' mean 46.844 kW. Imputed exclusions across the four compared weeks: 0. This may differ from the configured vacation weeks; no adjustment was made.
