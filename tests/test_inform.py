"""Test add-on orchestration without claiming to emulate NVDA's text diffing."""

import importlib.util
from difflib import SequenceMatcher
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class FakeLiveText:
    def __init__(self):
        self._keepMonitoring = False
        self.startCount = 0
        self.changeCount = 0
        self.spoken = []
        self.typed = []

    def startMonitoring(self):
        self._keepMonitoring = True
        self.startCount += 1

    def stopMonitoring(self):
        self._keepMonitoring = False

    def event_textChange(self):
        self.changeCount += 1

    def event_typedCharacter(self, ch):
        self.typed.append(ch)

    def _calculateNewText(self, newText, oldText):
        # A small stand-in for NVDA's insertion diff; exercise the real input
        # tracker, not NVDA's external diff implementation.
        return [
            newText[j1:j2]
            for tag, i1, i2, j1, j2 in SequenceMatcher(None, oldText, newText).get_opcodes()
            if tag in ("insert", "replace")
        ]

    def _reportNewLines(self, lines):
        for line in lines:
            self._reportNewText(line)

    def _reportNewText(self, line):
        self.spoken.append(line)


class FakeAppModule:
    processID = 123

    def terminate(self):
        pass


class FakeTimer:
    def __init__(self, callback):
        self.callback = callback
        self.running = False

    def Start(self, interval):
        self.running = True

    def Stop(self):
        self.running = False


