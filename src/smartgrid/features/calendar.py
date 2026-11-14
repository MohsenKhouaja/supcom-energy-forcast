"""SUP'COM academic calendar: RECONSTRUCTED, not official.

Rules live in configs/calendar.yaml (JSON syntax, valid YAML 1.2). Public
holidays come from holidays/TN, including its estimated-date annotations.
No Islamic dates are hard-coded. Load comparisons cannot validate these rules.
"""

from datetime import date, timedelta

import holidays
import numpy as np
import pandas as pd

STATUS = "RECONSTRUCTED, not official"


def tunisian_holidays(config):
    """Return the actual package dates, retaining estimated labels in English."""
    return holidays.country_holidays(config["country"], years=config["holiday_years"],
                                    language="en_US")


def academic_periods(config, *, include_initial_summer=True):
    """Inclusive date ranges. Exams are working periods, not vacations.

    The preceding year's summer closure is included solely to cover July/August
    2022; it uses the same RECONSTRUCTED rule as the four requested years.
    """
    public = tunisian_holidays(config)
    records = []

    def add(year, name, start, end, vacation, context=False):
        records.append(dict(academic_year=f"{year}/{year+1}", period=name,
                            start=pd.Timestamp(start), end=pd.Timestamp(end),
                            is_vacation=vacation, context_only=context, status=STATUS))

    for year in config["academic_year_starts"]:
        winter = config["winter_vacation"]
        anchor = date.fromisoformat(f"{year}-{winter['anchor']}")
        monday = anchor-timedelta(days=anchor.weekday())
        start = monday-timedelta(weeks=winter["weeks_before"])
        end = monday+timedelta(weeks=winter["weeks_after"]+1, days=-1)
        add(year, "rentree", f"{year}-{config['rentree']}", f"{year}-{config['rentree']}", False)
        add(year, "vacances hiver", start, end, True)
        add(year, "exams Sem 1", end+timedelta(days=1),
            end+timedelta(weeks=config["exam_weeks_after_winter"]), False)
        spring = date.fromisocalendar(year+1, config["spring_iso_week"], 1)
        add(year, "vacances printemps", spring, spring+timedelta(days=6), True)
        fitr = sorted(d for d, name in public.items() if d.year == year+1 and "Eid al-Fitr" in name)
        if not fitr:
            raise ValueError(f"holidays/TN returned no Eid al-Fitr for {year+1}")
        fitr_start = fitr[0]-timedelta(days=fitr[0].weekday())
        add(year, "vacances Aid Al Fitr", fitr_start, fitr_start+timedelta(days=6), True)
        add(year, "fin annee", f"{year+1}-{config['fin_annee']}", f"{year+1}-{config['fin_annee']}", False)
        add(year, "summer closure", f"{year+1}-{config['summer_closure']['start']}",
            f"{year+1}-{config['summer_closure']['end']}", True)
    if include_initial_summer:
        year = min(config["academic_year_starts"])-1
        add(year, "summer closure (initial-record context)", f"{year+1}-{config['summer_closure']['start']}",
            f"{year+1}-{config['summer_closure']['end']}", True, True)
    return pd.DataFrame(records)


def vacation_mask(index, periods):
    """Union overlapping RECONSTRUCTED vacation dates, never double-counting."""
    days = pd.DatetimeIndex(index).normalize()
    mask = np.zeros(len(days), dtype=bool)
    for row in periods.loc[periods.is_vacation].itertuples():
        mask |= (days >= row.start) & (days <= row.end)
    return mask


def vacation_load_comparison(frame, periods, public):
    """Observed weekday power vs two adjacent term weeks on each side.

    Surrounding comparison excludes weekends, public holidays and ALL reconstructed
    vacations. Truncated/no-coverage periods and excluded counts are explicit.
    """
    index = frame.index
    term = (index.day_of_week < 5) & ~vacation_mask(index, periods) & ~np.isin(index.date, list(public))
    valid = ~frame.is_imputed.fillna(True) & frame.P_avg.notna()
    records = []
    for period in periods.loc[periods.is_vacation].itertuples():
        during = (index >= period.start) & (index < period.end+pd.Timedelta(days=1)) & (index.day_of_week < 5)
        around = (((index >= period.start-pd.Timedelta(days=14)) & (index < period.start)) |
                  ((index >= period.end+pd.Timedelta(days=1)) & (index < period.end+pd.Timedelta(days=15)))) & term
        item = dict(academic_year=period.academic_year, period=period.period, status=STATUS)
        for name, mask in (("vacation", during), ("surrounding_term", around)):
            item[f"{name}_weekday_mean_kW"] = frame.loc[mask & valid, "P_avg"].mean()
            item[f"{name}_observed_rows"] = int((mask & valid).sum())
            item[f"{name}_excluded_imputed"] = int((mask & frame.is_imputed).sum())
            item[f"{name}_other_missing"] = int((mask & ~frame.is_imputed & frame.P_avg.isna()).sum())
        records.append(item)
    return pd.DataFrame(records)


def winter_weekday_profile(frame, years):
    """Observed weekday means for ISO weeks 49..52/53 then 01..03; no inference."""
    records = []
    valid = ~frame.is_imputed.fillna(True) & frame.P_avg.notna()
    iso = frame.index.isocalendar()
    for year in years:
        for iso_year, week in [(year, w) for w in range(49, date(year, 12, 28).isocalendar().week+1)] + [(year+1,w) for w in range(1,4)]:
            mask = (iso.year.to_numpy() == iso_year) & (iso.week.to_numpy() == week) & (frame.index.day_of_week < 5)
            records.append(dict(academic_year=f"{year}/{year+1}", iso_week=f"{iso_year}-W{week:02d}",
                start=str(date.fromisocalendar(iso_year, week, 1)), mean_weekday_P_kW=frame.loc[mask & valid, "P_avg"].mean(),
                observed_rows=int((mask & valid).sum()), excluded_imputed=int((mask & frame.is_imputed).sum()),
                other_missing=int((mask & ~frame.is_imputed & frame.P_avg.isna()).sum()), status=STATUS))
    return pd.DataFrame(records)
