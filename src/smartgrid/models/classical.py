"""Four pooled direct regressors per family, with validation-only selection.

Each channel shares one model across h=1..96, with h and known target-calendar
features supplied as predictors. Every candidate is validated on ALL eligible
validation origin/horizon pairs. Only training is subsampled. RF/XGB use all 96
horizons of every seventh usable training origin. SVR uses at most 20,000
deterministically selected training pairs. The runner enforces fit budgets.
"""

import json
import time

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.svm import SVR

from smartgrid.features.tabular import capped_training_pairs, complete_pairs
from .base import CHANNELS, ForecastModel, HORIZON


def count_parameters(estimator,family):
    """Stored fitted prediction scalars; definition is explicit in the report.

    Trees: one leaf prediction + threshold and feature-index per internal node.
    XGB also has one fitted base score per channel. SVR: support-vector entries,
    dual coefficients and intercept. Counts are not neural weight equivalents.
    """
    if family == "RandomForest":
        return int(sum(tree.tree_.n_leaves+2*(tree.tree_.node_count-tree.tree_.n_leaves) for tree in estimator.estimators_))
    if family == "XGBoost":
        def count(node):
            return 1 if "leaf" in node else 2+sum(count(child) for child in node["children"])
        return 1+sum(count(json.loads(tree)) for tree in estimator.get_booster().get_dump(dump_format="json"))
    return int(estimator.support_vectors_.size+estimator.dual_coef_.size+estimator.intercept_.size)


class DirectForecaster(ForecastModel):
    family = None

    def __init__(self,features,scaler,config,*,half_sample=False,progress=None):
        self.features,self.scaler,self.config = features,scaler,config
        self.half_sample,self.progress = half_sample,progress
        self.estimators = []
        self.selection = []
        self.training = {}

    @property
    def name(self):
        return self.family

    @property
    def n_parameters(self):
        return sum(count_parameters(model,self.family) for model in self.estimators)

    def notify(self,**info):
        if self.progress:
            value=dict(model=self.name,training_rows=self.training.get("rows"),sampled_origins=self.training.get("sampled_origins"))
            value.update(info)
            self.progress(value)

    def grid(self):
        block = self.config[{"RandomForest":"rf","XGBoost":"xgb","SVR":"svr"}[self.family]]
        key = "C_grid" if self.family == "SVR" else "max_depth_grid"
        return [{("C" if self.family == "SVR" else "max_depth"):value} for value in block[key]]

    def estimator(self,parameters):
        key = {"RandomForest":"rf","XGBoost":"xgb","SVR":"svr"}[self.family]
        options = {k:v for k,v in self.config[key].items() if not k.endswith("_grid")}
        options.update(parameters)
        if self.family == "RandomForest":
            options.setdefault("verbose",1)
            return RandomForestRegressor(**options,random_state=self.config["random_seed"])
        if self.family == "XGBoost":
            from xgboost import XGBRegressor
            return XGBRegressor(**options,objective="reg:squarederror",random_state=self.config["random_seed"])
        return SVR(**options)

    def _model_features(self,values):
        if self.family == "SVR":
            values = values.astype(np.float64,copy=True)
            values[:,-1] /= HORIZON
        return values

    def fit(self,train_origins,val_origins):
        train_origins = np.asarray(train_origins,dtype=np.int64)
        val_origins = np.asarray(val_origins,dtype=np.int64)
        usable_train = train_origins[self.features.usable_origins(train_origins)]
        selected = usable_train[::self.config["training_origin_stride"]]
        if self.half_sample:
            # Keep all four clock phases; [::2] of stride 7 would favour two phases.
            selected = selected[np.arange(len(selected))%8 < 4]
        if self.family == "SVR":
            left,h = capped_training_pairs(selected,self.config["svr_training_rows"])
        else:
            left,h = complete_pairs(selected)
        self.training = dict(eligible_train_origins=len(train_origins),usable_train_origins=len(usable_train),
            sampled_origins=len(np.unique(left)),rows=len(left),stride=self.config["training_origin_stride"],
            half_sample=self.half_sample,selected_origin_indices=np.unique(left).tolist())
        x_train = self._model_features(self.features.build(left,h))
        y_train = self.features.targets(left,h)
        if not np.isfinite(x_train).all():
            raise ValueError("Selected training features are incomplete")
        val_left,val_h = complete_pairs(val_origins)
        x_val = self._model_features(self.features.build(val_left,val_h))
        y_val = self.features.targets(val_left,val_h)
        if not np.isfinite(x_val).all():
            raise ValueError("Every eligible validation origin must have finite features")
        self.estimators,self.selection = [],[]
        shared_rf_parameters=None
        for channel,name in enumerate(CHANNELS):
            best_model,best_loss = None,np.inf
            # A budget-triggered half-size retry selects ONE depth on dEa.
            # All four final heads still have200 trees and full96-step labels.
            grid=[shared_rf_parameters] if (self.family == "RandomForest" and self.half_sample and channel > 0) else self.grid()
            for parameters in grid:
                self.notify(phase="candidate_fit",channel=name,parameters=parameters,training_rows=len(left))
                estimator = self.estimator(parameters)
                started = time.perf_counter()
                estimator.fit(x_train,y_train[:,channel])
                fit_seconds = time.perf_counter()-started
                self.notify(phase="candidate_validation",channel=name,parameters=parameters,candidate_fit_seconds=fit_seconds,
                    candidate_parameters=count_parameters(estimator,self.family))
                started = time.perf_counter()
                predicted = estimator.predict(x_val)
                actual = y_val[:,channel]*self.scaler["scale"][channel]+self.scaler["mean"][channel]
                error = np.abs((predicted-y_val[:,channel])*self.scaler["scale"][channel])
                loss = float(error.sum()/np.abs(actual).sum()*100)
                item = dict(channel=name,parameters=parameters,validation_wape_pct=loss,
                    candidate_fit_seconds=fit_seconds,validation_seconds=time.perf_counter()-started,
                    n_parameters=count_parameters(estimator,self.family),
                    depth_shared_from_dEa=bool(self.family == "RandomForest" and self.half_sample and channel > 0))
                self.selection.append(item)
                self.notify(phase="candidate_done",**item)
                if loss < best_loss:
                    best_model,best_loss = estimator,loss
                    if channel == 0:
                        shared_rf_parameters=parameters
            self.estimators.append(best_model)
        self.notify(phase="fit_complete",n_parameters=self.n_parameters,training_rows=len(left))
        return None

    def predict(self,origins):
        """Call each of four regressors 96 times, one batch per horizon."""
        if len(self.estimators) != 4:
            raise ValueError("All four channel estimators must be fitted")
        origins = np.asarray(origins,dtype=np.int64)
        good = self.features.usable_origins(origins)
        result = np.full((len(origins),HORIZON,4),np.nan,dtype=np.float64)
        usable = origins[good]
        if not len(usable):
            return result
        for h in range(1,HORIZON+1):
            values = self._model_features(self.features.build(usable,np.full(len(usable),h,dtype=np.int64)))
            for channel,estimator in enumerate(self.estimators):
                result[good,h-1,channel] = estimator.predict(values)
            if h == 1 or h%12 == 0:
                self.notify(phase="prediction_progress",h=h,origins=len(origins))
        return result


class RandomForestForecaster(DirectForecaster):
    family = "RandomForest"


class XGBoostForecaster(DirectForecaster):
    family = "XGBoost"


class SVRForecaster(DirectForecaster):
    family = "SVR"
