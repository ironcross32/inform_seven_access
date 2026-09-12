# Version 0.2.0 validation

## CI checks follow-up (2026-09-10)

- Added explicit types for add-on code, deployment helpers and test fixtures.
  Strict Pyright checking now includes the partial NVDA/wx declarations in
  `typings/`; it no longer requires a sibling NVDA source checkout. See
  [the API contract notes](typings/API.md) for scope and upstream references.
- Kept missing imports and annotation/argument/return diagnostics enabled.
  Adjusted runtime-source and lifecycle checks for stub-only CI dependencies,
  NVDA overlay/settings initialization and unittest fixtures.
- Aligned the Ruff hook with the pinned dependency version and repository space
  indentation. Applied trailing-comma, formatting and final-newline fixes.
  Excluded the user-maintained README.md from automatic pre-commit hooks.
- All pre-commit hooks pass, including Pyright with zero errors and warnings;
  standalone Ruff lint and formatting checks pass.
- All 71 regression tests pass on Python 3.13.11, including a new missing-geometry
  status-selection case. The workflow now runs this suite after code checks.
- `uv run scons -s` and `uv run scons pot` succeed locally. Hosted Linux CI and
  live speech, braille and settings behavior still require verification.

Recorded September 9, 2026.

Logging follow-up: routine Inform activity now uses Debug rather than Info.
Existing failure warnings/errors remain. The logging regression check verifies
that focus/reporting transitions use Debug and do not emit Info messages.

Slider follow-up: the volume control now uses `gui.nvdaControls.EnhancedInputSlider`,
the same class used by NVDA 2026.1.1's Audio settings, with the existing accessible
label, 0–100 bounds, stored value and Apply/Cancel behavior. Keyboard handling is
inherited from NVDA; no add-on key handlers were added. Native keyboard and speech
behavior still require live confirmation after reload.

Volume follow-up: added the labeled Syntax sound volume (%) numeric control,
range 0–100, default 100, with Apply/Cancel and profile support. Zero mutes only
the cues; intermediate values use cached PCM-attenuated WAV copies queued through
the same WaveFileCommand. Original sound files and other NVDA audio are unchanged.
All 70 tests pass on Python 3.13.11. New tests cover labels, bounds, profile values,
Apply/Cancel, mute and full-volume behavior, cached output, unchanged source files,
retained duration/channels/sample rate for 8/16/24/32-bit PCM, and safe handling of
scaling failure. Live loudness and numeric-control accessibility remain to be
confirmed after reload. Earlier verification snapshots follow below.

Sound-mode follow-up: the labeled Syntax highlighting feedback selector now
offers None, Speech, Speech and sounds, and Sounds. Old enabled/disabled profile
settings resolve to Speech/None until a new mode is saved. The supplied eight
WAV files are valid mono 44.1 kHz files. `WaveFileCommand` queues each sound at
the same boundary used for speech; combined mode places the sound immediately
before the spoken marker. Inform 6 uses the comment cues because no dedicated
pair was supplied. Missing files are logged once without suppressing combined
mode speech. The WAVs are included in scratchpad deployment and the add-on bundle.
Tests now cover 66 cases, including all modes, labels, profile compatibility,
sound order across adjacent Say All chunks, word cues, silent character reads,
missing sounds and sound deployment/backups. Interactive label announcement,
audible timing and cancellation still require live confirmation after reload.

Character-delimiter follow-up: character reads now omit private syntax fields,
preserving NVDA's single-character spelling path for closing brackets and quotes.
Word ranges still receive markers, including after copying a TextInfo. All 59
tests pass on Python 3.13.11, with Ruff checks passing. The fix is deployed and
verified against source; audible confirmation after reload remains pending.

Word-navigation follow-up: syntax markers are now enabled for word reading,
including NVDA's `extraDetail` path. The updated suite passes all 57 tests on
Python 3.13.11, and Ruff checks pass. Tests cover entry, exit, substitutions,
interior words, repeated word reads and disabling the setting. The update has
been copied into the scratchpad and all deployed files verified against source.
Interactive word-navigation speech still needs verification after plugin reload.
The results below describe the earlier 56-test baseline.

## Automated checks

- `python -m unittest discover -s tests -q`: 56 tests pass on Python 3.13.11.
  This includes existing interpreter/history/status/navigation tests, editor
  selection, settings/profile stubs, syntax and formatting, and scratchpad copying.
