#!/usr/bin/env python3
"""Benchmark three non-learning forecasts, sequentially, in isolated CPU workers.

Run on the VM with project-local TMPDIR/caches and numerical thread limits.
No ingestion, window generation, scaler fitting, training, or GPU work occurs.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
import time
import uuid

import numpy as np
import pandas as pd

from smartgrid.evaluation.benchmark import breakdown_metrics, predict_physical, timed_fit, write_predictions
from smartgrid.evaluation.metrics import BENCHMARK_COLUMNS, BREAKDOWN_COLUMNS, SCHEMA_VERSION, append_records, evaluate, normalize_electrical
from smartgrid.models.base import CHANNELS
from smartgrid.models.baselines import Persistence, SeasonalNaiveDaily, SeasonalNaiveWeekly

MODELS = {model.__name__:model for model in (SeasonalNaiveDaily,SeasonalNaiveWeekly,Persistence)}


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            result.update(block)
    return result.hexdigest()


def read_origins(processed, metadata, split):
    return pd.read_parquet(processed/metadata["origin_files"][split])["origin_index"].to_numpy(dtype=np.int64)


def worker(args):
    root = args.root.resolve()
    processed = root/"data/processed"
    metadata = json.loads((processed/"features.json").read_text(encoding="utf-8"))
    scaler = json.loads((processed/"scaler.json").read_text(encoding="utf-8"))
    source_hash = sha256(processed/"em_virtual.parquet")
    scaler_hash = sha256(processed/"scaler.json")
    feature_hash = sha256(processed/"features.npy")
    if (source_hash,scaler_hash,feature_hash) != (metadata["source_em_sha256"],metadata["scaler_sha256"],metadata["features_sha256"]):
        raise ValueError("Existing processed artifacts no longer match features.json")
    frame = pd.read_parquet(processed/"em_virtual.parquet").set_index("timestamp")
    index = frame.index
    if len(index) > 1 and not (index[1:]-index[:-1] == pd.Timedelta(minutes=15)).all():
        raise ValueError("The source must retain the complete canonical 15-minute grid")
    physical = frame.loc[:,list(CHANNELS)].to_numpy(dtype=np.float64)
    flags = frame.is_imputed.fillna(True).to_numpy(dtype=bool)
    origins = read_origins(processed,metadata,args.split)
    target_positions = origins[:,None]+np.arange(1,97)
    if flags[target_positions].any() or not np.isfinite(physical[target_positions]).all():
        raise ValueError("Saved target eligibility violated: targets must be observed and finite")
    period = metadata["split_config"]["splits"][args.split]
    if (index[origins+1] < pd.Timestamp(period["start"])).any() or (
            index[origins+96] >= pd.Timestamp(period["end"])+pd.Timedelta(days=1)).any():
        raise ValueError("Saved targets cross their split boundary")
    history = normalize_electrical(physical,scaler)
    model = MODELS[args.worker](history,flags)
    fit_seconds = timed_fit(model,read_origins(processed,metadata,"train"),read_origins(processed,metadata,"val"))
    prediction,predict_seconds = predict_physical(model,origins,scaler)
    truth = physical[target_positions]
    scored = evaluate(truth,prediction,input_space="physical")
    saved_features = np.load(processed/"features.npy",mmap_mode="r",allow_pickle=False)
    non_working = saved_features[origins+1,10]
    slices = []
    for dimension,label,metrics in breakdown_metrics(truth,prediction,index[origins+1],non_working):
        slices.extend(dict(row,breakdown=dimension,group=label) for row in metrics)
    origin_hash = sha256(processed/metadata["origin_files"][args.split])
    provenance = dict(schema_version=SCHEMA_VERSION,source_sha256=source_hash,origins_sha256=origin_hash,
        scaler_sha256=scaler_hash,calendar_status=metadata["calendar_status"],units="kWh,kvarh,kW,kVA",
        horizon=96,origin_semantics="last input timestamp",prediction_space="physical")
    path = write_predictions(root/"data/predictions",model.name,args.split,args.run_id,origins,index,truth,prediction,provenance)
    # Isolated worker's high-water memory includes scoring and serialization.
    peak_rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024/1e6
    common = dict(schema_version=SCHEMA_VERSION,run_id=args.run_id,run_utc=args.run_utc,git_commit=args.git_commit,
        model=model.name,split=args.split,n_parameters=model.n_parameters,fit_seconds=fit_seconds,
        predict_seconds=predict_seconds,peak_rss_mb=peak_rss_mb,predictions_path=path.relative_to(root).as_posix(),
        source_sha256=source_hash,origins_sha256=origin_hash,scaler_sha256=scaler_hash,calendar_status=metadata["calendar_status"])
    rows = [dict(common,**row) for row in scored]
    breakdown_rows = [dict(common,**row) for row in slices]
    append_records(root/"reports/benchmark.csv",rows)
    append_records(root/"reports/baseline_breakdowns.csv",breakdown_rows,columns=BREAKDOWN_COLUMNS)
    info = dict(model=model.name,split=args.split,n_origins=scored[0]["n_origins"],
        n_scored_windows=scored[0]["n_scored_windows"],n_excluded_windows=scored[0]["n_excluded_windows"],
        n_parameters=model.n_parameters,fit_seconds=fit_seconds,predict_seconds=predict_seconds,peak_rss_mb=peak_rss_mb,
        prediction_rows=len(origins),prediction_bytes=path.stat().st_size)
    (root/"cache/baselines"/args.run_id/f"{model.name}_{args.split}.json").write_text(json.dumps(info,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(info),flush=True)


def markdown(table):
    def cell(value):
        if pd.isna(value):
            return "NA"
        if isinstance(value,(float,np.floating)):
            return f"{value:.6f}"
        return str(value).replace("|","/")
    lines = ["| "+" | ".join(table.columns)+" |","|"+"---|"*len(table.columns)]
    lines.extend("| "+" | ".join(cell(v) for v in row)+" |" for row in table.itertuples(index=False,name=None))
    return "\n".join(lines)


def report(root,manifest):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    table = pd.read_csv(root/"reports/benchmark.csv")
    table = table.loc[table.run_id == manifest["run_id"]].copy()
    breakdowns = pd.read_csv(root/"reports/baseline_breakdowns.csv")
    breakdowns = breakdowns.loc[breakdowns.run_id == manifest["run_id"]]
    if len(table) != 24:
        raise ValueError(f"Expected 24 headline records for this invocation, found {len(table)}")
    horizon = breakdowns.loc[breakdowns.breakdown == "horizon"].copy()
    horizon["step"] = horizon["group"].astype(int)
    figure,axes = plt.subplots(2,4,figsize=(18,8),sharex=True)
    for row,split in enumerate(("val","test")):
        for col,channel in enumerate(CHANNELS):
            axis = axes[row,col]
            for model in MODELS:
                series = horizon.loc[(horizon.split == split) & (horizon.channel == channel) & (horizon.model == model)].sort_values("step")
                axis.plot(series.step,series.mae,label=model)
            unit = table.loc[table.channel == channel,"unit"].iloc[0]
            axis.set_title(f"{split}: {channel}")
            axis.set_ylabel(f"MAE ({unit})")
            axis.set_xlabel("Forecast step h (15 minutes)")
            axis.set_xlim(1,96)
            axis.grid(alpha=.25)
    axes[0,0].legend(fontsize=8)
    figure.suptitle("Observed targets and observed lagged history only; whole-window exclusions shown in BASELINES.md")
    figure.tight_layout()
    figures = root/"reports/figures"
    figures.mkdir(parents=True,exist_ok=True)
    figure.savefig(figures/"baseline_error_by_horizon.png",dpi=150)
    plt.close(figure)
    runs = table.drop_duplicates(["model","split"])
    validation_s = table.loc[(table.split == "val") & (table.channel == "S_avg")]
    winner = validation_s.sort_values("pde_s_pct").iloc[0]
    winners = []
    for channel in CHANNELS:
        best = table.loc[(table.split == "val") & (table.channel == channel)].sort_values("wape_pct").iloc[0]
        winners.append(dict(channel=channel,lowest_validation_WAPE_model=best.model,WAPE_pct=best.wape_pct))
    headline_cols = ["model","split","channel","unit","mae","rmse","r2","mape_pct","mape_status","wape_pct"]
    season_cols = ["model","split","group","channel","mae","rmse","r2","mape_pct","mape_status","wape_pct","pde_p_pct","pde_s_pct"]
    lines = ["# Seasonal-naive baselines and reusable evaluation", "",
        f"Run `{manifest['run_id']}`. No packages added; no ML/DL, training, ingestion, scaler fitting or window generation. "
        "Validation selects references; test is held-out descriptive reporting. All metrics below are physical-unit metrics.", "",
        "## Model and timing contract", "",
        "Every model implements fit(train_origins,val_origins)->None, predict(origins)->[n,96,4], n_parameters and name. "
        "Origins identify the last input timestamp t. Model output is normalized dEa,dEr,P_avg,S_avg; the reusable harness "
        "inverse-transforms using the saved train-only scaler before scoring and saving. Fit and predict calls are timed with "
        "a monotonic wall clock; inverse-transform/scoring/export are outside predict_seconds.", "",
        "Daily: yhat(t+h)=y(t+h-96). Weekly: yhat(t+h)=y(t+h-672). Persistence: yhat(t+h)=y(t). "
        "All required readings are at or before t. Persistence uses exactly t; an imputed origin is not replaced by an older reading. "
        "Missing or imputed lagged rows produce NaN step vectors; the whole window is then excluded, never zero-filled.", "",
        "## Excluded windows", "", markdown(runs[["model","split","n_origins","n_scored_windows","n_excluded_windows"]]), "",
        "The saved target origins already require observed, non-imputed labels. Counts above are ADDITIONAL model-specific "
        "exclusions from unavailable lagged history. All channel, calendar and horizon metrics retain the full-window mask. "
        "Models can have different scoring supports; these are not strictly paired comparisons. Overlapping rolling origins "
        "repeat timestamps as forecast cases and must not be treated as independent observations.", "",
        "## Headline channel metrics", "",
        "MAE/RMSE use the channel's unit; MAPE/WAPE are percentages; R2 is dimensionless. "
        "MAPE omits exact-zero denominators and reports its status/count in benchmark.csv. dEr MAPE is always unreliable "
        "because signed reactive energy crosses/approaches zero; use WAPE as its primary percentage error. "
        "WAPE divides by sum(abs(y)), preventing cancellation. All-zero denominators yield NA with a reason, never infinity.", "",
        markdown(table[headline_cols]), "", "## Peak-demand error and physical consistency", "",
        "For EACH window: PDE_P=abs(max(yhat_P)-max(y_P))/max(y_P); PDE_S analogously. "
        "Then average the per-window ratios and multiply by 100. Maxima are over all 96 future steps; "
        "this is not the average of per-step relative errors. Nonpositive true maxima are excluded from PDE, "
        "with counts in benchmark.csv. No demand-register channel is used as a label.", "",
        markdown(runs[["model","split","pde_p_pct","pde_s_pct","pde_p_zero_windows","pde_s_zero_windows",
                       "consistency_p_median_kw","consistency_s_median_kva"]]), "",
        "Physical diagnostics use the predictions themselves: median abs(P-4*dEa), and median abs(S-hypot(P,4*dEr)). "
        "The measured channels already have a nonzero P-minus-4*dEa discrepancy (WINDOWS.md: median 0.25 kW), "
        "so copying them need not yield exact zero on that diagnostic. Baselines do not alter copied measurements "
        "to manufacture consistency. S and signed dEr were derived consistently in ingestion.", "",
        "## Forecast-step errors", "",
        "![Error by horizon](figures/baseline_error_by_horizon.png)", "",
        "Figure: reports/figures/baseline_error_by_horizon.png, 150 dpi. h=1 is 15 minutes ahead, h=96 is 24 hours. "
        "Each curve uses the same model/split windows at every step. Full metrics for h=1..96 are in "
        "baseline_breakdowns.csv. An h-only slice's PDE is over that single retained step; the headline PDE above always uses 96.", "",
        "## Seasonal breakdown", "",
        "Calendar cohorts use the FIRST target timestamp, retaining the full 24-hour forecast. "
        "Seasons: DJF winter, MAM spring, JJA summer, SON autumn. Month/day-type/non-working breakdowns "
        "use the same convention and are all in baseline_breakdowns.csv. Non-working labels remain "
        "**RECONSTRUCTED, not official**; existing calendar features were read, not regenerated.", "",
        markdown(breakdowns.loc[breakdowns.breakdown == "season",season_cols]), "",
        "## Frugality", "", markdown(runs[["model","split","n_parameters","fit_seconds","predict_seconds","peak_rss_mb"]]), "",
        "Each model/split ran once in a fresh worker, sequentially, with numerical threads limited to 1. "
        "Peak RSS is the worker lifetime high-water mark in decimal MB, including loading, forecast/target arrays, "
        "scoring and serialization. It is not parameter memory alone. No [n,672,11] input array is materialized. "
        "The no-op fit timings are measured, not replaced by an assumed zero.", "",
        "## Which reference is hardest to beat?", "",
        f"Using validation PDE_S as the peak-demand reference, **{winner.model}** is hardest to beat here "
        f"with PDE_S **{winner.pde_s_pct:.4f}%** and S_avg WAPE **{winner.wape_pct:.4f}%**. "
        +("It reuses yesterday's full quarter-hour profile, preserving daily shape instead of a flat line while tracking recent conditions." if winner.model == "SeasonalNaiveDaily" else
          "It reuses the same weekday's quarter-hour profile from the preceding week, preserving the weekly operating pattern instead of a flat line." if winner.model == "SeasonalNaiveWeekly" else
          "Holding the latest reading flat is the strongest peak reference on this validation support; later models must demonstrate an improvement rather than assume that extra complexity helps.")+
        " This is a validation-only choice, not a claim that the same model wins every channel or season. "
        "Different exclusions also limit direct comparisons. Channel-specific validation winners are:", "",
        markdown(pd.DataFrame(winners)), "",
        "A later model should be compared against all three. Persistence is the additional floor; the two seasonal-naive "
        "references are required by the specification. Test results were not used to select the reference.", "",
        "## Output schema and provenance", "",
        "[BENCHMARK_SCHEMA.md](BENCHMARK_SCHEMA.md) defines all fixed CSV columns, formulas, undefined-value policies, "
        "cohort semantics and the prediction Parquet schema. Reports append one row per (run,model,split,channel) "
        "to benchmark.csv. Immutable prediction versions preserve old run provenance; latest aliases are at "
        "data/predictions/<model>_<split>.parquet. Predictions include all candidate origins and their is_scored flags.", "",
        f"Source/scaler/origin hashes and source-file hashes are recorded in baseline_run.json. "
        f"Source Parquets and processed features were checked unchanged after this invocation. "
        f"Total benchmark invocation runtime: {manifest['runtime_seconds']:.3f} seconds.", "",
        "## Pytest output", "", "```text", (root/"logs/baselines-pytest.log").read_text(encoding="utf-8").rstrip(), "```", ""]
    (root/"reports/BASELINES.md").write_text("\n".join(lines),encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument("--git-commit",required=True)
    parser.add_argument("--worker",choices=list(MODELS))
    parser.add_argument("--split",choices=["val","test"])
    parser.add_argument("--run-id")
    parser.add_argument("--run-utc")
    args = parser.parse_args()
    if args.worker:
        worker(args)
        return
    root = args.root.resolve()
    started = time.perf_counter()
    run_utc = datetime.now(timezone.utc).isoformat()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"_"+uuid.uuid4().hex[:8]
    cache = root/"cache/baselines"/run_id
    cache.mkdir(parents=True)
    sources = [p for tree in ("src","scripts","tests") for p in sorted((root/tree).rglob("*.py"))]
    source_files = {p.relative_to(root).as_posix():sha256(p) for p in sources}
    processed = root/"data/processed"
    tracked_inputs = [processed/name for name in ("em_virtual.parquet","all_meters.parquet","features.npy","features.json",
                        "scaler.json","train_origins.parquet","val_origins.parquet","test_origins.parquet")]
    before = {p.relative_to(root).as_posix():sha256(p) for p in tracked_inputs}
    for model in MODELS:
        for split in ("val","test"):
            subprocess.run([sys.executable,str(Path(__file__).resolve()),"--root",str(root),"--git-commit",args.git_commit,
                "--worker",model,"--split",split,"--run-id",run_id,"--run-utc",run_utc],check=True)
    after = {p.relative_to(root).as_posix():sha256(p) for p in tracked_inputs}
    if before != after:
        raise ValueError("Processed source artifacts changed during benchmarking")
    manifest = dict(schema_version=SCHEMA_VERSION,run_id=run_id,run_utc=run_utc,git_commit=args.git_commit,
        source_files=source_files,processed_inputs=before,inputs_unchanged=True,
        runtime_seconds=time.perf_counter()-started,
        runs=[json.loads(p.read_text(encoding="utf-8")) for p in sorted(cache.glob("*.json"))])
    (root/"reports/baseline_run.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    report(root,manifest)
    print("BASELINES_DONE",json.dumps(dict(run_id=run_id,runtime_seconds=manifest["runtime_seconds"])),flush=True)


if __name__ == "__main__":
    main()
