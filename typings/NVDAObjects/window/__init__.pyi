from NVDAObjects import NVDAObject

class Window(NVDAObject):
    windowHandle: int
    windowClassName: str
    windowStyle: int
    def _get_windowText(self) -> str: ...
    def _get_displayText(self) -> str: ...
