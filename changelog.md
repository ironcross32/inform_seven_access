# Changes

## 0.2.0 prototype

- Use NVDA's native status-bar commands for the Inform story status grid through
  the app-module status hooks, including standard speech, spelling, clipboard,
  braille, and missing-status handling. When focus is outside the interpreter,
  explain how to focus it with Control+F3 before requesting the story status.

- Move routine focus, interpreter-output and lifecycle diagnostics to Debug,
  keeping normal Info logs quiet while retaining warnings and errors.

- Use NVDA's EnhancedInputSlider for syntax sound volume, matching the Audio
  settings slider and its native keyboard navigation.

- Add a labeled Syntax sound volume (%) control from 0 to 100, with profile
  support and Apply/OK/Cancel behavior. Preserve queued playback and original WAVs.

- Replace the syntax checkbox with a labeled None / Speech / Speech and sounds /
  Sounds selector. Preserve existing enabled/disabled profile values.
- Queue the supplied WAV cues at syntax boundaries, including word navigation
  and Say All; copy the sounds with scratchpad deployment.

- Preserve NVDA's single-character punctuation speech for closing brackets and
  quotes while retaining syntax markers during word navigation.

- Add default-on source syntax announcements for word/line/paragraph reading and Say All,
  including substitutions within quotations and nested comments.
- Add the Inform 7 settings category with a Source editor selector, supporting
  Apply/OK, Cancel, and NVDA configuration profiles.
- Correct source font sizes and expose foreground/background colors independently
  of syntax announcements. Keep markers out of text, clipboard and braille text.
- Extend scratchpad deployment and packaging to include shared support and the
  global settings plugin. Preserve interpreter, history, status and navigation features.

## 0.1.4 prototype

- Add interpreter-only Control+Shift+U/I/O for previous/current/next line and
  Control+Shift+N/Y for last/first line.
- Keep a separate reading position per interpreter pane, read fresh text on each
  command, and announce Top/Bottom when moving beyond the transcript limits.

## 0.1.3 prototype

- Override Inform's status-bar command to read the story status grid above the
  interpreter, including room and time fields.
- Support desktop and laptop bindings, double-press spelling, and triple-press
  copying. Read fresh display-model text on every invocation.

## 0.1.2 prototype

- Track typed-character events to exclude command echoes from the text diff,
  including bursts of typing with NVDA typing feedback disabled.
- Capture confirmed pending input before forwarding Enter, preserving responses
  that immediately follow the command on the same line.
- Preserve NVDA's existing Up/Down navigation and command-history handling.

## 0.1.1 prototype

- Use the native multiline window style when selecting the interpreter overlay;
  NVDA's MULTILINE state is not available until the Rich Edit overlay is applied.
- Log module location/version, app and object focus, overlay matching, monitoring,
  text length changes, and speech batches at Info level.

## 0.1.0 prototype

- Automatically report new text in a focused Inform interpreter candidate,
  honoring NVDA's dynamic content setting.
- Poll for text updates when accessibility events are unavailable.
- Add a scratchpad copy script with optional destination, dry run, and backups.
