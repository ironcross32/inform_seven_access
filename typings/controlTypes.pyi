from enum import Enum

class Role(Enum):
	EDITABLETEXT = 1
	UNKNOWN = 2
	DOCUMENT = 3
	PANE = 4
	WINDOW = 5
	DIALOG = 6
	POPUPMENU = 7
	MENUITEM = 8
	TABCONTROL = 9

class State(Enum):
	INVISIBLE = 1
	OFFSCREEN = 2
	MULTILINE = 3
	BUSY = 4

class OutputReason(Enum):
	SAYALL = 1
