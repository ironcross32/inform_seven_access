"""NVDA contract stubs: these tests do not assert live speech or braille output."""

from __future__ import annotations

from typing import Any, Self, override

# Tests intentionally exercise protected NVDA extension points.
# pyright: reportPrivateUsage=false


import importlib
from pathlib import Path
import sys
import tempfile
import wave
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
FORMAT = {
	"reportFontSize": True,
	"reportColor": True,
	"detectFormatAfterCursor": True,
}


class Field(dict[str, Any]):
	pass


class FieldCommand:
	def __init__(self, command: str, field: Field) -> None:
		self.command, self.field = command, field


class FakeConfig(dict[str, Any]):
	def __init__(self) -> None:
		super().__init__(documentFormatting=FORMAT.copy())
		self.spec: dict[str, dict[str, str]] = {}

	@override
	def __getitem__(self, key: str) -> Any:
		if key == "inform7" and key not in self:
			assert self.spec[key]["automaticallyReadSyntaxHighlighting"] == "boolean(default=True)"
			self[key] = {"automaticallyReadSyntaxHighlighting": True}
		return super().__getitem__(key)


class FakeScintillaTextInfo:
	"""Byte-indexed text with the formatting method signatures from NVDA 2026.1.1."""

	def __init__(self, parts: list[tuple[str, int]], start: int = 0, end: int | None = None) -> None:
		self.data = b""
		self.styles: list[int] = []
		self.boundaries = [0]
		for text, style in parts:
			for char in text:
				encoded = char.encode("utf-8")
				self.data += encoded
				self.styles.extend([style] * len(encoded))
				self.boundaries.append(len(self.data))
		self._startOffset = start
		self._endOffset = len(self.data) if end is None else end
		self.obj = SimpleNamespace(windowHandle=42)
		self.rawSize = 110
		self.queries: list[tuple[int, int]] = []

	@property
	def text(self) -> str:
		return self._getTextRange(self._startOffset, self._endOffset)

	def _send(self, msg: int, value: int = 0) -> int:
		self.queries.append((msg, value))
		if msg == 2010:
			return self.styles[value] if value < len(self.styles) else 0
		if msg == 2007:
			return self.data[value]
		return {2485: self.rawSize, 2481: 0x563412, 2482: 0xEFCDAB}[msg]

	def _getStoryLength(self) -> int:
		return len(self.data)

	def expand(self, unit: str) -> None:
		# Test ranges are preselected; exercise production expansion bookkeeping.
		pass

	def copy(self) -> Self:
		import copy

		return copy.copy(self)

	def _getCharacterOffsets(self, offset: int) -> tuple[int, int]:
		for start, end in zip(self.boundaries, self.boundaries[1:]):
			if start <= offset < end:
				return start, end
		return offset, offset + 1

	def _getTextRange(self, start: int, end: int) -> str:
		return self.data[start:end].decode("utf-8")

	def _getLineOffsets(self, offset: int) -> tuple[int, int]:
		start = self.data.rfind(b"\n", 0, offset) + 1
		end = self.data.find(b"\n", offset)
		return start, len(self.data) if end < 0 else end + 1

	def _getFormatFieldAndOffsets(
		self,
		offset: int,
		formatConfig: dict[str, bool],
		calculateOffsets: bool = True,
	) -> tuple[Field, tuple[int, int]]:
		field = Field()
		if formatConfig.get("reportFontSize"):
			field["font-size"] = f"{self.rawSize} pt"
		if not calculateOffsets:
			return field, (self._startOffset, self._endOffset)
		end = offset + 1
		while end < len(self.data) and self.styles[end] == self.styles[offset]:
			end += 1
		return field, (offset, end)

	def getTextWithFields(self, formatConfig: dict[str, bool] | None = None) -> list[str | FieldCommand]:
		formatConfig = formatConfig or FORMAT
		items: list[str | FieldCommand] = []
		pos = self._startOffset
		while pos < self._endOffset:
			field, (_, end) = self._getFormatFieldAndOffsets(pos, formatConfig)
			if not formatConfig.get("detectFormatAfterCursor"):
				end = self._endOffset
			end = min(end, self._endOffset)
			items.extend(
				[
					FieldCommand("formatChange", field),
					self._getTextRange(pos, end),
				],
			)
			pos = end
		return items

	def getFormatFieldSpeech(
		self,
		attrs: Field,
		attrsCache: Field | None = None,
		formatConfig: dict[str, bool] | None = None,
		reason: str | None = None,
		unit: str | None = None,
		extraDetail: bool = False,
		initialFormat: bool = False,
	) -> list[str]:
		if attrsCache is not None:
			attrsCache.clear()
			attrsCache.update(attrs)
		return ["normal formatting"] if attrs.get("speakNormal") else []


