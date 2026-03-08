"""Custom errors for pipeline stages."""


class ComicAgentError(Exception):
    """Base class for pipeline exceptions."""


class StageError(ComicAgentError):
    """Error tied to a specific manager stage."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(f"[{stage}] {message}")
        self.stage = stage


class ValidationFailedError(ComicAgentError):
    """Raised when output does not pass validation after retries."""
