"""The conversion engine. Nothing in here depends on the GUI."""

from chameleon.core.engine import MAX_WORKERS, ConversionJob, default_workers, plan_tasks
from chameleon.core.errors import OperationCancelled
from chameleon.core.models import (
    ConvertOptions,
    ExistingFiles,
    FileError,
    JobResult,
    OutputFormat,
    Phase,
    ProgressSnapshot,
)

__all__ = [
    "MAX_WORKERS",
    "ConversionJob",
    "ConvertOptions",
    "ExistingFiles",
    "FileError",
    "JobResult",
    "OperationCancelled",
    "OutputFormat",
    "Phase",
    "ProgressSnapshot",
    "default_workers",
    "plan_tasks",
]
