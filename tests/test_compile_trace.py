"""Exercise opt-in trace lifecycle and saved records without a live NVDA process."""

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from typing import Any, override
from unittest.mock import Mock, patch

from test_inform import InformTestCase


class CompileTraceTests(InformTestCase):
	@override
	def setUp(self) -> None:
		super().setUp()
		self.now = 0.0
		self.controller = self.app.compileFocus
		self.controller.clock = lambda: self.now
		self.trace = self.controller.trace
		directory = tempfile.TemporaryDirectory()
		self.addCleanup(directory.cleanup)
		self.addCleanup(self.trace.stop, "test cleanup")
		self.trace.directory = Path(directory.name)
		self.editor = SimpleNamespace(
			processID=123,
			windowHandle=10,
			windowClassName="Scintilla",
			role="edit",
			IAccessibleChildID=0,
			IA2UniqueID=1,
			value="private editor contents",
			name="Source",
			states=set(),
			treeInterceptor=None,
		)
		self.api.getFocusObject.return_value = self.editor

	def rows(self) -> list[dict[str, Any]]:
		assert self.trace.path is not None
		return [json.loads(line) for line in self.trace.path.read_text(encoding="utf-8").splitlines()]

	def begin(self) -> None:
		self.app.script_traceCompilation(Mock())
		self.app.script_compile(Mock())

	def test_disabled_trace_does_no_property_inspection_or_file_io(self) -> None:
		self.controller.start()
		with patch.object(self.trace, "belongs") as inspectObject:
			self.trace.record("test", self.editor)
		inspectObject.assert_not_called()
		self.assertEqual(list(self.trace.directory.iterdir()), [])

	def test_arming_starts_on_f5_and_records_baseline_without_editor_value(self) -> None:
		self.app.script_traceCompilation(Mock())
		self.assertTrue(self.trace.armed)
		self.assertEqual(list(self.trace.directory.iterdir()), [])
		gesture = Mock()
		self.app.script_compile(gesture)
		gesture.send.assert_called_once()
		self.assertFalse(self.trace.armed)
		self.assertEqual(self.rows()[0]["event"], "traceStart")
		self.assertNotIn("private editor contents", str(self.rows()))

	def test_tab_panel_decision_and_ancestors_are_recorded(self) -> None:
		self.begin()
		doc = SimpleNamespace(**vars(self.editor))
		doc.windowClassName = "Chrome_RenderWidgetHostHWND"
		doc.role = "document"
		doc.value = "file:///Test/Build/Problems.html"
		parent = SimpleNamespace(**vars(self.editor))
		parent.role = "tabcontrol"
		parent.windowClassName = "AfxWnd140s"
		parent.name = "tab panel"
		self.api.getFocusObject.return_value = doc
		self.api.getFocusAncestors.return_value = [parent]
		handler = Mock()
		self.app.event_focusEntered(parent, handler)
		handler.assert_not_called()
		row = self.rows()[-1]
		self.assertEqual(row["event"], "focusEntered")
		self.assertTrue(row["suppressed"])
		self.assertEqual(row["ancestors"][0]["role"], "tabcontrol")
		self.assertEqual(row["focus"]["documentURL"], doc.value)

	def test_early_cancellation_keeps_trace_until_quiet_tail(self) -> None:
		self.begin()
		self.app.event_gainFocus(self.editor, Mock())
		self.assertFalse(self.controller.active)
		self.assertIsNotNone(self.trace.stream)
		self.assertIn("unexpected focus destination", str(self.rows()))
		self.now = 14
		self.trace.record("laterEvent", self.editor)
		self.now = 15
		self.controller.poll()
		self.assertIsNotNone(self.trace.stream)
		self.now = 17
		self.controller.poll()
		self.assertIsNone(self.trace.stream)
		self.assertEqual(self.rows()[-1]["reason"], "capture settled")

	def test_repeated_f5_keeps_the_same_file_and_both_sessions(self) -> None:
		self.begin()
		path = self.trace.path
		self.app.script_compile(Mock())
		self.assertEqual(self.trace.path, path)
		self.assertEqual(sum(row["event"] == "suppressionStart" for row in self.rows()), 2)

	def test_switching_projects_stops_before_recording_other_window(self) -> None:
		self.begin()
		self.winUser.getForegroundWindow.return_value = 2
		self.editor.name = "other application private title"
		self.trace.record("focusEntered", self.editor)
		self.assertIsNone(self.trace.stream)
		self.assertNotIn("other application", str(self.rows()))
		self.winUser.getForegroundWindow.return_value = 1
		self.trace.record("return", self.editor)
		self.assertEqual(self.rows()[-1]["event"], "traceEnd")

	def test_property_failure_does_not_abort_capture(self) -> None:
		self.begin()

		class BrokenName:
			processID = 123
			windowHandle = 10

			@property
			def name(self) -> str:
				raise RuntimeError("provider disappeared")

		self.trace.record("focusEntered", BrokenName())
		self.assertEqual(self.rows()[-1]["object"]["name"], {"error": "RuntimeError"})
		self.assertIsNotNone(self.trace.stream)

	def test_trace_failure_never_prevents_f5(self) -> None:
		self.trace.directory = self.trace.directory / "file"
		self.trace.directory.write_text("occupied", encoding="utf-8")
		self.app.script_traceCompilation(Mock())
		gesture = Mock()
		self.app.script_compile(gesture)
		gesture.send.assert_called_once()
		self.assertTrue(self.controller.active)
		self.assertIsNone(self.trace.stream)

	def test_manual_stop_disarm_and_reload(self) -> None:
		self.app.script_traceCompilation(Mock())
		self.app.script_traceCompilation(Mock())
		self.assertFalse(self.trace.armed)
		self.begin()
		self.app.script_traceCompilation(Mock())
		self.assertIsNone(self.trace.stream)
		self.assertIn("trace stopped", self.ui.message.call_args.args[0])
		self.begin()
		self.app.terminate()
		self.assertIsNone(self.trace.stream)
		self.assertEqual(self.rows()[-1]["reason"], "module terminated")

	def test_time_and_event_limits(self) -> None:
		self.begin()
		self.now = 120
		self.trace.poll(True)
		self.assertEqual(self.rows()[-1]["reason"], "120 second limit")
		self.begin()
		self.trace.count = 3999
		self.trace.record("lastEvent", self.editor)
		self.assertEqual(self.rows()[-1]["reason"], "event limit")

	def test_report_url_and_unowned_identity_remain_diagnosable(self) -> None:
		self.begin()
		obj = SimpleNamespace(**vars(self.editor))
		obj.role = "document"
		obj.value = None
		obj.treeInterceptor = SimpleNamespace(documentURL="file:///Example/Build/Problems.html")
		self.trace.record("gainFocus", obj)
		self.assertEqual(self.rows()[-1]["object"]["documentURL"], obj.treeInterceptor.documentURL)
		self.winUser.getAncestor.return_value = 0
		self.trace.record("gainFocus", obj)
		row = self.rows()[-1]
		self.assertNotIn("object", row)
		self.assertEqual(row["eventIdentity"]["nativeRoot"], 0)
		self.assertEqual(row["focusIdentity"]["windowClassName"], "Scintilla")
