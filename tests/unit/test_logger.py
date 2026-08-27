"""Unit tests for PULSE centralized structured logging utility (src/utils/logger.py).

Verifies logger instantiation, formatting, file handlers, headline separators, and log spacers.

Authority: Phase 7 Decision D-11, Workflow Stage 3.
"""

import logging
from pathlib import Path

from src.utils.logger import get_logger, log_spacer


def test_get_logger_default() -> None:
    """Verify get_logger returns a configured logger instance with INFO level."""
    logger = get_logger()
    assert logger.name == "PULSE"
    assert logger.level == logging.INFO
    assert len(logger.handlers) >= 2


def test_get_logger_custom_name() -> None:
    """Verify get_logger returns a named logger."""
    logger = get_logger("pulse.test_module")
    assert logger.name == "pulse.test_module"
    assert logger.level == logging.INFO


def test_get_logger_with_headline(tmp_path: Path, monkeypatch) -> None:
    """Verify get_logger writes headline banner to the log file when supplied."""
    test_log_file = tmp_path / "logs" / "test_pulse.log"
    monkeypatch.setattr("src.utils.logger.LOG_FILE", test_log_file)

    logger = get_logger("pulse.headline_test", headline="TEST_EXPERIMENT")
    logger.info("Executing test message under headline")

    assert test_log_file.exists()
    content = test_log_file.read_text(encoding="utf-8")
    assert "START: TEST_EXPERIMENT" in content
    assert "Executing test message under headline" in content


def test_log_spacer(tmp_path: Path, monkeypatch) -> None:
    """Verify log_spacer appends newline spacing to the log file."""
    test_log_file = tmp_path / "logs" / "test_spacer.log"
    monkeypatch.setattr("src.utils.logger.LOG_FILE", test_log_file)

    test_log_file.parent.mkdir(parents=True, exist_ok=True)
    test_log_file.write_text("INITIAL_CONTENT", encoding="utf-8")

    log_spacer()
    content = test_log_file.read_text(encoding="utf-8")
    assert content.endswith("\n")
