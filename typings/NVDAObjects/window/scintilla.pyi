from typing import Any
from NVDAObjects.window import Window
from textInfos import TextInfo, FormatField

class ScintillaTextInfo(TextInfo):
    obj: Window
    _startOffset: int
    _endOffset: int
    def _getFormatFieldAndOffsets(
        self, offset: int, formatConfig: dict[str, Any], calculateOffsets: bool = True
    ) -> tuple[FormatField, tuple[int, int]]: ...
    def _getLineOffsets(self, offset: int) -> tuple[int, int]: ...
    def _getCharacterOffsets(self, offset: int) -> tuple[int, int]: ...
    def _getStoryLength(self) -> int: ...
    def _getTextRange(self, start: int, end: int) -> str: ...

class Scintilla(Window):
    TextInfo: type[ScintillaTextInfo]
