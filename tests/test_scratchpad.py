"""Deployment keeps unrelated files and every previous changed version."""

import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "scratchpad_copier", ROOT / "copy_to_scratchpad.py")
copier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(copier)


class ScratchpadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "scratchpad"
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def test_dry_run_creates_nothing(self):
        copier.copy_to_scratchpad(self.root, True)
        self.assertFalse(self.root.exists())

    def test_deploys_all_components_and_preserves_backups_and_unrelated_files(self):
        app = self.root / "appModules" / "inform.py"
        app.parent.mkdir(parents=True)
        app.write_text("old version")
        unrelated = app.with_name("anotherAddon.py")
        unrelated.write_text("unrelated")
        copier.copy_to_scratchpad(self.root)
        for source in copier.deployment_sources():
            self.assertEqual(
                (self.root / source.relative_to(copier.ADDON)).read_bytes(), source.read_bytes())
        self.assertEqual(app.with_name(
            "inform.py.bak").read_text(), "old version")
        self.assertEqual(unrelated.read_text(), "unrelated")
        copier.copy_to_scratchpad(self.root)
        self.assertFalse(app.with_name("inform.py.bak.1").exists())
        app.write_text("second version")
        copier.copy_to_scratchpad(self.root)
        self.assertEqual(app.with_name(
            "inform.py.bak.1").read_text(), "second version")
        self.assertEqual(app.with_name(
            "inform.py.bak").read_text(), "old version")

    def test_source_directory_rejected_before_any_copy(self):
        with self.assertRaises(ValueError):
            copier.copy_to_scratchpad(copier.ADDON)

    def test_sound_deployment_preserves_changed_and_unrelated_sounds(self):
        folder = self.root / "sounds"
        folder.mkdir(parents=True)
        (folder / "quote_start.wav").write_bytes(b"previous sound")
        (folder / "unrelated.wav").write_bytes(b"another plugin")
        copier.copy_to_scratchpad(self.root)
        sounds = list((copier.ADDON / "sounds").glob("*.wav"))
        self.assertEqual(len(sounds), 8)
        for source in sounds:
            self.assertEqual(
                (folder / source.name).read_bytes(), source.read_bytes())
        self.assertEqual(
            (folder / "quote_start.wav.bak").read_bytes(), b"previous sound")
        self.assertEqual(
            (folder / "unrelated.wav").read_bytes(), b"another plugin")
