"""CI Test Suite: Phase 6 Pre-Registration Safeguard Verification.

Enforces Amendment 1 Section E:
1. No Phase 6 script under scripts/phase6/ may directly open or import
   data/multi/historical_10y_raw.csv or relative_features_v1.csv, bypassing
   the Phase 6 data loader (scripts/phase6/data_loader.py).
2. The data loader must refuse any rows or dates past the development cutoff
   (2025-09-16 = 2025-09-30 minus 10-trading-day purge gap).
3. The repo working tree must not contain Window A or Window B holdout data.
4. docs/holdout_access_log.md and preregistration docs must be intact.
"""

import os
import re
import sys
import unittest
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHASE6_DIR = os.path.join(BASE_DIR, "scripts", "phase6")
DATA_DIR = os.path.join(BASE_DIR, "data", "multi")
DOCS_DIR = os.path.join(BASE_DIR, "docs")

DEVELOPMENT_CUTOFF_DATE = "2025-09-16"
WINDOW_A_ARCHIVE_HASH = "71d16366ea3b8b7e7388ba1119e7a14f94fdbd19a474e85ed1fcbf829d364b6f"
WINDOW_B_ARCHIVE_HASH = "2e76ad72536d9df095e352c218c2acd3eee8cacea581d25eb1828795b4a89965"


class TestPhase6Safeguards(unittest.TestCase):

    def test_preregistration_documents_exist(self):
        """Ensure both signed pre-registration documents exist in docs/."""
        orig_doc = os.path.join(DOCS_DIR, "RESEARCH_PREREGISTRATION.md")
        amend_doc = os.path.join(DOCS_DIR, "RESEARCH_PREREGISTRATION_AMENDMENT_1.md")
        log_doc = os.path.join(DOCS_DIR, "holdout_access_log.md")

        self.assertTrue(os.path.isfile(orig_doc), f"Missing {orig_doc}")
        self.assertTrue(os.path.isfile(amend_doc), f"Missing {amend_doc}")
        self.assertTrue(os.path.isfile(log_doc), f"Missing {log_doc}")

        # Check that holdout_access_log.md has the pre-filled hashes
        with open(log_doc, "r", encoding="utf-8") as f:
            log_content = f.read()
        self.assertIn(WINDOW_A_ARCHIVE_HASH, log_content)
        self.assertIn(WINDOW_B_ARCHIVE_HASH, log_content)

    def test_no_direct_csv_access_in_phase6_scripts(self):
        """Phase 6 scripts under scripts/phase6/ must not read raw/feature CSVs directly."""
        prohibited_patterns = [
            re.compile(r"['\"].*?historical_10y_raw\.csv['\"]"),
            re.compile(r"['\"].*?relative_features_v1\.csv['\"]"),
        ]

        violations = []
        for root, _, files in os.walk(PHASE6_DIR):
            for file in files:
                if not file.endswith(".py"):
                    continue
                if file in ("data_loader.py",):
                    continue  # The loader itself legitimately references the storage path

                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, BASE_DIR)

                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                for pat in prohibited_patterns:
                    matches = pat.findall(content)
                    if matches:
                        violations.append(
                            f"{rel_path}: Matches forbidden direct reference {matches}. "
                            f"Phase 6 scripts must load data exclusively via scripts.phase6.data_loader."
                        )

        self.assertEqual(
            len(violations),
            0,
            "\n[CI FAILURE] Direct holdout/raw CSV access detected in Phase 6 scripts:\n"
            + "\n".join(violations),
        )

    def test_data_loader_refuses_post_cutoff_requests(self):
        """Data loader must raise PreRegistrationDataLeakError when given post-cutoff dates."""
        sys.path.insert(0, BASE_DIR)
        from scripts.phase6.data_loader import (
            load_development_data,
            load_development_features,
            load_development_raw,
            PreRegistrationDataLeakError,
        )

        # 1. Purge gap refusal (2025-09-20 > 2025-09-16)
        with self.assertRaises(PreRegistrationDataLeakError) as ctx:
            load_development_features(end_date="2025-09-20")
        self.assertIn("exceeds the Phase 6 development cutoff", str(ctx.exception))

        # 2. Window A refusal (start_date in Window A)
        with self.assertRaises(PreRegistrationDataLeakError) as ctx:
            load_development_features(start_date="2025-10-01")
        self.assertIn("falls after the development cutoff", str(ctx.exception))

        # 3. Window B refusal (start_date in Window B)
        with self.assertRaises(PreRegistrationDataLeakError) as ctx:
            load_development_raw(start_date="2026-04-01")
        self.assertIn("falls after the development cutoff", str(ctx.exception))

    def test_working_tree_data_never_exceeds_cutoff(self):
        """Verify that any CSVs in data/multi/ within the repo strictly end on or before the cutoff."""
        for filename in ["historical_10y_raw.csv", "relative_features_v1.csv"]:
            file_path = os.path.join(DATA_DIR, filename)
            if not os.path.isfile(file_path):
                continue

            df = pd.read_csv(file_path, usecols=["date"])
            max_date = df["date"].max()
            self.assertLessEqual(
                max_date,
                DEVELOPMENT_CUTOFF_DATE,
                f"{filename} contains date {max_date} which exceeds cutoff {DEVELOPMENT_CUTOFF_DATE}! "
                f"Window A and B data must be stored outside git in sealed archives.",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
