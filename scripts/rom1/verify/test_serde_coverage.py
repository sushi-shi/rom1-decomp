from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rom1.verify.serde_coverage import load_selected_vendor_collisions


class SerdeCoverageTest(unittest.TestCase):
    def test_selected_mfc_ambiguous_fid_is_vendor_owned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            compiler = root / "compiler.toml"
            compiler.write_text(
                'status = "selected"\n'
                'archive_set_sha256 = "abc123"\n'
            )
            fid = root / "fid.tsv"
            fid.write_text(
                "# archive_set_sha256=abc123\n"
                "rva\tlib\tconfidence\trva_identity_count\tsource\tnotes\n"
                "0x184413\tNAFXCW.LIB\tAMBIG\t13\tanchored\t"
                "identity_multimatch=6;rva_multiidentity=13\n"
                "0x123456\tNAFXCW.LIB\tHIGH\t1\tanchored\t\n"
                "0x654321\tGAME.LIB\tAMBIG\t2\tanchored\t"
                "rva_multiidentity=2\n"
            )
            self.assertEqual(
                load_selected_vendor_collisions(fid, compiler),
                {0x184413},
            )

    def test_vendor_collision_census_hash_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            compiler = root / "compiler.toml"
            compiler.write_text(
                'status = "selected"\n'
                'archive_set_sha256 = "selected"\n'
            )
            fid = root / "fid.tsv"
            fid.write_text(
                "# archive_set_sha256=other\n"
                "rva\tlib\tconfidence\trva_identity_count\tsource\tnotes\n"
            )
            with self.assertRaisesRegex(ValueError, "does not match selected"):
                load_selected_vendor_collisions(fid, compiler)


if __name__ == "__main__":
    unittest.main()