class InformTests(unittest.TestCase):
    def setUp(self):
        self.api = SimpleNamespace(getFocusObject=Mock(return_value=None))
        self.config = SimpleNamespace(
            conf={"presentation": {"reportDynamicContentChanges": True}})
        self.log = Mock()
        self.ui = SimpleNamespace(message=Mock())
        self.speech = SimpleNamespace(speakSpelling=Mock())
        self.scriptHandler = SimpleNamespace(
            script=lambda **kwargs: lambda func: func, getLastScriptRepeatCount=Mock(return_value=0),
        )
        self.getObject = Mock()
        self.winUser = SimpleNamespace(
            ES_MULTILINE=4, GW_HWNDNEXT=2, OBJID_CLIENT=-4)
        stubs = {
            "api": self.api,
            "appModuleHandler": SimpleNamespace(AppModule=FakeAppModule),
            "config": self.config,
            "controlTypes": SimpleNamespace(
                Role=SimpleNamespace(
                    EDITABLETEXT="edit", UNKNOWN="unknown"),
                State=SimpleNamespace(
                    MULTILINE="multiline", INVISIBLE="invisible", OFFSCREEN="offscreen"),
            ),
            "wx": SimpleNamespace(PyTimer=FakeTimer),
            "winUser": self.winUser,
            "logHandler": SimpleNamespace(log=self.log),
            "scriptHandler": self.scriptHandler,
            "speech": self.speech,
            "ui": self.ui,
            "NVDAObjects": SimpleNamespace(),
            "NVDAObjects.behaviors": SimpleNamespace(LiveText=FakeLiveText),
            "NVDAObjects.IAccessible": SimpleNamespace(getNVDAObjectFromEvent=self.getObject),
        }
        with patch.dict(sys.modules, stubs):
            spec = importlib.util.spec_from_file_location(
                "inform_under_test", Path(__file__).resolve(
                ).parents[1] / "addon/appModules/inform.py"
            )
            self.inform = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.inform)
        self.app = self.inform.AppModule()
        self.addCleanup(self.app.terminate)
        self.obj = self.inform.InterpreterOutput()
        self.obj.initOverlayClass()
        self.obj.appModule = self.app
        self.obj.windowHandle = 42
        self.obj.windowClassName = "RICHEDIT50W"
        self.obj.windowStyle = 1344282884
        self.obj.role = "edit"
        self.obj.IAccessibleChildID = 0

    def focus(self):
        self.api.getFocusObject.return_value = self.obj
        self.app._poll()

    def test_match_excludes_other_controls_and_children(self):
        attrs = dict(windowClassName="RICHEDIT50W", role="edit",
                     windowStyle=4, IAccessibleChildID=0)
        self.assertTrue(self.inform.isInterpreterCandidate(
            SimpleNamespace(**attrs)))
        for change in (
                {"windowClassName": "Scintilla"},
                {"role": "window"},
                {"windowStyle": 0},
                {"IAccessibleChildID": 1},
        ):
            with self.subTest(change=change):
                self.assertFalse(self.inform.isInterpreterCandidate(
                    SimpleNamespace(**(attrs | change))))

    def test_overlay_selected_before_rich_edit_adds_multiline_state(self):
        # Before dynamic class construction, raw MSAA has no MULTILINE state.
        obj = SimpleNamespace(
            windowClassName="RICHEDIT50W", role="edit", states={"focused", "focusable"},
            windowStyle=1344282884, IAccessibleChildID=0,
        )
        classes = [FakeLiveText]
        self.app.chooseNVDAObjectOverlayClasses(obj, classes)
        self.assertIs(classes[0], self.inform.InterpreterOutput)

    def test_source_overlay_is_scoped_to_scintilla_client_controls(self):
        sourceOverlay = type("InformSourceEditor", (), {})
        register = Mock()
        with patch.dict(sys.modules, {
                "appModules.inform7Support": SimpleNamespace(registerConfig=register),
                "appModules.inform7Support.editor": SimpleNamespace(InformSourceEditor=sourceOverlay),
        }):
            for className, childID, matched in (("Scintilla", 0, True), ("Scintilla", 1, False),
                                                ("Edit", 0, False), ("RichEdit", 0, False)):
                classes = []
                obj = SimpleNamespace(
                    windowClassName=className, IAccessibleChildID=childID)
                self.app.chooseNVDAObjectOverlayClasses(obj, classes)
                self.assertEqual(classes, [sourceOverlay] if matched else [])
        register.assert_called_once_with()

    def test_debug_logs_focus_and_reporting_transitions_without_poll_spam(self):
        self.focus()
        self.log.debug.reset_mock()
        self.app._poll()
        self.app._poll()
        self.log.debug.assert_not_called()
        self.config.conf["presentation"]["reportDynamicContentChanges"] = False
        self.app._poll()
        self.assertIn("focus check", self.log.debug.call_args.args[0])
        self.assertEqual(
            self.log.debug.call_args.args[1:4], (True, False, True))
        self.app.event_appModule_loseFocus()
        self.assertFalse(self.obj._keepMonitoring)
        self.log.info.assert_not_called()

    def test_missing_overlay_is_logged_for_focused_candidate(self):
        self.api.getFocusObject.return_value = SimpleNamespace(
            windowClassName="RICHEDIT50W", role="edit", windowStyle=4,
            IAccessibleChildID=0, appModule=self.app,
        )
        self.app._poll()
        self.log.warning.assert_called_once()
        self.assertIn("has no overlay", self.log.warning.call_args.args[0])

    def test_poll_starts_once_and_updates_while_reporting_disabled(self):
        self.focus()
        self.config.conf["presentation"]["reportDynamicContentChanges"] = False
        self.app._timer.callback()
        self.app._timer.callback()
        self.assertEqual(self.obj.startCount, 1)
        self.assertEqual(self.obj.changeCount, 2)
        self.assertTrue(self.obj.hasContentChangedSinceLastSelection)

    def test_focus_departure_stops_and_return_restarts(self):
        self.focus()
        self.api.getFocusObject.return_value = None
        self.app._poll()
        self.assertFalse(self.obj._keepMonitoring)
        self.focus()
        self.assertEqual(self.obj.startCount, 2)

    def test_other_inform_process_is_not_monitored(self):
        self.obj.appModule = object()
        self.focus()
        self.assertEqual(self.obj.startCount, 0)

    def test_queued_speech_is_gated_by_setting_focus_and_monitoring(self):
        self.focus()
        self.obj._reportNewLines(["A new room"])
        self.config.conf["presentation"]["reportDynamicContentChanges"] = False
        self.obj._reportNewLines(["Disabled"])
        self.obj._reportNewText("Disabled delayed line")
        self.config.conf["presentation"]["reportDynamicContentChanges"] = True
        self.api.getFocusObject.return_value = None
        self.obj._reportNewLines(["Old focus"])
        self.obj._reportNewText("Old focus delayed line")
        self.api.getFocusObject.return_value = self.obj
        self.app._stopMonitoring()
        self.obj._reportNewLines(["Stopped"])
        self.assertEqual(self.obj.spoken, ["A new room"])

    def test_text_uses_fresh_window_getter_and_normalizes_newlines(self):
        self.obj._get_windowText = Mock(
            side_effect=["one\r\ntwo\r", "changed"])
        self.assertEqual(self.obj._getText(), "one\ntwo\n")
        self.assertEqual(self.obj._getText(), "changed")

    def test_terminate_stops_timer_and_monitor_and_stale_callback(self):
        self.focus()
        self.app.terminate()
        self.app._timer.callback()
        self.assertFalse(self.app._timer.running)
        self.assertFalse(self.obj._keepMonitoring)
        self.assertEqual(self.obj.startCount, 1)

    def test_focus_event_preserves_normal_nvda_handling(self):
        self.api.getFocusObject.return_value = self.obj
        nextHandler = Mock()
        self.app.event_gainFocus(self.obj, nextHandler)
        nextHandler.assert_called_once_with()

    def test_typed_echo_filter_handles_bursts_and_preserves_response(self):
        adjust = self.inform.accountForTypedText
        self.assertEqual(adjust("room\n>", "room\n>look",
                         "look"), ("room\n>look", ""))
        self.assertEqual(adjust("room\n>", "room\n>lo",
                         "look"), ("room\n>lo", "ok"))
        self.assertEqual(
            adjust("room\n>", "room\n>lookTaken.\n>",
                   "look"), ("room\n>look", ""),
        )

    def test_typed_echo_filter_handles_middle_insertion_and_selection_replacement(self):
        adjust = self.inform.accountForTypedText
        self.assertEqual(adjust(">get lamp", ">get red lamp",
                         "red "), (">get red lamp", ""))
        self.assertEqual(adjust(">open door", ">close door",
                         "close"), (">close door", ""))
        self.assertEqual(adjust(">go north", ">go south",
                         "south"), (">go south", ""))

    def test_output_and_unobserved_keystrokes_are_not_confused(self):
        adjust = self.inform.accountForTypedText
        self.assertEqual(adjust(">", ">", "look"), (">", "look"))
        self.assertEqual(adjust(">", ">locked", "look"), (">", ""))
        self.assertEqual(adjust(">look", ">loo", "stale"), (">look", ""))
        self.assertEqual(adjust(">", ">Taken.", ""), (">", ""))

    def readAndDiff(self, text):
        oldText = getattr(self.obj, "_lastReadText", "")
        self.obj._get_windowText = Mock(return_value=text)
        newText = self.obj._getText()
        return self.obj._calculateNewText(newText, oldText)

    def typeText(self, text):
        for ch in text:
            self.obj.event_typedCharacter(ch)

    def test_fast_typing_is_silent_but_next_output_is_reported(self):
        self.readAndDiff("room\n>")
        self.typeText("get ")
        self.assertEqual(self.readAndDiff("room\n>get "), [])
        self.typeText("lamp")
        self.assertEqual(self.readAndDiff("room\n>get lamp"), [])
        self.assertEqual(self.readAndDiff("room\n>get lampTaken."), ["Taken."])
        self.assertEqual("".join(self.obj.typed), "get lamp")

    def test_enter_before_poll_preserves_same_line_response(self):
        self.readAndDiff("room\n>")
        self.typeText("look")
        self.obj._get_windowText = Mock(return_value="room\n>look")
        gesture = Mock()
        self.obj.script_submitCommand(gesture)
        gesture.send.assert_called_once_with()
        self.assertEqual(self.readAndDiff(
            "room\n>lookYou see a lamp.\n>"), ["You see a lamp.\n>"])

    def test_enter_snapshot_does_not_discard_unreported_output(self):
        self.readAndDiff("room\n>")
        self.typeText("look")
        self.obj._get_windowText = Mock(
            return_value="room\n>A bell rings.\n>look")
        self.obj.script_submitCommand(Mock())
        self.assertIsNone(self.obj._submittedBaseline)
        self.assertIn("A bell rings.", "".join(
            self.readAndDiff("room\n>A bell rings.\n>lookA lamp.\n>")))

    def test_history_navigation_is_inherited_and_history_text_is_not_typed(self):
        self.assertNotIn("script_caret_moveByLine",
                         self.inform.InterpreterOutput.__dict__)
        self.readAndDiff("room\n>")
        self.typeText("north")
        self.assertEqual(self.readAndDiff("room\n>north"), [])
        # History still receives exactly the normal diff, while the inherited
        # arrow script remains responsible for speaking the full recalled line.
        expected = FakeLiveText._calculateNewText(
            self.obj, "room\n>look", "room\n>north")
        self.assertEqual(self.readAndDiff("room\n>look"), expected)
        self.assertEqual(self.readAndDiff("room\n>"), [])

    def test_input_tracking_stays_current_with_dynamic_reporting_off(self):
        self.readAndDiff(">")
        self.config.conf["presentation"]["reportDynamicContentChanges"] = False
        self.typeText("look")
        self.obj._get_windowText = Mock(return_value=">look")
        self.obj._getText()  # LiveText skips _calculateNewText while disabled.
        self.assertEqual(self.obj._pendingTypedText, "")
        self.config.conf["presentation"]["reportDynamicContentChanges"] = True
        self.assertEqual(self.readAndDiff(
            ">looklook around."), ["look around."])

    def test_enter_is_forwarded_even_if_snapshot_fails(self):
        self.obj._get_windowText = Mock(
            side_effect=RuntimeError("window gone"))
        gesture = Mock()
        self.obj.script_submitCommand(gesture)
        gesture.send.assert_called_once_with()

    def test_status_padding_becomes_field_separator(self):
        self.assertEqual(
            self.inform.formatStatusText(
                " small cave                         9:00 am         "),
            "small cave, 9:00 am",
        )
        self.assertEqual(self.inform.formatStatusText(" \r\n   "), "")

    def test_status_geometry_matches_log_and_rejects_wrong_panes(self):
        interpreter = SimpleNamespace(
            windowHandle=42, location=(966, 140, 911, 891))
        status = SimpleNamespace(windowHandle=43, location=(966, 118, 928, 22))
        wrong = [
            SimpleNamespace(location=(0, 118, 928, 22)),  # Other side.
            SimpleNamespace(location=(966, 118, 928, 913)),  # Container.
            SimpleNamespace(location=(966, 1040, 928, 22)),  # IDE status bar.
            # Toolbar above pane.
            SimpleNamespace(location=(966, 20, 928, 22)),
        ]
        self.assertIs(self.inform.chooseStoryStatus(
            [interpreter], wrong + [status]), status)
        self.assertIsNone(self.inform.chooseStoryStatus([interpreter], wrong))

    def test_status_prefers_active_interpreter_and_defaults_to_right(self):
        left = SimpleNamespace(windowHandle=10, location=(10, 140, 900, 800))
        right = SimpleNamespace(windowHandle=20, location=(966, 140, 900, 800))
        leftStatus = SimpleNamespace(location=(10, 118, 900, 22))
        rightStatus = SimpleNamespace(location=(966, 118, 900, 22))
        choose = self.inform.chooseStoryStatus
        self.assertIs(
            choose([left, right], [leftStatus, rightStatus]), rightStatus)
        self.assertIs(
            choose([left, right], [leftStatus, rightStatus], 10), leftStatus)

    def test_status_is_fresh_and_independent_of_dynamic_reporting(self):
        status = SimpleNamespace(_get_displayText=Mock(
            side_effect=["cave    9:00 am", "cave    9:01 am"]))
        self.app._findStoryStatus = Mock(return_value=status)
        self.config.conf["presentation"]["reportDynamicContentChanges"] = False
        self.app.script_reportStatusLine(Mock())
        self.app.script_reportStatusLine(Mock())
        self.assertEqual([call.args[0] for call in self.ui.message.call_args_list], [
                         "cave, 9:00 am", "cave, 9:01 am"])

    def test_status_repeat_spells_and_copies(self):
        self.app._findStoryStatus = Mock(return_value=SimpleNamespace(
            _get_displayText=lambda: "cave    noon"))
        self.scriptHandler.getLastScriptRepeatCount.return_value = 1
        self.app.script_reportStatusLine(Mock())
        self.speech.speakSpelling.assert_called_once_with("cave, noon")
        self.scriptHandler.getLastScriptRepeatCount.return_value = 2
        self.api.copyToClip = Mock(return_value=True)
        self.app.script_reportStatusLine(Mock())
        self.api.copyToClip.assert_called_once_with("cave, noon")

    def test_missing_status_is_reported_without_reading_ide_status(self):
        self.app._findStoryStatus = Mock(return_value=None)
        self.app.script_reportStatusLine(Mock())
        self.assertIn("not found", self.ui.message.call_args.args[0])

    def test_status_lookup_uses_visible_native_windows_in_active_process(self):
        self.winUser.getForegroundWindow = Mock(return_value=1)
        self.winUser.getWindowThreadProcessID = Mock(return_value=(123, 99))
        self.winUser.getTopWindow = lambda hwnd: {1: 10}.get(hwnd, 0)
        self.winUser.getWindow = lambda hwnd, relation: {
            10: 20, 20: 30}.get(hwnd, 0)
        self.winUser.isWindowVisible = lambda hwnd: hwnd != 30
        self.winUser.getClassName = lambda hwnd: {
            10: "RICHEDIT50W", 20: "AfxWnd140s"}[hwnd]
        self.obj.processID = 123
        self.obj.windowHandle = 10
        self.obj.location = (966, 140, 911, 891)
        self.obj.states = set()
        status = SimpleNamespace(
            windowHandle=20, processID=123, location=(966, 118, 928, 22), states=set(),
            windowClassName="AfxWnd140s", role="unknown", IAccessibleChildID=0,
        )
        self.getObject.side_effect = lambda hwnd, objectID, childID: {
            10: self.obj, 20: status}[hwnd]
        self.assertIs(self.app._findStoryStatus(), status)
        self.assertEqual(self.getObject.call_count, 2)
        self.winUser.getWindowThreadProcessID.return_value = (999, 99)
        self.assertIsNone(self.app._findStoryStatus())

    def test_line_cursor_navigation_and_boundaries(self):
        cursor = self.inform.LineReadingCursor()
        text = "first\r\nsecond\rthird"
        self.assertEqual(cursor.read(text, "current"), "third")
        self.assertEqual(cursor.read(text, "previous"), "second")
        self.assertEqual(cursor.read(text, "current"), "second")
        self.assertEqual(cursor.read(text, "first"), "first")
        self.assertEqual(cursor.read(text, "previous"), "Top, first")
        self.assertEqual(cursor.read(text, "next"), "second")
        self.assertEqual(cursor.read(text, "last"), "third")
        self.assertEqual(cursor.read(text, "next"), "Bottom, third")

    def test_line_cursor_keeps_position_as_output_arrives_and_text_changes(self):
        cursor = self.inform.LineReadingCursor()
        self.assertEqual(cursor.read("first\nsecond", "current"), "second")
        self.assertEqual(cursor.read(
            "first\nsecond\nnew output", "current"), "second")
        self.assertEqual(cursor.read(
            "first\nchanged second\nnew output", "current"), "changed second")
        self.assertEqual(cursor.read(
            "first\nchanged second\nnew output", "next"), "new output")

    def test_line_cursor_blank_lines_and_shortened_transcript(self):
        cursor = self.inform.LineReadingCursor()
        self.assertEqual(cursor.read("first\n\n", "last"), "blank")
        self.assertEqual(cursor.read("first\n\n", "previous"), "blank")
        self.assertEqual(cursor.read("restart", "current"), "Bottom, restart")
        self.assertEqual(cursor.read("", "previous"), "Top, blank")
        self.assertEqual(cursor.read("", "next"), "Bottom, blank")

    def test_line_gestures_are_focus_only_and_not_on_app_module(self):
        for name in ("readPreviousLine", "readCurrentLine", "readNextLine", "readLastLine", "readFirstLine"):
            with self.subTest(name=name):
                gesture = Mock()
                getattr(self.obj, "script_" + name)(gesture)
                gesture.send.assert_called_once_with()
                self.assertNotIn("script_" + name,
                                 self.inform.AppModule.__dict__)
        self.ui.message.assert_not_called()

    def test_line_gestures_use_fresh_text_without_changing_live_text_state(self):
        self.api.getFocusObject.return_value = self.obj
        self.config.conf["presentation"]["reportDynamicContentChanges"] = False
        self.obj._lastReadText = "monitor baseline"
        self.obj._preparedDiff = ("monitor", "baseline")
        self.obj._get_windowText = Mock(return_value="first\nsecond\n>")
        gesture = Mock()
        self.obj.script_readFirstLine(gesture)
        self.obj.script_readNextLine(gesture)
        self.typeText("look")
        self.obj._get_windowText.return_value = "first\nsecond updated\n>look\nresponse\n>"
        self.obj.script_readCurrentLine(gesture)
        self.obj.script_readLastLine(gesture)
        self.obj.script_readPreviousLine(gesture)
        self.assertEqual(
            [call.args[0] for call in self.ui.message.call_args_list],
            ["first", "second", "second updated", ">", "response"],
        )
        self.assertEqual(self.obj._lastReadText, "monitor baseline")
        self.assertEqual(self.obj._preparedDiff, ("monitor", "baseline"))
        gesture.send.assert_not_called()

    def test_line_cursor_persists_across_object_recreation_and_is_per_window(self):
        self.api.getFocusObject.return_value = self.obj
        self.obj._get_windowText = Mock(return_value="first\nsecond\n>")
        self.obj.script_readFirstLine(Mock())
        recreated = self.inform.InterpreterOutput()
        recreated.initOverlayClass()
        recreated.appModule = self.app
        recreated.windowHandle = self.obj.windowHandle
        recreated._get_windowText = Mock(return_value="first\nsecond\n>typed")
        self.api.getFocusObject.return_value = recreated
        recreated.script_readCurrentLine(Mock())
        self.assertEqual(self.ui.message.call_args.args[0], "first")
        recreated.windowHandle = 99
        recreated.script_readCurrentLine(Mock())
        self.assertEqual(self.ui.message.call_args.args[0], ">typed")

    def test_line_read_failure_keeps_position_and_does_not_speak_cached_text(self):
        self.api.getFocusObject.return_value = self.obj
        self.obj._get_windowText = Mock(return_value="first\nsecond")
        self.obj.script_readFirstLine(Mock())
        self.obj._get_windowText.side_effect = RuntimeError(
            "window unavailable")
        self.obj.script_readNextLine(Mock())
        self.assertIn("Unable to read", self.ui.message.call_args.args[0])
        self.assertEqual(self.app._lineReadingCursors[42].index, 0)


if __name__ == "__main__":
    unittest.main()
