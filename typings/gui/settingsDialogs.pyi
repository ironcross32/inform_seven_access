import wx

class SettingsPanel(wx.Panel):
    title: str
    def makeSettings(self, settingsSizer: wx.Sizer) -> None: ...
    def onSave(self) -> None: ...

class NVDASettingsDialog:
    categoryClasses: list[type[SettingsPanel]]
