"""Inform-only Scintilla formatting and private speech boundary fields."""

from __future__ import annotations

from typing import Any, Self, TYPE_CHECKING, override, cast

if TYPE_CHECKING:
    from speech.commands import SpeechCommand
    from .syntax import SyntaxStack, SyntaxEvent


import colors
import config
import controlTypes
import textInfos
import watchdog
from logHandler import log
from NVDAObjects.window.scintilla import Scintilla, ScintillaTextInfo

from . import _, syntaxEnabled
from .syntax import renderMarker, stackEvents, styleStack


SYNTAX_FIELD = "_inform7SyntaxBoundaries"
SCI_GETSTYLEAT = 2010
SCI_GETCHARAT = 2007
SCI_STYLEGETSIZE = 2485
SCI_STYLEGETFORE = 2481
SCI_STYLEGETBACK = 2482


class InformSourceTextInfo(ScintillaTextInfo):
    _syntaxReadingUnit: str | None = None

    @override
    def expand(self, unit: str) -> None:
        super().expand(unit)
        self._syntaxReadingUnit = unit

    @override
    def copy(self) -> Self:
        info = super().copy()
        info._syntaxReadingUnit = getattr(self, "_syntaxReadingUnit", None)
        return info

    def _send(self, message: int, value: int = 0) -> int:
        return watchdog.cancellableSendMessage(self.obj.windowHandle, message, value, 0)

    @override
    def _getFormatFieldAndOffsets(
        self,
        offset: int,
        formatConfig: dict[str, Any],
        calculateOffsets: bool = True,
    ) -> tuple[textInfos.FormatField, tuple[int, int]]:
        # Inherit NVDA's attributes without its whole-line byte-by-byte style scan.
        field, offsets = super()._getFormatFieldAndOffsets(
            offset,
            formatConfig,
            calculateOffsets=False,
        )
        style = self._send(SCI_GETSTYLEAT, offset)
        if calculateOffsets:
            lineEnd = self._getLineOffsets(offset)[1]
            limit = min(lineEnd, self._endOffset)
            end = self._getCharacterOffsets(offset)[1]
            while end < limit and self._send(SCI_GETSTYLEAT, end) == style:
                nextEnd = self._getCharacterOffsets(end)[1]
                if nextEnd <= end:
                    raise ValueError("Invalid Scintilla formatting boundary")
                end = nextEnd
            offsets = (offset, end)
        if formatConfig.get("reportFontSize"):
            # Inform stores tenths of points in the otherwise integral size query.
            size = self._send(SCI_STYLEGETSIZE, style) / 10
            field["font-size"] = _("%s pt") % f"{size:g}"
        if formatConfig.get("reportColor"):
            field["color"] = colors.RGB.fromCOLORREF(
                self._send(SCI_STYLEGETFORE, style),
            )
            field["background-color"] = colors.RGB.fromCOLORREF(
                self._send(SCI_STYLEGETBACK, style),
            )
        return field, offsets

    def _syntaxEvents(self) -> dict[int, list[SyntaxEvent]]:
        """Map character indices in this range to events, using native byte offsets.

        Only the requested range and its immediate neighbours are queried. Nothing
        is cached across reads, so edits, repeated reads and profile switches work.
        """
        start, end = self._startOffset, self._endOffset
        length = self._getStoryLength()
        if start >= end or start >= length:
            return {}
        end = min(end, length)
        styles: dict[int, SyntaxStack] = {}

        def stack(offset: int) -> SyntaxStack:
            if offset < 0:
                return ()
            if offset not in styles:
                styles[offset] = styleStack(self._send(SCI_GETSTYLEAT, offset))
            return styles[offset]

        def previous(offset: int) -> int:
            return self._getCharacterOffsets(offset - 1)[0] if offset > 0 else -1

        def char(offset: int) -> str:
            return self._getTextRange(offset, self._getCharacterOffsets(offset)[1]) if offset >= 0 else ""

        result: dict[int, list[SyntaxEvent]] = {}
        pos, index = start, 0
        prev = previous(start)
        before = stack(prev)
        while pos <= end:
            if pos < length:
                after = stack(pos)
            else:
                # No next style at EOF. Close only syntax with a real terminator.
                after = before
                last = char(prev)
                if before and before[-1] == "heading":
                    after = ()
                elif before and before[-1] in ("comment", "text substitution") and last == "]":
                    after = before[:-1]
                elif before and before[0] == "quoted text" and last in ('"', "\u201c", "\u201d"):
                    # A lone opening quote at EOF is unfinished, even with a smart quote.
                    prior = stack(previous(prev))
                    if prior and prior[0] == "quoted text":
                        after = ()
                elif before == ("Inform 6 code",) and last == ")" and char(previous(prev)) == "-":
                    after = ()
            events: list[SyntaxEvent] = stackEvents(before, after)
            # Adjacent siblings can share a style, concealing their transition.
            if before == after and before and pos < length and prev >= 0:
                kind = before[-1]
                if kind in ("comment", "text substitution"):
                    if self._send(SCI_GETCHARAT, prev) == ord("]") and self._send(SCI_GETCHARAT, pos) == ord(
                        "[",
                    ):
                        events = [("end", kind), ("begin", kind)]
                elif kind == "Inform 6 code" and self._send(SCI_GETCHARAT, prev) == ord(")"):
                    if (
                        char(previous(prev)) == "-"
                        and pos + 1 < length
                        and self._send(SCI_GETCHARAT, pos) == ord("(")
                        and self._send(SCI_GETCHARAT, pos + 1) == ord("-")
                    ):
                        events = [("end", kind), ("begin", kind)]
            events = [
                event
                for event in events
                if (event[0] == "end" and start < pos <= end) or (event[0] == "begin" and start <= pos < end)
            ]
            if events:
                result[index] = events
            if pos == end:
                break
            prev, before = pos, after
            nextPos = self._getCharacterOffsets(pos)[1]
            if nextPos <= pos or nextPos > end:
                raise ValueError("Invalid Scintilla character boundary")
            pos = nextPos
            index += 1
        return result

    @override
    def getTextWithFields(
        self,
        formatConfig: dict[str, Any] | None = None,
    ) -> list[str | textInfos.FieldCommand]:
        formatConfig = formatConfig or cast(dict[str, Any], config.conf["documentFormatting"])
        ordinary = super().getTextWithFields(formatConfig)
        if not syntaxEnabled():
            return ordinary
        # A trailing formatChange prevents NVDA from using its character-spelling
        # path, even if getFormatFieldSpeech returns no speech for that field.
        # extraDetail alone cannot distinguish word from character navigation.
        unit = getattr(self, "_syntaxReadingUnit", None)
        if unit == textInfos.UNIT_CHARACTER or (
            unit != textInfos.UNIT_WORD
            and formatConfig.get("extraDetail")
            and len("".join(item for item in ordinary if isinstance(item, str))) == 1
        ):
            return ordinary
        try:
            events = self._syntaxEvents()
            if not events:
                return ordinary
            result: list[str | textInfos.FieldCommand] = []
            active = textInfos.FormatField()
            index = 0
            for item in ordinary:
                if not isinstance(item, str):
                    if item.command == "formatChange":
                        active = textInfos.FormatField(item.field or {})
                    result.append(item)
                    continue
                stop = index + len(item)
                cursor = index
                for boundary in sorted(p for p in events if index <= p < stop):
                    if boundary > cursor:
                        result.append(item[cursor - index : boundary - index])
                    field = textInfos.FormatField(active)
                    field[SYNTAX_FIELD] = tuple(events.pop(boundary))
                    result.append(
                        textInfos.FieldCommand(
                            "formatChange",
                            field,
                        ),
                    )
                    cursor = boundary
                result.append(item[cursor - index :])
                index = stop
            if index in events:
                field = textInfos.FormatField(active)
                field[SYNTAX_FIELD] = tuple(events.pop(index))
                result.append(textInfos.FieldCommand("formatChange", field))
            if events:
                raise ValueError("Scintilla text and style range mismatch")
            return result
        except Exception:
            # Do not include exception text: it might contain source-code contents.
            log.warning(
                "Inform 7 Access: syntax extraction failed; using ordinary reading",
            )
            return ordinary

    @override
    def getFormatFieldSpeech(
        self,
        attrs: textInfos.Field,
        attrsCache: textInfos.Field | None = None,
        formatConfig: dict[str, bool] | None = None,
        reason: controlTypes.OutputReason | None = None,
        unit: str | None = None,
        extraDetail: bool = False,
        initialFormat: bool = False,
    ) -> list[str | SpeechCommand]:
        # Keep the private events out of NVDA's persistent formatting cache.
        ordinary = textInfos.FormatField(
            {key: value for key, value in attrs.items() if key != SYNTAX_FIELD},
        )
        sequence = super().getFormatFieldSpeech(
            ordinary,
            attrsCache,
            formatConfig,
            reason,
            unit,
            extraDetail,
            initialFormat,
        )
        if (
            syntaxEnabled()
            and (not extraDetail or unit == textInfos.UNIT_WORD)
            and unit != textInfos.UNIT_CHARACTER
            and (
                unit
                in (
                    textInfos.UNIT_WORD,
                    textInfos.UNIT_LINE,
                    textInfos.UNIT_PARAGRAPH,
                    textInfos.UNIT_READINGCHUNK,
                )
                or reason == controlTypes.OutputReason.SAYALL
            )
        ):
            for event in attrs.get(SYNTAX_FIELD, ()):
                sequence.extend(renderMarker(event))
        return sequence


class InformSourceEditor(Scintilla):
    TextInfo = InformSourceTextInfo
