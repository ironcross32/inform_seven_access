"""Shared configuration and translations for the app module and global plugin."""

import config


def _(message):
    """English fallback for scratchpad loading without an add-on catalogue."""
    return message


try:
    import addonHandler
except ImportError:
    pass
else:
    try:
        addonHandler.initTranslation()
    except addonHandler.AddonError:
        pass


def registerConfig():
    config.conf.spec["inform7"] = {
        "soundVolume": "integer(min=0, max=100, default=100)",
        "syntaxFeedbackMode": "option('none', 'speech', 'speechAndSounds', 'sounds', 'legacy', default='legacy')",
        # Retain the old value so existing profiles keep their enabled/disabled
        # behavior until a mode is explicitly saved through Settings.
        "automaticallyReadSyntaxHighlighting": "boolean(default=True)",
    }


SYNTAX_MODES = ("none", "speech", "speechAndSounds", "sounds")


def getSoundVolume():
    return config.conf["inform7"].get("soundVolume", 100)


def syntaxMode():
    section = config.conf["inform7"]
    mode = section.get("syntaxFeedbackMode", "legacy")
    if mode == "legacy":
        return "speech" if section["automaticallyReadSyntaxHighlighting"] else "none"
    return mode


def syntaxEnabled():
    # Read the active profile each time, rather than caching its value.
    return syntaxMode() != "none"
