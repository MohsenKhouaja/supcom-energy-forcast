#!/usr/bin/env python3
"""CPU-only classical forecast experiments; all test scoring follows selection.

Author locally, run on the VM. All files/caches stay under the project.
The previous benchmark run_id is reused as requested; schema is unchanged.
"""

import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import pickle
import resource
import subprocess
import sys
import time

import numpy as np
import pandas as pd

from smartgrid.evaluation.benchmark import breakdown_metrics, predict_physical, timed_fit, write_predictions
from smartgrid.evaluation.metrics import BREAKDOWN_COLUMNS, append_records, evaluate, normalize_electrical
from smartgrid.features.tabular import FEATURE_NAMES, TabularFeatures, complete_pairs, evenly_spaced_origins
from smartgrid.models.base import CHANNELS
from smartgrid.models.classical import RandomForestForecaster, SVRForecaster, XGBoostForecaster

MODELS = {model.family:model for model in (RandomForestForecaster,XGBoostForecaster,SVRForecaster)}


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path,value):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8")
    os.replace(temporary,path)


def load_context(root):
    directory=root/"data/processed"
    metadata=json.loads((directory/"features.json").read_text(encoding="utf-8"))
    scaler=json.loads((directory/"scaler.json").read_text(encoding="utf-8"))
    config=json.loads((root/"configs/forecast_ml.yaml").read_text(encoding="utf-8"))
    checks={"em_virtual.parquet":"source_em_sha256","scaler.json":"scaler_sha256","features.npy":"features_sha256"}
    for name,key in checks.items():
        if sha256(directory/name) != metadata[key]:
            raise ValueError(f"Processed artifact hash mismatch: {name}")
    frame=pd.read_parquet(directory/"em_virtual.parquet").set_index("timestamp")
    if not (frame.index[1:]-frame.index[:-1] == pd.Timedelta(minutes=15)).all():
        raise ValueError("Canonical grid must remain explicit and consecutive")
    physical=frame.loc[:,list(CHANNELS)].to_numpy(dtype=np.float64)
    saved=np.load(directory/"features.npy",mmap_mode="r",allow_pickle=False)
    builder=TabularFeatures(normalize_electrical(physical,scaler),saved[:,4:],frame.is_imputed.fillna(True).to_numpy(dtype=bool))
    origins={split:pd.read_parquet(directory/file).origin_index.to_numpy(dtype=np.int64)
             for split,file in metadata["origin_files"].items()}
    for split,values in origins.items():
        positions=values[:,None]+np.arange(1,97)
        period=metadata["split_config"]["splits"][split]
        if builder.is_imputed[positions].any() or not np.isfinite(physical[positions]).all():
            raise ValueError(f"Non-observed target detected in {split}")
        if (frame.index[values+1] < pd.Timestamp(period["start"])).any() or (
                frame.index[values+96] >= pd.Timestamp(period["end"])+pd.Timedelta(days=1)).any():
            raise ValueError(f"Targets cross their {split} boundary")
    return dict(root=root,directory=directory,metadata=metadata,scaler=scaler,config=config,frame=frame,
                physical=physical,builder=builder,origins=origins)


def record_progress(root,key,info):
    value=dict(utc=datetime.now(timezone.utc).isoformat(),**info)
    atomic_json(root/f"cache/forecast_ml/{key}_progress.json",value)
    with (root/"logs/forecast-ml-progress.jsonl").open("a",encoding="utf-8") as stream:
        stream.write(json.dumps(dict(key=key,**value))+"\n")
    print(key,json.dumps(value),flush=True)


def training_population(context):
    origins=context["origins"]["train"]
    usable=origins[context["builder"].usable_origins(origins)]
    selected=usable[::context["config"]["training_origin_stride"]]
    index=context["frame"].index[selected]
    return selected,dict(eligible_origins=len(origins),usable_origins=len(usable),additional_unusable=len(origins)-len(usable),
        selected_origins=len(selected),rows=len(selected)*96,stride=context["config"]["training_origin_stride"],
        first_origin=str(index[0]),last_origin=str(index[-1]),
        quarter_hour_counts={str(minute):int((index.minute == minute).sum()) for minute in (0,15,30,45)},
        month_counts=pd.Series(index.strftime("%Y-%m")).value_counts().sort_index().to_dict())


