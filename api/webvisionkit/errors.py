from __future__ import annotations


class RecoverableStreamError(RuntimeError):
    pass


class FatalStreamError(RuntimeError):
    pass


class ChromeProbeError(RecoverableStreamError):
    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


class TargetClosedError(RecoverableStreamError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Chrome detached the target: {reason}")
        self.reason = reason
