# Inform 7 Access: automatic announcements for the embedded interpreter.

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Literal, Protocol, TYPE_CHECKING, override, cast

if TYPE_CHECKING:
	from NVDAObjects import NVDAObject
	from NVDAObjects.IAccessible import IAccessible

import weakref
import threading
import re

import api
import appModuleHandler
import config
import controlTypes
import winUser
import wx
import ui
from logHandler import log
from NVDAObjects.IAccessible import getNVDAObjectFromEvent
from NVDAObjects.behaviors import LiveText
from scriptHandler import script
from appModules.inform7Support import _
from appModules.inform7Support.compileFocus import CompileFocusController, InformDocument
from NVDAObjects.IAccessible.chromium import Document

LineAction = Literal["first", "last", "previous", "current", "next"]


class SendableGesture(Protocol):
	def send(self) -> None: ...


POLL_INTERVAL_MS = 250


class LineReadingCursor:
	"""A logical line index, independent of NVDA review and the editing caret."""

	def __init__(self) -> None:
		self.index: int | None = None

	def read(self, text: str, action: LineAction) -> str:
		lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
		last = len(lines) - 1
		if self.index is None:
			self.index = last
		boundary = ""
		# A cleared/shortened transcript must never leave an invalid position.
		if self.index > last:
			self.index = last
			boundary = "Bottom"
		if action == "first":
			target = 0
			boundary = ""
		elif action == "last":
			target = last
			boundary = ""
		else:
			target = (
				self.index
				+ {
					"previous": -1,
					"current": 0,
					"next": 1,
				}[action]
			)
		if target < 0:
			boundary = "Top"
		elif target > last:
			boundary = "Bottom"
		self.index = min(max(target, 0), last)
		line = lines[self.index].strip() or "blank"
		return f"{boundary}, {line}" if boundary else line


def formatStatusText(text: str) -> str:
	"""Turn the grid's column padding into pauses, keeping each field intact."""
	return ", ".join(
		field.strip()
		for line in text.splitlines()
		for field in re.split(r"\s{2,}", line.strip())
		if field.strip()
	)


def chooseStoryStatus(
	interpreters: Sequence[IAccessible],
	candidates: Sequence[IAccessible],
	preferredHandle: int | None = None,
) -> IAccessible | None:
	"""Match a short status grid just above a visible interpreter, by geometry."""
	matches: list[tuple[tuple[bool, int, int, int], IAccessible]] = []
	for interpreter in interpreters:
		if interpreter.location is None:
			continue
		x, y, width, height = interpreter.location
		if width <= 0 or height <= 0:
			continue
		for candidate in candidates:
			if candidate.location is None:
				continue
			left, top, gridWidth, gridHeight = candidate.location
			gap = y - (top + gridHeight)
			if (
				0 < gridHeight <= min(120, height / 3)
				and abs(left - x) <= max(8, width * 0.05)
				and abs(gridWidth - width) <= max(24, width * 0.15)
				and -2 <= gap <= max(12, gridHeight * 2)
			):
				# Prefer the focused/last-used interpreter; otherwise the right
				# pane requested by the user. Never choose a whole container pane.
				score = (
					interpreter.windowHandle != preferredHandle,
					-x,
					abs(gap),
					abs(left - x),
				)
				matches.append((score, candidate))
	return min(matches, key=lambda match: match[0])[1] if matches else None