def learning_curve(root):
    from xgboost import XGBRegressor
    context=load_context(root)
    selected,population=training_population(context)
    builder=context["builder"]
    # Nested, deterministic, time-spread origin subsets; keep every horizon.
    settings=context["config"]["learning_curve"]
    requested=settings["requested_rows"]
    nested=[selected]
    for size in reversed(requested):
        nested.insert(0,evenly_spaced_origins(nested[0],round(size/96)))
    left,h=complete_pairs(context["origins"]["val"])
    x_val=builder.build(left,h)
    y_val=builder.targets(left,h)[:,0]
    if not np.isfinite(x_val).all():
        raise ValueError("Learning curve must evaluate every eligible validation pair")
    actual=y_val*context["scaler"]["scale"][0]+context["scaler"]["mean"][0]
    options={key:value for key,value in context["config"]["xgb"].items() if not key.endswith("_grid")}
    options.update(max_depth=settings["max_depth"],objective="reg:squarederror",random_state=context["config"]["random_seed"])
    rows=[]
    for count,subset in zip([*requested,population["rows"]],nested):
        left,h=complete_pairs(subset)
        record_progress(root,"curve",dict(phase="fit",requested_rows=count,actual_rows=len(left)))
        x_train=builder.build(left,h)
        y_train=builder.targets(left,h)[:,0]
        estimator=XGBRegressor(**options)
        start=time.perf_counter()
        estimator.fit(x_train,y_train)
        fit_seconds=time.perf_counter()-start
        record_progress(root,"curve",dict(phase="validation",actual_rows=len(left),fit_seconds=fit_seconds))
        start=time.perf_counter()
        prediction=estimator.predict(x_val)
        predict_seconds=time.perf_counter()-start
        wape=float(np.abs((prediction-y_val)*context["scaler"]["scale"][0]).sum()/np.abs(actual).sum()*100)
        row=dict(requested_rows=count,actual_rows=len(left),training_origins=len(subset),
                 validation_origins=len(context["origins"]["val"]),validation_pairs=len(y_val),
                 val_dEa_wape_pct=wape,fit_seconds=fit_seconds,predict_seconds=predict_seconds)
        rows.append(row)
        pd.DataFrame(rows).to_csv(root/"reports/forecast_ml_learning_curve.csv",index=False)
        record_progress(root,"curve",dict(phase="point_complete",**row))
    atomic_json(root/"reports/forecast_ml_population.json",population)
    atomic_json(root/"reports/forecast_ml_curve.json",dict(options=options,population=population,rows=rows))


def train_worker(args):
    root=args.root.resolve()
    context=load_context(root)
    key=f"{args.model}_train_{'half' if args.half_sample else 'full'}"
    model=MODELS[args.model](context["builder"],context["scaler"],context["config"],half_sample=args.half_sample,
        progress=lambda info:record_progress(root,key,info))
    record_progress(root,key,dict(phase="fit_start"))
    fit_seconds=timed_fit(model,context["origins"]["train"],context["origins"]["val"])
    payload=dict(family=model.family,estimators=model.estimators,training=model.training,selection=model.selection,
                 fit_seconds=fit_seconds,n_parameters=model.n_parameters,half_sample=args.half_sample)
    artifact=root/f"outputs/forecast_ml/{model.name}.pkl"
    artifact.parent.mkdir(parents=True,exist_ok=True)
    # Only our own newly fitted objects are serialized/loaded; never raw input.
    with artifact.open("wb") as stream:
        pickle.dump(payload,stream,protocol=pickle.HIGHEST_PROTOCOL)
    info={key:value for key,value in payload.items() if key != "estimators"}
    info.update(status="completed",peak_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024/1e6,
                artifact_sha256=sha256(artifact),artifact_path=artifact.relative_to(root).as_posix())
    atomic_json(root/f"reports/forecast_ml_{model.name}_fit.json",info)
    record_progress(root,key,dict(phase="saved",fit_seconds=fit_seconds,n_parameters=model.n_parameters))


