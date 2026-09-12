from collections.abc import Callable
from typing import Any, override
from NVDAObjects import NVDAObject

class ChromeVBuf:
	rootNVDAObject: Any
	rootID: int
	isReady: bool
	isLoading: bool
	def event_treeInterceptor_gainFocus(self) -> None: ...
	def event_gainFocus(self, obj: Any, nextHandler: Callable[[], None]) -> None: ...
	def _loadProgress(self) -> None: ...

class Document(NVDAObject):
	def _get_treeInterceptorClass(self) -> Any: ...
	@override
	def event_gainFocus(self) -> None: ...
