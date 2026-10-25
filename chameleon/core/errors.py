"""Exceptions used by the engine."""


class OperationCancelled(Exception):
    """Raised inside the engine when the user asked the job to stop."""
