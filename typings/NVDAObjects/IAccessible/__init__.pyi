from NVDAObjects.window import Window

class IAccessible(Window):
	IAccessibleChildID: int

def getNVDAObjectFromEvent(window: int, objectID: int, childID: int) -> IAccessible | None: ...
