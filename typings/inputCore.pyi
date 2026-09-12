from collections.abc import Callable

class InputGesture:
	isModifier: bool
	normalizedIdentifiers: list[str]

class _Decider:
	def register(self, handler: Callable[[InputGesture], bool]) -> None: ...
	def unregister(self, handler: Callable[[InputGesture], bool]) -> None: ...

decide_executeGesture: _Decider
