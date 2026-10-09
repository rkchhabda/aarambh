"""Fold-local preprocessing transformations with strict temporal leakage prevention.

Implements transformers and pipelines that:
1. Fit scaling, winsorization, imputation, and parameter statistics strictly on training slices.
2. Freeze parameters upon fitting to prevent leakage from validation or test data.
3. Perform cross-sectional ranking partitioned strictly by trading session date.
4. Record deterministic parameter hashes for provenance auditing.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from decimal import Decimal
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
import pandas as pd

from phase7.data.contracts import compute_row_hash
from phase7.validation.contracts import (
    PreprocessingLeakageError,
    PreprocessingNotFittedError,
    PreprocessingParameterRecord,
)


def _canonicalize_params_for_hashing(val: Any) -> Any:
    """Recursively convert float values to Decimal or explicit strings for deterministic hashing."""
    if isinstance(val, float):
        if math.isinf(val):
            return "Infinity" if val > 0 else "-Infinity"
        if math.isnan(val):
            return "NaN"
        return Decimal(f"{val:.8f}")
    if isinstance(val, dict):
        return {str(k): _canonicalize_params_for_hashing(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_canonicalize_params_for_hashing(v) for v in val]
    return val


class BaseFoldLocalTransformer(ABC):
    """Abstract base class for fold-local preprocessing transformations."""

    def __init__(self) -> None:
        self._is_fitted: bool = False
        self._fitted_params: Dict[str, Any] = {}
        self._feature_names: Tuple[str, ...] = ()
        self._fitted_row_count: int = 0
        self._fitted_timestamp: Optional[datetime] = None

    @property
    def is_fitted(self) -> bool:
        """Whether the transformer has been fitted on a training fold."""
        return self._is_fitted

    @property
    def fitted_parameters(self) -> Dict[str, Any]:
        """Dictionary of fitted parameter values."""
        if not self._is_fitted:
            raise PreprocessingNotFittedError("Transformer has not been fitted.")
        return dict(self._fitted_params)

    @property
    def feature_names(self) -> Tuple[str, ...]:
        """Tuple of feature names fitted."""
        return self._feature_names

    def _check_is_fitted(self) -> None:
        """Assert transformer has been fitted before transform."""
        if not self._is_fitted:
            raise PreprocessingNotFittedError(
                f"{self.__class__.__name__} is not fitted. Must call fit() before transform()."
            )

    @abstractmethod
    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: Optional[Any] = None) -> "BaseFoldLocalTransformer":
        """Fit transformer parameters strictly on training fold data."""
        pass

    @abstractmethod
    def transform(self, X: Union[pd.DataFrame, np.ndarray]) -> Union[pd.DataFrame, np.ndarray]:
        """Transform data using pre-fitted, frozen parameters."""
        pass

    def fit_transform(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Optional[Any] = None,
    ) -> Union[pd.DataFrame, np.ndarray]:
        """Fit transformer on training slice and return transformed slice."""
        return self.fit(X, y).transform(X)

    def get_parameter_hash(self) -> str:
        """Compute deterministic SHA-256 hash of fitted parameter dictionary."""
        self._check_is_fitted()
        return compute_row_hash(_canonicalize_params_for_hashing(self._fitted_params))


class FoldLocalWinsorizer(BaseFoldLocalTransformer):
    """Winsorize features by clipping outliers strictly to training fold percentiles."""

    def __init__(self, lower_quantile: float = 0.01, upper_quantile: float = 0.99) -> None:
        super().__init__()
        if not (0.0 <= lower_quantile < upper_quantile <= 1.0):
            raise ValueError(f"Invalid quantiles: lower={lower_quantile}, upper={upper_quantile}")
        self.lower_quantile = lower_quantile
        self.upper_quantile = upper_quantile

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: Optional[Any] = None) -> "FoldLocalWinsorizer":
        if isinstance(X, pd.DataFrame):
            self._feature_names = tuple(str(c) for c in X.columns)
            self._fitted_row_count = len(X)
            limits: Dict[str, Dict[str, float]] = {}
            for col in X.columns:
                series = X[col].dropna()
                if len(series) == 0:
                    q_low, q_high = float("-inf"), float("inf")
                else:
                    q_low = float(series.quantile(self.lower_quantile))
                    q_high = float(series.quantile(self.upper_quantile))
                limits[str(col)] = {"lower": q_low, "upper": q_high}
            self._fitted_params = limits
        elif isinstance(X, np.ndarray):
            self._feature_names = tuple(f"feature_{i}" for i in range(X.shape[1] if X.ndim > 1 else 1))
            self._fitted_row_count = len(X)
            limits = {}
            arr = np.atleast_2d(X)
            for i in range(arr.shape[1]):
                col = arr[:, i]
                valid = col[~np.isnan(col)]
                if len(valid) == 0:
                    q_low, q_high = float("-inf"), float("inf")
                else:
                    q_low = float(np.percentile(valid, self.lower_quantile * 100))
                    q_high = float(np.percentile(valid, self.upper_quantile * 100))
                limits[f"feature_{i}"] = {"lower": q_low, "upper": q_high}
            self._fitted_params = limits
        else:
            raise TypeError("X must be a pandas DataFrame or numpy ndarray.")

        self._fitted_timestamp = datetime.now(timezone.utc)
        self._is_fitted = True
        return self

    def transform(self, X: Union[pd.DataFrame, np.ndarray]) -> Union[pd.DataFrame, np.ndarray]:
        self._check_is_fitted()
        if isinstance(X, pd.DataFrame):
            out = X.copy()
            for col in X.columns:
                col_str = str(col)
                if col_str in self._fitted_params:
                    q_low = self._fitted_params[col_str]["lower"]
                    q_high = self._fitted_params[col_str]["upper"]
                    out[col] = out[col].clip(lower=q_low, upper=q_high)
            return out
        elif isinstance(X, np.ndarray):
            out = X.copy()
            arr = np.atleast_2d(out)
            for i in range(arr.shape[1]):
                key = f"feature_{i}"
                if key in self._fitted_params:
                    q_low = self._fitted_params[key]["lower"]
                    q_high = self._fitted_params[key]["upper"]
                    arr[:, i] = np.clip(arr[:, i], q_low, q_high)
            return out
        else:
            raise TypeError("X must be a pandas DataFrame or numpy ndarray.")


class FoldLocalStandardScaler(BaseFoldLocalTransformer):
    """Standardize features (z-score) using mean and std fitted strictly on training fold."""

    def __init__(self, with_mean: bool = True, with_std: bool = True, eps: float = 1e-8) -> None:
        super().__init__()
        self.with_mean = with_mean
        self.with_std = with_std
        self.eps = eps

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: Optional[Any] = None) -> "FoldLocalStandardScaler":
        if isinstance(X, pd.DataFrame):
            self._feature_names = tuple(str(c) for c in X.columns)
            self._fitted_row_count = len(X)
            stats: Dict[str, Dict[str, float]] = {}
            for col in X.columns:
                series = X[col].dropna()
                mean = float(series.mean()) if len(series) > 0 else 0.0
                std = float(series.std(ddof=0)) if len(series) > 0 else 1.0
                if std < self.eps:
                    std = 1.0  # safe variance floor
                stats[str(col)] = {"mean": mean, "std": std}
            self._fitted_params = stats
        elif isinstance(X, np.ndarray):
            self._feature_names = tuple(f"feature_{i}" for i in range(X.shape[1] if X.ndim > 1 else 1))
            self._fitted_row_count = len(X)
            stats = {}
            arr = np.atleast_2d(X)
            for i in range(arr.shape[1]):
                col = arr[:, i]
                valid = col[~np.isnan(col)]
                mean = float(np.mean(valid)) if len(valid) > 0 else 0.0
                std = float(np.std(valid)) if len(valid) > 0 else 1.0
                if std < self.eps:
                    std = 1.0
                stats[f"feature_{i}"] = {"mean": mean, "std": std}
            self._fitted_params = stats
        else:
            raise TypeError("X must be a pandas DataFrame or numpy ndarray.")

        self._fitted_timestamp = datetime.now(timezone.utc)
        self._is_fitted = True
        return self

    def transform(self, X: Union[pd.DataFrame, np.ndarray]) -> Union[pd.DataFrame, np.ndarray]:
        self._check_is_fitted()
        if isinstance(X, pd.DataFrame):
            out = X.copy()
            for col in X.columns:
                col_str = str(col)
                if col_str in self._fitted_params:
                    mean = self._fitted_params[col_str]["mean"] if self.with_mean else 0.0
                    std = self._fitted_params[col_str]["std"] if self.with_std else 1.0
                    out[col] = (out[col] - mean) / std
            return out
        elif isinstance(X, np.ndarray):
            out = X.copy().astype(float)
            arr = np.atleast_2d(out)
            for i in range(arr.shape[1]):
                key = f"feature_{i}"
                if key in self._fitted_params:
                    mean = self._fitted_params[key]["mean"] if self.with_mean else 0.0
                    std = self._fitted_params[key]["std"] if self.with_std else 1.0
                    arr[:, i] = (arr[:, i] - mean) / std
            return out
        else:
            raise TypeError("X must be a pandas DataFrame or numpy ndarray.")


class FoldLocalRobustScaler(BaseFoldLocalTransformer):
    """Scale features using median and interquartile range fitted strictly on training fold."""

    def __init__(self, quantile_range: Tuple[float, float] = (0.25, 0.75), eps: float = 1e-8) -> None:
        super().__init__()
        q_low, q_high = quantile_range
        if not (0.0 <= q_low < q_high <= 1.0):
            raise ValueError(f"Invalid quantile_range: {quantile_range}")
        self.quantile_range = quantile_range
        self.eps = eps

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: Optional[Any] = None) -> "FoldLocalRobustScaler":
        q_low_p, q_high_p = self.quantile_range
        if isinstance(X, pd.DataFrame):
            self._feature_names = tuple(str(c) for c in X.columns)
            self._fitted_row_count = len(X)
            stats: Dict[str, Dict[str, float]] = {}
            for col in X.columns:
                series = X[col].dropna()
                median = float(series.median()) if len(series) > 0 else 0.0
                q_low = float(series.quantile(q_low_p)) if len(series) > 0 else 0.0
                q_high = float(series.quantile(q_high_p)) if len(series) > 0 else 1.0
                iqr = q_high - q_low
                if iqr < self.eps:
                    iqr = 1.0
                stats[str(col)] = {"median": median, "iqr": iqr}
            self._fitted_params = stats
        elif isinstance(X, np.ndarray):
            self._feature_names = tuple(f"feature_{i}" for i in range(X.shape[1] if X.ndim > 1 else 1))
            self._fitted_row_count = len(X)
            stats = {}
            arr = np.atleast_2d(X)
            for i in range(arr.shape[1]):
                col = arr[:, i]
                valid = col[~np.isnan(col)]
                median = float(np.median(valid)) if len(valid) > 0 else 0.0
                q_low = float(np.percentile(valid, q_low_p * 100)) if len(valid) > 0 else 0.0
                q_high = float(np.percentile(valid, q_high_p * 100)) if len(valid) > 0 else 1.0
                iqr = q_high - q_low
                if iqr < self.eps:
                    iqr = 1.0
                stats[f"feature_{i}"] = {"median": median, "iqr": iqr}
            self._fitted_params = stats
        else:
            raise TypeError("X must be a pandas DataFrame or numpy ndarray.")

        self._fitted_timestamp = datetime.now(timezone.utc)
        self._is_fitted = True
        return self

    def transform(self, X: Union[pd.DataFrame, np.ndarray]) -> Union[pd.DataFrame, np.ndarray]:
        self._check_is_fitted()
        if isinstance(X, pd.DataFrame):
            out = X.copy()
            for col in X.columns:
                col_str = str(col)
                if col_str in self._fitted_params:
                    median = self._fitted_params[col_str]["median"]
                    iqr = self._fitted_params[col_str]["iqr"]
                    out[col] = (out[col] - median) / iqr
            return out
        elif isinstance(X, np.ndarray):
            out = X.copy().astype(float)
            arr = np.atleast_2d(out)
            for i in range(arr.shape[1]):
                key = f"feature_{i}"
                if key in self._fitted_params:
                    median = self._fitted_params[key]["median"]
                    iqr = self._fitted_params[key]["iqr"]
                    arr[:, i] = (arr[:, i] - median) / iqr
            return out
        else:
            raise TypeError("X must be a pandas DataFrame or numpy ndarray.")


class FoldLocalImputer(BaseFoldLocalTransformer):
    """Impute missing values using statistics fitted strictly on training fold."""

    def __init__(self, strategy: str = "median") -> None:
        super().__init__()
        if strategy not in ("median", "mean", "zero"):
            raise ValueError(f"Unsupported strategy '{strategy}'. Must be 'median', 'mean', or 'zero'.")
        self.strategy = strategy

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: Optional[Any] = None) -> "FoldLocalImputer":
        if isinstance(X, pd.DataFrame):
            self._feature_names = tuple(str(c) for c in X.columns)
            self._fitted_row_count = len(X)
            stats: Dict[str, float] = {}
            for col in X.columns:
                series = X[col].dropna()
                if self.strategy == "median":
                    val = float(series.median()) if len(series) > 0 else 0.0
                elif self.strategy == "mean":
                    val = float(series.mean()) if len(series) > 0 else 0.0
                else:
                    val = 0.0
                stats[str(col)] = val
            self._fitted_params = stats
        elif isinstance(X, np.ndarray):
            self._feature_names = tuple(f"feature_{i}" for i in range(X.shape[1] if X.ndim > 1 else 1))
            self._fitted_row_count = len(X)
            stats = {}
            arr = np.atleast_2d(X)
            for i in range(arr.shape[1]):
                col = arr[:, i]
                valid = col[~np.isnan(col)]
                if self.strategy == "median":
                    val = float(np.median(valid)) if len(valid) > 0 else 0.0
                elif self.strategy == "mean":
                    val = float(np.mean(valid)) if len(valid) > 0 else 0.0
                else:
                    val = 0.0
                stats[f"feature_{i}"] = val
            self._fitted_params = stats
        else:
            raise TypeError("X must be a pandas DataFrame or numpy ndarray.")

        self._fitted_timestamp = datetime.now(timezone.utc)
        self._is_fitted = True
        return self

    def transform(self, X: Union[pd.DataFrame, np.ndarray]) -> Union[pd.DataFrame, np.ndarray]:
        self._check_is_fitted()
        if isinstance(X, pd.DataFrame):
            out = X.copy()
            for col in X.columns:
                col_str = str(col)
                if col_str in self._fitted_params:
                    out[col] = out[col].fillna(self._fitted_params[col_str])
            return out
        elif isinstance(X, np.ndarray):
            out = X.copy().astype(float)
            arr = np.atleast_2d(out)
            for i in range(arr.shape[1]):
                key = f"feature_{i}"
                if key in self._fitted_params:
                    fill = self._fitted_params[key]
                    mask = np.isnan(arr[:, i])
                    arr[mask, i] = fill
            return out
        else:
            raise TypeError("X must be a pandas DataFrame or numpy ndarray.")


class CrossSectionalRanker:
    """Rank features cross-sectionally per trading date without multi-session pooling."""

    def __init__(self, centered: bool = True) -> None:
        """Initialize cross-sectional ranker.

        Args:
            centered: If True, ranks are centered to [-0.5, 0.5]; if False, normalized to [0.0, 1.0].
        """
        self.centered = centered

    def transform_df(
        self,
        df: pd.DataFrame,
        feature_columns: Sequence[str],
        date_column: str = "trading_date",
    ) -> pd.DataFrame:
        """Compute cross-sectional percentile ranks per trading session date.

        Args:
            df: DataFrame containing date_column and feature_columns.
            feature_columns: Feature columns to rank.
            date_column: Column identifying the trading date.

        Returns:
            DataFrame with transformed feature columns.
        """
        if date_column not in df.columns:
            raise KeyError(f"date_column '{date_column}' not found.")

        groups = []
        for dt, group in df.groupby(date_column):
            group_copy = group.copy()
            n = len(group_copy)
            if n <= 1:
                for col in feature_columns:
                    group_copy[col] = 0.0 if self.centered else 0.5
            else:
                for col in feature_columns:
                    ranks = group_copy[col].rank(method="average", ascending=True, na_option="keep")
                    pct = (ranks - 0.5) / n
                    group_copy[col] = (pct - 0.5) if self.centered else pct
            groups.append(group_copy)

        out = pd.concat(groups, axis=0) if groups else df.copy()
        return out


class FoldLocalPipeline:
    """Sequential pipeline of fold-local transformers with provenance tracking."""

    def __init__(self, steps: Sequence[Tuple[str, BaseFoldLocalTransformer]]) -> None:
        """Initialize pipeline with ordered steps.

        Args:
            steps: List of (step_name, transformer_instance) tuples.
        """
        self.steps = list(steps)
        self._is_fitted: bool = False
        self._fitted_row_count: int = 0
        self._fitted_timestamp: Optional[datetime] = None

    @property
    def is_fitted(self) -> bool:
        return self._is_fitted

    def fit(self, X: Union[pd.DataFrame, np.ndarray], y: Optional[Any] = None) -> "FoldLocalPipeline":
        """Fit all pipeline transformers sequentially on the training fold."""
        cur_X = X
        for name, transformer in self.steps:
            cur_X = transformer.fit_transform(cur_X, y)

        self._fitted_row_count = len(X)
        self._fitted_timestamp = datetime.now(timezone.utc)
        self._is_fitted = True
        return self

    def transform(self, X: Union[pd.DataFrame, np.ndarray]) -> Union[pd.DataFrame, np.ndarray]:
        """Transform data through all fitted transformers."""
        if not self._is_fitted:
            raise PreprocessingNotFittedError("Pipeline has not been fitted.")

        cur_X = X
        for name, transformer in self.steps:
            cur_X = transformer.transform(cur_X)
        return cur_X

    def fit_transform(
        self,
        X: Union[pd.DataFrame, np.ndarray],
        y: Optional[Any] = None,
    ) -> Union[pd.DataFrame, np.ndarray]:
        return self.fit(X, y).transform(X)

    def build_parameter_record(
        self,
        fold_index: int,
        dataset_version: str = "v1.0.0",
    ) -> PreprocessingParameterRecord:
        """Build an immutable PreprocessingParameterRecord for audit provenance."""
        if not self._is_fitted:
            raise PreprocessingNotFittedError("Pipeline has not been fitted.")

        combined_params: Dict[str, Any] = {}
        all_features: List[str] = []

        for name, transformer in self.steps:
            combined_params[name] = transformer.fitted_parameters
            for feat in transformer.feature_names:
                if feat not in all_features:
                    all_features.append(feat)

        canon_params = _canonicalize_params_for_hashing(combined_params)

        return PreprocessingParameterRecord(
            fold_index=fold_index,
            transformer_name="FoldLocalPipeline",
            feature_names=tuple(all_features),
            parameters=canon_params,
            fitted_row_count=self._fitted_row_count,
            fitted_timestamp=self._fitted_timestamp or datetime.now(timezone.utc),
            dataset_version=dataset_version,
        )
