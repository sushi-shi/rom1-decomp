from __future__ import annotations

import tomllib
import unittest

from rom1.core.paths import CONFIG, retail_exe
from rom1.core.pe import Pe
from rom1.core.relocs import load as load_relocs
from rom1.core.tsv import read as read_tsv
from rom1.delink.image import Image as DelinkImage
from rom1.delink.implib import _decorated_export_imp
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

    def test_retail_decorated_vendor_imports_are_exact_iat_identities(self):
        _banner, fields, rows = read_tsv(
            CONFIG.parent / "vendor/smacker-3.1l/retail_imports.tsv")
        self.assertEqual(fields, ["hint", "symbol", "function", "stack_bytes"])
        self.assertEqual(len(rows), 16)
        self.assertEqual(
            [_decorated_export_imp(row["symbol"]) for row in rows],
            ["__imp_" + row["symbol"] for row in rows])
        self.assertIsNone(_decorated_export_imp("CreateFileA"))
        self.assertIsNone(_decorated_export_imp("_SmackOpen"))

    def test_all_consumers_share_the_recovered_relocations(self):
        sites = load_relocs()
        self.assertEqual(len(sites), 32454)
        self.assertEqual(DelinkImage(self.pe).reloc_sites, sites)
        self.assertEqual(sorted(SemaImage(self.pe).reloc), sites)
        self.assertEqual(self.pe.directories[5], (0, 0))
        _banner, fields, rows = read_tsv(
            CONFIG / "retail/reloc_referents.tsv")
        self.assertEqual(fields, ["function_rva", "target_rva", "site_rva",
                                  "owner", "addend", "occurrences",
                                  "provenance"])
        self.assertEqual(rows, [])

    def test_compiler_selection_is_fail_closed(self):
        selection = tomllib.loads((CONFIG / "compiler.toml").read_text())
        self.assertIn(selection["status"], ("unresolved", "selected"))
        if selection["status"] == "unresolved":
            self.assertEqual(selection["eligible_service_levels"], ["SP1", "SP2"])
        else:
            self.assertIn(selection["service_level"], ("SP1", "SP2"))
            self.assertEqual(selection["selection_policy"], "sp2-first")
            self.assertEqual(selection["fallback_candidate"], "vc5-sp1")
            self.assertRegex(selection["tool_set_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(selection["archive_set_sha256"])
            matrix = tomllib.loads((CONFIG / "toolchains.toml").read_text())
            candidate = next(row for row in matrix["candidate"]
                             if row["id"] == selection["candidate"])
            self.assertEqual(selection["tool_set_sha256"],
                             candidate["expected_tool_set_sha256"])
            self.assertEqual(selection["archive_set_sha256"],
                             candidate["expected_archive_set_sha256"])

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
        self.assertEqual((len(thunks), sum(int(row["size"], 0) for row in thunks)),
                         (474, 2844))
        self.assertEqual([int(row["rva"], 0) for row in thunks[:4]],
                         [0x0CEB20, 0x0CEB26, 0x0CEB2C, 0x0CEB32])
        self.assertEqual([int(row["rva"], 0) for row in thunks[-14:]],
                         list(range(0x16F120, 0x16F174, 6)))
        self.assertEqual(
            [(int(row["rva"], 0), row["import"]) for row in thunks
             if int(row["rva"], 0) in (0x15BF40, 0x15BF50)],
            [(0x15BF40, "KERNEL32.dll!GetCurrentThreadId"),
             (0x15BF50, "KERNEL32.dll!GetCurrentThread")])
        self.assertNotIn(0x15969D, {int(row["rva"], 0) for row in thunks})
        self.assertNotIn(0x1596B2, {int(row["rva"], 0) for row in thunks})

    def test_mfc_runtime_class_and_vtable_census(self):
        records, rows = recover_runtime_classes(self.pe)
        vtables, providers = recover_vtables(self.pe, records)
        self.assertEqual((len(rows), len(vtables), len(providers)),
                         (117, 358, 114))
        self.assertEqual(records[0x1C2558]["class"], "AreaEffect")
        self.assertEqual(records[0x1C2558]["object_size"], 80)

    def test_model_census_uses_exact_extents_and_full_manual_partition(self):
        functions = censuses.functions()
        self.assertEqual(len(functions), 13023)
        kinds = {kind: sum(row["kind"] == kind for row in functions)
                 for kind in ("", "eh", "helper", "thunk", "pad")}
        self.assertEqual(kinds,
                         {"": 8268, "eh": 4134, "helper": 147,
                          "thunk": 474, "pad": 0})
        self.assertEqual(next(row["size"] for row in functions
                              if row["rva"] == 0x1000), 0x5B)
        data = censuses.data()
        # Complete census: relocation/RTTI/code-vptr scan plus the eight
        # GetRuntimeClass witnesses whose first relocation site is absent.
        self.assertEqual(sum(row["kind"] == "vtable" for row in data), 425)
        self.assertEqual(
            [(row["rva"], row["kind"]) for row in data
             if row["rva"] in (0x1C086C, 0x1C0888)],
            [(0x1C086C, "string"), (0x1C0888, "string")])
        self.assertEqual(censuses.link_bands(), [
            (0x001000, 0x1868D0, "text-body"),
            (0x1868D0, 0x196C60, "eh-funclets"),
            (0x197000, 0x1B7450, "rdata"),
            (0x1B8000, 0x1CD600, "data-init"),
            (0x1CD600, 0x231DBC, "bss"),
            (0x232000, 0x235000, "idata"),
        ])


if __name__ == "__main__":
    unittest.main()