- The 18 editor tests also pass with NVDA 2026.1.1's actual
  `ScintillaTextInfo._getFormatFieldAndOffsets` and
  `OffsetsTextInfo.getTextWithFields` methods substituted for the corresponding
  stub methods. Native messages and other NVDA services remain mocked.
- Ruff checks and formatting checks pass for new support/plugin code, the copier,
  and new tests. Bytecode compilation succeeds for the add-on and tests.
- The packaging source globs include all five deployed Python files. Bytecode
  files are excluded from packaging. The scratchpad copier's dry run lists all
  five files without writing them; tests verify numbered backups and retention
  of unrelated files.

The boundary tests include complete and unfinished spans, adjacent substitutions
and comments with identical styles, adjacent Inform 6 spans, comment nesting,
multiline text, partial ranges, every character-aligned split of nested UTF-8
examples, repeated reads, punctuation preservation, runtime disabling, normal
formatting speech, and a renderer returning a speech-command stand-in.

These are automated contract and logic checks. Settings use a wx stub, profile
switches use a configuration stub, and braille checks establish unchanged source
text and inherited braille methods. They do not verify the interactive NVDA UI,
profile persistence to disk, audible speech, queue cancellation or physical
braille output.

## Read-only checks in running applications

- Installed NVDA executable reports **2026.1.1**.
- Two visible Inform Scintilla editors report code page **65001 (UTF-8)**.
- Sampling up to the first 1,024 bytes reports styles **0, 1 and 2**, with
  **110** from the native font-size query for each sampled style.
- Sampled COLORREF foreground values are **16777215**, **16635229**, and
  **15174638** respectively; backgrounds are **0**. This confirms native color
  queries and Inform's raw size convention on the installed application.

The probe only read native metadata. It did not change source text or print source
contents. The new add-on was not deployed into the running NVDA instance during
these checks.

### Deployment follow-up

After the user reported missing settings, inspection found only the previous
`appModules/inform.py` in the scratchpad. The initial delivery had run only the
copier's dry run. All five updated files have now been copied to the default
scratchpad and verified byte-for-byte against the source. The previous app module
was preserved as `inform.py.bak.4`. Reloading NVDA and interactive verification
are still required.

## Interactive checks still required

There is no interactive desktop or speech-monitoring tool connected to this
session. The following end-to-end checks remain unverified:

1. Deploy with `python copy_to_scratchpad.py`, enable developer scratchpad loading,
   reload plugins with NVDA+Control+F3, and refocus Inform. Restart NVDA if it keeps
   an old editor object. Check that the source object's class hierarchy contains
   `InformSourceEditor` and its TextInfo is `InformSourceTextInfo`.
2. Open NVDA Settings. Confirm one **Inform 7** category, an accessible **Source
   editor** grouping and the labeled **Syntax highlighting feedback** selector
   with None, Speech, Speech and sounds, and Sounds. Test each mode, including
   exact cue timing and cancellation. Test Cancel, Apply and OK;
   switch configuration profiles and test NVDA's normal save/restart behavior.
3. Read the supplied nested example with Up/Down and paragraph reading. As an
   additional sample, use the following in a disposable Inform project:

   ```inform7
   Section Syntax sample

   The Lab is a room.
   When play begins:
       say "Café [if true]hello[otherwise]goodbye[end if].".

   [An outer comment [with an inner comment] ends here.]

   Include (- [ Example; rtrue; ]; -).
   ```

   Each substitution opens and closes inside the quotation. Each nested comment
   has its own markers. `say` is ordinary text. Delimiters follow NVDA's punctuation
   setting. Repeat lines and begin reading inside a quotation.
4. Add a quotation or comment spanning multiple lines. Run Say All across it and
   stop speech midway. Check marker order, no duplicates between chunks, and
   cancellation together with ordinary speech. Leave syntax unfinished at EOF
   and verify there is no invented closing marker.
5. Disable syntax announcements and reread without restarting. Check character
   and word navigation and typing feedback. Query font size and colors with
   syntax off. Compare clipboard and braille text with the source.
6. Repeat interpreter command/history/status/navigation checks in the readme and
   reload plugins again to check settings-category cleanup.

Compatibility manifest fields remain unset pending these live checks.

## Interface references

