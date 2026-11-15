"""Reusable timed prediction, cohort scoring, and streaming prediction export.

Calendar groups describe the FIRST target timestamp; each retains the full
24-hour forecast, so a cohort's PDE is still a horizon-maximum error. For h-only
groups, PDE is over the single retained step. All groups use the SAME complete
window mask as the headline metrics; an otherwise valid step in an excluded
window is never scored. Rolling overlapping forecasts are counted as forecast
cases, not as independent timestamp observations.
"""

import os
from pathlib import Path
import time
import uuid

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from smartgrid.models.base import CHANNELS, HORIZON
from .metrics import evaluate, inverse_predictions, scored_window_mask


def timed_fit(model, train_origins, val_origins):
    started = time.perf_counter()
    result = model.fit(train_origins,val_origins)
    elapsed = time.perf_counter()-started
    if result is not None:
        raise ValueError("Model.fit must return None")
    return elapsed


def predict_physical(model, origins, scaler):
    """Time only model.predict; inverse transformation is outside that timing."""
    started = time.perf_counter()
    predicted = model.predict(origins)
    elapsed = time.perf_counter()-started
    if not isinstance(predicted,np.ndarray) or predicted.shape != (len(origins),HORIZON,4):
        raise ValueError("Model.predict violated [n_origins,96,4] contract")
    return inverse_predictions(predicted,scaler),elapsed


def breakdown_metrics(truth, prediction, target_starts, non_working):
    """Yield (dimension,label,four metrics), retaining whole-window exclusions."""
    starts = pd.DatetimeIndex(target_starts)
    if len(starts) != len(truth) or np.asarray(non_working).shape != (len(starts),):
        raise ValueError("Cohort labels must align with forecast origins")
    good = scored_window_mask(truth,prediction)
    season = np.array(["Winter","Winter","Spring","Spring","Spring","Summer", "Summer","Summer","Autumn","Autumn","Autumn","Winter"])[starts.month-1]
    labels = {
        "month":starts.strftime("%Y-%m").to_numpy(),
        "season":season,
        "day_type":np.where(starts.day_of_week >= 5,"weekend","weekday"),
        "is_non_working_day":np.asarray(non_working,dtype=int).astype(str),
    }
    for dimension,values in labels.items():
        for label in np.unique(values):
            selected = values == label
            subset_pred = prediction[selected].copy()
            subset_pred[~good[selected]] = np.nan
            yield dimension,str(label),evaluate(truth[selected],subset_pred,input_space="physical")
    for step in range(HORIZON):
        subset_pred = prediction[:,step:step+1].copy()
        subset_pred[~good] = np.nan
        yield "horizon",str(step+1),evaluate(truth[:,step:step+1],subset_pred,input_space="physical")


def write_predictions(directory, model, split, run_id, origins, index, truth, prediction, metadata):
    """One Parquet row per origin; eight fixed-size 96-element physical lists.

    Keep an immutable run version for append-only benchmark history and a hard
    link at <model>_<split>.parquet for the latest run. No duplicate file payload.
    Write bounded Arrow row groups, rather than millions of flattened rows.
    """
    directory = Path(directory)
    versioned = directory/"runs"/run_id/f"{model}_{split}.parquet"
    versioned.parent.mkdir(parents=True,exist_ok=True)
    if versioned.exists():
        raise FileExistsError(f"Prediction run already exists: {versioned}")
    good = scored_window_mask(truth,prediction)
    writer = None
    try:
        for start in range(0,len(origins),512):
            stop = min(start+512,len(origins))
            positions = origins[start:stop]
            columns = {
                "run_id":pa.array([run_id]*(stop-start)),
                "model":pa.array([model]*(stop-start)),
                "split":pa.array([split]*(stop-start)),
                "origin_index":pa.array(positions,type=pa.int64()),
                "origin_timestamp":pa.array(index[positions].to_numpy(dtype="datetime64[ns]")),
                "target_start":pa.array(index[positions+1].to_numpy(dtype="datetime64[ns]")),
                "target_end":pa.array(index[positions+HORIZON].to_numpy(dtype="datetime64[ns]")),
                "is_scored":pa.array(good[start:stop]),
                "exclusion_reason":pa.array(np.where(good[start:stop],"","nonfinite_truth_or_prediction")),
            }
            for prefix,values in (("true",truth),("pred",prediction)):
                for channel,field in enumerate(CHANNELS):
                    flat = np.ascontiguousarray(values[start:stop,:,channel]).reshape(-1)
                    columns[f"{prefix}_{field}"] = pa.FixedSizeListArray.from_arrays(pa.array(flat,type=pa.float64()),HORIZON)
            table = pa.table(columns)
            if writer is None:
                schema_metadata = {str(k).encode():str(v).encode() for k,v in metadata.items()}
                table = table.replace_schema_metadata(schema_metadata)
                writer = pq.ParquetWriter(versioned,table.schema,compression="snappy")
            writer.write_table(table)
    finally:
        if writer is not None:
            writer.close()
    if writer is None:
        raise ValueError("Cannot persist an empty prediction run")
    alias = directory/f"{model}_{split}.parquet"
    temporary = directory/f".{model}_{split}.{uuid.uuid4().hex}.tmp"
    temporary.hardlink_to(versioned)
    os.replace(temporary,alias)
    return versioned
