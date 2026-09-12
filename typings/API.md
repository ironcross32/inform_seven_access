# NVDA API types used by Inform 7 Access

These partial stubs describe only the NVDA and wx interfaces consumed by this
add-on. Pyright loads them through `stubPath`; Python never imports them at
runtime, and they are not included in the `.nvda-addon` package. CI therefore
does not need a Windows NVDA installation or a sibling source checkout.

The declarations follow the NVDA 2026.1.1 interfaces used by the existing runtime
contract tests. Reference sources:

- [LiveText](https://github.com/nvaccess/nvda/blob/release-2026.1.1/source/NVDAObjects/behaviors.py)
- [Scintilla](https://github.com/nvaccess/nvda/blob/release-2026.1.1/source/NVDAObjects/window/scintilla.py)
- [Text fields and speech hooks](https://github.com/nvaccess/nvda/blob/release-2026.1.1/source/textInfos/__init__.py)
- [Settings controls](https://github.com/nvaccess/nvda/blob/release-2026.1.1/source/gui/guiHelper.py)
- Compile suppression also uses Chromium's `Document` and `ChromeVBuf`, the
  gesture execution decider, and native foreground/root-window helpers. Their
  signatures and focus ordering were inspected at both compatibility endpoints:
  [NVDA 2025.1 Chromium](https://github.com/nvaccess/nvda/blob/release-2025.1/source/NVDAObjects/IAccessible/chromium.py),
  [NVDA 2026.1.1 Chromium](https://github.com/nvaccess/nvda/blob/release-2026.1.1/source/NVDAObjects/IAccessible/chromium.py),
  [gesture decider](https://github.com/nvaccess/nvda/blob/release-2026.1.1/source/inputCore.py),
  [focus ordering](https://github.com/nvaccess/nvda/blob/release-2026.1.1/source/eventHandler.py), and
  [browser presentation](https://github.com/nvaccess/nvda/blob/release-2026.1.1/source/browseMode.py).
  The subclass delegates caret initialization, loading, and reading preferences
  to NVDA; these stubs do not emulate those implementations.
  Chromium inherits its `documentURL` implementation from
  [Gecko_ia2](https://github.com/nvaccess/nvda/blob/release-2026.1.1/source/virtualBuffers/gecko_ia2.py),
  which reads the root accessible object's `accValue(0)`. The ordinary NVDA
  document `value` can be empty and is not the primary URL source.

Keep declarations narrow and update them against the relevant upstream source
when adding API calls or changing the supported NVDA version. They are an
explicit compatibility contract, not a replacement for live NVDA validation.
`Any` is reserved for NVDA's heterogeneous configuration/field dictionaries,
dynamic app-module association, and forwarded framework arguments. API methods
have concrete argument and return types wherever this add-on relies on them.

Strict checking covers the add-on, copier, test helpers and these stubs. The
pre-commit hook checks the configured project once rather than passing filenames
that override Pyright's exclusions. Framework lifecycle checks allow NVDA's
overlay/settings hooks and unittest's `setUp` initialization; missing runtime
source is allowed for stubbed modules, while missing imports remain errors.