def monitored_worker(args,phase,*,model,timeout=None,half_sample=False):
    """Watch only our own child PID; never inspect/kill another user's process."""
    root=args.root.resolve()
    attempt="half" if half_sample else "full"
    key=f"{model}_{'train' if phase == 'train-worker' else 'eval'}_{attempt}"
    command=[sys.executable,str(Path(__file__).resolve()),"--root",str(root),"--phase",phase,"--model",model]
    if half_sample:
        command.append("--half-sample")
    started=time.perf_counter()
    last_notice=started
    timed_out=False
    with (root/f"logs/forecast-ml-{key}.log").open("w",encoding="utf-8") as stream:
        process=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT)
        while True:
            pid,status,usage=os.wait4(process.pid,os.WNOHANG)
            if pid:
                process.returncode=os.waitstatus_to_exitcode(status)
                break
            elapsed=time.perf_counter()-started
            if timeout is not None and elapsed >= timeout:
                # This PID was created immediately above by this runner.
                process.kill()
                _,status,usage=os.wait4(process.pid,0)
                process.returncode=os.waitstatus_to_exitcode(status)
                timed_out=True
                break
            if time.perf_counter()-last_notice >= 60:
                print("BUDGET_PROGRESS",model,phase,attempt,round(elapsed,1),"seconds",flush=True)
                last_notice=time.perf_counter()
            time.sleep(1)
    progress_path=root/f"cache/forecast_ml/{key}_progress.json"
    progress=json.loads(progress_path.read_text()) if progress_path.exists() else {}
    result=dict(model=model,phase=phase,attempt=attempt,elapsed_seconds=time.perf_counter()-started,
        budget_seconds=timeout,timed_out=timed_out,exit_code=process.returncode,
        peak_rss_mb=usage.ru_maxrss*1024/1e6,last_progress=progress)
    print("WORKER_FINISHED",json.dumps(result),flush=True)
    if process.returncode != 0 and not timed_out:
        raise RuntimeError(f"{model} {phase} failed: see logs/forecast-ml-{key}.log")
    return result


def train_all(args):
    root=args.root.resolve()
    config=json.loads((root/"configs/forecast_ml.yaml").read_text())
    baseline=json.loads((root/"reports/baseline_run.json").read_text())
    if not (root/"reports/forecast_ml_curve.json").exists():
        raise ValueError("Complete the learning curve before main model runs")
    attempts=[]
    run=dict(run_id=baseline["run_id"],started_utc=datetime.now(timezone.utc).isoformat(),
             git_commit="3a0de08",config=config,attempts=attempts,models={})
    atomic_json(root/"reports/forecast_ml_run.json",run)
    for name in ("XGBoost","RandomForest","SVR"):
        budget=config["rf_fit_budget_seconds"] if name == "RandomForest" else config["svr_budget_seconds"] if name == "SVR" else None
        result=monitored_worker(args,"train-worker",model=name,timeout=budget)
        attempts.append(result)
        if result["timed_out"] and name == "RandomForest":
            result=monitored_worker(args,"train-worker",model=name,timeout=budget,half_sample=True)
            attempts.append(result)
        if result["timed_out"]:
            info=dict(family=name,status="did not converge within budget",fit_seconds=result["elapsed_seconds"],
                peak_rss_mb=result["peak_rss_mb"],n_parameters=0,last_progress=result["last_progress"],
                training=None,selection=[],half_sample=(result["attempt"] == "half"))
            atomic_json(root/f"reports/forecast_ml_{name}_fit.json",info)
        else:
            info=json.loads((root/f"reports/forecast_ml_{name}_fit.json").read_text())
        run["models"][name]=dict(status=info["status"],fit_seconds=info["fit_seconds"],n_parameters=info["n_parameters"])
        atomic_json(root/"reports/forecast_ml_run.json",run)
    run["selection_complete_utc"]=datetime.now(timezone.utc).isoformat()
    atomic_json(root/"reports/forecast_ml_run.json",run)
    print("ALL_SELECTION_COMPLETE; test has not been scored.",flush=True)


def array_column(table,name):
    return np.asarray(table[name].to_pylist(),dtype=np.float64)


