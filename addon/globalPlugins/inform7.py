from __future__ import annotations

from typing import Any, override

import globalPluginHandler
import gui
import gui.guiHelper
import gui.settingsDialogs
import gui.nvdaControls
import wx

from appModules.inform7Support import _, SYNTAX_MODES, registerConfig, syntaxMode, getSoundVolume
import config


class Inform7Settings(gui.settingsDialogs.SettingsPanel):
	title = _("Inform 7")
	_inform7SettingsCategory = True

	@override
	def makeSettings(self, settingsSizer: wx.Sizer) -> None:
		helper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		group = wx.StaticBoxSizer(wx.VERTICAL, self, label=_("Source editor"))
		groupHelper = gui.guiHelper.BoxSizerHelper(self, sizer=group)
		# addLabeledControl associates the accessible label with the selector.
		self.syntaxModeChoice = groupHelper.addLabeledControl(
			_("Syntax highlighting feedback"),
			wx.Choice,
			choices=[
				_("None"),
				_("Speech"),
				_(
					"Speech and sounds",
				),
				_("Sounds"),
			],
		)
		self.syntaxModeChoice.SetSelection(SYNTAX_MODES.index(syntaxMode()))
		self.soundVolumeControl = groupHelper.addLabeledControl(
			_("Syntax sound volume (%)"),
			gui.nvdaControls.EnhancedInputSlider,
			minValue=0,
			maxValue=100,
		)
		self.soundVolumeControl.SetValue(getSoundVolume())
		helper.addItem(group)

	@override
	def onSave(self) -> None:
		config.conf["inform7"]["syntaxFeedbackMode"] = SYNTAX_MODES[self.syntaxModeChoice.GetSelection()]
		config.conf["inform7"]["soundVolume"] = self.soundVolumeControl.GetValue()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self, *args: Any, **kwargs: Any) -> None:
		super().__init__(*args, **kwargs)
		registerConfig()
		categories = gui.settingsDialogs.NVDASettingsDialog.categoryClasses
		# A module reload produces a new class identity. Remove stale registrations.
		categories[:] = [
			c
			for c in categories
			if not getattr(
				c,
				"_inform7SettingsCategory",
				False,
			)
		]
		categories.append(Inform7Settings)
		self._settingsClass = Inform7Settings

	@override
	def terminate(self) -> None:
		try:
			categories = gui.settingsDialogs.NVDASettingsDialog.categoryClasses
			if self._settingsClass in categories:
				categories.remove(self._settingsClass)
		finally:
			super().terminate()
