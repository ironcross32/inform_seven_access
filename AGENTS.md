# Repository Guidelines

## Project Structure & Module Organization

This Windows NVDA add-on improves Inform 7 editor and interpreter accessibility.
- `addon/appModules/inform.py`: application integration, interpreter output, and navigation.
- `addon/appModules/inform7Support/`: editor formatting, syntax boundaries, configuration, and sound volume helpers.
- `addon/globalPlugins/inform7.py`: NVDA settings integration.
- `addon/sounds/`: WAV feedback cues; `addon/doc/en/`: packaged documentation.
- `tests/`: automated tests with NVDA and wx stubs.
- `sconstruct`, `site_scons/`, `buildVars.py`, and manifest templates: packaging and add-on metadata.
- `validation.md`: recorded checks and outstanding interactive verification.

## Protected files

- README.md is maintained exclusively by the user.
- Never modify, replace, delete, rename, regenerate, or format README.md.

## Build, Test, and Development Commands

Use Python 3.13 and run commands from the repository root, first activating the virtual environment called, "env64", which is located in this project's parent directory. Install dependencies with `uv sync`; gettext tools are also needed for translation tasks.

- `uv run scons -s`: build `informSevenAccess-<version>.nvda-addon`.
- `uv run scons pot`: generate the translation template.
- `uv run python -m unittest discover -s tests -q`: run automated tests.
- `uv run ruff check .` and `uv run ruff format --check .`: check lint and formatting.
- `uv run pre-commit run --all-files`: run configured hooks, including fixes and Pyright. Pyright expects NVDA sources at `../nvda/source`.

For local deployment, preview with `uv run python copy_to_scratchpad.py --scratchpad "$env:APPDATA\nvda\scratchpad" --dry-run`. Remove `--dry-run` to copy with numbered backups. Specify your path because the script default is developer-specific. Enable NVDA developer scratchpad loading and reload plugins with NVDA+Control+F3.

## Coding Style & Naming Conventions

Use tabs, LF endings, and Ruff's 110-character line limit. Follow surrounding naming: PascalCase classes, NVDA-style camelCase methods and callbacks, and UPPER_SNAKE_CASE constants. Preserve NVDA API signatures and wrap user-facing text with `_()` for translation.

Use tabs for code indentation in source, tests, type stubs, and build/release scripts. Ruff and `.editorconfig` enforce these defaults. Preserve spaces inside string data and prose, and use spaces for YAML indentation as required by that format.

Follow the [NVDA addon development guide](https://github.com/nvdaaddons/devguide/wiki/NVDA%20Add-on%20Development%20Guide). If the guide suggests something that goes against Python convensions, defer to the guide's way of doing things.

## Testing Guidelines

Use `unittest`, `test_*.py` files, and `test_*` methods. Add regression tests for changed behavior, especially syntax boundaries, profiles, sound ordering, and deployment. No coverage percentage is configured. Stub tests cannot establish audible speech, braille, or UI accessibility; perform relevant live checks from `validation.md` and record remaining gaps.

## Commit & Pull Request Guidelines

Git history is unavailable in this checkout, so commit conventions cannot be verified. Use concise imperative subjects, such as `Fix duplicate syntax announcements`. Work on a feature branch. PRs should describe behavior changes, link relevant issues, report automated and live validation, and update documentation or the changelog for user-visible changes.
