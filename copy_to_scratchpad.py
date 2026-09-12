"""Copy Inform 7 Access modules and settings to NVDA's developer scratchpad.

Run with an ordinary Python installation; no NVDA imports are needed.
"""

from __future__ import annotations


import argparse
from pathlib import Path
import shutil
import sys


DEFAULT_SCRATCHPAD = Path(r"C:\Users\bcros\AppData\Roaming\nvda\scratchpad")
SOURCE = Path(__file__).resolve().parent / "addon" / "appModules" / "inform.py"
ADDON = SOURCE.parent.parent


def deployment_sources() -> list[Path]:
	return [
		SOURCE,
		*(
			ADDON / "appModules" / "inform7Support" / name
			for name in ("__init__.py", "editor.py", "syntax.py", "soundVolume.py")
		),
		ADDON / "globalPlugins" / "inform7.py",
		*sorted((ADDON / "sounds").glob("*.wav")),
	]


def copy_to_scratchpad(scratchpad: Path, dry_run: bool = False) -> Path:
	"""Deploy our files only, retaining numbered backups of changed files."""
	root = scratchpad.expanduser().resolve()
	sources = deployment_sources()
	for source in sources:
		if not source.is_file():
			raise FileNotFoundError(f"Add-on source not found: {source}")
		if (root / source.relative_to(ADDON)).resolve() == source.resolve():
			raise ValueError(
				"Scratchpad destination must differ from the source directory",
			)
	for source in sources:
		_ = _copy_file(source, root / source.relative_to(ADDON), dry_run)
	return root / "appModules" / SOURCE.name


def _copy_file(source: Path, destination: Path, dry_run: bool) -> Path:
	if dry_run:
		print(f"Would copy {source} -> {destination}")
		return destination
	if destination.is_file() and destination.read_bytes() == source.read_bytes():
		print(f"Already up to date: {destination}")
		return destination
	destination.parent.mkdir(parents=True, exist_ok=True)
	if destination.exists():
		# Keep previous versions without overwriting an earlier backup.
		backup = destination.with_name(destination.name + ".bak")
		index = 1
		while backup.exists():
			backup = destination.with_name(f"{destination.name}.bak.{index}")
			index += 1
		_ = shutil.copy2(destination, backup)
		print(f"Backup: {backup}")
	_ = shutil.copy2(source, destination)
	print(f"Copied: {destination}")
	return destination


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	_ = parser.add_argument(
		"--scratchpad",
		type=Path,
		default=DEFAULT_SCRATCHPAD,
		help=f"Scratchpad directory (default: {DEFAULT_SCRATCHPAD})",
	)
	_ = parser.add_argument(
		"--dry-run",
		action="store_true",
		help="Show the copy without changing files",
	)
	args = parser.parse_args()
	try:
		_ = copy_to_scratchpad(args.scratchpad, args.dry_run)
	except (OSError, ValueError) as error:
		print(f"Copy failed: {error}", file=sys.stderr)
		return 1
	if not args.dry_run:
		print("Enable NVDA's developer scratchpad, then press NVDA+Control+F3 to reload plugins.")
		print("Refocus Inform's source editor or interpreter. Restart NVDA if the overlay has not loaded.")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
