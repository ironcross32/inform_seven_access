# Compiling with F5

Press F5 to compile and run your story. Inform 7 Access temporarily silences
intermediate Chromium documents and compile-pane focus announcements. NVDA
continues tracking focus throughout compilation.

Suppression includes the native tab controls and pane wrappers around intermediate
browser documents, so changing compile panes does not announce their ancestors.
Actual focus on a native tab control still cancels suppression normally.

Fast reruns can briefly focus an unnamed native pane while the interpreter is
being recreated. This transition is silenced for up to 1.5 seconds while the
original project remains foreground. A detached focus object is tolerated only
when its native root is unavailable and its nearest recorded ancestor is that
project's unnamed transition pane. Other project windows and dialogs are not
covered by this exception.

The same short transition allowance covers a destroyed Rich Edit interpreter
whose recorded parent is an unnamed pane in the original project. Its stale
window wrapper is silenced and output monitoring waits for the replacement
interpreter to receive valid focus.

Normal presentation resumes immediately when the interpreter receives focus.
If compilation stops at the translation report, the add-on presents that report
after it has remained ready and not busy for at least 750 milliseconds. NVDA's
saved reading position and automatic page-reading preference still apply.

Report recognition uses the browser's document URL, with a native accessibility
fallback, because NVDA's ordinary document value can be empty. A settled error
report therefore receives normal presentation instead of remaining silent.

Pressing another key or using another NVDA gesture cancels suppression. A modifier
key alone does not cancel it. Pressing F5 again starts a new suppression session.
Switching to another application or another Inform project window also cancels
suppression; returning does not resume the old session. Dialogs, menus, editor
focus, and unexpected destinations receive normal handling.

Suppression expires after two minutes. The report settling delay is a heuristic;
a report that pauses during compilation may be presented before compilation ends.
Only F5 starts suppression. There are no new settings or compilation-status
announcements.

## Recording a compilation trace

To investigate announcements that escape suppression:

1. In Inform, press **NVDA+Shift+F5**. NVDA confirms that the next compilation
   will be traced and announces the output folder.
2. Press **F5** normally. Recording begins automatically before F5 is forwarded.
   You do not need to act during compilation.
3. After compilation, leave Inform foreground briefly. Recording stops once
   suppression has ended, at least 15 seconds have elapsed since F5, and there
   have been no recorded events for three seconds. It always stops at two minutes
   or 4,000 events. **NVDA+Shift+F5** can also stop and save the trace immediately.
4. Open `%TEMP%\inform7-access-traces` using Windows+R. Share the newest
   `compile-*.jsonl` file. These are plain-text files with one JSON record per line.

Pressing NVDA+Shift+F5 again before compilation disarms tracing. Switching away
or reloading plugins stops a running trace. Repeated F5 presses during recording
are included in the same file. Automatic completion is silent, and the exact
file path is also written to NVDA's log. Trace write failures are logged there.

The trace records elapsed times, suppression decisions and cancellation reasons,
focus and ancestor events, document state/loading events, name changes, and
browser presentation entry points. Object records include available roles,
states, names, window classes, accessibility identifiers, document URLs, and
buffer readiness. It continues after early suppression cancellation so subsequent
announcements can be investigated.

This is a targeted NVDA event trace, not a complete MSAA/UIA tree snapshot or a
recording of speech output. It reads no editor/interpreter values or document
text, but accessible names and document URLs can include project titles and paths.
Properties are bounded and unavailable properties are marked. Tracing is off
by default and must be armed for each capture.
