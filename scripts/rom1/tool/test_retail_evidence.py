from __future__ import annotations

import tomllib
import unittest

from rom1.core.paths import CONFIG, retail_exe
from rom1.core.pe import Pe
from rom1.core.relocs import load as load_relocs
from rom1.delink.image import Image as DelinkImage
from rom1.sema.image import Image as SemaImage
from rom1.tool.retail_census import fpo_rows, import_rows, string_rows


class RetailEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pe = Pe(retail_exe())

    def test_exact_partition_and_string_counts(self):
        self.assertEqual(len(fpo_rows(self.pe)), 4384)
        self.assertEqual(len(string_rows(self.pe)), 10296)

    def test_import_descriptor_order(self):
        rows = import_rows(self.pe)
        dlls = []
        for row in rows:
            if row["dll"] not in dlls:
                dlls.append(row["dll"])
        self.assertEqual(dlls, [
            "DDRAW.dll", "WINMM.dll", "DSOUND.dll", "ole32.dll",
            "smackw32.dll", "KERNEL32.dll", "USER32.dll", "GDI32.dll",
            "comdlg32.dll", "WINSPOOL.DRV", "ADVAPI32.dll", "SHELL32.dll",
            "COMCTL32.dll", "WSOCK32.dll",
        ])
        self.assertEqual(len(rows), 472)

    def test_all_consumers_share_the_recovered_relocations(self):
        sites = load_relocs()
        self.assertEqual(len(sites), 32454)
        self.assertEqual(DelinkImage(self.pe).reloc_sites, sites)
        self.assertEqual(sorted(SemaImage(self.pe).reloc), sites)
        self.assertEqual(self.pe.directories[5], (0, 0))

    def test_compiler_selection_is_fail_closed(self):
        selection = tomllib.loads((CONFIG / "compiler.toml").read_text())
        self.assertIn(selection["status"], ("unresolved", "selected"))
        if selection["status"] == "unresolved":
            self.assertEqual(selection["eligible_service_levels"], ["SP1", "SP2"])
        else:
            self.assertIn(selection["service_level"], ("SP1", "SP2"))
            self.assertTrue(selection["archive_set_sha256"])


if __name__ == "__main__":
    unittest.main()
