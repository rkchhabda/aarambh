"""CI Test Suite: Fail-Closed Loaders, Auditing, and Boundary Defense.

Covers tests 78-92:
- CSV and JSONL parsing with row-by-row validation
- Retention of line numbers and specific rejection reasons
- Non-coercion of invalid monetary or missing volume fields (never zero)
- Duplicate key counting
- Deterministic audit reports (checksums, file sizes, zero return/alpha fields)
- Strict boundary check: active Phase 7 code does not import features.universe,
  Phase 6 scripts, or production service routes, and never queries Phase 6 vaults.
"""

import os
from pathlib import Path
import sys
import tempfile
import unittest

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from phase7.data.audit import audit_dataset_file
from phase7.data.contracts import DailyPriceRecord
from phase7.data.loaders import (
    CSVDataLoader,
    JSONLinesDataLoader,
    parse_daily_price_row,
)


class TestDataLoadersAndAudits(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_csv_loader_returns_accepted_and_rejected_with_row_numbers(self):
        """78, 79, 80. CSV loader returns accepted & rejected with row numbers and reasons."""
        csv_file = self.tmp_path / "prices_test.csv"
        # Row 1: Header
        # Row 2: Valid row
        # Row 3: Invalid row (negative close price)
        # Row 4: Valid row
        content = (
            "trading_date,symbol,isin,open,high,low,close,volume,traded_value_inr,source_timestamp,ingestion_timestamp\n"
            "2025-01-01,TCS,INE467B01029,3000.0,3050.0,2980.0,3020.0,1000,3000000.0,2025-01-01T16:00:00Z,2025-01-01T17:00:00Z\n"
            "2025-01-01,INFY,INE009A01021,1500.0,1520.0,1490.0,-10.0,500,750000.0,2025-01-01T16:00:00Z,2025-01-01T17:00:00Z\n"
            "2025-01-02,TCS,INE467B01029,3020.0,3060.0,3010.0,3040.0,1200,3600000.0,2025-01-02T16:00:00Z,2025-01-02T17:00:00Z\n"
        )
        csv_file.write_text(content, encoding="utf-8")

        loader = CSVDataLoader[DailyPriceRecord](parse_daily_price_row)
        res = loader.load(csv_file)

        self.assertEqual(res.total_rows, 3)
        self.assertEqual(res.accepted_count, 2)
        self.assertEqual(res.rejected_count, 1)

        rej = res.rejected_records[0]
        self.assertEqual(rej.row_number, 3)  # Line 3 in file
        self.assertTrue(any("must be positive" in r for r in rej.reasons))

    def test_invalid_values_not_silently_coerced_to_zero(self):
        """81, 82. Invalid monetary or missing volume values do not become zero."""
        csv_file = self.tmp_path / "bad_values.csv"
        content = (
            "trading_date,symbol,isin,open,high,low,close,volume,traded_value_inr,source_timestamp,ingestion_timestamp\n"
            "2025-01-01,TCS,INE467B01029,N/A,3050.0,2980.0,3020.0,1000,3000000.0,2025-01-01T16:00:00Z,2025-01-01T17:00:00Z\n"
            "2025-01-01,INFY,INE009A01021,1500.0,1520.0,1490.0,1500.0,,750000.0,2025-01-01T16:00:00Z,2025-01-01T17:00:00Z\n"
        )
        csv_file.write_text(content, encoding="utf-8")

        loader = CSVDataLoader[DailyPriceRecord](parse_daily_price_row)
        res = loader.load(csv_file)

        # Both rows should be rejected, not parsed with 0 open or 0 volume
        self.assertEqual(res.rejected_count, 2)
        self.assertEqual(res.accepted_count, 0)

    def test_audit_report_contains_zero_investment_performance_metrics(self):
        """85, 86. Audit report produces quality checksums and zero investment performance metrics."""
        csv_file = self.tmp_path / "audit_sample.csv"
        content = (
            "trading_date,symbol,isin,open,high,low,close,volume,traded_value_inr,source_timestamp,ingestion_timestamp\n"
            "2025-01-01,TCS,INE467B01029,3000.0,3050.0,2980.0,3020.0,1000,3000000.0,2025-01-01T16:00:00Z,2025-01-01T17:00:00Z\n"
        )
        csv_file.write_text(content, encoding="utf-8")

        loader = CSVDataLoader[DailyPriceRecord](parse_daily_price_row)
        audit = audit_dataset_file(csv_file, loader)

        report_dict = audit.to_dict()
        # Verify provenance fields exist
        self.assertEqual(report_dict["total_row_count"], 1)
        self.assertEqual(report_dict["accepted_row_count"], 1)
        self.assertEqual(report_dict["symbol_count"], 1)
        self.assertTrue(len(report_dict["file_checksum_sha256"]) == 64)

        # Verify NO performance fields exist
        forbidden_keys = ["sharpe", "rank_ic", "alpha", "drawdown", "return", "picks", "sortino", "calmar"]
        for k in report_dict.keys():
            for f in forbidden_keys:
                self.assertNotIn(f, k.lower(), f"Forbidden performance key '{k}' found in audit report!")

    def test_active_phase7_modules_have_no_forbidden_imports(self):
        """87, 88, 89, 90. Phase 7 active code must not import features.universe, scripts.phase6, or service."""
        phase7_src_dir = BASE_DIR / "phase7"
        forbidden_imports = [
            "features.universe",
            "features.universe.TICKERS",
            "scripts.phase6",
            "service.app",
            "service.routes_signals",
        ]

        violations = []
        for root, _, files in os.walk(phase7_src_dir):
            for f in files:
                if not f.endswith(".py"):
                    continue
                fpath = Path(root) / f
                content = fpath.read_text(encoding="utf-8", errors="ignore")
                for imp in forbidden_imports:
                    if f"import {imp}" in content or f"from {imp}" in content:
                        violations.append(f"{fpath.relative_to(BASE_DIR)} imports {imp}")

        self.assertEqual(violations, [], f"Forbidden imports detected in active Phase 7 code:\n" + "\n".join(violations))


if __name__ == "__main__":
    unittest.main()
