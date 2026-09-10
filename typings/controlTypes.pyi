from enum import Enum

class Role(Enum):
    EDITABLETEXT = 1
    UNKNOWN = 2

class State(Enum):
    INVISIBLE = 1
    OFFSCREEN = 2
    MULTILINE = 3

class OutputReason(Enum):
    SAYALL = 1