def accountForTypedText(oldText: str, newText: str, pending: str) -> tuple[str, str]:
	"""Put confirmed keyboard insertions in the diff baseline, preserving output.

	Returns the adjusted old text and any characters not yet seen in the window.
	No prompt strings, minimum output lengths, or typing-speed thresholds are used.
	"""
	if not pending or newText == oldText:
		return oldText, pending
	if newText.startswith(oldText):
		start = len(oldText)
	else:
		start = 0
		for before, after in zip(oldText, newText):
			if before != after:
				break
			start += 1
	oldEnd, newEnd = len(oldText), len(newText)
	while oldEnd > start and newEnd > start and oldText[oldEnd - 1] == newText[newEnd - 1]:
		oldEnd -= 1
		newEnd -= 1
	inserted = newText[start:newEnd]
	if not inserted or not (inserted.startswith(pending) or pending.startswith(inserted)):
		# A deletion, replacement, or unrelated output invalidates stale input.
		return oldText, ""
	count = min(len(inserted), len(pending))
	baseline = oldText[:start] + inserted[:count] + oldText[oldEnd:]
	# Replacements can reuse an equal suffix from the old selection. Do not
	# leave those already-entered characters waiting to suppress later output.
	remaining = (
		pending[count:]
		if count
		== len(
			inserted,
		)
		and oldEnd == start
		else ""
	)
	return baseline, remaining


def isInterpreterCandidate(obj: NVDAObject) -> bool:
	"""Provisional match until we have stable parent-window information."""
	return (
		(getattr(obj, "windowClassName", "") or "").upper() == "RICHEDIT50W"
		and obj.role == controlTypes.Role.EDITABLETEXT
		# During overlay selection, EditBase has not yet added MULTILINE to
		# obj.states. The native window style is available at this stage.
		and bool(getattr(obj, "windowStyle", 0) & winUser.ES_MULTILINE)
		and getattr(obj, "IAccessibleChildID", None) == 0
	)


def describeObject(obj: object | None) -> str:
	"""Log identification fields without reading the story or invoking TextInfo."""
	if obj is None:
		return "None"
	fields: list[str] = []
	for name in ("processID", "windowHandle", "windowClassName", "windowStyle", "IAccessibleChildID", "role"):
		try:
			value = getattr(obj, name, None)
		except Exception:
			value = "unavailable"
		fields.append(f"{name}={value!r}")
	fields.append(f"pythonClass={type(obj).__name__}")
	return ", ".join(fields)


