import logging
from typing import Any

class Logger(logging.Logger):
    def debugWarning(self, msg: str, *args: object, **kwargs: Any) -> None: ...

log: Logger
