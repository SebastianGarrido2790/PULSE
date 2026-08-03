"""Custom exception hierarchy for the PULSE Engine.

All custom exceptions inherit from BasePulseException (or PulseException) to ensure
consistent error handling and precise traceback logging across the MLOps pipeline
and deterministic Markov solver.
"""

from pathlib import Path
from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def error_message_detail(error: Exception | str, error_detail: ModuleType) -> str:
    """Extracts detailed error message including relative file name and line number.

    Args:
        error: The exception or error message string.
        error_detail: The sys module containing execution context.

    Returns:
        Formatted error message string.
    """
    _, _, exc_tb = error_detail.exc_info()

    if exc_tb is not None and exc_tb.tb_frame is not None:
        file_name = exc_tb.tb_frame.f_code.co_filename
        line_number = exc_tb.tb_lineno
    else:
        file_name = "unknown"
        line_number = 0

    if file_name != "unknown":
        file_path = Path(file_name)
        try:
            display_path = str(file_path.relative_to(PROJECT_ROOT))
        except (ValueError, TypeError):
            display_path = str(file_path)
    else:
        display_path = "unknown"

    return f"Error occurred in script [{display_path}] line [{line_number}]: {error!s}"


class BasePulseException(Exception):
    """Base exception class for all PULSE engine errors."""

    def __init__(self, error_message: Exception | str, error_detail: ModuleType | None = None):
        """Initialize BasePulseException.

        Args:
            error_message: The original error message or exception object.
            error_detail: Optional sys module to capture stack trace details.
        """
        if error_detail is not None:
            self.detailed_message = error_message_detail(error_message, error_detail)
        else:
            self.detailed_message = str(error_message)
        super().__init__(self.detailed_message)

    def __str__(self) -> str:
        return self.detailed_message


# Backward compatibility alias
PulseException = BasePulseException
CustomException = BasePulseException


class SolverException(BasePulseException):
    """Raised when the closed-form Markov solver encounters mathematical or convergence errors."""


class SufficiencyGateException(BasePulseException):
    """Raised when an operation violates data sufficiency thresholds."""


class InvalidMatchStateError(BasePulseException):
    """Raised when match score or state transitions are invalid."""


class ModelInferenceError(BasePulseException):
    """Raised when point-win or pressure models fail during inference."""


class SanitizationError(BasePulseException):
    """Raised when prompt input fails security sanitization checks."""


class IngestionException(BasePulseException):
    """Raised when raw data ingestion or schema validation fails."""