class InterpreterOutput(LiveText):
	"""Keep Rich Edit navigation, adding NVDA's normal live-text reporting."""

	if TYPE_CHECKING:
		# Supplied by the Rich Edit Window overlay in NVDA's dynamic MRO.
		windowHandle: int
		_get_windowText: Callable[[], str]
		_lastReadText: str | None

	# NVDA initializes each overlay separately; this hook must not call super.
	@override
	def initOverlayClass(self) -> None:
		self._inputLock = threading.RLock()
		self._pendingTypedText = ""
		self._submittedBaseline: str | None = None
		self._preparedDiff: tuple[str, str] | None = None

	def _readTranscriptLine(self, gesture: SendableGesture, action: LineAction) -> None:
		if api.getFocusObject() is not self:
			gesture.send()
			return
		try:
			# Read the actual window afresh without touching LiveText's baseline,
			# review position, selection, or caret. Keep position across NVDA
			# object recreation and focus changes, separately for each pane.
			text = self._get_windowText()
			cursors = cast(AppModule, self.appModule)._lineReadingCursors  # pyright: ignore[reportPrivateUsage]
			cursor = cursors.setdefault(self.windowHandle, LineReadingCursor())
			ui.message(cursor.read(text, action))
		except Exception:
			log.exception("Inform 7 Access: unable to read interpreter line")
			ui.message(
				"Unable to read the interpreter text. See the NVDA log for details.",
			)

	@script(
		description="Read the previous interpreter line using the independent reading cursor.",
		category="Inform 7 Access",
		gesture="kb:control+shift+u",
		speakOnDemand=True,
	)
	def script_readPreviousLine(self, gesture: SendableGesture) -> None:
		self._readTranscriptLine(gesture, "previous")

	@script(
		description="Read or reread the current interpreter line using the independent reading cursor.",
		category="Inform 7 Access",
		gesture="kb:control+shift+i",
		speakOnDemand=True,
	)
	def script_readCurrentLine(self, gesture: SendableGesture) -> None:
		self._readTranscriptLine(gesture, "current")

	@script(
		description="Read the next interpreter line using the independent reading cursor.",
		category="Inform 7 Access",
		gesture="kb:control+shift+o",
		speakOnDemand=True,
	)
	def script_readNextLine(self, gesture: SendableGesture) -> None:
		self._readTranscriptLine(gesture, "next")

	@script(
		description="Jump to the last interpreter line and read it.",
		category="Inform 7 Access",
		gesture="kb:control+shift+n",
		speakOnDemand=True,
	)
	def script_readLastLine(self, gesture: SendableGesture) -> None:
		self._readTranscriptLine(gesture, "last")

	@script(
		description="Jump to the first interpreter line and read it.",
		category="Inform 7 Access",
		gesture="kb:control+shift+y",
		speakOnDemand=True,
	)
	def script_readFirstLine(self, gesture: SendableGesture) -> None:
		self._readTranscriptLine(gesture, "first")

	@override
	def startMonitoring(self) -> None:
		if not self._keepMonitoring:
			self._lastReadText = None
			with self._inputLock:
				self._pendingTypedText = ""
				self._submittedBaseline = None
				self._preparedDiff = None
		super().startMonitoring()

	@override
	def event_typedCharacter(self, ch: str) -> None:
		# These events are delivered even when NVDA typing echo is disabled.
		if ch.isprintable():
			with self._inputLock:
				self._pendingTypedText += ch
		super().event_typedCharacter(ch)

	@script(gestures=["kb:enter", "kb:numpadEnter"])
	def script_submitCommand(self, gesture: SendableGesture) -> None:
		try:
			# Capture a fast command before Enter can produce a response, even
			# if the polling thread has not observed the final typed characters.
			with self._inputLock:
				snapshot = self._get_windowText().replace("\r\n", "\n").replace("\r", "\n")
				previous = getattr(self, "_lastReadText", None)
				if previous is not None:
					baseline, _ = accountForTypedText(
						previous,
						snapshot,
						self._pendingTypedText,
					)
					if baseline == snapshot:
						self._submittedBaseline = snapshot
						self._pendingTypedText = ""
		except Exception:
			log.exception(
				"Inform 7 Access: unable to capture submitted command",
			)
		finally:
			gesture.send()

	@override
	def _getText(self) -> str:
		# Call the getter directly: the polling thread must not reuse a cached
		# NVDAObject property. This uses cancellable WM_GETTEXT messages and
		# avoids the ITextDocument interface which failed in the supplied log.
		with self._inputLock:
			text = self._get_windowText().replace("\r\n", "\n").replace("\r", "\n")
			previous = getattr(self, "_lastReadText", None)
			baseline = previous
			if self._submittedBaseline is not None:
				if text.startswith(self._submittedBaseline):
					baseline = self._submittedBaseline
				self._submittedBaseline = None
			if baseline is not None:
				beforeFiltering = baseline
				baseline, self._pendingTypedText = accountForTypedText(
					baseline,
					text,
					self._pendingTypedText,
				)
				self._preparedDiff = (text, baseline)
				if baseline != beforeFiltering:
					log.debug(
						"Inform 7 Access: typed input excluded from output diff; window=%s",
						self.windowHandle,
					)
			else:
				self._pendingTypedText = ""
			self._lastReadText = text
		if previous is None:
			log.debug(
				"Inform 7 Access: initial text read; window=%s, characters=%s",
				self.windowHandle,
				len(
					text,
				),
			)
		elif text != previous:
			log.debug(
				"Inform 7 Access: text changed; window=%s, characters=%s -> %s",
				self.windowHandle,
				len(previous),
				len(text),
			)
		return text

	@override
	def _calculateNewText(self, newText: str, oldText: str) -> list[str]:
		# _getText runs even when reporting is off, keeping input tracking in
		# sync without accumulating stale keystrokes for the next enable.
		with self._inputLock:
			prepared = self._preparedDiff
			if prepared is not None and prepared[0] == newText:
				oldText = prepared[1]
		return super()._calculateNewText(newText, oldText)

	@override
	def _reportNewLines(self, lines: list[str]) -> None:
		# A report can be queued just before focus changes or NVDA+D is used.
		if (
			self._keepMonitoring
			and api.getFocusObject() is self
			and config.conf["presentation"]["reportDynamicContentChanges"]
		):
			log.debug(
				"Inform 7 Access: reporting %s new lines; window=%s",
				len(lines),
				self.windowHandle,
			)
			super()._reportNewLines(lines)
		else:
			log.debug(
				"Inform 7 Access: queued report suppressed; monitoring=%s, focused=%s, dynamicReporting=%s",
				self._keepMonitoring,
				api.getFocusObject() is self,
				config.conf["presentation"]["reportDynamicContentChanges"],
			)

	@override
	def _reportNewText(self, line: str) -> None:
		# Recent NVDA releases yield while reporting large batches of lines.
		if (
			self._keepMonitoring
			and api.getFocusObject() is self
			and config.conf["presentation"]["reportDynamicContentChanges"]
		):
			super()._reportNewText(line)

	@override
	def event_textChange(self) -> None:
		# Preserve Rich Edit's selection-change tracking as well as LiveText.
		super().event_textChange()
		self.hasContentChangedSinceLastSelection = True


