from __future__ import annotations

import tomllib
import unittest

from rom1.core.paths import CONFIG, retail_exe
from rom1.core.pe import Pe
from rom1.core.relocs import load as load_relocs
from rom1.delink.image import Image as DelinkImage
from rom1.retail_labels import censuses
from rom1.sema.image import Image as SemaImage
from rom1.tool.retail_census import fpo_rows, import_rows, string_rows
from rom1.tool.retail_partition import (eh_tables, load_fpo, recover_dyninit,
                                        recover_eh, recover_iat_thunks,
                                        recover_runtime_classes,
                                        recover_vtables)


class RetailEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pe = Pe(retail_exe())
        cls.fpo = load_fpo(cls.pe)
        cls.eh_groups, cls.frame_handler = recover_eh(
            cls.pe, set(load_relocs()))

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

    def test_global_eh_partition_closes_the_virtual_text_tail(self):
        _lo, text_end = self.pe.text_span()
        groups, actions, partition, tail = eh_tables(
            self.eh_groups, self.fpo, text_end)
        self.assertEqual(self.frame_handler, 0x153910)
        self.assertEqual(len(groups), 1382)
        self.assertEqual(len(actions), 4186)
        self.assertEqual(sum(row["region"] == "tail" for row in actions), 4118)
        self.assertEqual((len(partition), tail, text_end - tail),
                         (4134, 0x1868D0, 66448))
        self.assertEqual(max(group.stub + 10 for group in self.eh_groups), text_end)

    def test_crt_initializer_and_iat_thunk_closures(self):
        rows, helpers, xi, xc, initterm = recover_dyninit(self.pe, self.fpo)
        self.assertEqual((xi, xc, initterm),
                         ((0x1B8224, 0x1B8234),
                          (0x1B8000, 0x1B8220), 0x158450))
        self.assertEqual(sum(row["table"] == "XC" for row in rows), 135)
        self.assertEqual(len(helpers), 147)
        thunks = recover_iat_thunks(self.pe, self.fpo)
        self.assertEqual([(int(row["rva"], 0), int(row["iat_rva"], 0))
                          for row in thunks],
                         [(0x15BF40, 0x232C48), (0x15BF50, 0x232B30)])

    def test_mfc_runtime_class_and_vtable_census(self):
        records, rows = recover_runtime_classes(self.pe)
        vtables, providers = recover_vtables(self.pe, records)
        self.assertEqual((len(rows), len(vtables), len(providers)),
                         (117, 358, 114))
        self.assertEqual(records[0x1C2558]["class"], "AreaEffect")
        self.assertEqual(records[0x1C2558]["object_size"], 80)

    def test_model_census_uses_exact_extents_and_full_manual_partition(self):
        functions = censuses.functions()
        self.assertEqual(len(functions), 12563)
        kinds = {kind: sum(row["kind"] == kind for row in functions)
                 for kind in ("", "eh", "helper", "thunk", "pad")}
        self.assertEqual(kinds,
                         {"": 8280, "eh": 4134, "helper": 147,
                          "thunk": 2, "pad": 0})
        self.assertEqual(next(row["size"] for row in functions
                              if row["rva"] == 0x1000), 0x5B)
        data = censuses.data()
        self.assertEqual(len(data), 3476)
        self.assertEqual(sum(row["kind"] == "vtable" for row in data), 358)


if __name__ == "__main__":
    unittest.main()
