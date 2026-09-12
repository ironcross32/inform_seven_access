"""Synthetic focus sequences use no recorded titles, handles, or story text."""

from typing import Any, override
from types import SimpleNamespace
from unittest.mock import Mock, patch

from test_inform import InformTestCase, FakeChromeVBuf, FakeDocument


class CompileFocusTests(InformTestCase):
	def missingRoot(self, hwnd: int, flags: int) -> int:
		return 0 if hwnd == 99 else 1

	# Structural sequence from the capture; synthetic IDs and no project titles.
	COMPILE_ANCESTORS = (
		("window", "Afx:ABC:b:10003:0:0"),
		("pane", "Afx:ABC:b:10003:0:0"),
		("window", "AfxWnd140s"),
		("tabcontrol", "AfxWnd140s"),
		("pane", "AfxWnd140s"),
		("window", "AfxMDIFrame140s"),
		("pane", "AfxMDIFrame140s"),
		("pane", "Chrome_WidgetWin_1"),
	)

	@override
	def setUp(self) -> None:
		super().setUp()
		self.now = 0.0
		self.controller = self.app.compileFocus
		self.controller.clock = lambda: self.now
		self.editor = self.destination(10, "edit", "Scintilla")
		self.api.getFocusObject.return_value = self.editor

	def destination(
		self,
		unique: int,
		role: str = "document",
		windowClass: str = "Chrome_RenderWidgetHostHWND",
		url: str = "file:///X/Index.html",
	) -> Any:
		return SimpleNamespace(
			processID=123,
			windowHandle=10,
			IA2UniqueID=unique,
			IAccessibleChildID=0,
			windowClassName=windowClass,
			windowStyle=0,
			role=role,
			value=url,
			states=set(),
			treeInterceptor=None,
			appModule=self.app,
			event_gainFocus=Mock(),
		)

	def browser(self, unique: int = 20, report: bool = False) -> Any:
		obj = self.destination(
			unique,
			url="file:///X/Build/Problems.html" if report else "file:///X/Index.html",
		)
		buffer = self.compileModule.InformChromeVBuf()
		buffer.rootNVDAObject = obj
		buffer.rootID = unique
		buffer.isReady = True
		buffer.isLoading = False
		obj.treeInterceptor = buffer
		return obj

	def arrive(self, obj: Any) -> Mock:
		self.api.getFocusObject.return_value = obj
		nextHandler = Mock()
		self.app.event_gainFocus(obj, nextHandler)
		return nextHandler

	def advance(self, seconds: float) -> None:
		self.now += seconds
		self.app._poll()

	def test_success_sequence_releases_before_interpreter_ancestors(self) -> None:
		self.app.script_compile(Mock())
		pane = self.destination(11, "pane", "Afx:ABC123:0")
		last = self.browser(23)
		for obj in [pane, self.browser(21), self.browser(22), last]:
			_ = self.arrive(obj).assert_not_called()
			parent = Mock()
			self.app.event_focusEntered(pane, parent)
			parent.assert_not_called()
			if obj.treeInterceptor:
				obj.treeInterceptor.event_treeInterceptor_gainFocus()
				self.assertFalse(hasattr(obj.treeInterceptor, "presented"))
		old = last.treeInterceptor
		self.obj.processID = 123
		self.api.getFocusObject.return_value = self.obj
		parent = Mock()
		self.app.event_focusEntered(pane, parent)
		parent.assert_called_once()
		_ = self.arrive(self.obj).assert_called_once()
		self.assertTrue(self.obj._keepMonitoring)
		old.event_treeInterceptor_gainFocus()
		self.assertFalse(hasattr(old, "presented"))

	def test_failure_sequence_presents_report_once(self) -> None:
		self.app.script_compile(Mock())
		obj = self.browser(23, report=True)
		for destination in [self.browser(21), self.browser(22), obj]:
			_ = self.arrive(destination).assert_not_called()
		self.advance(0.5)
		self.assertFalse(hasattr(obj.treeInterceptor, "presented"))
		self.advance(0.25)
		self.assertEqual(obj.treeInterceptor.presented, 1)
		self.advance(10)
		self.assertEqual(obj.treeInterceptor.presented, 1)
		self.assertFalse(self.controller.active)

	def test_delayed_readiness_and_busy_restart_settling(self) -> None:
		self.controller.start()
		obj = self.browser(report=True)
		obj.treeInterceptor.isReady = False
		_ = self.arrive(obj)
		self.advance(5)
		obj.treeInterceptor.isReady = True
		self.advance(0.25)
		self.advance(0.5)
		obj.states.add("busy")
		self.app.event_stateChange(obj, Mock())
		self.advance(1)
		obj.states.clear()
		self.advance(0.25)
		self.advance(0.5)
		self.assertTrue(self.controller.active)
		self.advance(0.25)
		self.assertEqual(obj.treeInterceptor.presented, 1)

	def test_loading_and_document_replacement_reset_interval(self) -> None:
		self.controller.start()
		obj = self.browser(report=True)
		_ = self.arrive(obj)
		self.advance(0.5)
		obj.IA2UniqueID += 1
		self.advance(0.25)
		self.advance(0.5)
		self.app.event_documentLoadComplete(obj, Mock())
		self.advance(0.25)
		self.advance(0.5)
		self.assertTrue(self.controller.active)
		self.advance(0.25)
		self.assertFalse(self.controller.active)

	def test_recreated_python_object_keeps_native_identity(self) -> None:
		self.controller.start()
		obj = self.browser(report=True)
		_ = self.arrive(obj)
		self.advance(0.5)
		recreated = SimpleNamespace(**vars(obj))
		self.api.getFocusObject.return_value = recreated
		self.advance(0.25)
		self.assertEqual(obj.treeInterceptor.presented, 1)

	def test_repeated_f5_and_stale_completion(self) -> None:
		gesture = Mock()
		self.app.script_compile(gesture)
		oldSerial = self.controller.serial
		_ = self.arrive(self.browser(report=True))
		self.app.script_compile(gesture)
		self.controller.finish(oldSerial)
		self.assertTrue(self.controller.active)
		self.assertEqual(gesture.send.call_count, 2)

	def test_forwarding_error_clears_session(self) -> None:
		gesture = Mock()
		gesture.send.side_effect = RuntimeError()
		with self.assertRaises(RuntimeError):
			self.app.script_compile(gesture)
		gesture.send.assert_called_once()
		self.assertFalse(self.controller.active)

	def test_long_compile_and_timeout_present_current_once(self) -> None:
		self.controller.start()
		obj = self.browser()
		_ = self.arrive(obj)
		self.advance(119)
		self.assertTrue(self.controller.active)
		self.advance(1)
		self.assertEqual(obj.treeInterceptor.presented, 1)
		self.advance(1)
		self.assertEqual(obj.treeInterceptor.presented, 1)

	def test_switch_away_and_return_never_resume(self) -> None:
		for sameProcess in (False, True):
			with self.subTest(sameProcess=sameProcess):
				self.winUser.getForegroundWindow.return_value = 1
				self.controller.start()
				obj = self.browser(report=True)
				_ = self.arrive(obj)
				serial = self.controller.serial
				self.winUser.getForegroundWindow.return_value = 2
				if not sameProcess:
					self.app.event_appModule_loseFocus()
				self.advance(1)
				self.controller.finish(serial)
				obj.treeInterceptor.event_treeInterceptor_gainFocus()
				self.assertFalse(hasattr(obj.treeInterceptor, "presented"))
				self.winUser.getForegroundWindow.return_value = 1
				self.advance(1)
				self.assertFalse(self.controller.active)
				self.assertFalse(hasattr(obj.treeInterceptor, "presented"))

	def test_unknown_dialog_menu_and_editor_receive_normal_handling(self) -> None:
		for role, windowClass in [
			("dialog", "#32770"),
			("menu", "#32768"),
			("edit", "Scintilla"),
			("unknown", "Other"),
			("menuitem", "Chrome_RenderWidgetHostHWND"),
		]:
			with self.subTest(role=role):
				self.api.getFocusObject.return_value = self.editor
				self.controller.start()
				_ = self.arrive(self.destination(50, role, windowClass)).assert_called_once()
				self.assertFalse(self.controller.active)

	def test_gesture_observer_does_not_consume_input(self) -> None:
		for modifier, identifiers, active in [
			(True, ["kb:shift"], True),
			(False, ["kb:f5"], True),
			(False, ["kb:shift+f5"], False),
			(False, ["br:display:route"], False),
		]:
			self.controller.start()
			self.assertTrue(
				self.controller.observeGesture(
					SimpleNamespace(
						isModifier=modifier,
						normalizedIdentifiers=identifiers,
					),
				),
			)
			self.assertEqual(self.controller.active, active)

	def test_inspection_failure_releases_withheld_destination(self) -> None:
		self.controller.start()
		obj = self.browser()
		_ = self.arrive(obj)
		self.controller.interpreter = Mock(side_effect=RuntimeError())
		self.advance(0.25)
		self.assertFalse(self.controller.active)
		self.assertEqual(obj.treeInterceptor.presented, 1)

	def test_reload_unregisters_observer_and_late_callbacks_stay_silent(self) -> None:
		self.controller.start()
		obj = self.browser(report=True)
		_ = self.arrive(obj)
		serial = self.controller.serial
		self.app.terminate()
		self.decider.unregister.assert_called_once_with(self.controller.observeGesture)
		self.controller.finish(serial)
		self.app._timer.callback()
		obj.treeInterceptor.event_treeInterceptor_gainFocus()
		self.assertFalse(hasattr(obj.treeInterceptor, "presented"))

	def test_overlay_installed_outside_compile_and_ordinary_navigation_delegates(self) -> None:
		classes = [FakeDocument]
		obj = self.browser()
		self.app.chooseNVDAObjectOverlayClasses(obj, classes)
		self.assertEqual(classes[0], self.compileModule.InformDocument)
		self.api.getFocusObject.return_value = obj
		obj.treeInterceptor.event_treeInterceptor_gainFocus()
		self.assertEqual(obj.treeInterceptor.presented, 1)
		handler = Mock()
		obj.treeInterceptor.event_gainFocus(obj, handler)
		handler.assert_called_once()
		self.assertIs(
			self.compileModule.InformDocument()._get_treeInterceptorClass(),
			self.compileModule.InformChromeVBuf,
		)
		self.assertIsInstance(obj.treeInterceptor, FakeChromeVBuf)

	def test_report_requires_local_decoded_path(self) -> None:
		for url, completes in [
			("file:///X/%42uild/Problems.html", True),
			("https://example.org/Build/Problems.html", False),
			("file:///X/Build/Problems.html.bak", False),
		]:
			self.api.getFocusObject.return_value = self.editor
			self.controller.start()
			obj = self.browser(report=True)
			obj.value = url
			_ = self.arrive(obj)
			self.advance(0.75)
			self.assertEqual(not self.controller.active, completes)

	def test_f5_waits_for_transition_from_interpreter_or_existing_report(self) -> None:
		self.obj.processID = 123
		for obj in (self.obj, self.browser(report=True)):
			self.api.getFocusObject.return_value = obj
			self.controller.start()
			self.advance(5)
			self.assertTrue(self.controller.active)

	def test_editor_destination_cancels_before_ancestor_presentation(self) -> None:
		self.controller.start()
		parent = Mock()
		self.app.event_focusEntered(self.destination(11, "pane", "Afx:ABC:0"), parent)
		parent.assert_called_once()
		self.assertFalse(self.controller.active)

	def test_report_delegation_preserves_saved_position_and_reading_preferences(self) -> None:
		for autoRead in (False, True):
			self.api.getFocusObject.return_value = self.editor
			self.controller.start()
			obj = self.browser(report=True)
			buffer = obj.treeInterceptor
			buffer.selection = object()
			savedSelection = buffer.selection
			self.config.conf["virtualBuffers"] = {"autoSayAllOnPageLoad": autoRead}
			with patch.object(FakeChromeVBuf, "event_treeInterceptor_gainFocus") as normalPresentation:
				_ = self.arrive(obj)
				buffer.event_treeInterceptor_gainFocus()
				normalPresentation.assert_not_called()
				self.advance(0.75)
				normalPresentation.assert_called_once_with()
			self.assertIs(buffer.selection, savedSelection)
			self.assertEqual(self.config.conf["virtualBuffers"]["autoSayAllOnPageLoad"], autoRead)

	def test_focus_failure_does_not_duplicate_normal_presentation(self) -> None:
		self.controller.start()
		obj = self.browser()
		_ = self.arrive(obj)
		self.controller.interpreter = Mock(side_effect=RuntimeError())
		self.arrive(obj).assert_called_once()
		self.assertFalse(hasattr(obj.treeInterceptor, "presented"))

	def test_foreground_inspection_failure_cancels_without_unsafe_presentation(self) -> None:
		self.controller.start()
		obj = self.browser()
		_ = self.arrive(obj)
		self.winUser.getForegroundWindow.side_effect = RuntimeError()
		self.advance(1)
		self.assertFalse(self.controller.active)
		self.assertFalse(hasattr(obj.treeInterceptor, "presented"))

	def test_switch_after_completion_does_not_replay_report(self) -> None:
		self.controller.start()
		obj = self.browser(report=True)
		_ = self.arrive(obj)
		self.advance(0.75)
		self.winUser.getForegroundWindow.return_value = 2
		self.advance(1)
		obj.treeInterceptor.event_treeInterceptor_gainFocus()
		self.winUser.getForegroundWindow.return_value = 1
		self.advance(1)
		self.assertEqual(obj.treeInterceptor.presented, 1)

	def test_deferred_loading_presentation_is_gated(self) -> None:
		self.controller.start()
		obj = self.browser()
		_ = self.arrive(obj)
		obj.treeInterceptor._loadProgress()
		self.assertFalse(hasattr(obj.treeInterceptor, "loadingReported"))
		self.app.event_appModule_loseFocus()
		self.api.getFocusObject.return_value = self.editor
		obj.treeInterceptor._loadProgress()
		self.assertFalse(hasattr(obj.treeInterceptor, "loadingReported"))
		self.api.getFocusObject.return_value = obj
		obj.treeInterceptor._loadProgress()
		self.assertTrue(obj.treeInterceptor.loadingReported)

	def test_recorded_compile_wrappers_are_silent_until_interpreter_arrives(self) -> None:
		self.controller.start()
		for unique in range(20, 26):
			doc = self.browser(unique)
			self.api.getFocusObject.return_value = doc
			for role, className in self.COMPILE_ANCESTORS:
				with self.subTest(document=unique, role=role, className=className):
					handler = Mock()
					self.app.event_focusEntered(self.destination(30, role, className), handler)
					handler.assert_not_called()
					self.assertTrue(self.controller.active)
			doc.treeInterceptor.event_treeInterceptor_gainFocus()
			self.assertFalse(hasattr(doc.treeInterceptor, "presented"))
			self.arrive(doc).assert_not_called()
		self.obj.processID = 123
		self.api.getFocusObject.return_value = self.obj
		for role, className in self.COMPILE_ANCESTORS:
			handler = Mock()
			self.app.event_focusEntered(self.destination(30, role, className), handler)
			handler.assert_called_once()
		self.assertFalse(self.controller.active)
		self.arrive(self.obj).assert_called_once()

	def test_new_ancestor_types_do_not_expand_actual_focus_suppression(self) -> None:
		for role, className in self.COMPILE_ANCESTORS:
			with self.subTest(role=role, className=className):
				self.api.getFocusObject.return_value = self.editor
				self.controller.start()
				self.api.getFocusObject.return_value = self.destination(30, role, className)
				handler = Mock()
				self.app.event_focusEntered(self.destination(31, "tabcontrol", "AfxWnd140s"), handler)
				handler.assert_called_once()
				self.assertFalse(self.controller.active)

	def test_new_ancestor_filter_excludes_dialogs_menus_and_unrecognized_classes(self) -> None:
		self.controller.start()
		self.api.getFocusObject.return_value = self.browser()
		for role, className in (
			("dialog", "AfxWnd140s"),
			("menu", "AfxWnd140s"),
			("edit", "AfxWnd140s"),
			("tabcontrol", "UnrelatedTabs"),
			("pane", "Afx:invalid"),
		):
			with self.subTest(role=role, className=className):
				handler = Mock()
				self.app.event_focusEntered(self.destination(30, role, className), handler)
				handler.assert_called_once()

	def test_new_ancestors_are_presented_outside_session_or_after_project_switch(self) -> None:
		self.api.getFocusObject.return_value = self.browser()
		parent = self.destination(30, "tabcontrol", "AfxWnd140s")
		handler = Mock()
		self.app.event_focusEntered(parent, handler)
		handler.assert_called_once()
		self.controller.start()
		self.winUser.getForegroundWindow.return_value = 2
		handler = Mock()
		self.app.event_focusEntered(parent, handler)
		handler.assert_called_once()
		self.assertFalse(self.controller.active)

	def test_error_report_uses_buffer_url_when_nvda_value_is_empty(self) -> None:
		self.controller.start()
		obj = self.browser(report=True)
		obj.value = None
		obj.treeInterceptor.documentURL = "about:blank"
		_ = self.arrive(obj)
		self.advance(1)
		self.assertTrue(self.controller.active)
		obj.treeInterceptor.documentURL = "file:///Synthetic/Build/Problems.html"
		self.app.event_documentLoadComplete(obj, Mock())
		self.advance(0.25)
		self.advance(0.75)
		self.assertFalse(self.controller.active)
		self.assertEqual(obj.treeInterceptor.presented, 1)
		self.advance(3)
		self.assertEqual(obj.treeInterceptor.presented, 1)

	def test_native_url_fallback_and_buffer_url_priority(self) -> None:
		obj = self.browser()
		obj.value = None
		obj.IAccessibleObject = SimpleNamespace(
			accValue=Mock(return_value="file:///Test/Build/Problems.html"),
		)
		self.assertEqual(self.compileModule.documentURL(obj), "file:///Test/Build/Problems.html")
		obj.IAccessibleObject.accValue.assert_called_once_with(0)
		obj.treeInterceptor.documentURL = "about:blank"
		self.assertEqual(self.compileModule.documentURL(obj), "about:blank")
		obj.treeInterceptor.documentURL = None
		obj.IAccessibleObject.accValue.side_effect = RuntimeError()
		self.assertEqual(self.compileModule.documentURL(obj), "")

	def test_fast_rerun_bridges_detached_focus_and_unknown_pane(self) -> None:
		self.controller.start()
		pane = self.destination(30, "unknown", "AfxWnd140s")
		pane.name = None
		detached = self.destination(31, "unknown", "Detached")
		detached.windowHandle = 99
		self.winUser.getAncestor.side_effect = self.missingRoot
		self.api.getFocusAncestors.return_value = [pane]
		self.api.getFocusObject.return_value = detached
		handler = Mock()
		self.app.event_focusEntered(pane, handler)
		handler.assert_not_called()
		self.arrive(detached).assert_not_called()
		self.advance(0.03)
		self.arrive(pane).assert_not_called()
		self.advance(0.7)
		self.assertTrue(self.controller.active)
		self.obj.processID = 123
		self.arrive(self.obj).assert_called_once()
		self.assertFalse(self.controller.active)
		self.assertTrue(self.obj._keepMonitoring)

	def test_unknown_pane_grace_expires_and_presents_once(self) -> None:
		self.controller.start()
		pane = self.destination(30, "unknown", "AfxWnd140s")
		_ = self.arrive(pane)
		self.advance(1.5)
		self.assertFalse(self.controller.active)
		pane.event_gainFocus.assert_called_once()
		self.advance(1)
		pane.event_gainFocus.assert_called_once()

	def test_detached_focus_requires_observed_owning_ancestor(self) -> None:
		self.controller.start()
		detached = self.destination(31, "unknown", "Detached")
		detached.windowHandle = 99
		self.winUser.getAncestor.side_effect = self.missingRoot
		self.arrive(detached).assert_called_once()
		self.assertFalse(self.controller.active)

	def test_transient_grace_never_covers_another_project_or_named_control(self) -> None:
		for named in (False, True):
			self.api.getFocusObject.return_value = self.editor
			self.controller.start()
			pane = self.destination(30, "unknown", "AfxWnd140s")
			pane.name = "Unrelated control" if named else None
			if not named:
				self.winUser.getForegroundWindow.return_value = 2
			self.arrive(pane).assert_called_once()
			self.assertFalse(self.controller.active)
			self.winUser.getForegroundWindow.return_value = 1

	def test_real_foreign_window_rejected_even_with_stale_transient_ancestor(self) -> None:
		self.controller.start()
		pane = self.destination(30, "unknown", "AfxWnd140s")
		self.api.getFocusAncestors.return_value = [pane]
		foreign = self.destination(31, "unknown", "OtherApp")
		foreign.windowHandle = 99

		def nativeRoot(hwnd: int, flags: int) -> int:
			return 2 if hwnd == 99 else 1

		self.winUser.getAncestor.side_effect = nativeRoot
		self.arrive(foreign).assert_called_once()
		self.assertFalse(self.controller.active)

	def test_destroyed_interpreter_rerun_keeps_suppression_until_replacement(self) -> None:
		self.controller.start()
		pane = self.destination(30, "pane", "AfxWnd140s")
		dead = self.obj
		dead.processID = 123
		dead.windowHandle = 99
		wrapper = self.destination(31, "window", "RICHEDIT50W")
		wrapper.windowHandle = 99
		self.winUser.getAncestor.side_effect = self.missingRoot
		self.api.getFocusAncestors.return_value = [pane, wrapper]
		self.api.getFocusObject.return_value = dead
		for ancestor in (pane, wrapper):
			handler = Mock()
			self.app.event_focusEntered(ancestor, handler)
			handler.assert_not_called()
		self.arrive(dead).assert_not_called()
		self.assertFalse(dead._keepMonitoring)
		self.advance(0.03)
		pane.role = "unknown"
		self.api.getFocusAncestors.return_value = []
		self.arrive(pane).assert_not_called()
		self.advance(0.7)
		dead.windowHandle = 42  # Replacement's live native window.
		self.arrive(dead).assert_called_once()
		self.assertFalse(self.controller.active)
		self.assertTrue(dead._keepMonitoring)

	def test_destroyed_interpreter_requires_own_unnamed_pane(self) -> None:
		for parentClass, parentName, deadClass in (
			("AfxWnd140s", "Other pane", "RICHEDIT50W"),
			("OtherContainer", None, "RICHEDIT50W"),
			("AfxWnd140s", None, "Scintilla"),
		):
			self.api.getFocusObject.return_value = self.editor
			self.controller.start()
			pane = self.destination(30, "pane", parentClass)
			pane.name = parentName
			dead = self.destination(31, "edit", deadClass)
			dead.windowHandle = 99
			self.winUser.getAncestor.side_effect = self.missingRoot
			self.api.getFocusAncestors.return_value = [pane]
			self.arrive(dead).assert_called_once()
			self.assertFalse(self.controller.active)

	def test_destroyed_interpreter_grace_expires_without_presenting_dead_window(self) -> None:
		self.controller.start()
		pane = self.destination(30, "pane", "AfxWnd140s")
		dead = self.destination(31, "edit", "RICHEDIT50W")
		dead.windowHandle = 99
		self.winUser.getAncestor.side_effect = self.missingRoot
		self.api.getFocusAncestors.return_value = [pane]
		self.arrive(dead).assert_not_called()
		self.advance(1.5)
		self.assertFalse(self.controller.active)
		dead.event_gainFocus.assert_not_called()

	def test_destroyed_interpreter_does_not_hide_project_switch(self) -> None:
		self.controller.start()
		pane = self.destination(30, "pane", "AfxWnd140s")
		dead = self.destination(31, "edit", "RICHEDIT50W")
		dead.windowHandle = 99
		self.winUser.getAncestor.side_effect = self.missingRoot
		self.api.getFocusAncestors.return_value = [pane]
		self.arrive(dead).assert_not_called()
		self.winUser.getForegroundWindow.return_value = 2
		self.advance(0.1)
		self.assertFalse(self.controller.active)