class FakeChoice:
	def __init__(self, parent: object, choices: list[str]) -> None:
		self.choices = choices

	def SetSelection(self, value: int) -> None:
		self.value = value

	def GetSelection(self) -> int:
		return self.value


class FakeWaveFileCommand:
	def __init__(self, fileName: str) -> None:
		self.fileName = fileName


class FakeSlider:
	def __init__(self, parent: object, minValue: int, maxValue: int) -> None:
		self.min, self.max, self.value = minValue, maxValue, minValue

	def GetValue(self) -> int:
		return self.value

	def SetValue(self, value: int) -> None:
		self.value = value


class FakePanel:
	def onDiscard(self) -> None:
		pass


class FakePlugin:
	def terminate(self) -> None:
		pass


class EditorTests(unittest.TestCase):
	@override
	def setUp(self) -> None:
		self.conf = FakeConfig()
		self.log = Mock()
		self.categories = [FakePanel]
		settings = SimpleNamespace(
			SettingsPanel=FakePanel,
			NVDASettingsDialog=SimpleNamespace(
				categoryClasses=self.categories,
			),
		)

		def labeledControl(label: str, control: Any, **kwargs: Any) -> Any:
			item = control(None, **kwargs)
			item.label = label
			return item

		def boxSizerHelper(*args: Any, **kwargs: Any) -> SimpleNamespace:
			return SimpleNamespace(addItem=identity, addLabeledControl=labeledControl)

		def identity(item: Any) -> Any:
			return item

		def fromColorRef(n: int) -> tuple[int, int, int]:
			return n & 255, n >> 8 & 255, n >> 16 & 255

		helper = SimpleNamespace(
			BoxSizerHelper=boxSizerHelper,
		)
		self.wx = SimpleNamespace(
			Choice=FakeChoice,
			VERTICAL=1,
			StaticBoxSizer=Mock(return_value=object()),
		)
		controls = SimpleNamespace(EnhancedInputSlider=FakeSlider)
		gui = SimpleNamespace(
			settingsDialogs=settings,
			guiHelper=helper,
			nvdaControls=controls,
		)
		stubs = {
			"speech.commands": SimpleNamespace(WaveFileCommand=FakeWaveFileCommand),
			"config": SimpleNamespace(conf=self.conf),
			"colors": SimpleNamespace(
				RGB=SimpleNamespace(fromCOLORREF=fromColorRef),
			),
			"textInfos": SimpleNamespace(
				FormatField=Field,
				FieldCommand=FieldCommand,
				UNIT_CHARACTER="character",
				UNIT_WORD="word",
				UNIT_LINE="line",
				UNIT_PARAGRAPH="paragraph",
				UNIT_READINGCHUNK="readingChunk",
			),
			"controlTypes": SimpleNamespace(OutputReason=SimpleNamespace(SAYALL="sayAll")),
			"watchdog": SimpleNamespace(cancellableSendMessage=Mock()),
			"logHandler": SimpleNamespace(log=self.log),
			"NVDAObjects.window.scintilla": SimpleNamespace(
				Scintilla=object,
				ScintillaTextInfo=FakeScintillaTextInfo,
			),
			"globalPluginHandler": SimpleNamespace(GlobalPlugin=FakePlugin),
			"gui": gui,
			"gui.settingsDialogs": settings,
			"gui.guiHelper": helper,
			"gui.nvdaControls": controls,
			"wx": self.wx,
		}
		self.modules = patch.dict(sys.modules, stubs)
		self.modules.start()
		self.addCleanup(self.modules.stop)
		self.paths = patch.object(
			sys,
			"path",
			[str(ROOT / "addon"), *sys.path],
		)
		_ = self.paths.start()
		self.addCleanup(self.paths.stop)
		self.support = importlib.import_module("appModules.inform7Support")
		self.support.registerConfig()
		self.editor = importlib.import_module(
			"appModules.inform7Support.editor",
		)
		self.plugin = importlib.import_module("globalPlugins.inform7")
		# Use the real subclass with a native-message simulator underneath.
		self.Info = type(
			"TestInfo",
			(self.editor.InformSourceTextInfo,),
			{
				"_send": FakeScintillaTextInfo._send,
			},
		)

	def info(self, parts: list[tuple[str, int]], start: int = 0, end: int | None = None) -> Any:
		return self.Info(parts, start, end)

	def events(self, info: Any, formatConfig: dict[str, bool] | None = None) -> list[tuple[str, str]]:
		return [
			(action, kind)
			for item in info.getTextWithFields(formatConfig)
			if not isinstance(item, str)
			for action, kind in item.field.get(self.editor.SYNTAX_FIELD, ())
		]

	def spoken(
		self,
		info: Any,
		unit: str | None = "line",
		reason: str = "caret",
		formatConfig: dict[str, bool] | None = None,
	) -> list[Any]:
		if unit is not None:
			info.expand(unit)
		sequence: list[Any] = []
		cache: dict[str, Any] = {}
		extraDetail = unit in ("word", "character")
		formatConfig = dict(formatConfig or FORMAT)
		if extraDetail:
			formatConfig["extraDetail"] = True
		for item in info.getTextWithFields(formatConfig):
			if isinstance(item, str):
				sequence.append(item)
			else:
				sequence.extend(
					info.getFormatFieldSpeech(
						item.field,
						cache,
						unit=unit,
						reason=reason,
						extraDetail=extraDetail,
					),
				)
		self.assertNotIn(self.editor.SYNTAX_FIELD, cache)
		return sequence

	def test_default_profile_values_and_runtime_toggle(self) -> None:
		self.assertTrue(self.support.syntaxEnabled())
		info = self.info([('"hi"', 1)])
		self.assertEqual(len(self.events(info)), 2)
		baseProfile = self.conf["inform7"]
		self.conf["inform7"] = {"automaticallyReadSyntaxHighlighting": False}
		self.assertFalse(self.support.syntaxEnabled())
		self.assertEqual(self.events(info), [])
		self.conf["inform7"] = baseProfile
		self.assertEqual(len(self.events(info)), 2)

	def test_settings_apply_cancel_and_accessible_labels(self) -> None:
		panel = self.plugin.Inform7Settings()
		panel.makeSettings(object())
		self.assertEqual(panel.title, "Inform 7")
		self.assertEqual(
			self.wx.StaticBoxSizer.call_args.kwargs["label"],
			"Source editor",
		)
		self.assertEqual(
			panel.syntaxModeChoice.label,
			"Syntax highlighting feedback",
		)
		self.assertEqual(
			panel.syntaxModeChoice.choices,
			[
				"None",
				"Speech",
				"Speech and sounds",
				"Sounds",
			],
		)
		self.assertEqual(panel.syntaxModeChoice.GetSelection(), 1)
		panel.syntaxModeChoice.SetSelection(0)
		panel.onDiscard()
		self.assertTrue(self.support.syntaxEnabled())
		panel.onSave()
		self.assertFalse(self.support.syntaxEnabled())
		for index, mode in enumerate(self.support.SYNTAX_MODES):
			panel.syntaxModeChoice.SetSelection(index)
			panel.onSave()
			self.assertEqual(self.support.syntaxMode(), mode)

	def test_modes_preserve_legacy_profiles_and_explicit_modes_take_precedence(self) -> None:
		self.assertIn(
			"default='legacy'",
			self.conf.spec["inform7"]["syntaxFeedbackMode"],
		)
		self.conf["inform7"] = {
			"syntaxFeedbackMode": "legacy",
			"automaticallyReadSyntaxHighlighting": False,
		}
		self.assertEqual(self.support.syntaxMode(), "none")
		self.conf["inform7"]["syntaxFeedbackMode"] = "sounds"
		self.assertEqual(self.support.syntaxMode(), "sounds")
		self.conf["inform7"] = {
			"syntaxFeedbackMode": "speechAndSounds",
			"automaticallyReadSyntaxHighlighting": True,
		}
		self.assertEqual(self.support.syntaxMode(), "speechAndSounds")

	def test_volume_accessible_label_apply_cancel_and_profiles(self) -> None:
		self.assertEqual(
			self.conf.spec["inform7"]["soundVolume"],
			"integer(min=0, max=100, default=100)",
		)
		panel = self.plugin.Inform7Settings()
		panel.makeSettings(object())
		control = panel.soundVolumeControl
		self.assertEqual(control.label, "Syntax sound volume (%)")
		self.assertEqual(
			(control.min, control.max, control.GetValue()),
			(0, 100, 100),
		)
		control.SetValue(25)
		panel.onDiscard()
		self.assertEqual(self.support.getSoundVolume(), 100)
		panel.onSave()
		self.assertEqual(self.support.getSoundVolume(), 25)
		baseProfile = self.conf["inform7"]
		self.conf["inform7"] = {"soundVolume": 70}
		self.assertEqual(self.support.getSoundVolume(), 70)
		self.conf["inform7"] = baseProfile
		self.assertEqual(self.support.getSoundVolume(), 25)

	def test_volume_zero_mutes_only_sounds_and_reduced_volume_uses_cached_wave(self) -> None:
		syntax = importlib.import_module("appModules.inform7Support.syntax")
		self.conf["inform7"].update(
			syntaxFeedbackMode="speechAndSounds",
			soundVolume=0,
		)
		self.assertEqual(
			syntax.renderMarker(
				("begin", "quoted text"),
			),
			["Begin quoted text"],
		)
		self.conf["inform7"]["syntaxFeedbackMode"] = "sounds"
		self.assertEqual(syntax.renderMarker(("begin", "quoted text")), [])
		self.conf["inform7"]["soundVolume"] = 25
		first = syntax.renderMarker(("begin", "quoted text"))[0]
		second = syntax.renderMarker(("begin", "quoted text"))[0]
		self.assertIsInstance(first, FakeWaveFileCommand)
		self.assertEqual(first.fileName, second.fileName)
		self.assertTrue(Path(first.fileName).is_file())
		self.assertNotEqual(
			Path(first.fileName),
			syntax.SOUND_DIRECTORY / "quote_start.wav",
		)
		self.conf["inform7"]["soundVolume"] = 100
		self.assertEqual(
			Path(syntax.renderMarker(("begin", "quoted text"))[0].fileName),
			syntax.SOUND_DIRECTORY / "quote_start.wav",
		)

	def test_volume_scaling_preserves_pcm_format_duration_source_and_queued_files(self) -> None:
		volumeModule = importlib.import_module(
			"appModules.inform7Support.soundVolume",
		)
		with tempfile.TemporaryDirectory() as folder:
			for width in (1, 2, 3, 4):
				source = Path(folder) / f"pcm{width}.wav"
				samples = [40, -40, 0, 80]
				data = b"".join(
					(n + 128 if width == 1 else n).to_bytes(
						width,
						"little",
						signed=width != 1,
					)
					for n in samples
				)
				with wave.open(str(source), "wb") as output:
					output.setnchannels(2)
					output.setsampwidth(width)
					output.setframerate(44100)
					output.writeframes(data)
				original = source.read_bytes()
				quiet = volumeModule.scaledSoundPath(source, 25)
				with wave.open(str(quiet), "rb") as result:
					self.assertEqual(
						(
							result.getnchannels(),
							result.getsampwidth(),
							result.getframerate(),
							result.getnframes(),
						),
						(2, width, 44100, 2),
					)
					frames = result.readframes(2)
				values = [
					int.from_bytes(
						frames[i : i + width],
						"little",
						signed=width != 1,
					)
					- (128 if width == 1 else 0)
					for i in range(0, len(frames), width)
				]
				self.assertEqual(values, [10, -10, 0, 20])
				self.assertEqual(source.read_bytes(), original)
				self.assertEqual(
					volumeModule.scaledSoundPath(source, 100),
					source,
				)
				louder = volumeModule.scaledSoundPath(source, 50)
				self.assertNotEqual(quiet, louder)
				self.assertTrue(quiet.is_file())
				self.assertEqual(
					volumeModule.scaledSoundPath(source, 25),
					quiet,
				)

	def test_scaling_failure_never_plays_full_volume_and_keeps_speech(self) -> None:
		syntax = importlib.import_module("appModules.inform7Support.syntax")
		self.conf["inform7"].update(
			syntaxFeedbackMode="speechAndSounds",
			soundVolume=25,
		)
		with patch.object(syntax, "scaledSoundPath", side_effect=wave.Error("invalid WAV")):
			self.assertEqual(
				syntax.renderMarker(
					("begin", "quoted text"),
				),
				["Begin quoted text"],
			)
		self.log.warning.assert_called_once()

	def test_sound_modes_queue_commands_at_existing_boundaries(self) -> None:
		info = self.info([('"hi ', 1), ("[name]", 2), ('"', 1)])
		self.conf["inform7"]["syntaxFeedbackMode"] = "sounds"
		sequence = self.spoken(info)
		self.assertEqual(
			[
				Path(item.fileName).name
				if isinstance(
					item,
					FakeWaveFileCommand,
				)
				else item
				for item in sequence
			],
			[
				"quote_start.wav",
				'"hi ',
				"substitution_start.wav",
				"[name]",
				"substitution_end.wav",
				'"',
				"quote_end.wav",
			],
		)
		self.conf["inform7"]["syntaxFeedbackMode"] = "speechAndSounds"
		sequence = self.spoken(info)
		self.assertIsInstance(sequence[0], FakeWaveFileCommand)
		self.assertEqual(sequence[1], "Begin quoted text")
		self.assertIsInstance(sequence[-2], FakeWaveFileCommand)
		self.assertEqual(sequence[-1], "End quoted text")
		for mode in ("speech", "none"):
			self.conf["inform7"]["syntaxFeedbackMode"] = mode
			self.assertFalse(
				any(isinstance(item, FakeWaveFileCommand) for item in self.spoken(info)),
			)

	def test_all_supplied_sounds_are_mapped_and_character_reads_have_no_sound(self) -> None:
		syntax = importlib.import_module("appModules.inform7Support.syntax")
		self.conf["inform7"]["syntaxFeedbackMode"] = "sounds"
		for kind, prefix in (
			("quoted text", "quote"),
			("text substitution", "substitution"),
			("heading", "heading"),
			("comment", "comment"),
		):
			for action, suffix in (("begin", "start"), ("end", "end")):
				seq = syntax.renderMarker((action, kind))
				self.assertEqual(len(seq), 1)
				self.assertEqual(
					Path(seq[0].fileName).name,
					f"{prefix}_{suffix}.wav",
				)
				self.assertTrue(Path(seq[0].fileName).is_file())
		info = self.info([('"hi"', 1)], 3, 4)
		self.assertEqual(self.spoken(info, "character"), ['"'])
		self.assertEqual(self.spoken(info, None, "typing"), ['"'])
		self.assertEqual(self.spoken(info, None, "query"), ['"'])

	def test_missing_sound_retains_speech_in_combined_mode_and_logs_once(self) -> None:
		syntax = importlib.import_module("appModules.inform7Support.syntax")
		self.conf["inform7"]["syntaxFeedbackMode"] = "speechAndSounds"
		with patch.object(Path, "is_file", return_value=False):
			for _repeat in range(2):
				self.assertEqual(
					syntax.renderMarker(
						("begin", "quoted text"),
					),
					["Begin quoted text"],
				)
		self.log.warning.assert_called_once()

	def test_inform6_reuses_comment_cues_with_its_own_spoken_label(self) -> None:
		syntax = importlib.import_module("appModules.inform7Support.syntax")
		self.conf["inform7"]["syntaxFeedbackMode"] = "speechAndSounds"
		for action, suffix, label in (("begin", "start", "Begin"), ("end", "end", "End")):
			sequence = syntax.renderMarker((action, "Inform 6 code"))
			self.assertEqual(
				Path(sequence[0].fileName).name,
				f"comment_{suffix}.wav",
			)
			self.assertEqual(sequence[1], f"{label} Inform 6 code")

	def test_sound_boundary_order_survives_word_reading_and_adjacent_say_all_chunks(self) -> None:
		self.conf["inform7"]["syntaxFeedbackMode"] = "sounds"
		parts = [('"é ', 1), ("[name]", 2), ('"', 1)]
		whole = self.info(parts)

		def cues(info: Any, unit: str = "readingChunk", reason: str = "sayAll") -> list[str]:
			return [
				Path(item.fileName).name
				for item in self.spoken(info, unit, reason)
				if isinstance(item, FakeWaveFileCommand)
			]

		expected = cues(whole)
		for split in whole.boundaries[1:-1]:
			self.assertEqual(
				cues(self.info(parts, 0, split)) + cues(self.info(parts, split)),
				expected,
			)
		self.assertEqual(
			cues(self.info(parts, 4, 10), "word", "caret"),
			[
				"substitution_start.wav",
				"substitution_end.wav",
			],
		)

	def test_category_reload_and_late_termination(self) -> None:
		first = self.plugin.GlobalPlugin()
		_ = importlib.reload(self.plugin)
		second = self.plugin.GlobalPlugin()
		self.assertEqual(len(self.categories), 2)
		first.terminate()
		self.assertEqual(len(self.categories), 2)
		second.terminate()
		second.terminate()
		self.assertEqual(self.categories, [FakePanel])

	def test_sizes_colours_and_disabled_syntax(self) -> None:
		self.conf["inform7"]["automaticallyReadSyntaxHighlighting"] = False
		info = self.info([("say", 0)])
		for raw, expected in ((110, "11 pt"), (99, "9.9 pt")):
			info.rawSize = raw
			field, _ = info._getFormatFieldAndOffsets(0, FORMAT, False)
			self.assertEqual(field["font-size"], expected)
			self.assertEqual(field["color"], (18, 52, 86))
			self.assertEqual(field["background-color"], (171, 205, 239))
			self.assertNotIn(self.editor.SYNTAX_FIELD, field)
		field, _ = info._getFormatFieldAndOffsets(
			0,
			{"reportFontSize": False, "reportColor": False},
		)
		self.assertEqual(field, {})

	def test_say_is_plain_and_markers_surround_delimiters(self) -> None:
		self.assertEqual(self.events(self.info([("say", 0)])), [])
		info = self.info(
			[("say ", 0), ('"Hi ', 1), ("[name]", 2), ('!"', 1), (".", 0)],
		)
		self.assertEqual(
			self.spoken(info),
			[
				"say ",
				"Begin quoted text",
				'"Hi ',
				"Begin text substitution",
				"[name]",
				"End text substitution",
				'!"',
				"End quoted text",
				".",
			],
		)

	def test_style_mask_and_all_categories(self) -> None:
		for style, kind in ((1, "quoted text"), (3, "Inform 6 code"), (4, "heading"), (5, "comment")):
			with self.subTest(style=style):
				self.assertEqual(
					self.events(self.info([("x", style | 0x80), (" ", 0)])),
					[
						("begin", kind),
						("end", kind),
					],
				)
		self.assertEqual(self.editor.styleStack(20), ("comment",) * 16)
		self.assertEqual(self.editor.styleStack(21), ())

	def test_nested_and_adjacent_comments(self) -> None:
		info = self.info([("[a ", 5), ("[b]", 6), (" c]", 5), (" ", 0)])
		self.assertEqual(
			self.events(info),
			[
				("begin", "comment"),
				("begin", "comment"),
				("end", "comment"),
				("end", "comment"),
			],
		)
		self.assertEqual(
			self.events(self.info([("[a][b]", 5)])),
			[
				("begin", "comment"),
				("end", "comment"),
			]
			* 2,
		)

	def test_partial_and_multiline_ranges(self) -> None:
		parts = [('"one\ntwo"', 1), (".", 0)]
		self.assertEqual(self.events(self.info(parts, 2, 4)), [])
		self.assertEqual(
			self.events(self.info(parts, 0, 4)),
			[("begin", "quoted text")],
		)
		self.assertEqual(
			self.events(self.info(parts, 5, 9)),
			[("end", "quoted text")],
		)
		self.assertEqual(self.events(self.info(parts, 5, 8)), [])

	def test_adjacent_substitutions_and_inform6_spans(self) -> None:
		for parts, kind in (
			([('"', 1), ("[a][b]", 2), ('"', 1)], "text substitution"),
			([("(- a -)(- b -)", 3)], "Inform 6 code"),
		):
			whole = self.info(parts)
			expected = self.events(whole)
			self.assertEqual(
				[e for e in expected if e[1] == kind],
				[
					("begin", kind),
					("end", kind),
				]
				* 2,
			)
			for split in whole.boundaries[1:-1]:
				self.assertEqual(
					self.events(self.info(parts, 0, split)) + self.events(self.info(parts, split)),
					expected,
				)

	def test_quote_can_end_substitution_and_outer_quote_together(self) -> None:
		self.assertEqual(
			self.events(self.info([('"', 1), ('[name"', 2)])),
			[
				("begin", "quoted text"),
				("begin", "text substitution"),
				("end", "text substitution"),
				("end", "quoted text"),
			],
		)

	def test_adjacent_chunks_equal_whole_read_without_cache_deduplication(self) -> None:
		parts = [('"a', 1), ("[x]", 2), ('"', 1), ("[c]", 5), (".", 0)]
		whole = self.info(parts)
		expected = self.events(whole)
		for split in whole.boundaries[1:-1]:
			self.assertEqual(
				self.events(self.info(parts, 0, split)) + self.events(self.info(parts, split)),
				expected,
			)
		self.assertEqual(self.events(whole), expected)
		self.assertEqual(self.spoken(whole), self.spoken(whole))

	def test_unfinished_eof_never_invents_closures(self) -> None:
		for parts, ends in (
			([('"unfinished', 1)], []),
			([('"', 1)], []),
			([("say ", 0), ('"', 1)], []),
			([('"hi ', 1), ("[name", 2)], []),
			([('"hi ', 1), ("[name]", 2)], [("end", "text substitution")]),
			([("[a ", 5), ("[b]", 6)], [("end", "comment")]),
			([("[unfinished", 5)], []),
			([("(- unfinished", 3)], []),
		):
			with self.subTest(parts=parts):
				self.assertEqual(
					[
						e
						for e in self.events(
							self.info(parts),
						)
						if e[0] == "end"
					],
					ends,
				)

	def test_complete_eof_and_utf8(self) -> None:
		for text, style, kind in (
			('""', 1, "quoted text"),
			("“é🙂”", 1, "quoted text"),
			("[]", 5, "comment"),
			("(- code -)", 3, "Inform 6 code"),
			("Section Test", 4, "heading"),
		):
			self.assertEqual(
				self.events(self.info([(text, style)])),
				[
					("begin", kind),
					("end", kind),
				],
			)
		parts = [("say é ", 0), ('"🙂', 1), ("[café]", 2), ("”", 1)]
		whole = self.info(parts)
		for split in whole.boundaries[1:-1]:
			self.assertEqual(
				self.events(self.info(parts, 0, split)) + self.events(self.info(parts, split)),
				self.events(whole),
			)

	def test_character_typing_and_formatting_queries_are_silent(self) -> None:
		info = self.info([('"hi"', 1)])
		for unit, reason in (("character", "caret"), (None, "typing"), (None, "query")):
			self.assertFalse(
				any("Begin" in s or "End" in s for s in self.spoken(info, unit, reason)),
			)
		field, _ = info._getFormatFieldAndOffsets(0, FORMAT, False)
		self.assertNotIn(self.editor.SYNTAX_FIELD, field)
		for unit, reason in (
			("word", "caret"),
			("line", "caret"),
			("paragraph", "caret"),
			("readingChunk", "sayAll"),
			(None, "sayAll"),
		):
			self.assertIn("Begin quoted text", self.spoken(info, unit, reason))

	def test_word_reading_announces_entry_and_exit_at_actual_boundaries(self) -> None:
		parts = [('"hello ', 1), ("[name]", 2), (' friend"', 1), (".", 0)]
		for start, end, expected in (
			(0, 7, ["Begin quoted text", '"hello ']),
			(
				7,
				13,
				[
					"Begin text substitution",
					"[name]",
					"End text substitution",
				],
			),
			(14, 21, ['friend"', "End quoted text"]),
			(1, 6, ["hello"]),
		):
			info = self.info(parts, start, end)
			self.assertEqual(self.spoken(info, "word"), expected)
			self.assertEqual(self.spoken(info, "word"), expected)
		self.conf["inform7"]["automaticallyReadSyntaxHighlighting"] = False
		self.assertEqual(
			self.spoken(
				self.info(parts, 7, 13),
				"word",
			),
			["[name]"],
		)

	def test_character_delimiters_keep_nvda_single_character_spelling_path(self) -> None:
		parts = [('"', 1), ("[x]", 2), ('"', 1), (" ", 0), ("[c]", 5)]
		for start in (0, 1, 3, 4, 6, 8):
			for expanded in (False, True):
				info = self.info(parts, start, start + 1)
				if expanded:
					info.expand("character")
					info = info.copy()
				fields = info.getTextWithFields(FORMAT | {"extraDetail": True})
				# NVDA removes initial fields, then requires one text string and
				# no trailing formatChange to spell punctuation independently of
				# the normal sentence punctuation verbosity.
				while fields and not isinstance(fields[0], str):
					self.assertNotIn(
						self.editor.SYNTAX_FIELD,
						fields.pop(0).field,
					)
				self.assertEqual(fields, [info.text])

	def test_word_closing_delimiter_keeps_marker_after_copy(self) -> None:
		info = self.info([('"hi"', 1)], 3, 4)
		info.expand("word")
		info = info.copy()
		self.assertEqual(
			self.events(info, FORMAT | {"extraDetail": True}),
			[
				("end", "quoted text"),
			],
		)
		self.assertEqual(self.spoken(info, "word"), ['"', "End quoted text"])
		info.expand("character")
		self.assertEqual(self.events(info, FORMAT | {"extraDetail": True}), [])

	def test_syntax_ignores_detect_format_after_cursor_but_preserves_text(self) -> None:
		info = self.info([("say ", 0), ('"hi ', 1), ("[name]", 2), ('".', 1)])
		for detect in (False, True):
			fields = info.getTextWithFields(
				FORMAT | {"detectFormatAfterCursor": detect},
			)
			self.assertEqual(
				"".join(item for item in fields if isinstance(item, str)),
				info.text,
			)
			self.assertEqual(
				len(self.events(info, FORMAT | {"detectFormatAfterCursor": detect})),
				3,
			)
		# No overrides of text, clipboard or braille methods; metadata is speech-only.
		for name in ("_get_text", "copyToClipboard", "getFormatFieldBraille", "getControlFieldBraille"):
			self.assertNotIn(name, self.editor.InformSourceTextInfo.__dict__)

	def test_renderer_supports_speech_commands_and_retains_normal_speech(self) -> None:
		info = self.info([('"hi"', 1)])
		command = object()
		with patch.object(self.editor, "renderMarker", return_value=[command]):
			seq = info.getFormatFieldSpeech(
				Field(
					speakNormal=True,
					**{self.editor.SYNTAX_FIELD: (("begin", "quoted text"),)},
				),
				unit="line",
			)
		self.assertEqual(seq, ["normal formatting", command])

	def test_failure_falls_back_without_source_in_log(self) -> None:
		info = self.info([('"private source"', 1)])
		with patch.object(info, "_syntaxEvents", side_effect=RuntimeError("private source")):
			self.assertEqual(self.events(info), [])
			self.assertEqual(
				"".join(x for x in info.getTextWithFields() if isinstance(x, str)),
				info.text,
			)
		self.assertNotIn("private source", str(self.log.mock_calls))

	def test_style_sampling_is_local_to_requested_range(self) -> None:
		info = self.info(
			[
				("a" * 10000, 0),
				('"hi"', 1),
				("b" * 10000, 0),
			],
			10000,
			10004,
		)
		_ = self.events(info)
		positions = [offset for message, offset in info.queries if message == 2010]
		self.assertTrue(all(9999 <= pos <= 10004 for pos in positions))
		self.assertLess(len(positions), 12)


if __name__ == "__main__":
	_ = unittest.main()
