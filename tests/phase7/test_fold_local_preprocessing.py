"""Unit tests for fold-local preprocessing transformations and leakage prevention."""

from datetime import date
import numpy as np
import pandas as pd
import pytest

from phase7.validation.contracts import (
    PreprocessingNotFittedError,
    PreprocessingParameterRecord,
)
from phase7.validation.preprocessing import (
    CrossSectionalRanker,
    FoldLocalImputer,
    FoldLocalPipeline,
    FoldLocalRobustScaler,
    FoldLocalStandardScaler,
    FoldLocalWinsorizer,
)


class TestFoldLocalPreprocessing:
    """Test suite verifying fold-local preprocessing transformations and leakage defense."""

    def test_winsorizer_fits_strictly_on_train_slice(self) -> None:
        """Verify that winsorizer bounds are derived exclusively from train data."""
        train_data = pd.DataFrame({"feat1": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]})
        test_data = pd.DataFrame({"feat1": [0.0, 5.0, 100.0]})  # Extreme outlier 100.0

        winsorizer = FoldLocalWinsorizer(lower_quantile=0.10, upper_quantile=0.90)
        winsorizer.fit(train_data)

        # Fitted limits based on train
        params = winsorizer.fitted_parameters
        q_low = params["feat1"]["lower"]
        q_high = params["feat1"]["upper"]

        assert q_low == pytest.approx(1.9, rel=1e-2)
        assert q_high == pytest.approx(9.1, rel=1e-2)

        # Transform test data clips test outlier to train q_high
        transformed_test = winsorizer.transform(test_data)
        assert transformed_test["feat1"].iloc[2] == pytest.approx(q_high)
        assert transformed_test["feat1"].iloc[0] == pytest.approx(q_low)

        # Transformer parameters did not change
        assert winsorizer.fitted_parameters["feat1"]["upper"] == pytest.approx(q_high)

    def test_standard_scaler_fits_strictly_on_train_slice(self) -> None:
        """Verify that standard scaler parameters use train mean and std."""
        train_data = pd.DataFrame({"feat1": [10.0, 20.0, 30.0]})  # mean=20, std=sqrt(200/3)=8.165
        test_data = pd.DataFrame({"feat1": [20.0, 50.0]})

        scaler = FoldLocalStandardScaler()
        scaler.fit(train_data)

        params = scaler.fitted_parameters
        assert params["feat1"]["mean"] == pytest.approx(20.0)
        assert params["feat1"]["std"] == pytest.approx(8.1649658, rel=1e-4)

        transformed_test = scaler.transform(test_data)
        # 20.0 - 20.0 = 0.0
        assert transformed_test["feat1"].iloc[0] == pytest.approx(0.0)
        # 50.0 - 20.0 = 30.0 / 8.165 = 3.674
        assert transformed_test["feat1"].iloc[1] == pytest.approx(3.67423, rel=1e-4)

    def test_robust_scaler_fits_strictly_on_train_slice(self) -> None:
        """Verify robust scaler uses train median and IQR."""
        train_data = pd.DataFrame({"feat1": [1.0, 2.0, 3.0, 4.0, 5.0]})  # median=3.0, IQR = 4.0 - 2.0 = 2.0
        test_data = pd.DataFrame({"feat1": [3.0, 7.0]})

        scaler = FoldLocalRobustScaler(quantile_range=(0.25, 0.75))
        scaler.fit(train_data)

        params = scaler.fitted_parameters
        assert params["feat1"]["median"] == pytest.approx(3.0)
        assert params["feat1"]["iqr"] == pytest.approx(2.0)

        transformed_test = scaler.transform(test_data)
        assert transformed_test["feat1"].iloc[0] == pytest.approx(0.0)
        assert transformed_test["feat1"].iloc[1] == pytest.approx(2.0)  # (7-3)/2 = 2.0

    def test_imputer_fits_strictly_on_train_slice(self) -> None:
        """Verify imputer fills missing values using train median."""
        train_data = pd.DataFrame({"feat1": [10.0, 20.0, np.nan, 30.0]})  # median=20.0
        test_data = pd.DataFrame({"feat1": [np.nan, 100.0]})

        imputer = FoldLocalImputer(strategy="median")
        imputer.fit(train_data)

        assert imputer.fitted_parameters["feat1"] == pytest.approx(20.0)

        transformed_test = imputer.transform(test_data)
        assert transformed_test["feat1"].iloc[0] == pytest.approx(20.0)
        assert transformed_test["feat1"].iloc[1] == pytest.approx(100.0)

    def test_unfitted_transformer_raises_error(self) -> None:
        """Verify that transform before fit raises PreprocessingNotFittedError."""
        scaler = FoldLocalStandardScaler()
        df = pd.DataFrame({"feat1": [1.0, 2.0]})
        with pytest.raises(PreprocessingNotFittedError, match="not fitted"):
            scaler.transform(df)

        winsorizer = FoldLocalWinsorizer()
        with pytest.raises(PreprocessingNotFittedError, match="not fitted"):
            winsorizer.transform(df)

    def test_anti_leakage_proof_global_vs_fold_local(self) -> None:
        """Demonstrate mathematically that global preprocessing leaks test data into train."""
        # Train dataset
        train_data = pd.DataFrame({"feat1": [10.0, 20.0, 30.0]})
        # Test dataset A: standard
        test_data_A = pd.DataFrame({"feat1": [20.0, 25.0]})
        # Test dataset B: extreme outlier
        test_data_B = pd.DataFrame({"feat1": [20.0, 10000.0]})

        # Fold-local scaler: fit ONLY on train
        scaler_local = FoldLocalStandardScaler()
        scaler_local.fit(train_data)
        train_transformed_local = scaler_local.transform(train_data)

        # Global scaler with test A
        global_data_A = pd.concat([train_data, test_data_A], ignore_index=True)
        scaler_global_A = FoldLocalStandardScaler()
        scaler_global_A.fit(global_data_A)
        train_transformed_global_A = scaler_global_A.transform(train_data)

        # Global scaler with test B (outlier)
        global_data_B = pd.concat([train_data, test_data_B], ignore_index=True)
        scaler_global_B = FoldLocalStandardScaler()
        scaler_global_B.fit(global_data_B)
        train_transformed_global_B = scaler_global_B.transform(train_data)

        # In global scaling, the outlier in test B shifts the training transformed values:
        # train_transformed_global_A != train_transformed_global_B (LEAKAGE PROOF)
        assert not np.allclose(
            train_transformed_global_A["feat1"].values,
            train_transformed_global_B["feat1"].values,
        )

        # In fold-local scaling, test data B does not affect training transformation:
        # Re-fitting local scaler on train produces identical result regardless of test B
        scaler_local_2 = FoldLocalStandardScaler()
        scaler_local_2.fit(train_data)
        train_transformed_local_2 = scaler_local_2.transform(train_data)
        assert np.allclose(
            train_transformed_local["feat1"].values,
            train_transformed_local_2["feat1"].values,
        )

    def test_cross_sectional_ranker_per_date_partitioning(self) -> None:
        """Verify cross-sectional ranker groups strictly by date without pooling."""
        df = pd.DataFrame({
            "trading_date": [
                date(2023, 1, 2), date(2023, 1, 2), date(2023, 1, 2),
                date(2023, 1, 3), date(2023, 1, 3), date(2023, 1, 3),
            ],
            "symbol": ["A", "B", "C", "A", "B", "C"],
            "feat1": [10.0, 20.0, 30.0, 100.0, 200.0, 300.0],
        })

        ranker = CrossSectionalRanker(centered=True)
        ranked = ranker.transform_df(df, feature_columns=["feat1"])

        # Date 1 ranks: [10, 20, 30] -> percentile ranks [-0.333, 0.0, 0.333]
        d1 = ranked[ranked["trading_date"] == date(2023, 1, 2)]["feat1"].values
        # Date 2 ranks: [100, 200, 300] -> identical relative percentiles
        d2 = ranked[ranked["trading_date"] == date(2023, 1, 3)]["feat1"].values

        assert np.allclose(d1, d2)
        assert d1[0] == pytest.approx((1.0 - 0.5) / 3.0 - 0.5)  # -0.33333
        assert d1[1] == pytest.approx((2.0 - 0.5) / 3.0 - 0.5)  # 0.0
        assert d1[2] == pytest.approx((3.0 - 0.5) / 3.0 - 0.5)  # 0.33333

    def test_pipeline_provenance_and_parameter_record(self) -> None:
        """Verify FoldLocalPipeline chains transformers and produces immutable parameter record."""
        train_df = pd.DataFrame({
            "f1": [1.0, 2.0, np.nan, 4.0, 50.0],  # Outlier and NaN
            "f2": [10.0, 20.0, 30.0, 40.0, 50.0],
        })

        pipeline = FoldLocalPipeline([
            ("winsorize", FoldLocalWinsorizer(lower_quantile=0.05, upper_quantile=0.95)),
            ("impute", FoldLocalImputer(strategy="median")),
            ("scale", FoldLocalStandardScaler()),
        ])

        assert not pipeline.is_fitted
        pipeline.fit(train_df)
        assert pipeline.is_fitted

        rec = pipeline.build_parameter_record(fold_index=0, dataset_version="v1.0.0")
        assert isinstance(rec, PreprocessingParameterRecord)
        assert rec.fold_index == 0
        assert rec.parameter_hash != ""
        assert "winsorize" in rec.parameters
        assert "impute" in rec.parameters
        assert "scale" in rec.parameters

        # Re-fitting with same data produces identical parameter hash
        pipeline2 = FoldLocalPipeline([
            ("winsorize", FoldLocalWinsorizer(lower_quantile=0.05, upper_quantile=0.95)),
            ("impute", FoldLocalImputer(strategy="median")),
            ("scale", FoldLocalStandardScaler()),
        ])
        pipeline2.fit(train_df)
        rec2 = pipeline2.build_parameter_record(fold_index=0, dataset_version="v1.0.0")
        assert rec.parameter_hash == rec2.parameter_hash
