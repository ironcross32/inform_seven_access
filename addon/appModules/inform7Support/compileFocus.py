"""Project-scoped compile presentation gate; never changes NVDA or Windows focus."""

from __future__ import annotations

from collections.abc import Callable
import re
import time
from typing import Any, override
from urllib.parse import unquote, urlsplit

import api
import controlTypes
import inputCore
from logHandler import log
from NVDAObjects.IAccessible.chromium import ChromeVBuf, Document
import winUser
from .compileTrace import CompileTrace, documentURL

SETTLE_SECONDS = 0.750
TIMEOUT_SECONDS = 120
TRANSIENT_FOCUS_SECONDS = 1.5


def objectKey(obj: Any) -> tuple[int, int, int, int]:
	"""Native accessibility identity survives NVDA object recreation."""
	return (
		obj.processID,
		obj.windowHandle,
		getattr(obj, "IA2UniqueID", 0),
		getattr(obj, "IAccessibleChildID", 0),
	)


def isChromium(obj: Any) -> bool:
	return getattr(obj, "windowClassName", "") == "Chrome_RenderWidgetHostHWND"


class CompileFocusController:
	def __init__(
		self,
		processID: int,
		interpreter: Callable[[Any], bool],
		clock: Callable[[], float] = time.monotonic,
	) -> None:
		self.processID = processID
		self.interpreter = interpreter
		self.clock = clock
		self.serial = 0
		self.active = False
		self.terminated = False
		self.window = 0
		self.started = 0.0
		self.lastTransition = 0.0
		self.pendingReport: tuple[Any, ...] | None = None
		self.withheld: tuple[int, int, int, int] | None = None
		self.initialFocus: tuple[int, int, int, int] | None = None
		self.transientSince: float | None = None
		self.trace = CompileTrace(processID, lambda: self.clock())
		inputCore.decide_executeGesture.register(self.observeGesture)

	def cancel(self, reason: str = "cancelled") -> None:
		if self.active:
			self.trace.record("suppressionEnd", reason=reason, session=self.serial)
		self.serial += 1
		self.active = False
		self.pendingReport = None
		self.withheld = None
		self.transientSince = None

	def ownsForeground(self) -> bool:
		hwnd = winUser.getForegroundWindow()
		return bool(
			hwnd and hwnd == self.window and winUser.getWindowThreadProcessID(hwnd)[0] == self.processID,
		)

	def ownsObject(self, obj: Any) -> bool:
		return bool(
			obj is not None
			and obj.processID == self.processID
			and winUser.getAncestor(obj.windowHandle, winUser.GA_ROOT) == self.window,
		)

	def start(self) -> None:
		self.cancel("new F5")
		if self.terminated:
			return
		try:
			self.window = winUser.getForegroundWindow()
			obj = api.getFocusObject()
			if not self.ownsForeground() or not self.ownsObject(obj):
				return
			self.initialFocus = objectKey(obj)
			self.started = self.lastTransition = self.clock()
			self.trace.begin(self.window)
			self.active = True
			self.trace.record("suppressionStart", obj, session=self.serial)
		except Exception:
			self.cancel("startup inspection failed")
			log.exception("Inform 7 Access: unable to start compile focus suppression")

	def observeGesture(self, gesture: inputCore.InputGesture) -> bool:
		# Deciders must return True: this observer never consumes input.
		if not gesture.isModifier and "kb:f5" not in gesture.normalizedIdentifiers:
			self.cancel("user gesture")
		return True

	def allowed(self, obj: Any) -> bool:
		if self.isTransientPane(obj):
			return True
		if isChromium(obj):
			return obj.role not in (
				controlTypes.Role.DIALOG,
				controlTypes.Role.POPUPMENU,
				controlTypes.Role.MENUITEM,
				controlTypes.Role.EDITABLETEXT,
			)
		return (
			obj.role in (controlTypes.Role.PANE, controlTypes.Role.WINDOW)
			and re.fullmatch(r"Afx:[0-9A-Fa-f]+:0", obj.windowClassName) is not None
		)

	def isTransientPane(self, obj: Any) -> bool:
		return bool(
			obj is not None
			and obj.role == controlTypes.Role.UNKNOWN
			and re.fullmatch(r"AfxWnd\d+s", getattr(obj, "windowClassName", ""))
			and getattr(obj, "IAccessibleChildID", None) == 0
			and not getattr(obj, "name", None),
		)

	def isTransientFocus(self, obj: Any) -> bool:
		if self.ownsObject(obj):
			return self.isTransientPane(obj)
		if self.isDetachedInterpreter(obj):
			ancestors = api.getFocusAncestors()
			# NVDA may retain the dead interpreter's WindowRoot as the last
			# ancestor. Skip only that wrapper, never an unrelated ancestor.
			if ancestors and self.isDetachedInterpreterWrapper(ancestors[-1], obj):
				ancestors = ancestors[:-1]
			parent = ancestors[-1] if ancestors else None
			return bool(
				parent is not None
				and self.ownsObject(parent)
				and re.fullmatch(r"AfxWnd\d+s", getattr(parent, "windowClassName", ""))
				and parent.role in (controlTypes.Role.PANE, controlTypes.Role.UNKNOWN)
				and getattr(parent, "IAccessibleChildID", None) == 0
				and not getattr(parent, "name", None),
			)
		# Never tolerate a live window belonging to another project/application.
		if obj is not None and (
			getattr(obj, "role", None)
			not in (controlTypes.Role.UNKNOWN, controlTypes.Role.WINDOW, controlTypes.Role.PANE)
			or winUser.getAncestor(getattr(obj, "windowHandle", 0), winUser.GA_ROOT)
		):
			return False
		ancestors = api.getFocusAncestors()
		return bool(ancestors and self.ownsObject(ancestors[-1]) and self.isTransientPane(ancestors[-1]))

	def isDetachedInterpreter(self, obj: Any) -> bool:
		# A destroyed HWND no longer provides reliable native window styles.
		return bool(
			obj is not None
			and getattr(obj, "processID", None) == self.processID
			and getattr(obj, "windowClassName", "").upper() == "RICHEDIT50W"
			and obj.role == controlTypes.Role.EDITABLETEXT
			and getattr(obj, "IAccessibleChildID", None) == 0
			and not winUser.getAncestor(getattr(obj, "windowHandle", 0), winUser.GA_ROOT),
		)

	def isDetachedInterpreterWrapper(self, obj: Any, focus: Any) -> bool:
		return bool(
			obj is not None
			and focus is not None
			and getattr(obj, "processID", None) == self.processID
			and getattr(obj, "windowHandle", None) == getattr(focus, "windowHandle", None)
			and getattr(obj, "windowClassName", "").upper() == "RICHEDIT50W"
			and obj.role == controlTypes.Role.WINDOW
			and not winUser.getAncestor(obj.windowHandle, winUser.GA_ROOT),
		)

	def check(self, focusEvent: bool = False) -> bool:
		if not self.active:
			return False
		obj = api.getFocusObject()
		if not self.ownsForeground():
			self.cancel("foreground or project changed")
			return False
		if self.isTransientFocus(obj):
			if self.transientSince is None:
				self.transientSince = self.clock()
				self.trace.record("transientFocusStart", obj)
			if self.clock() - self.transientSince < TRANSIENT_FOCUS_SECONDS:
				return True
			if focusEvent:
				self.cancel("transient focus expired")
			else:
				self.finish(self.serial, "transient focus expired")
			return False
		self.transientSince = None
		if not self.ownsObject(obj):
			self.cancel("foreground or project changed")
			return False
		if not focusEvent and self.withheld is None and objectKey(obj) == self.initialFocus:
			return True
		if self.interpreter(obj):
			self.cancel("interpreter arrived")
			return False
		if not self.allowed(obj):
			self.cancel("unexpected focus destination")
			return False
		return True

	def allowedAncestor(self, obj: Any) -> bool:
		"""Compile pane wrappers observed around Chromium in the captured trace.

		These are ancestors only: actual focus on a native tab control or pane
		still follows the narrower destination policy in check().
		"""
		if self.allowed(obj):
			return True
		className = getattr(obj, "windowClassName", "")
		if re.fullmatch(r"AfxWnd\d+s", className):
			return obj.role in (
				controlTypes.Role.WINDOW,
				controlTypes.Role.PANE,
				controlTypes.Role.TABCONTROL,
			)
		if obj.role not in (controlTypes.Role.WINDOW, controlTypes.Role.PANE):
			return False
		return bool(
			className == "Chrome_WidgetWin_1"
			or re.fullmatch(r"AfxMDIFrame\d+s", className)
			or re.fullmatch(
				r"Afx:[0-9A-Fa-f]+:[0-9A-Fa-f]+:[0-9A-Fa-f]+:[0-9A-Fa-f]+:[0-9A-Fa-f]+",
				className,
			),
		)

	def suppress(
		self,
		obj: Any,
		*,
		focusEvent: bool = False,
		ancestor: bool = False,
		source: str = "documentFocus",
	) -> bool:
		suppressed = self._suppress(obj, focusEvent=focusEvent, ancestor=ancestor)
		self.trace.record(
			"gainFocus" if focusEvent else "focusEntered" if ancestor else source,
			obj,
			suppressed=suppressed,
			active=self.active,
			session=self.serial,
		)
		return suppressed

	def _suppress(self, obj: Any, *, focusEvent: bool = False, ancestor: bool = False) -> bool:
		try:
			if not self.check(focusEvent or ancestor):
				return False
			if self.clock() - self.started >= TIMEOUT_SECONDS:
				# The caller will present this destination normally.
				self.cancel("120 second timeout")
				return False
			if not self.ownsObject(obj):
				focus = api.getFocusObject()
				return self.transientSince is not None and (
					obj is focus or (ancestor and self.isDetachedInterpreterWrapper(obj, focus))
				)
			if ancestor:
				return self.allowedAncestor(obj)
			if not self.allowed(obj):
				self.cancel("unexpected presentation object")
				return False
			self.withheld = objectKey(api.getFocusObject())
			if focusEvent:
				self.lastTransition = self.clock()
				self.pendingReport = None
			return True
		except Exception:
			# This focus handler will continue normal presentation itself.
			log.exception("Inform 7 Access: compile focus inspection failed")
			self.cancel("focus inspection failed")
			return False

	def activity(self, obj: Any, source: str = "documentActivity") -> None:
		self.trace.record(source, obj, active=self.active)
		if self.active:
			try:
				if self.check() and self.ownsObject(obj) and isChromium(obj):
					self.lastTransition = self.clock()
					self.pendingReport = None
			except Exception:
				self.fail()

	def finish(self, serial: int, reason: str = "report settled") -> None:
		if not self.active or serial != self.serial:
			return
		withheld = self.withheld
		self.cancel(reason)
		try:
			obj = api.getFocusObject()
			if (
				self.terminated
				or obj is None
				or not self.ownsForeground()
				or not self.ownsObject(obj)
				or objectKey(obj) != withheld
			):
				return
			buffer = getattr(obj, "treeInterceptor", None)
			if isinstance(buffer, InformChromeVBuf) and buffer.isReady:
				buffer.event_treeInterceptor_gainFocus()
			else:
				obj.event_gainFocus()
		except Exception:
			log.exception("Inform 7 Access: unable to present compile destination")

	def fail(self) -> None:
		log.exception("Inform 7 Access: compile focus inspection failed")
		self.finish(self.serial, "inspection failed")

	def poll(self) -> None:
		self.trace.poll(self.active)
		try:
			if not self.check():
				return
			if self.clock() - self.started >= TIMEOUT_SECONDS:
				self.finish(self.serial, "120 second timeout")
				return
			if self.withheld is None:
				return
			if self.transientSince is not None:
				return
			obj = api.getFocusObject()
			if obj is None:
				self.cancel()
				return
			buffer = getattr(obj, "treeInterceptor", None)
			url = urlsplit(documentURL(obj))
			report = (
				isChromium(obj)
				and obj.role == controlTypes.Role.DOCUMENT
				and url.scheme.lower() == "file"
				and unquote(url.path).replace("\\", "/").lower().endswith("/build/problems.html")
			)
			ready = (
				isinstance(buffer, InformChromeVBuf)
				and buffer.isReady
				and not buffer.isLoading
				and controlTypes.State.BUSY not in obj.states
			)
			key = (*objectKey(obj), url.geturl(), getattr(buffer, "rootID", None)) if report else None
			if not report or not ready or key != self.pendingReport:
				if report and key != self.pendingReport:
					self.trace.record("reportReadiness", obj, ready=ready)
				self.pendingReport = key if report and ready else None
				self.lastTransition = self.clock()
			elif self.clock() - self.lastTransition >= SETTLE_SECONDS:
				self.finish(self.serial)
		except Exception:
			self.fail()

	def terminate(self) -> None:
		if self.terminated:
			return
		self.terminated = True
		self.cancel("module terminated")
		self.trace.armed = False
		self.trace.stop("module terminated")
		inputCore.decide_executeGesture.unregister(self.observeGesture)


