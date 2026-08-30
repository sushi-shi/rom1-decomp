from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rom1.tool import parity


class ParityPinTest(unittest.TestCase):
    def test_local_files_excludes_gitignored_build_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / ".gitignore").write_text("*.obj\ntarget/\n")
            (root / "tracked.txt").write_text("source\n")
            (root / "new.txt").write_text("new source\n")
            (root / "output.obj").write_text("generated\n")
            (root / "target").mkdir()
            (root / "target" / "cache.bin").write_bytes(b"generated")
            subprocess.run(["git", "add", ".gitignore", "tracked.txt"],
                           cwd=root, check=True)
            with mock.patch.object(parity, "REPO", root):
                self.assertEqual(parity.local_files(), {
                    ".gitignore", "new.txt", "tracked.txt",
                })

    def test_git_checkout_must_be_the_advertised_pin(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".git").mkdir()
            result = subprocess.CompletedProcess([], 0, stdout="wrong\n")
            with mock.patch.object(parity.subprocess, "run", return_value=result):
                with self.assertRaisesRegex(ValueError, "expected pinned"):
                    parity.verify_upstream_revision(root)

    def test_dirty_pinned_checkout_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".git").mkdir()
            calls = [
                subprocess.CompletedProcess([], 0, stdout=parity.PIN + "\n"),
                subprocess.CompletedProcess([], 0, stdout=" M README.md\n"),
            ]
            with mock.patch.object(parity.subprocess, "run", side_effect=calls):
                with self.assertRaisesRegex(ValueError, "checkout is dirty"):
                    parity.verify_upstream_revision(root)

    def test_source_export_uses_per_file_hashes_without_git(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(
                    parity.subprocess, "run",
                    side_effect=AssertionError("git should not run")):
                parity.verify_upstream_revision(Path(td))


if __name__ == "__main__":
    unittest.main()
