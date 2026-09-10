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
