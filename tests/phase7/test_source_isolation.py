"""Architectural isolation and governance boundary safeguards for phase7.sources."""

import ast
from pathlib import Path
import pytest

FORBIDDEN_IMPORTS = {
    "features.data_provider",
    "features.universe",
    "scripts.phase6",
    "service",
    "connector_review",
}

FORBIDDEN_KEYWORDS = [
    "vault",
    "window_a_sealed",
    "window_b_sealed",
    "v6.0-sealed",
]


def test_sources_modules_have_no_forbidden_imports():
    """Verify that phase7.sources never imports production, feature, or Phase 6 modules."""
    sources_dir = Path(__file__).resolve().parent.parent.parent / "phase7" / "sources"
    assert sources_dir.exists()

    for py_file in sources_dir.glob("*.py"):
        with open(py_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(py_file))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for forbidden in FORBIDDEN_IMPORTS:
                        assert not alias.name.startswith(forbidden), (
                            f"Forbidden import '{alias.name}' detected in {py_file}"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for forbidden in FORBIDDEN_IMPORTS:
                        assert not node.module.startswith(forbidden), (
                            f"Forbidden from-import '{node.module}' detected in {py_file}"
                        )


def test_sources_modules_have_no_vault_references():
    """Verify zero Phase 6 holdout vault or sealed archive references."""
    sources_dir = Path(__file__).resolve().parent.parent.parent / "phase7" / "sources"
    for py_file in sources_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8").lower()
        for kw in FORBIDDEN_KEYWORDS:
            assert kw not in content, f"Forbidden keyword '{kw}' found in {py_file}"


def test_no_top_level_nse_import():
    """Verify that 'nse' is never imported at module top-level across phase7.sources."""
    sources_dir = Path(__file__).resolve().parent.parent.parent / "phase7" / "sources"
    for py_file in sources_dir.glob("*.py"):
        with open(py_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(py_file))

        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "nse", f"Top-level import 'nse' found in {py_file}"
            elif isinstance(node, ast.ImportFrom):
                assert node.module != "nse", f"Top-level 'from nse' found in {py_file}"
