from typing import Any
from controlTypes import Role, State

class NVDAObject:
	appModule: Any
	processID: int
	role: Role
	states: set[State]
	location: tuple[int, int, int, int] | None
	def event_typedCharacter(self, ch: str) -> None: ...
	def event_gainFocus(self) -> None: ...