def evaluate_worker(args):
    import pyarrow.parquet as pq
    root=args.root.resolve()
    context=load_context(root)
    run=json.loads((root/"reports/forecast_ml_run.json").read_text())
    info=json.loads((root/f"reports/forecast_ml_{args.model}_fit.json").read_text())
    key=f"{args.model}_eval_full"
    model=None
    if info["status"] == "completed":
        path=root/info["artifact_path"]
        if sha256(path) != info["artifact_sha256"]:
            raise ValueError("Own fitted-model artifact hash changed before loading")
        with path.open("rb") as stream:
            payload=pickle.load(stream)
        model=MODELS[args.model](context["builder"],context["scaler"],context["config"],
            progress=lambda value:record_progress(root,key,value))
        model.estimators=payload["estimators"]
    attempts=[item for item in run["attempts"] if item["model"] == args.model]
    wasted_fit=sum(item["elapsed_seconds"] for item in attempts if item["timed_out"])
    fit_seconds=info["fit_seconds"]+(wasted_fit if info["status"] == "completed" else 0.)
    if info["status"] != "completed":
        fit_seconds=sum(item["elapsed_seconds"] for item in attempts)
    source_hash=sha256(context["directory"]/"em_virtual.parquet")
    scaler_hash=sha256(context["directory"]/"scaler.json")
    frame=context["frame"]
    benchmark=pd.read_csv(root/"reports/benchmark.csv")
    if ((benchmark.run_id == run["run_id"]) & (benchmark.model == args.model)).any():
        raise ValueError(f"{args.model} already scored for this run_id; refuse to touch test again")
    collected=[]
    for split in ("val","test"):
        origins=context["origins"][split]
        record_progress(root,key,dict(phase="prediction_start",split=split,origins=len(origins)))
        if model is None:
            prediction=np.full((len(origins),96,4),np.nan)
            predict_seconds=np.nan  # no model.predict call occurred
        else:
            prediction,predict_seconds=predict_physical(model,origins,context["scaler"])
        positions=origins[:,None]+np.arange(1,97)
        truth=context["physical"][positions]
        scores=evaluate(truth,prediction,input_space="physical")
        origin_hash=sha256(context["directory"]/context["metadata"]["origin_files"][split])
        provenance=dict(schema_version=1,source_sha256=source_hash,origins_sha256=origin_hash,scaler_sha256=scaler_hash,
            units="kWh,kvarh,kW,kVA",horizon=96,prediction_space="physical",calendar_status=context["metadata"]["calendar_status"],
            model_status=info["status"])
        path=write_predictions(root/"data/predictions",args.model,split,run["run_id"],origins,frame.index,truth,prediction,provenance)
        slices=[]
        for dimension,label,rows in breakdown_metrics(truth,prediction,frame.index[origins+1],context["builder"].calendar[origins+1,6]):
            slices.extend(dict(row,breakdown=dimension,group=label) for row in rows)
        daily_row=benchmark.loc[(benchmark.run_id == run["run_id"]) & (benchmark.model == "SeasonalNaiveDaily") & (benchmark.split == split)].iloc[0]
        if daily_row.source_sha256 != source_hash or daily_row.origins_sha256 != origin_hash:
            raise ValueError("Daily comparison must use identical source and origin artifacts")
        daily=pq.read_table(root/daily_row.predictions_path)
        if daily["origin_index"].to_pylist() != origins.tolist():
            raise ValueError("Daily comparison origin alignment changed")
        daily_prediction=np.stack([array_column(daily,f"pred_{field}") for field in CHANNELS],axis=-1)
        paired_prediction=prediction.copy()
        paired_prediction[~np.isfinite(daily_prediction).all(axis=(1,2))]=np.nan
        paired=evaluate(truth,paired_prediction,input_space="physical")
        daily_paired=daily_prediction.copy()
        daily_paired[~np.isfinite(prediction).all(axis=(1,2))]=np.nan
        daily_scores=evaluate(truth,daily_paired,input_space="physical")
        paired_rows=[]
        for score,baseline in zip(paired,daily_scores):
            paired_rows.append(dict(model=args.model,split=split,channel=score["channel"],n_origins=len(origins),
                n_scored_windows=score["n_scored_windows"],n_excluded_windows=score["n_excluded_windows"],
                ml_wape_pct=score["wape_pct"],daily_wape_pct=baseline["wape_pct"],
                wape_result="beaten" if score["wape_pct"] < baseline["wape_pct"] else "not beaten" if np.isfinite(score["wape_pct"]) else "not evaluated: budget",
                ml_pde_s_pct=score["pde_s_pct"],daily_pde_s_pct=baseline["pde_s_pct"],
                pde_s_result="beaten" if score["pde_s_pct"] < baseline["pde_s_pct"] else "not beaten" if np.isfinite(score["pde_s_pct"]) else "not evaluated: budget"))
        pair_mask=np.isfinite(paired_prediction).all(axis=(1,2))
        horizon_rows=[]
        for h in range(1,97):
            error=np.abs(prediction[pair_mask,h-1,:]-truth[pair_mask,h-1,:])
            means=error.mean(axis=0) if len(error) else np.full(4,np.nan)
            horizon_rows.extend(dict(model=args.model,split=split,channel=channel,h=h,mae=float(means[i]),
                n_scored_windows=int(pair_mask.sum())) for i,channel in enumerate(CHANNELS))
        pd.DataFrame(horizon_rows).to_csv(root/"reports/forecast_ml_paired_horizon.csv",mode="a",header=False,index=False)
        peak=max([resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024/1e6,*[item["peak_rss_mb"] for item in attempts]])
        common=dict(schema_version=1,run_id=run["run_id"],run_utc=run["started_utc"],git_commit=run["git_commit"],
            model=args.model,split=split,n_parameters=info["n_parameters"],fit_seconds=fit_seconds,predict_seconds=predict_seconds,
            peak_rss_mb=peak,predictions_path=path.relative_to(root).as_posix(),source_sha256=source_hash,origins_sha256=origin_hash,
            scaler_sha256=scaler_hash,calendar_status=context["metadata"]["calendar_status"])
        rows=[dict(common,**row) for row in scores]
        breakdown_rows=[dict(common,**row) for row in slices]
        append_records(root/"reports/benchmark.csv",rows)
        append_records(root/"reports/forecast_ml_breakdowns.csv",breakdown_rows,columns=BREAKDOWN_COLUMNS)
        pair_path=root/"reports/forecast_ml_paired_daily.csv"
        pd.DataFrame(paired_rows).to_csv(pair_path,mode="a",header=not pair_path.exists(),index=False)
        collected.append(dict(split=split,fit_seconds=fit_seconds,predict_seconds=(float(predict_seconds) if np.isfinite(predict_seconds) else None),peak_rss_mb=peak,
            n_origins=len(origins),n_scored_windows=scores[0]["n_scored_windows"],n_excluded_windows=scores[0]["n_excluded_windows"],
            n_parameters=info["n_parameters"],status=info["status"]))
        record_progress(root,key,dict(phase="split_scored",**collected[-1]))
    atomic_json(root/f"reports/forecast_ml_{args.model}_evaluation.json",collected)


