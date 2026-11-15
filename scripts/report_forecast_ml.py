#!/usr/bin/env python3
"""Render the completed classical ML experiment; never fit or predict here."""

import hashlib
import importlib.metadata
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from smartgrid.features.tabular import FEATURE_SPECS, evenly_spaced_origins
from smartgrid.models.base import CHANNELS


def markdown(table):
    def cell(value):
        if pd.isna(value):
            return "NA"
        if isinstance(value,(float,np.floating)):
            return f"{value:.6f}"
        return str(value).replace("|","/")
    result=["| "+" | ".join(table.columns)+" |","|"+"---|"*len(table.columns)]
    result.extend("| "+" | ".join(cell(value) for value in row)+" |" for row in table.itertuples(index=False,name=None))
    return "\n".join(result)


def main():
    root=Path(__file__).resolve().parents[1]
    run=json.loads((root/"reports/forecast_ml_run.json").read_text())
    if not run.get("inputs_unchanged"):
        raise ValueError("Complete evaluation and input-integrity checks before reporting")
    config=run["config"]
    environment={package:importlib.metadata.version(package) for package in ("numpy","pandas","pyarrow","scikit-learn","xgboost","matplotlib")}
    (root/"reports/forecast_ml_environment.json").write_text(json.dumps(environment,indent=2)+"\n",encoding="utf-8")
    population=json.loads((root/"reports/forecast_ml_population.json").read_text())
    curve=pd.read_csv(root/"reports/forecast_ml_learning_curve.csv")
    rf_sample_rows=[]
    svr_candidate_rows=[]
    progress_file=root/"logs/forecast-ml-progress.jsonl"
    for line in progress_file.read_text(encoding="utf-8").splitlines():
        event=json.loads(line)
        within_run=pd.Timestamp(run["started_utc"]) <= pd.Timestamp(event["utc"]) <= pd.Timestamp(run["selection_complete_utc"])
        if event.get("model") == "SVR" and event.get("phase") == "candidate_done" and within_run:
            svr_candidate_rows.append(dict(channel=event["channel"],C=event["parameters"]["C"],
                validation_wape_pct=event["validation_wape_pct"],candidate_fit_seconds=event["candidate_fit_seconds"],
                validation_seconds=event["validation_seconds"],candidate_parameters=event["n_parameters"]))
        if event.get("model") == "RandomForest" and event.get("phase") == "candidate_done" and event.get("channel") == "dEa" and (
                within_run):
            size=population["rows"] if event["key"].endswith("_full") else event["training_rows"]
            rf_sample_rows.append(dict(training_rows=size,max_depth=event["parameters"]["max_depth"],
                val_dEa_wape_pct=event["validation_wape_pct"],candidate_fit_seconds=event["candidate_fit_seconds"]))
    rf_sample_table=pd.DataFrame(rf_sample_rows,columns=["training_rows","max_depth","val_dEa_wape_pct","candidate_fit_seconds"])
    rf_sample_table.to_csv(root/"reports/forecast_ml_rf_sample_check.csv",index=False)
    svr_candidates=pd.DataFrame(svr_candidate_rows,columns=["channel","C","validation_wape_pct","candidate_fit_seconds","validation_seconds","candidate_parameters"])
    svr_candidates.to_csv(root/"reports/forecast_ml_svr_candidates.csv",index=False)
    phase_path=root/"reports/forecast_ml_curve_phase_counts.csv"
    xgb_fit=json.loads((root/"reports/forecast_ml_XGBoost_fit.json").read_text())
    identifiers=xgb_fit.get("training",{}).get("selected_origin_indices")
    if identifiers is not None:
        nested=[np.asarray(identifiers,dtype=np.int64)]
        for size in reversed(config["learning_curve"]["requested_rows"]):
            nested.insert(0,evenly_spaced_origins(nested[0],round(size/96)))
        minutes=pd.read_parquet(root/"data/processed/em_virtual.parquet",columns=["timestamp"]).timestamp.dt.minute.to_numpy()
        phase_table=pd.DataFrame([dict(training_rows=len(subset)*96,**{f"minute_{minute:02d}":int((minutes[subset] == minute).sum())
            for minute in (0,15,30,45)}) for subset in nested])
        phase_table.to_csv(phase_path,index=False)
    else:
        phase_table=pd.read_csv(phase_path)
    benchmark=pd.read_csv(root/"reports/benchmark.csv")
    cohort=benchmark.loc[benchmark.run_id == run["run_id"]]
    ml=cohort.loc[cohort.model.isin(["RandomForest","XGBoost","SVR"])]
    if len(ml) != 24:
        raise ValueError("Expected 24 ML rows appended to the original 24 baseline rows")
    paired=pd.read_csv(root/"reports/forecast_ml_paired_daily.csv")
    base_slices=pd.read_csv(root/"reports/baseline_breakdowns.csv")
    ml_slices=pd.read_csv(root/"reports/forecast_ml_breakdowns.csv")
    slices=pd.concat([base_slices,ml_slices],ignore_index=True)
    slices=slices.loc[(slices.run_id == run["run_id"]) & (slices.breakdown == "horizon")].copy()
    slices["step"]=slices["group"].astype(int)
    figures=root/"reports/figures"
    figure,axis=plt.subplots(figsize=(8,5))
    axis.plot(curve.actual_rows/1000,curve.val_dEa_wape_pct,marker="o")
    for row in curve.itertuples():
        axis.annotate(f"{row.val_dEa_wape_pct:.2f}%",(row.actual_rows/1000,row.val_dEa_wape_pct),xytext=(0,8),textcoords="offset points",ha="center")
    axis.set_xlabel("Training rows (thousands); all 96 horizons per sampled origin")
    axis.set_ylabel("Validation dEa WAPE (%)")
    axis.set_title("XGBoost depth 4: full validation set; no test selection")
    axis.grid(alpha=.3)
    axis.margins(y=.2)
    figure.tight_layout()
    figure.savefig(figures/"forecast_ml_learning_curve.png",dpi=150)
    plt.close(figure)
    models=["SeasonalNaiveDaily","SeasonalNaiveWeekly","Persistence","RandomForest","XGBoost","SVR"]
    figure,axes=plt.subplots(2,4,figsize=(19,9),sharex=True)
    colors=plt.get_cmap("tab10")
    for row,split in enumerate(("val","test")):
        for column,channel in enumerate(CHANNELS):
            axis=axes[row,column]
            for i,name in enumerate(models):
                group=slices.loc[(slices.model == name) & (slices.split == split) & (slices.channel == channel)].sort_values("step")
                if group.mae.notna().any():
                    axis.plot(group.step,group.mae,label=name,color=colors(i),linestyle="--" if i<3 else "-")
                else:
                    axis.plot([],[],label=f"{name}: budget exceeded",color=colors(i))
            unit=cohort.loc[cohort.channel == channel,"unit"].iloc[0]
            axis.set_title(f"{split}: {channel}")
            axis.set_xlabel("Forecast step h (15 minutes)")
            axis.set_ylabel(f"MAE ({unit})")
            axis.set_xlim(1,96)
            axis.grid(alpha=.25)
    handles,labels=axes[0,0].get_legend_handles_labels()
    figure.legend(handles,labels,loc="lower center",ncol=3,fontsize=9)
    figure.suptitle("Full ML evaluation vs baseline supports; paired Daily comparison is reported separately")
    figure.tight_layout(rect=(0,.07,1,.96))
    figure.savefig(figures/"forecast_ml_error_by_horizon.png",dpi=150)
    plt.close(figure)
    # Same-origin Daily overlays complement the complete-origin main figure.
    paired_horizons=root/"reports/forecast_ml_paired_horizon.csv"
    if paired_horizons.exists():
        paired_curve=pd.read_csv(paired_horizons)
        figure,axes=plt.subplots(1,4,figsize=(18,4.5))
        for i,channel in enumerate(CHANNELS):
            axis=axes[i]
            group=paired_curve.loc[(paired_curve.split == "val") & (paired_curve.channel == channel)]
            for name in ["SeasonalNaiveDaily","RandomForest","XGBoost","SVR"]:
                values=group.loc[group.model == name].sort_values("h")
                if values.mae.notna().any():
                    axis.plot(values.h,values.mae,label=name)
                else:
                    axis.plot([],[],label=f"{name}: budget exceeded")
            axis.set_title(f"Validation: {channel}")
            axis.set_xlabel("Forecast step h")
            unit=cohort.loc[cohort.channel == channel,"unit"].iloc[0]
            axis.set_ylabel(f"MAE ({unit})")
            axis.grid(alpha=.25)
        axes[0].legend(fontsize=8)
        figure.suptitle("Identical Daily-observable origin support for the paired comparison")
        figure.tight_layout()
        figure.savefig(figures/"forecast_ml_paired_daily_horizon.png",dpi=150)
        plt.close(figure)
    fit_rows=[]
    selections=[]
    for name in ("RandomForest","XGBoost","SVR"):
        path=root/f"reports/forecast_ml_{name}_fit.json"
        fit=json.loads(path.read_text())
        if fit.get("training"):
            training=fit["training"]
            identifiers=training.pop("selected_origin_indices",None)
            if identifiers is not None:
                array=np.asarray(identifiers,dtype=np.int64)
                training["sampled_origin_indices_sha256"]=hashlib.sha256(array.tobytes()).hexdigest()
                index=pd.read_parquet(root/"data/processed/em_virtual.parquet",columns=["timestamp"]).timestamp.iloc[array]
                training["quarter_hour_counts"]={str(minute):int((index.dt.minute == minute).sum()) for minute in (0,15,30,45)}
                path.write_text(json.dumps(fit,indent=2)+"\n",encoding="utf-8")
            rows=training["rows"]
            sampled=training["sampled_origins"]
        else:
            rows=fit.get("last_progress",{}).get("training_rows",20000 if name == "SVR" else population["rows"])
            sampled=fit.get("last_progress",{}).get("sampled_origins","not recorded")
        full_cost=ml.loc[ml.model == name,"fit_seconds"].iloc[0]
        fit_rows.append(dict(model=name,status=fit["status"],training_rows=rows,sampled_origins=sampled,
            base_origin_stride=7,half_sample=fit["half_sample"],fit_seconds_all_attempts=full_cost,
            n_parameters=fit["n_parameters"],sample_sufficiency=("RF dEa full/half comparisons; no four-channel sufficiency proof" if name == "RandomForest" else
                "not established; computational cap only" if name == "SVR" else "no benefit from more rows for fixed depth 4")))
        selection=pd.DataFrame(fit.get("selection",[]))
        if not selection.empty:
            for channel,group in selection.groupby("channel",sort=False):
                best=group.sort_values("validation_wape_pct").iloc[0]
                selections.append(dict(model=name,channel=channel,selected_parameters=json.dumps(best.parameters),
                    validation_wape_pct=best.validation_wape_pct))
    fit_table=pd.DataFrame(fit_rows)
    fit_table.to_csv(root/"reports/forecast_ml_training_summary.csv",index=False)
    feature_rows=pd.DataFrame([dict(position=i+1,name=spec.name,source=spec.kind,
        earliest_relative_electrical_row=spec.earliest_relative_row,latest_relative_electrical_row=spec.latest_relative_row)
        for i,spec in enumerate(FEATURE_SPECS)])
    feature_rows.to_csv(root/"reports/forecast_ml_features.csv",index=False)
    improvement=float(curve.iloc[-2].val_dEa_wape_pct-curve.iloc[-1].val_dEa_wape_pct)
    if improvement > config["learning_curve"]["flat_wape_threshold_percentage_points"]:
        conclusion="The curve is still falling materially at the largest size. This configuration may benefit from a larger training sample; sample sufficiency is not established."
    elif improvement < 0:
        conclusion="The curve worsens as rows increase; it does not support a claim that this fixed configuration is data-limited or that more rows would improve it. More data did not fix its error."
    else:
        conclusion="The gain from 500k to full is below the predeclared 0.5 percentage-point threshold: a near-plateau for this fixed XGB/dEa setup, not proof of sufficiency for other models/channels."
    attempts=pd.DataFrame([{key:item.get(key) for key in ("model","attempt","elapsed_seconds","budget_seconds","timed_out","peak_rss_mb")} for item in run["attempts"]])
    budgets=[]
    for name in ("RandomForest","SVR"):
        fit=json.loads((root/f"reports/forecast_ml_{name}_fit.json").read_text())
        if fit["status"] != "completed":
            last=fit.get("last_progress",{})
            returned_fit=(f" The last individual fit call had already returned in {last['candidate_fit_seconds']:.6f} seconds before full validation prediction began."
                if last.get("phase") == "candidate_validation" and "candidate_fit_seconds" in last else "")
            budgets.append(f"{name}: **did not converge within budget** for the complete fit/validation-selection procedure. "
                f"Last recorded phase: {last.get('phase')}, channel {last.get('channel')}, parameters {last.get('parameters')}. "
                +returned_fit+" "
                "An individual channel fit may have converged before validation/selection hit the time limit; this is not a claim about LIBSVM's internal convergence status. "
                "No completed four-channel model was available. Benchmark rows are retained with NA metrics, zero scored windows and NaN predictions; it was not silently dropped.")
    headline=["model","split","channel","mae","rmse","r2","mape_pct","mape_status","wape_pct"]
    costs=ml.drop_duplicates(["model","split"])
    val_pairs=paired.loc[paired.split == "val"]
    comparison_findings=[]
    for name in ("RandomForest","XGBoost","SVR"):
        selected=val_pairs.loc[val_pairs.model == name]
        wins=selected.loc[selected.wape_result == "beaten","channel"].tolist()
        losses=selected.loc[selected.wape_result == "not beaten","channel"].tolist()
        if selected.n_scored_windows.sum() == 0:
            comparison_findings.append(f"- {name}: **not evaluated within budget**; no claim of beating Daily is supported.")
        else:
            peak=selected.loc[selected.channel == "S_avg","pde_s_result"].iloc[0]
            comparison_findings.append(f"- {name}: validation WAPE **beaten** for {', '.join(wins) or 'no channels'}; "
                f"**not beaten** for {', '.join(losses) or 'no channels'}. Validation PDE_S: **{peak}**.")
    short_rows=[]
    if paired_horizons.exists():
        for name in ("SeasonalNaiveDaily","RandomForest","XGBoost","SVR"):
            values=paired_curve.loc[(paired_curve.split == "val") & (paired_curve.channel == "P_avg") & (paired_curve.model == name)]
            row=dict(model=name)
            for h in (1,4,96):
                selected=values.loc[values.h == h,"mae"]
                row[f"P_MAE_h{h}_kW"]=selected.iloc[0] if len(selected) else np.nan
            short_rows.append(row)
    lines=["# Classical multi-horizon forecasting — CPU only", "",
        f"Branch feat/forecast-ml, extending benchmark cohort `{run['run_id']}` without changing its 35-column schema. "
        "Only xgboost was added directly. No deep learning or GPU work. Existing ingestion, calendar and split artifacts were reused unchanged.", "",
        "## Exact features: 64, not approximately 50", "",
        "32 lag values (8 lags × 4 electrical channels), 24 trailing summaries (3 widths ×2 statistics × 4 channels), "
        "7 target-calendar features, and h. Order and dependency bounds:", "", markdown(feature_rows), "",
        "Lags 0..4 capture the latest hour,96/192 capture one/two days,672 captures the preceding week. "
        "Trailing 4/96/672 intervals cover the last hour/day/week, ending at t inclusively; std uses ddof=0. "
        "Electrical inputs and targets use the existing train-only normalization. Calendar values are unscaled. "
        "h is 1..96; SVR alone divides h by its known bound 96 before kernel computation. This uses no fitted or future information.", "",
        "The 7 calendar features are evaluated at TARGET t+h. Clock, weekday, day-of-year and the reconstructed holiday/vacation calendar "
        "are known in advance, so this is legitimate and is not leakage. The academic calendar remains **RECONSTRUCTED, not official**. "
        "No future electrical measurement enters a feature. Historical imputed INPUTS are allowed; imputed TARGETS are explicitly rejected before label reads.", "",
        f"The literal t-672 lag needs 673 timestamps rather than the original 672-slot input. "
        f"This excludes {population['additional_unusable']} of {population['eligible_origins']} training origins before stride sampling. "
        "Published validation/test scoring still considers every saved origin; incomplete predictions would be counted as exclusions.", "",
        "## Sampling and its measured justification", "",
        f"Usable training origins: {population['usable_origins']}; every seventh yields **{population['selected_origins']} origins × 96 = {population['rows']:,} rows**. "
        f"The float32 training feature payload is {population['rows']*64*4:,} bytes. "
        "This is a training-cost concession. Consecutive canonical input windows share 671/672 readings, so training on every origin repeats much of the same history. "
        "Sampling reduces that overlap; it is not a proof of lossless information retention. Fixed stride 7 avoids a fixed quarter-hour phase. "
        f"Observed selected-origin minute counts: {population['quarter_hour_counts']}. All 26 training months are represented; counts are in forecast_ml_population.json.", "",
        "### Learning curve before the main runs", "",
        "Nested deterministic time-spread subsets keep ALL 96 horizons per chosen origin. Requested 100k/250k/500k sizes "
        "are rounded to whole origins; actual counts below. Four XGB depth 4,200-tree fits use all 25,124 validation origins "
        "and all 2,411,904 target pairs. No test scoring influenced these experiments.", "", markdown(curve), "",
        "Actual quarter-hour coverage in every nested curve subset is shown below. All four phases are present, "
        "with modest count differences; this is one deterministic learning curve, not a repeated-seed uncertainty estimate.", "",
        markdown(phase_table), "",
        "![XGBoost learning curve](figures/forecast_ml_learning_curve.png)", "",
        f"Full-minus500k validation WAPE change: {-improvement:+.6f} percentage points. {conclusion} "
        "The full stride 7 sample was retained for XGBoost and RF's initial attempt as requested; any budget-triggered RF reduction is detailed below. "
        "This one-channel XGB curve cannot establish RF/SVR sufficiency.", "",
        "Completed RF dEa candidates also provide same-depth full/half comparisons without any extra fits. "
        "These are descriptive checks from the budgeted attempts, not a four-channel or repeated-seed learning curve:", "",
        markdown(rf_sample_table), "",
        "## Strategy and small search", "",
        "**Pooled direct multi-horizon with h as a predictor:** four scalar regressors per family, one per channel, "
        "shared across all 96 steps. During predict, each regressor is called96 times on batched origins. "
        "No predicted electrical value is fed back recursively. The alternative is one model per channel/horizon,384 models; "
        "sharing across h lowers storage/search cost and lets neighbouring horizons share training information, "
        "at the cost of less horizon-specific flexibility.", "",
        "Full-sample candidates are selected separately per channel by minimum physical-unit validation WAPE. "
        "The RF half-size retry, if needed, selects depth on dEa and shares it across heads as described below. EVERY candidate uses "
        "all eligible validation origin/horizon pairs; validation is never subsampled. Training labels stay in train. "
        "Validation only selects hyperparameters and never enters estimator.fit. Selected candidates are retained without a train+val refit. "
        "All three families finish selection or hit their explicit budget before any test scoring begins.", "",
        "```json",json.dumps(config,indent=2),"```", "",
        "[RF documentation](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html), "
        "[XGBoost CPU/hist parameters](https://xgboost.readthedocs.io/en/stable/parameter.html), "
        "[RBF SVR and its scaling cost](https://scikit-learn.org/stable/modules/generated/sklearn.svm.SVR.html). "
        "RF/XGB use at most 2 jobs/threads; BLAS uses 1. XGB explicitly uses device=cpu and hist; CUDA_VISIBLE_DEVICES=-1.", "",
        markdown(pd.DataFrame(selections)), "",
        "## Training rows, budgets and computational cost", "",markdown(fit_table), "",markdown(attempts), "",
        "RF has a 45-minute budget for its complete fit/selection call. On timeout the runner kills only its own child PID "
        "and retries at half the selected origins. A deterministic keep-four-of-eight pattern preserves quarter-hour phases; "
        "simply changing stride 7 to 14 would not. The retry also selects one shared depth on dEa and reuses it for the other three heads: "
        "five candidate forests instead of eight, with 200 trees in every final head. This is an explicit budget concession, "
        "not a claim that the dEa-selected depth is optimal for every channel. SVR uses exactly 20,000 deterministic training pairs and a 30-minute fit/selection budget. "
        "For the SVR cap, 209 time-spread origins are chosen from the stride 7 pool; their 20,064 pairs are evenly thinned to 20,000. "
        "This extra training concession is deterministic and retains all 96 horizon values; it never thins evaluation.", "",
        "The SVR cap does not affect validation/test population sizes. Budget times include validation selection; "
        "individual candidate fit and validation seconds are retained in the model fit JSON.", "",
        *budgets, "",
        "Completed individual SVR candidate diagnostics are retained below. A completed single-channel candidate "
        "does not constitute a selected four-channel family and is not substituted for the joint benchmark:", "",
        markdown(svr_candidates), "",
        "## Full-population physical-unit metrics", "",
        "Every saved validation/test origin is evaluated: 25,124/25,500, respectively. Successful ML models use identical "
        "origin supports; budget failures remain explicit unscored rows, not fabricated forecasts. "
        "MAPE is flagged unreliable for signed dEr; WAPE is primary. All formulas and zero-denominator policies are unchanged.", "",
        markdown(ml[headline]), "",markdown(costs[["model","split","n_origins","n_scored_windows","n_excluded_windows","pde_p_pct","pde_s_pct"]]), "",
        "PDE_S/PDE_P remain the mean per-window relative error of the maximum across96 physical-unit target steps. "
        "They are not per-step percentage errors. The four channels are predicted independently; consistency is measured rather than forced.", "",
        "## Beaten or not beaten: paired validation comparison with SeasonalNaiveDaily", "",
        "The Daily baseline intentionally cannot forecast windows needing imputed historical readings. ML may use imputed inputs, "
        "so its full-population support is larger. To avoid an unequal-support claim, compare each ML model with Daily on the SAME "
        "Daily-observable origin intersection below. No evaluation origins were randomly subsampled. "
        "The complete-population benchmark rows remain separate and show their counts. This paired table is the basis for the beaten/not-beaten statements.", "",
        markdown(val_pairs), "",*comparison_findings,"",
        "Paired test comparisons are descriptive only and are in forecast_ml_paired_daily.csv. Test was scored once for each selected family "
        "after all validation-only selection completed. A budget-failed model has no test score.", "",
        "## Error by horizon", "",
        "![All models by horizon](figures/forecast_ml_error_by_horizon.png)", "",
        "All three baseline curves are overlaid. The full ML curves use every eligible origin; baseline curves retain their existing "
        "missing-lag exclusions, so their raw supports differ. The paired validation figure below uses the same Daily-observable rows:", "",
        "![Paired Daily comparison](figures/forecast_ml_paired_daily_horizon.png)", "",
        "Short-horizon validation P errors on the same Daily-observable support (15 minutes, 1 hour, 24 hours):", "",
        markdown(pd.DataFrame(short_rows)), "",
        "All figures are PNG at 150 dpi. Forecast-step metrics, as well as month, season, weekday/weekend and non-working cohorts, "
        "are in forecast_ml_breakdowns.csv. Existing first-target-timestamp cohort definitions are unchanged.", "",
        "## Frugality and physical consistency", "",
        markdown(costs[["model","split","n_parameters","fit_seconds","predict_seconds","peak_rss_mb",
                        "consistency_p_median_kw","consistency_s_median_kva"]]), "",
        "fit_seconds includes the complete validation-selection fit call; a timed-out RF attempt is additionally charged if a reduced retry succeeds. "
        "The fit is reused for validation and test, not performed twice. predict_seconds times only the model.predict call for that split. "
        "Peak RSS is the maximum observed across its fitting attempts and evaluation worker, in decimal MB, including feature matrices and scoring/export.", "",
        f"Preliminary XGB learning-curve work is reported separately: {curve.fit_seconds.sum():.6f} fitting seconds and "
        f"{curve.predict_seconds.sum():.6f} validation-prediction seconds across its four points. These are not hidden in or substituted for the main model.fit timing.", "",
        "Parameter count means stored fitted prediction scalars: RF leaf values plus thresholds and feature indices at internal nodes; "
        "XGB the same plus one base score per channel; SVR support-vector coordinates, dual coefficients and intercepts. "
        "These are explicit non-neural counts, not neural-weight equivalents. A budget failure with no completed four-model family has 0 usable parameters, "
        "not a claim that no fitting work occurred. The run manifest preserves the attempt cost and last completed phase.", "",
        "## Findings and limitations", "",
        "The learning curve is a counterexample to assuming more training rows must improve this fixed estimator. "
        "Any measured budget failure is itself a frugality result and remains in benchmark.csv. "
        "Improved load errors do not imply exact physical consistency because the four regressors are independent. "
        "Use the explicit validation paired results above for performance claims; do not select on the test results. "
        "No thermal measurements were added, so summer effects must be learned indirectly from electrical history and known calendar variables.", "",
        "## Provenance and outputs", "",
        "benchmark.csv now appends the new rows under the SAME baseline run_id, with its fixed 35-column schema unchanged. "
        "run_utc records this extension's actual start; forecast_ml_run.json pins selection completion, attempt costs, source hashes and unchanged processed inputs. "
        "Prediction Parquets retain the existing fixed-list schema and immutable run paths. Model files under outputs/forecast_ml/ are ignored. "
        "Only this program's own freshly fitted, hash-verified model artifacts are loaded; raw dataset files are never executed.", "",
        markdown(pd.DataFrame([dict(package=name,version=version) for name,version in environment.items()])), "",
        "## Pytest output", "", "```text",(root/"logs/forecast-ml-pytest.log").read_text(encoding="utf-8").rstrip(),"```", ""]
    (root/"reports/FORECAST_ML.md").write_text("\n".join(lines),encoding="utf-8")
    print("FORECAST_ML_REPORT_WRITTEN",len(ml),"new benchmark rows",flush=True)


if __name__ == "__main__":
    main()
