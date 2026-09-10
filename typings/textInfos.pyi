from typing import Any, Self
from controlTypes import OutputReason
from speech.commands import SpeechCommand

UNIT_CHARACTER: str
UNIT_WORD: str
UNIT_LINE: str
UNIT_PARAGRAPH: str
UNIT_READINGCHUNK: str

class Field(dict[str, Any]): ...
class FormatField(Field): ...
class ControlField(Field): ...

class FieldCommand:
    command: str
    field: ControlField | FormatField | None
    def __init__(self, command: str, field: ControlField | FormatField | None) -> None: ...

class TextInfo:
    def expand(self, unit: str) -> None: ...
    def copy(self) -> Self: ...
    def getTextWithFields(self, formatConfig: dict[str, Any] | None = None) -> list[str | FieldCommand]: ...
    def getFormatFieldSpeech(
        self,
        attrs: Field,
        attrsCache: Field | None = None,
        formatConfig: dict[str, bool] | None = None,
        reason: OutputReason | None = None,
        unit: str | None = None,
        extraDetail: bool = False,
        initialFormat: bool = False,
    ) -> list[str | SpeechCommand]: ...
