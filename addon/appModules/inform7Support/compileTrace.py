"""Opt-in, bounded event tracing using objects NVDA has already discovered."""

from collections.abc import Callable, Iterable
from enum import Enum
from datetime import datetime
import json
from pathlib import Path
import tempfile
from typing import Any, TextIO, cast
from uuid import uuid4

import api
import controlTypes
from logHandler import log
import winUser


def documentURL(obj: Any) -> str:
	"""NVDA hides document values; Chromium's buffer exposes the native URL."""
	if getattr(obj, "role", None) != controlTypes.Role.DOCUMENT:
		return ""
	getters: tuple[Callable[[], Any], ...] = (
		lambda: getattr(getattr(obj, "treeInterceptor", None), "documentURL", None),
		lambda: obj.IAccessibleObject.accValue(0),
		lambda: getattr(obj, "value", None),
	)
	for getter in getters:
		try:
			value = getter()
			if isinstance(value, str) and value:
				return value
		except Exception:
			continue
	return ""


def scalar(value: Any) -> Any:
	if isinstance(value, Enum):
		return value.name
	if value is None or isinstance(value, (bool, int, float)):
		return value
	if isinstance(value, str):
		return value[:256]
	if isinstance(value, (tuple, list, set, frozenset)):
		return [scalar(item) for item in list(cast(Iterable[Any], value))[:40]]
	return type(value).__name__


def properties(obj: Any) -> dict[str, Any]:
	result: dict[str, Any] = {"pythonClass": type(obj).__name__}
	for name in (
		"processID",
		"windowHandle",
		"windowClassName",
		"windowStyle",
		"windowControlID",
		"role",
		"states",
		"name",
		"location",
		"IAccessibleRole",
		"IAccessibleStates",
		"IAccessibleChildID",
		"IA2UniqueID",
		"UIAElementRuntimeId",
	):
		try:
			result[name] = scalar(getattr(obj, name, None))
		except Exception as error:
			result[name] = {"error": type(error).__name__}
	# Only document values are URLs. Editable/interpreter values contain story text.
	try:
		if obj.role == controlTypes.Role.DOCUMENT:
			result["documentURL"] = scalar(documentURL(obj))
		buffer = getattr(obj, "treeInterceptor", None)
		if buffer is not None:
			result["buffer"] = {
				"class": type(buffer).__name__,
				**{
					name: scalar(getattr(buffer, name, None))
					for name in ("rootID", "isReady", "isLoading", "passThrough", "_hadFirstGainFocus")
				},
			}
	except Exception as error:
		result["documentError"] = type(error).__name__
	return result


class CompileTrace:
	def __init__(self, processID: int, clock: Callable[[], float]) -> None:
		self.processID = processID
		self.clock = clock
		self.directory = Path(tempfile.gettempdir()) / "inform7-access-traces"
		self.armed = False
		self.stream: TextIO | None = None
		self.path: Path | None = None
		self.window = 0
		self.started = 0.0
		self.lastEvent = 0.0
		self.count = 0

	def toggle(self) -> str:
		if self.stream is not None:
			self.stop("manual stop")
			return "saved"
		self.armed = not self.armed
		return "armed" if self.armed else "disarmed"

	def begin(self, window: int) -> None:
		if not self.armed or self.stream is not None:
			return
		self.armed = False
		try:
			self.directory.mkdir(parents=True, exist_ok=True)
			self.path = self.directory / f"compile-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}.jsonl"
			self.stream = self.path.open("x", encoding="utf-8", newline="\n")
			self.window = window
			self.started = self.lastEvent = self.clock()
			self.count = 0
			log.info("Inform 7 Access: compile trace started: %s", self.path)
			self.record("traceStart", api.getFocusObject())
		except Exception:
			log.exception("Inform 7 Access: unable to start compile trace")
			self.stop("trace startup failed")

	def belongs(self, obj: Any) -> bool:
		return (
			obj is not None
			and getattr(obj, "processID", None) == self.processID
			and winUser.getAncestor(getattr(obj, "windowHandle", 0), winUser.GA_ROOT) == self.window
		)

	def record(self, event: str, obj: Any = None, **details: Any) -> None:
		if self.stream is None:
			return
		try:
			if winUser.getForegroundWindow() != self.window:
				self.stop("foreground window changed")
				return
			now = self.clock()
			row: dict[str, Any] = {
				"elapsed": round(now - self.started, 4),
				"event": event,
				**{key: scalar(value) for key, value in details.items()},
			}
			# Native objects can disappear during a fast rerun. Keep structural
			# diagnostics even when we cannot safely read their names or values.
			for label, candidate in (("eventIdentity", obj), ("focusIdentity", api.getFocusObject())):
				identity: dict[str, Any] = {}
				for name in ("processID", "windowHandle", "windowClassName", "role"):
					try:
						identity[name] = scalar(getattr(candidate, name, None))
					except Exception as error:
						identity[name] = {"error": type(error).__name__}
				try:
					identity["nativeRoot"] = winUser.getAncestor(
						getattr(candidate, "windowHandle", 0),
						winUser.GA_ROOT,
					)
				except Exception as error:
					identity["rootError"] = type(error).__name__
				row[label] = identity
			if self.belongs(obj):
				row["object"] = properties(obj)
				focus = api.getFocusObject()
				if self.belongs(focus):
					row["focus"] = properties(focus)
				row["ancestors"] = [
					properties(parent) for parent in api.getFocusAncestors()[-40:] if self.belongs(parent)
				]
			_ = self.stream.write(json.dumps(row, ensure_ascii=False) + "\n")
			self.stream.flush()
			self.lastEvent = now
			self.count += 1
			if self.count >= 4000:
				self.stop("event limit")
		except Exception:
			log.exception("Inform 7 Access: compile trace recording failed")
			self.stop("recording failed")

	def poll(self, suppressionActive: bool) -> None:
		if self.stream is None:
			return
		try:
			now = self.clock()
			if winUser.getForegroundWindow() != self.window:
				self.stop("foreground window changed")
			elif now - self.started >= 120:
				self.stop("120 second limit")
			elif not suppressionActive and now - self.started >= 15 and now - self.lastEvent >= 3:
				self.stop("capture settled")
		except Exception:
			log.exception("Inform 7 Access: compile trace polling failed")
			self.stop("inspection failed")

	def stop(self, reason: str) -> None:
		stream, self.stream = self.stream, None
		if stream is None:
			return
		try:
			_ = stream.write(
				json.dumps({"event": "traceEnd", "reason": reason, "records": self.count}) + "\n",
			)
			stream.flush()
			log.info("Inform 7 Access: compile trace saved: %s (%s)", self.path, reason)
		except Exception:
			log.exception("Inform 7 Access: unable to finish compile trace")
		finally:
			try:
				stream.close()
			except Exception:
				log.exception("Inform 7 Access: unable to close compile trace")
