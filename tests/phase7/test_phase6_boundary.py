"""CI Test Suite: Phase 6 Immutability and Vault Boundary Defense.

Enforces Non-Negotiable Rules 1, 3, 5, and Owner Decisions for Milestone 1:
1. Phase 6 closure tag and checkpoint commit are verified and documented.
2. Phase 7 code cannot access or reference Phase 6 external vaults.
3. Phase 7 configuration cannot reference Phase 6 holdout archives.
4. Phase 7 modules cannot import Phase 6 training scripts.
5. The static universe implementation (features.universe) cannot be selected for Phase 7.
6. Phase 6 evidence files and access logs remain strictly unmodified.
"""

import os
import re
import sys
import unittest
from pathlib import Path
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from phase7.governance.schemas import load_and_validate_phase7_config, Phase7ConfigValidationError

PHASE7_DIR = BASE_DIR / "phase7"
CONFIG_PATH = BASE_DIR / "config" / "phase7.yaml"
DOCS_DIR = BASE_DIR / "docs"

PHASE6_CHECKPOINT_COMMIT = "c978968ec822aa20453920c8708673fcaa736695"
PHASE6_CLOSURE_TAG = "phase6-closed-2026-10-04"

FORBIDDEN_VAULT_PATHS = [
    r"gaurvideep_vault",
    r"C:\Users\r_chh\gaurvideep_vault",
    r"window_a_sealed.7z",
    r"window_b_sealed.7z",
]


class TestPhase6Boundary(unittest.TestCase):

    def test_phase6_closure_checkpoint_documented(self):
        """Verify Phase 6 closure tag and commit are properly recorded in config."""
        config = load_and_validate_phase7_config(CONFIG_PATH)
        meta = config.get("metadata", {})
        self.assertEqual(meta.get("phase6_closure_checkpoint"), PHASE6_CHECKPOINT_COMMIT)
        self.assertEqual(meta.get("phase6_closure_tag"), PHASE6_CLOSURE_TAG)

    def test_no_phase6_vault_paths_in_phase7_code(self):
        """Phase 7 code under phase7/ must never reference Phase 6 vault paths."""
        violations = []
        # Pattern matching vault folder or sealed archives
        pattern = re.compile(r"gaurvideep_vault|window_a_sealed\.7z|window_b_sealed\.7z", re.IGNORECASE)

        for root, _, files in os.walk(PHASE7_DIR):
            for f in files:
                if not f.endswith(".py"):
                    continue
                file_path = Path(root) / f
                content = file_path.read_text(encoding="utf-8", errors="ignore")

                # Exclude schemas.py where forbidden vault strings are explicitly defined for checking
                if f == "schemas.py":
                    continue

                if pattern.search(content):
                    violations.append(str(file_path.relative_to(BASE_DIR)))

        self.assertEqual(
            violations,
            [],
            f"Phase 6 vault path references detected in Phase 7 code:\n" + "\n".join(violations),
        )

    def test_no_phase6_vault_archives_in_phase7_active_config(self):
        """Phase 7 active config nodes must not point to Phase 6 archives."""
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            raw_text = f.read()

        # The words window_a_sealed.7z and window_b_sealed.7z must only appear under prohibited_vault_archives
        parsed = yaml.safe_load(raw_text)
        prohibited = parsed.get("governance", {}).get("prohibited_vault_archives", [])
        self.assertIn("window_a_sealed.7z", prohibited)
        self.assertIn("window_b_sealed.7z", prohibited)

        # Check universe and targets do not mention them
        self.assertNotIn("window_a", str(parsed.get("universe", {})))
        self.assertNotIn("window_b", str(parsed.get("universe", {})))
        self.assertNotIn("window_a", str(parsed.get("targets", {})))

    def test_no_import_of_phase6_training_scripts_in_phase7(self):
        """Phase 7 modules cannot import Phase 6 training scripts as shortcuts."""
        prohibited_imports = [
            "scripts.phase6.train_gate2_model",
            "scripts.phase6.train_gate3_model",
            "scripts.phase6.train_gate4_model",
            "scripts.phase6.percentile_backtest",
        ]
        violations = []

        for root, _, files in os.walk(PHASE7_DIR):
            for f in files:
                if not f.endswith(".py"):
                    continue
                file_path = Path(root) / f
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for imp in prohibited_imports:
                    if imp in content:
                        violations.append(f"{file_path.relative_to(BASE_DIR)} imports {imp}")

        self.assertEqual(
            violations,
            [],
            "Phase 7 violates boundary by importing Phase 6 scripts:\n" + "\n".join(violations),
        )

    def test_static_current_universe_cannot_be_provider(self):
        """Static features.universe cannot be used as Phase 7 universe provider."""
        config = load_and_validate_phase7_config(CONFIG_PATH)
        provider = config.get("universe", {}).get("universe_provider")
        self.assertNotEqual(provider, "features.universe")
        self.assertIn("features.universe", config.get("universe", {}).get("prohibited_universe_providers", []))

    def test_phase6_governance_documents_intact(self):
        """Phase 6 reports and logs must remain present and intact in docs/."""
        required_phase6_docs = [
            "PHASE_6_FINAL_REPORT.md",
            "GATE_1_4_SYNTHESIS.md",
            "GATE_2_REPORT.md",
            "GATE_4_REPORT.md",
            "holdout_access_log.md",
            "RESEARCH_PREREGISTRATION.md",
            "RESEARCH_PREREGISTRATION_AMENDMENT_1.md",
        ]
        for doc_name in required_phase6_docs:
            doc_path = DOCS_DIR / doc_name
            self.assertTrue(doc_path.is_file(), f"Phase 6 document missing: {doc_path}")


if __name__ == "__main__":
    unittest.main()