class InformChromeVBuf(ChromeVBuf):
	def _presentationAllowed(self, source: str) -> bool:
		focus = api.getFocusObject()
		# Native buffer load callbacks can arrive after focus left or a new
		# document replaced this one. Never replay presentation from that buffer.
		if focus is None or getattr(focus, "treeInterceptor", None) is not self:
			return False
		controller: CompileFocusController = self.rootNVDAObject.appModule.compileFocus
		if controller.terminated:
			return False
		if (
			winUser.getAncestor(getattr(focus, "windowHandle", 0), winUser.GA_ROOT)
			!= winUser.getForegroundWindow()
		):
			controller.cancel()
			return False
		return not controller.suppress(focus, source=source)

	@override
	def event_treeInterceptor_gainFocus(self) -> None:
		if self._presentationAllowed("treeInterceptor_gainFocus"):
			# Retain NVDA's initial/saved caret position and auto say-all choice.
			super().event_treeInterceptor_gainFocus()

	@override
	def event_gainFocus(self, obj: Any, nextHandler: Callable[[], None]) -> None:
		if self._presentationAllowed("browser_gainFocus"):
			super().event_gainFocus(obj, nextHandler)

	@override
	def _loadProgress(self) -> None:
		if self._presentationAllowed("browser_loadProgress"):
			super()._loadProgress()


class InformDocument(Document):
	@override
	def _get_treeInterceptorClass(self) -> Any:
		base = super()._get_treeInterceptorClass()
		return InformChromeVBuf if base is ChromeVBuf else base

	@override
	def event_gainFocus(self) -> None:
		if not self.appModule.compileFocus.suppress(self):
			super().event_gainFocus()
