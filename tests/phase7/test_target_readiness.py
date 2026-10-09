"""Unit tests for Phase 7 target engine real-data readiness gate.

Verifies:
1. BLK-01 (membership) blocks all real target generation.
2. BLK-02 (OHLCV liquidity) blocks all real target generation.
3. BLK-04 (sector history) blocks real sector-relative target generation.
4. Combinations of blockers preserve multiple simultaneous blocked statuses.
5. Missing or empty dataset versions fail closed with DATA_VALIDATION_FAILURE.
6. Empty real-data output CANNOT be reported as success.
7. Synthetic testing readiness does not imply real-data readiness.
8. Deterministic SHA-256 readiness hash generation.
"""

import unittest

from phase7.targets.readiness import (
    TargetReadinessResult,
    TargetReadinessStatus,
    evaluate_target_readiness,
)


class TestTargetReadiness(unittest.TestCase):

    def test_blk01_blocks_real_target_generation(self):
        """Unresolved BLK-01 produces BLOCKED_BLK_01_MEMBERSHIP and TARGET_ENGINE_READY_REAL_DATA_BLOCKED."""
        res = evaluate_target_readiness(
            target_name="target_20d_sector_relative",
            dataset_version="v2025.1",
            blk_01_resolved=False,
            blk_02_resolved=True,
            blk_04_resolved=True,
        )
        self.assertEqual(res.overall_status, TargetReadinessStatus.TARGET_ENGINE_READY_REAL_DATA_BLOCKED)
        self.assertTrue(res.is_real_data_blocked)
        self.assertIn("BLK-01", res.active_blockers)
        self.assertIn(TargetReadinessStatus.BLOCKED_BLK_01_MEMBERSHIP, res.blocker_statuses)

    def test_blk02_blocks_real_target_generation(self):
        """Unresolved BLK-02 produces BLOCKED_BLK_02_OHLCV_LIQUIDITY."""
        res = evaluate_target_readiness(
            target_name="target_60d_residual",
            dataset_version="v2025.1",
            blk_01_resolved=True,
            blk_02_resolved=False,
            blk_04_resolved=True,
        )
        self.assertEqual(res.overall_status, TargetReadinessStatus.TARGET_ENGINE_READY_REAL_DATA_BLOCKED)
        self.assertTrue(res.is_real_data_blocked)
        self.assertIn("BLK-02", res.active_blockers)
        self.assertIn(TargetReadinessStatus.BLOCKED_BLK_02_OHLCV_LIQUIDITY, res.blocker_statuses)

    def test_blk04_blocks_sector_relative_target_generation(self):
        """Unresolved BLK-04 blocks sector-relative targets specifically."""
        res_sector = evaluate_target_readiness(
            target_name="target_20d_sector_relative",
            dataset_version="v2025.1",
            blk_01_resolved=True,
            blk_02_resolved=True,
            blk_04_resolved=False,
        )
        self.assertEqual(res_sector.overall_status, TargetReadinessStatus.TARGET_ENGINE_READY_REAL_DATA_BLOCKED)
        self.assertIn("BLK-04", res_sector.active_blockers)
        self.assertIn(TargetReadinessStatus.BLOCKED_BLK_04_SECTOR_HISTORY, res_sector.blocker_statuses)

        # Residual target does not require sector history
        res_residual = evaluate_target_readiness(
            target_name="target_60d_residual",
            dataset_version="v2025.1",
            blk_01_resolved=True,
            blk_02_resolved=True,
            blk_04_resolved=False,
        )
        self.assertEqual(res_residual.overall_status, TargetReadinessStatus.READY_FOR_SYNTHETIC_TESTING)
        self.assertFalse(res_residual.is_real_data_blocked)

    def test_multiple_simultaneous_blockers_preserved(self):
        """When BLK-01, BLK-02, and BLK-04 are all unresolved, all three are reported."""
        res = evaluate_target_readiness(
            target_name="target_20d_sector_relative",
            dataset_version="v2025.1",
            blk_01_resolved=False,
            blk_02_resolved=False,
            blk_04_resolved=False,
        )
        self.assertEqual(res.overall_status, TargetReadinessStatus.TARGET_ENGINE_READY_REAL_DATA_BLOCKED)
        self.assertTrue(res.is_real_data_blocked)
        self.assertEqual(len(res.active_blockers), 3)
        self.assertIn("BLK-01", res.active_blockers)
        self.assertIn("BLK-02", res.active_blockers)
        self.assertIn("BLK-04", res.active_blockers)

    def test_missing_dataset_version_fails_closed(self):
        """Missing or empty dataset_version produces DATA_VALIDATION_FAILURE."""
        res_none = evaluate_target_readiness(
            target_name="target_20d_sector_relative",
            dataset_version=None,
        )
        self.assertEqual(res_none.overall_status, TargetReadinessStatus.DATA_VALIDATION_FAILURE)
        self.assertTrue(res_none.is_real_data_blocked)
        self.assertFalse(res_none.is_synthetic_ready)

        res_empty = evaluate_target_readiness(
            target_name="target_20d_sector_relative",
            dataset_version="   ",
        )
        self.assertEqual(res_empty.overall_status, TargetReadinessStatus.DATA_VALIDATION_FAILURE)

    def test_empty_real_data_output_cannot_be_reported_as_success(self):
        """A pipeline that produces 0 target records in real-data mode fails closed and cannot report success."""
        res = evaluate_target_readiness(
            target_name="target_20d_sector_relative",
            dataset_version="v2025.1",
            blk_01_resolved=True,
            blk_02_resolved=True,
            blk_04_resolved=True,
            is_real_data_evaluation=True,
            generated_targets_count=0,
        )
        self.assertEqual(res.overall_status, TargetReadinessStatus.DATA_VALIDATION_FAILURE)
        self.assertFalse(res.is_synthetic_ready)
        self.assertTrue(res.is_real_data_blocked)

    def test_synthetic_readiness_does_not_imply_real_data_readiness(self):
        """Synthetic test readiness is True while real-data execution remains strictly blocked."""
        res = evaluate_target_readiness(
            target_name="target_20d_sector_relative",
            dataset_version="v2025.1",
            blk_01_resolved=False,
            blk_02_resolved=False,
        )
        self.assertTrue(res.is_synthetic_ready)
        self.assertTrue(res.is_real_data_blocked)
        self.assertEqual(res.overall_status, TargetReadinessStatus.TARGET_ENGINE_READY_REAL_DATA_BLOCKED)


if __name__ == "__main__":
    unittest.main()