def evaluate_all(args):
    root=args.root.resolve()
    run=json.loads((root/"reports/forecast_ml_run.json").read_text())
    if "selection_complete_utc" not in run:
        raise ValueError("Do not score test before every model's selection is complete")
    base=pd.read_csv(root/"reports/baseline_breakdowns.csv")
    base=base.loc[(base.run_id == run["run_id"]) & (base.model == "SeasonalNaiveDaily") & (base.breakdown == "horizon")]
    base=base.assign(h=base["group"].astype(int))[["model","split","channel","h","mae","n_scored_windows"]]
    paired_path=root/"reports/forecast_ml_paired_horizon.csv"
    if paired_path.exists():
        raise FileExistsError("Paired evaluation already started; inspect existing results before resuming")
    base.to_csv(paired_path,index=False)
    inputs=[root/"data/processed"/name for name in ("em_virtual.parquet","all_meters.parquet","features.npy","features.json",
            "scaler.json","train_origins.parquet","val_origins.parquet","test_origins.parquet")]
    before={path.relative_to(root).as_posix():sha256(path) for path in inputs}
    results=[]
    for name in ("XGBoost","RandomForest","SVR"):
        results.append(monitored_worker(args,"eval-worker",model=name))
    after={path.relative_to(root).as_posix():sha256(path) for path in inputs}
    if before != after:
        raise ValueError("Processed inputs changed during evaluation")
    run["evaluation_workers"]=results
    run["processed_inputs"]=before
    run["inputs_unchanged"]=True
    run["completed_utc"]=datetime.now(timezone.utc).isoformat()
    source_files=[path for folder in ("src","scripts","tests","configs") for path in (root/folder).rglob("*") if path.is_file() and path.suffix in (".py",".yaml")]
    run["source_files"]={path.relative_to(root).as_posix():sha256(path) for path in sorted(source_files)}
    atomic_json(root/"reports/forecast_ml_run.json",run)
    print("ALL_ML_EVALUATION_COMPLETE",flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument("--phase",choices=["curve","train-worker","train","evaluate","eval-worker"],required=True)
    parser.add_argument("--model",choices=list(MODELS))
    parser.add_argument("--half-sample",action="store_true")
    args=parser.parse_args()
    (args.root/"cache/forecast_ml").mkdir(parents=True,exist_ok=True)
    if args.phase == "curve":
        learning_curve(args.root.resolve())
    elif args.phase == "train":
        train_all(args)
    elif args.phase == "evaluate":
        evaluate_all(args)
    elif args.phase == "eval-worker":
        evaluate_worker(args)
    else:
        train_worker(args)


if __name__ == "__main__":
    main()
