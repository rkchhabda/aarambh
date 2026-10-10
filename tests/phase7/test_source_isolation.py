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


def test_no_target_generation_or_model_training_in_sources():
    """Verify phase7.sources contains no model training, target generation, or financial metric logic."""
    sources_dir = Path(__file__).resolve().parent.parent.parent / "phase7" / "sources"
    forbidden_terms = [
        "target_engine",
        "rank_ic",
        "sharpe",
        "sortino",
        "drawdown",
        "train_model",
        "fit(",
        "cross_val",
        "lightgbm",
        "xgboost",
        "catboost",
        "sklearn",
    ]
    for py_file in sources_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8").lower()
        for term in forbidden_terms:
            assert term not in content, f"Forbidden modeling/performance term '{term}' found in {py_file}"


def test_no_repository_data_writes_in_sources():
    """Verify phase7.sources never hardcodes writes to repository data/ directory."""
    sources_dir = Path(__file__).resolve().parent.parent.parent / "phase7" / "sources"
    forbidden_patterns = [
        'Path("data/")',
        "Path('data/')",
        'Path("data")',
        "Path('data')",
        '"./data"',
        "'./data'",
    ]
    for py_file in sources_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for pat in forbidden_patterns:
            assert pat not in content, f"Forbidden repository data path pattern '{pat}' found in {py_file}"


def test_no_reusable_authorization_tokens_in_sources():
    """Verify phase7.sources contains zero reusable authorization phrases, CLI options, or secrets."""
    sources_dir = Path(__file__).resolve().parent.parent.parent / "phase7" / "sources"
    forbidden_tokens = [
        "owner-authorization",
        "owner_authorization",
        "AUTHORIZE MILESTONE",
        "password",
        "api_key",
        "bearer",
        "cookie",
    ]
    for py_file in sources_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8").lower()
        for ft in forbidden_tokens:
            assert ft.lower() not in content, f"Forbidden token/phrase '{ft}' found in {py_file}"