- [Golden Cursor settings registration and panel pattern](https://github.com/nvda-es/goldenCursor/blob/master/addon/globalPlugins/goldenCursor.py)
- [NVDA 2026.1.1 Scintilla implementation](https://github.com/nvaccess/nvda/blob/release-2026.1.1/source/NVDAObjects/window/scintilla.py)
- [NVDA 2026.1.1 offset-based text fields](https://github.com/nvaccess/nvda/blob/release-2026.1.1/source/textInfos/offsets.py)
- [NVDA 2026.1.1 scoped formatting speech hook](https://github.com/nvaccess/nvda/blob/release-2026.1.1/source/textInfos/__init__.py)
- [Inform Windows source lexer](https://github.com/DavidKinder/Windows-Inform7/blob/master/Inform7/SourceLexer.cpp)

## Release script validation (2026-09-10)

- PowerShell parser check passed for `scripts/release.ps1`.
- Disposable Git repositories and a local bare origin verified the default version
  bump, leading `v`, prerelease input, preservation of surrounding metadata,
  commit isolation from unrelated staged changes, annotated tags, and branch/tag pushes.
- Invalid or unchanged versions, local/remote duplicate tags, existing buildVars.py
  edits, detached HEAD, and an inaccessible origin were rejected before editing metadata.
- The global `git release` alias resolved a repository path containing spaces from
  a subdirectory and correctly rejected redirected input.
- Automated release runs bypassed the console-input guard only in disposable script
  copies and supplied prompt answers. Real interactive prompting and hosted GitHub
  Actions publishing remain unverified; no hosted release was created.
- This working folder has no Git metadata. A feature branch and repository-local
  alias could not be created. The installed global alias invokes the script in the
  current Git repository; releasing requires a checkout with an origin remote.

## Compile focus suppression (2026-09-12)

Implemented on `feat/compile-focus-suppression`. F5 starts a project-scoped
session before forwarding the key once. Intermediate Chromium and recorded MFC
pane focus presentation is withheld; NVDA still maintains focus normally.
Interpreter arrival releases immediately. A local `Build/Problems.html` report
must remain ready and not busy for at least 750 ms before normal browser
presentation resumes. The session expires after 120 seconds.

Automated validation uses Python 3.13 after activating the parent `env64`.
`uv` uses this repository's locked `.venv`, as configured by the project.

- Unit tests: 93 passed, including synthetic successful and failed compile
  sequences without recorded story text, names, or handles.
- Coverage includes ancestor/browser guards, delayed readiness, busy/loading
  resets, native document replacement and Python object recreation, repeated
  F5, forwarding/inspection failures, long compilation, timeout, gesture
  cancellation, app/project switches, returning, and plugin reload callbacks.
- Browser delegation tests verify the saved selection and automatic-reading
  configuration are unchanged; ordinary navigation and interpreter tests pass.
- Ruff lint/format checks and configured pre-commit hooks, including Pyright,
  pass. Hooks applied trailing-comma and formatting fixes to the new code.
- `uv run scons -s` builds `informSevenAccess-0.2.2.nvda-addon` for review.
  The package includes `doc/en/compiling.html`. No deployment was performed.
- README.md remains unchanged; debug.log remains untracked.

Compatibility source inspection covered NVDA 2025.1 and 2026.1.1 Chromium
document/buffer classes, gesture decider, focus event ordering, and virtual
buffer loading/browser presentation. See `typings/API.md` for the upstream
references. The add-on delegates buffer loading, initial/saved caret position,
and automatic-reading preferences to NVDA rather than copying its implementation.
This is API inspection and stub testing, not live compatibility certification.

Outstanding live speech/braille checks on both compatibility endpoints:

1. Compile successful and failing disposable projects with F5 from the editor,
   an existing browser document, and the interpreter. Confirm intermediate
   documents and pane ancestors are silent, the interpreter is presented
   immediately, and the translation report is presented once.
2. Repeat with automatic page reading on/off and with a saved report reading
   position. Confirm normal speech and braille presentation and reading position.
3. Exercise slow compilation, delayed browser loading, and report replacement.
   Validate the 750 ms heuristic; it cannot prove compilation has finished.
4. Switch away and back during/after compilation, including between projects in
   one Inform process. Confirm no stale output in the other application and no
   resumed suppression on returning. Test repeated F5 and plugin reload.
5. Press modifiers alone, then navigation keys and braille gestures. Confirm
   cancellation before ordinary interaction, normal dialogs/menus/editor focus,
   and unchanged browser navigation and interpreter output outside compilation.

These live checks require interactive NVDA/Inform use and remain unperformed.
No compatibility manifest claim was added.

## Automatic compile trace (2026-09-12)

- Added NVDA+Shift+F5 to arm the next F5 compilation, disarm, or stop an active
  trace. Files are saved and flushed incrementally under
  `%TEMP%\inform7-access-traces`; no separate application is required.
- Captures existing NVDA focus/ancestor objects, available MSAA/IA2 identifiers,
  roles/states/names, document URLs, browser readiness, presentation decisions,
  and explicit suppression termination reasons. No full tree traversal or
  editor/interpreter text retrieval is performed.
- The trace outlives early suppression cancellation, with a 15-second minimum
  observation period and three-second quiet tail once suppression ends. The
  hard limits are 120 seconds and 4,000 events. Switching windows, forwarding
  failure, manual stop, and plugin termination close the trace.
- All 103 unit tests pass, including ten new tests for arming, native ancestor
  capture, early cancellation, repeated F5, foreground isolation, property/file
  failures, manual stop/reload, and time/event limits. Existing suppression tests
  continue to pass. Ruff, Pyright, and configured hooks pass; the review add-on
  was rebuilt with the trace module and updated packaged help.
- Live validation remains outstanding: arm tracing in Inform, compile a project
  that produces repeated tab-panel announcements, and inspect the resulting
  JSONL file against audible speech. Test the shortcut with the user's keyboard
  layout and check the saved path is reachable. No deployment was performed.

## Trace-driven ancestor suppression fix (2026-09-12)

The user's 08:54:28 capture showed an uninterrupted suppression session ending
at 3.9524 seconds with `interpreter arrived`. All recorded document focus and
browser presentation attempts during the session were suppressed. However, 28
`focusEntered` events for native ancestors were allowed through while suppression
was active. These included two `AfxWnd140s` TABCONTROL events at approximately
0.257 and 3.257 seconds, plus MFC pane/window wrappers and Chromium widget panes.
The capture records presentation decisions, not the resulting speech, so it does
not establish that every one of these events produced an audible announcement.

- Added a separate ancestor filter for the observed MFC window-class forms,
  AfxWnd tab controls/panes, MDI frames, and `Chrome_WidgetWin_1` pane wrappers.
  Matching uses structural roles/classes, never project titles or saved handles.
- The focused-destination filter remains narrow. Native tab-control/pane focus,
  dialogs, menus, editor focus, interpreter arrival, and project switches retain
  their existing cancellation and normal presentation behavior.
- All 107 tests pass, including synthetic replay of the observed wrapper types
  across six browser destinations, interpreter release, actual-focus exclusion,
  unrelated role/class exclusion, and out-of-session/project-switch handling.
  The tracing test now confirms the observed tab-control ancestor is suppressed.
- Ruff, Pyright, configured pre-commit hooks, and the review add-on build pass.
  README.md and the original capture were not modified; the capture was not
  copied into the repository. No deployment was performed.

Outstanding live check: repeat the same compilation with the rebuilt add-on and
tracing enabled. Confirm tab/pane ancestors are silent, interpreter output still
starts normally, and the previously allowed ancestor events now show
`suppressed: true`. Repeat a failing compilation to verify final report reading.

## Error reports and fast reruns (2026-09-12)

The 09:09:38 successful capture and the user's listening check confirmed clean
suppression through interpreter arrival. The 09:13:58 deliberate-error capture
showed a ready report at 1.9808 seconds, but the traced document value was null.
There was no report-settled release; suppression ended only on a user gesture at
10.184 seconds. Report recognition now uses NVDA's browser `documentURL`, followed
by the native `accValue(0)` fallback, instead of relying on the ordinary value.
It still invokes normal browser presentation once and preserves reading settings.

The 09:13:30 unchanged-source capture cancelled at 0.0791 seconds on a failed
focus-ownership check, then focused an unnamed UNKNOWN AfxWnd pane at 0.1068
seconds and the interpreter at 0.7857 seconds. The first focus object's properties
were omitted by the old trace filter, so its exact native root remains unknown.
The new trace includes structural identities and native roots even when full
object inspection is excluded, plus the effective document URL.

An unnamed UNKNOWN AfxWnd client pane is now a bounded transition destination.
An unresolved native root can also be bridged when the nearest focus ancestor
is this pane in the originating project. Both cases share a 1.5-second limit;
foreground switches, live foreign roots, named controls, and dialogs still cancel.
Expiry restores presentation of a still-owned withheld destination once.

All 115 tests pass, including empty-value reports, native URL fallback and URL
priority, delayed report URL availability, detached focus followed by the
unnamed pane/interpreter, grace expiry, missing ancestry, foreign-root rejection,
and trace diagnostics. Ruff, Pyright, configured hooks, and the review build pass.
README.md and the supplied traces were not modified. No deployment was performed.

Live checks still needed with the rebuilt add-on: repeat successful, deliberate
error, and unchanged-source compilations. Confirm the error report is presented
once, no preliminary report interrupts a successful compile, and fast reruns
remain quiet until interpreter arrival. If the first fast-rerun focus object has
a live unexpected root, the improved trace is needed to identify it rather than
broadening the foreground guard speculatively.

## Destroyed interpreter on unchanged-source rerun (2026-09-12)

The latest successful and deliberate-error captures, together with the user's
listening checks, confirm that those paths work. The error report now releases
normally with `report settled` at approximately 3.13 seconds.

The 09:32:53 fast-rerun capture identifies the remaining gap: at 0.0742 seconds,
focus points to an EDITABLETEXT RICHEDIT50W object from the Inform process whose
native root is zero. Its surviving project ancestor is an unnamed AfxWnd PANE.
The previous grace rule excluded editable objects and required an UNKNOWN parent,
so it cancelled. An UNKNOWN pane then received focus at 0.0992 seconds, followed
by the replacement interpreter at 0.8112 seconds.

- Extended the existing 1.5-second grace specifically to this destroyed Rich Edit
  object with an unnamed owning pane. It does not depend on the destroyed
  window's native style. Only its matching dead WindowRoot wrapper may be skipped
  when checking the nearest surviving ancestor.
- Silences the stale window wrapper and defers interpreter output monitoring
  until valid interpreter focus arrives. The existing UNKNOWN pane transition
  continues within the same time limit.
- Added four regression tests for the full dead-interpreter/pane/replacement
  sequence, excluded parents/editor classes, grace expiry, and project switching.
  All 119 tests, Ruff checks, Pyright, and configured hooks pass. The review build
  includes the fix; no deployment was performed.
- README.md and all supplied traces remain untouched.

Remaining live check: repeat the unchanged-source rerun and confirm the last
`unknown` is gone. Its trace should retain suppression through the destroyed
interpreter and temporary pane, then end with `interpreter arrived`.

## Final compile suppression live validation (2026-09-12)

The user's 09:46:14 unchanged-source capture confirms the remaining rerun check:
the destroyed interpreter and its window wrapper, the unnamed pane, and their
intermediate focus events are all suppressed. The transient interval starts at
0.0744 seconds and suppression ends normally with `interpreter arrived` at
0.7903 seconds, well within the 1.5-second limit. The replacement interpreter's
focus presentation is allowed. There is no unexpected cancellation or timeout.

The user confirms the audible result is clean. Together with the preceding
successful and deliberate-error compilation checks, this completes the reported
compile-announcement issue. No further implementation changes were made after
reviewing this trace. This records the user's tested environment; it does not
claim additional braille or cross-version validation.

## Tab indentation (2026-09-12)

- Converted Python source, tests, stubs, build scripts, PowerShell, and editor JSON
  indentation to tabs. Ruff now enforces tabs, including `buildVars.py`;
  `.editorconfig` and VS Code defaults support future edits.
- All 119 unit tests and Ruff lint/format checks pass. All 51 Python/stub/build
  syntax trees match the original after normalizing docstring indentation.
  The PowerShell release script parses without errors; README.md's hash is unchanged.
- Excluded the local uv dependency cache from Pyright's source scan.
- All configured pre-commit hooks pass, including Pyright.
- This formatting change introduces no new live accessibility checks.

## Native app-module story status (2026-09-12)

- Replaced the app module's custom status-line script and gesture bindings with
  NVDA's `_get_statusBar` and `getStatusBarText` app-module hooks. The existing
  native-window lookup, dual-pane selection, and fresh display-model formatting
  remain in use.
- Added a `statusBarTextInfo` hook returning no fallback position. When the Story
  pane is absent, NVDA therefore reports a missing status line instead of reading
  Inform's unrelated IDE status bar from the bottom of the display model.
- When the status command is used outside the interpreter, its native app-module
  text hook now explains that the user can focus the interpreter with Control+F3
  and try again.
- All 120 unit tests pass. Ruff lint and format checks, Pyright, all configured
  pre-commit hooks, and the review build pass. README.md was not modified, and no
  deployment was performed.

Live checks still needed with the rebuilt add-on: verify NVDA's status command
from both the source editor and interpreter in desktop and laptop layouts; verify
single-press speech, double-press spelling, triple-press copying, changing room
and time values, dual Story panes, an empty status grid, and a closed Story pane.
Outside the interpreter, confirm the Control+F3 guidance is announced. The
closed-pane case must not announce Inform's IDE status bar.
