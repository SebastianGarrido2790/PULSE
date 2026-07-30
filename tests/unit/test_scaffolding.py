"""Unit test verifying Phase 1 scaffolding baseline configuration."""

from pathlib import Path


def test_project_structure_baseline():
    """Verify core directories and configuration files exist."""
    project_root = Path(__file__).resolve().parents[2]

    assert (project_root / "pyproject.toml").exists()
    assert (project_root / "pyrightconfig.json").exists()
    assert (project_root / "params.yaml").exists()
    assert (project_root / "dvc.yaml").exists()
    assert (project_root / "scripts" / "check_file_size.py").exists()
    assert (project_root / "src" / "utils" / "logger.py").exists()