class AppModule(appModuleHandler.AppModule):
	def __init__(self, *args: Any, **kwargs: Any) -> None:
		super().__init__(*args, **kwargs)
		self._output: InterpreterOutput | None = None
		self._terminated = False
		self._lastFocusStatus: tuple[bool, int | None, bool | None] | None = None
		self._lastInterpreterHandle: int | None = None
		self._statusUnavailableObject: NVDAObject | None = None
		self._lineReadingCursors: dict[int, LineReadingCursor] = {}
		self.compileFocus = CompileFocusController(self.processID, isInterpreterCandidate)
		# Keep only a weak reference in the timer callback.
		moduleRef = weakref.ref(self)

		def poll() -> None:
			module = moduleRef()
			if module is not None:
				module._poll()

		self._timer = wx.PyTimer(poll)
		_ = self._timer.Start(POLL_INTERVAL_MS)
		log.debug(
			"Inform 7 Access: module loaded; processID=%s, file=%s, pollInterval=%sms",
			self.processID,
			__file__,
			POLL_INTERVAL_MS,
		)

	@override
	def chooseNVDAObjectOverlayClasses(self, obj: NVDAObject, clsList: list[type[NVDAObject]]) -> None:
		if Document in clsList:
			clsList.insert(0, InformDocument)
		if (
			getattr(obj, "windowClassName", "") == "Scintilla"
			and getattr(obj, "IAccessibleChildID", None) == 0
		):
			from appModules.inform7Support import registerConfig
			from appModules.inform7Support.editor import InformSourceEditor

			registerConfig()
			clsList.insert(0, InformSourceEditor)
			return
		matched = isInterpreterCandidate(obj)
		if (getattr(obj, "windowClassName", "") or "").upper() == "RICHEDIT50W":
			log.debug(
				"Inform 7 Access: overlay selection; matched=%s; %s; proposedClasses=%s",
				matched,
				describeObject(obj),
				", ".join(cls.__name__ for cls in clsList),
			)
		if matched:
			clsList.insert(0, InterpreterOutput)

	def _findStoryStatus(self) -> IAccessible | None:
		root = winUser.getForegroundWindow()
		if not root or winUser.getWindowThreadProcessID(root)[0] != self.processID:
			return None
		# Walk native windows, not the potentially enormous documentation DOM.
		pending = [winUser.getTopWindow(root)]
		seen: set[int] = set()
		interpreters: list[IAccessible] = []
		candidates: list[IAccessible] = []
		while pending and len(seen) < 2000:
			hwnd = pending.pop()
			if not hwnd or hwnd in seen:
				continue
			seen.add(hwnd)
			pending.append(winUser.getWindow(hwnd, winUser.GW_HWNDNEXT))
			if not winUser.isWindowVisible(hwnd):
				continue
			pending.append(winUser.getTopWindow(hwnd))
			className = winUser.getClassName(hwnd)
			isGridClass = re.fullmatch(r"AfxWnd\d+s", className) is not None
			if not isGridClass and className.upper() != "RICHEDIT50W":
				continue
			try:
				obj = getNVDAObjectFromEvent(hwnd, winUser.OBJID_CLIENT, 0)
				if obj is None or obj.processID != self.processID or not obj.location:
					continue
				if {controlTypes.State.INVISIBLE, controlTypes.State.OFFSCREEN} & obj.states:
					continue
				if isInterpreterCandidate(obj):
					interpreters.append(obj)
				elif isGridClass and obj.role == controlTypes.Role.UNKNOWN and obj.IAccessibleChildID == 0:
					candidates.append(obj)
			except Exception:
				log.debugWarning(
					"Inform 7 Access: unable to inspect status candidate",
					exc_info=True,
				)
		focus = api.getFocusObject()
		preferred = getattr(focus, "windowHandle", None)
		if not any(obj.windowHandle == preferred for obj in interpreters):
			preferred = self._lastInterpreterHandle
		status = chooseStoryStatus(interpreters, candidates, preferred)
		log.debug(
			"Inform 7 Access: status lookup; interpreters=%s, grids=%s, selectedWindow=%s",
			len(interpreters),
			len(candidates),
			getattr(status, "windowHandle", None),
		)
		return status

	@override
	def _get_statusBar(self) -> NVDAObject | None:
		focus = api.getFocusObject()
		if not isinstance(focus, InterpreterOutput):
			# Returning the focus object lets getStatusBarText provide guidance
			# without replacing NVDA's native status-bar command.
			self._statusUnavailableObject = focus
			return focus
		self._statusUnavailableObject = None
		try:
			return self._findStoryStatus()
		except Exception:
			log.exception("Inform 7 Access: unable to locate story status line")
			return None

	@override
	def getStatusBarText(self, obj: NVDAObject) -> str:
		if obj is self._statusUnavailableObject:
			return _(
				"The status line is only available in the interpreter window, focus it with CTRL+F3 and try again.",
			)
		try:
			# The supplied grid has empty windowText and accValue. Its display
			# model contains the actual room/time fields; get a fresh read.
			return formatStatusText(cast("IAccessible", obj)._get_displayText())
		except Exception:
			log.exception("Inform 7 Access: unable to read story status line")
			return ""

	@override
	def _get_statusBarTextInfo(self) -> None:
		# A missing Story pane must not fall back to Inform's unrelated IDE
		# status bar through the bottom line of the display model.
		return None

	def _stopMonitoring(self, reason: str = "focus changed") -> None:
		if self._output is not None:
			log.debug(
				"Inform 7 Access: monitoring stopped; window=%s, reason=%s",
				self._output.windowHandle,
				reason,
			)
			self._output.stopMonitoring()
			self._output = None

	def _poll(self) -> None:
		if self._terminated:
			return
		self.compileFocus.poll()
		if self.compileFocus.active and self.compileFocus.transientSince is not None:
			self._stopMonitoring("transient compile focus")
			return
		try:
			obj = api.getFocusObject()
			belongsToApp = obj is not None and obj.appModule is self
			enabled = config.conf["presentation"]["reportDynamicContentChanges"]
			status = (
				belongsToApp,
				id(obj) if belongsToApp else None,
				enabled if belongsToApp else None,
			)
			if status != self._lastFocusStatus:
				self._lastFocusStatus = status
				log.debug(
					"Inform 7 Access: focus check; appFocused=%s, dynamicReporting=%s, overlayActive=%s; %s",
					belongsToApp,
					enabled,
					isinstance(obj, InterpreterOutput),
					describeObject(
						obj,
					)
					if belongsToApp
					else "focus outside this Inform process",
				)
				if (
					belongsToApp
					and obj is not None
					and isInterpreterCandidate(obj)
					and not isinstance(obj, InterpreterOutput)
				):
					log.warning(
						"Inform 7 Access: focused interpreter candidate has no overlay; restart NVDA to recreate it",
					)
			if not isinstance(obj, InterpreterOutput) or not belongsToApp:
				self._stopMonitoring()
				return
			if obj is not self._output:
				self._stopMonitoring()
				self._output = obj
				self._lastInterpreterHandle = obj.windowHandle
				obj.startMonitoring()
				log.debug(
					"Inform 7 Access: monitoring started; window=%s",
					obj.windowHandle,
				)
			else:
				# Poll as well as accepting real events. LiveText updates its
				# baseline even with reporting off, preventing a backlog on enable.
				obj.event_textChange()
		except Exception:
			log.exception("Inform 7 Access: unable to monitor interpreter")
			self._stopMonitoring("monitoring error")

	def event_gainFocus(self, obj: NVDAObject, nextHandler: Callable[[], None]) -> None:
		if self.compileFocus.suppress(obj, focusEvent=True):
			self._poll()
			return
		try:
			log.debug(
				"Inform 7 Access: object gainFocus event; %s",
				describeObject(obj),
			)
			self._poll()
		finally:
			nextHandler()

	def event_focusEntered(self, obj: NVDAObject, nextHandler: Callable[[], None]) -> None:
		if not self.compileFocus.suppress(obj, ancestor=True):
			nextHandler()

	def event_stateChange(self, obj: NVDAObject, nextHandler: Callable[[], None]) -> None:
		self.compileFocus.activity(obj, "stateChange")
		nextHandler()

	def event_documentLoadComplete(self, obj: NVDAObject, nextHandler: Callable[[], None]) -> None:
		self.compileFocus.activity(obj, "documentLoadComplete")
		nextHandler()

	def event_nameChange(self, obj: NVDAObject, nextHandler: Callable[[], None]) -> None:
		self.compileFocus.trace.record("nameChange", obj, active=self.compileFocus.active)
		nextHandler()

	@script(
		description=_("Compile and run, silencing intermediate focus announcements."),
		category="Inform 7 Access",
		gesture="kb:f5",
	)
	def script_compile(self, gesture: SendableGesture) -> None:
		self.compileFocus.start()
		try:
			gesture.send()
		except Exception:
			self.compileFocus.cancel("F5 forwarding failed")
			self.compileFocus.trace.stop("F5 forwarding failed")
			raise

	@script(
		description=_("Arm an automatic trace of the next F5 compilation, or stop the current trace."),
		category="Inform 7 Access",
		gesture="kb:NVDA+shift+f5",
	)
	def script_traceCompilation(self, gesture: SendableGesture) -> None:
		trace = self.compileFocus.trace
		result = trace.toggle()
		if result == "armed":
			ui.message(_("Compilation trace armed. Press F5. Traces are saved in %s.") % trace.directory)
		elif result == "saved":
			ui.message(_("Compilation trace stopped. File: %s") % trace.path)
		else:
			ui.message(_("Compilation trace disarmed."))

	def event_appModule_gainFocus(self) -> None:
		log.debug(
			"Inform 7 Access: app gained focus; processID=%s",
			self.processID,
		)
		self._poll()

	def event_appModule_loseFocus(self) -> None:
		self.compileFocus.cancel("app lost focus")
		self.compileFocus.trace.stop("app lost focus")
		log.debug("Inform 7 Access: app lost focus; processID=%s", self.processID)
		self._stopMonitoring("app lost focus")

	@override
	def terminate(self) -> None:
		try:
			super().terminate()
		finally:
			self._terminated = True
			self.compileFocus.terminate()
			self._timer.Stop()
			self._stopMonitoring("module terminated or plugins reloaded")
			log.debug(
				"Inform 7 Access: module terminated; processID=%s",
				self.processID,
			)
