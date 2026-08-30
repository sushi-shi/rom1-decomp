"""rom1.verify.selftest - NEGATIVE CONTROLS for the ported gates.

A gate nobody has seen FAIL is a green light, not a check (the ported
gate_selftest doctrine: the slot-binding gate once parsed its own baseline's
banner as the header row and passed everything, forever). Every ported gate
gets at least one demonstrated failure case AND a clean pass; the tests are
hermetic (tmpdir trees / synthetic models) except the DATA_COMPGEN control
set, which deliberately runs against real base objs (skipped loudly when the
tree is unbuilt).

    rom1 verify selftest             # every control, one dot each
    rom1 verify selftest -v          # name each control as it runs
    rom1 verify selftest -k Ledger   # only the controls matching a name
"""

from __future__ import annotations

import os
import shutil
import struct
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock


# --------------------------------------------------------------------------- #
# fast tier                                                                   #
# --------------------------------------------------------------------------- #
class BoardControls(unittest.TestCase):
    def test_ratcheted_metric_cannot_creep_up(self):
        from rom1.verify import board
        base = board.load_baseline()
        floor = base.get("unexplained casts", 0)
        rows = [("unexplained casts", floor + 1)]
        self.assertTrue(board.gate(rows))            # a rise FAILS
        self.assertFalse(board.gate([("unexplained casts", floor)]))

    def test_reviewed_reinterpret_cast_inventory_only_tracks(self):
        from rom1.verify import board
        self.assertFalse(board.gate([("reinterpret_casts", 10_000)]))

    def test_non_ratcheted_metric_only_tracks(self):
        from rom1.verify import board
        self.assertFalse(board.gate([("Unknown ids", 10_000)]))

    def test_address_derived_identifiers_are_counted(self):
        from rom1.verify.board import _count_address_derived_identifiers
        src = ("i32 m_8; CMapStringToOb m_10map; CString local_14; "
               "DWORD g_ratingRaw_64da84;")
        self.assertEqual(_count_address_derived_identifiers(src), 4)
        clean = "i32 m_reserved; CMapStringToOb m_workersByName;"
        self.assertEqual(_count_address_derived_identifiers(clean), 0)

    def test_unmeasured_semantic_floor_survives_a_bless(self):
        from rom1.verify import board
        with tempfile.TemporaryDirectory() as td:
            sem = Path(td) / "sem.tsv"
            sem.write_text("caller-callee FAKE-VIEW\t0\ntruncated masks\t0\n")
            with mock.patch.object(board, "SEMANTIC_BASELINE", sem), \
                 mock.patch.object(board, "TEXT_BASELINE", Path(td) / "t.tsv"):
                board.save_baseline([("nested static_casts", 25)],
                                    include_semantic=True)
                kept = board.load_baseline()
        self.assertEqual(kept.get("truncated masks"), 0)   # floor NOT dropped
        self.assertEqual(kept.get("nested static_casts"), 25)


class BansControls(unittest.TestCase):
    def _scan(self, text):
        from rom1.verify import bans
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "probe.h"
            f.write_text(text)
            with mock.patch("rom1.verify.bans.source_files",
                            return_value=[f]):
                return list(bans.scan())

    def test_manual_vtable_idiom_fails(self):
        hits = self._scan("struct CFooVtbl { void* slots[4]; };\n"
                          "int use(CFoo* p) { return p->vtbl != 0; }\n")
        self.assertGreaterEqual(len(hits), 2)

    def test_prose_does_not_trip_the_ban(self):
        hits = self._scan("// the old struct CFooVtbl idiom is banned\n"
                          "class CFoo { virtual void Render(); };\n")
        self.assertEqual(hits, [])


class CompilerArtifactControls(unittest.TestCase):
    def _scan(self, text):
        from rom1.verify import compiler_artifacts as ca
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Probe.cpp"
            path.write_text(text)
            return ca.source_findings(
                [path], placement_allow=Counter(), dtor_allow=Counter(),
                low_level_allow=Counter()
            )

    def test_allocator_calls_and_realizers_fail(self):
        findings = self._scan(
            "void* F(unsigned n) { return ::operator new(n); }\n"
            "CThing* RealizeCThing() { return new CThing(); }\n"
        )
        self.assertTrue(any("compiler allocation call" in row for row in findings))
        self.assertTrue(any("forced-emission helper" in row for row in findings))

    def test_comments_and_normal_new_expressions_pass(self):
        findings = self._scan(
            "// ::operator delete(p); CThing* RealizeCThing() {}\n"
            "CThing* F() { return new CThing(); }\n"
        )
        self.assertEqual(findings, [])

    def test_unreviewed_explicit_destructor_call_fails(self):
        findings = self._scan("void F(CThing* p) { p->~CThing(); }\n")
        self.assertTrue(any("explicit destructor call" in row for row in findings))

    def test_reviewed_typed_teardown_callback_passes(self):
        from rom1.verify import compiler_artifacts as ca
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Probe.h"
            path.write_text("template<class T> void dtf(T* p) { p->~T(); }\n")
            allowed = Counter({(str(path), "T"): 1})
            findings = ca.source_findings(
                [path], placement_allow=Counter(), dtor_allow=allowed,
                low_level_allow=Counter()
            )
        self.assertEqual(findings, [])

    def test_base_only_realizer_is_fatal(self):
        from rom1.verify import compiler_artifacts as ca
        rows = [("probe", "?RealizeCThing@@YAPAVCThing@@XZ"),
                ("probe", "??_GCThing@@UAEPAXI@Z")]
        self.assertEqual(len(ca.base_only_suspicious(rows)), 1)


class CastControls(unittest.TestCase):
    def test_seam_self_recursion_is_caught(self):
        from rom1.verify import casts
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "src").mkdir()
            (Path(td) / "include").mkdir()
            f = Path(td) / "src/Probe.cpp"
            f.write_text("inline u16* Scratch16() { return Scratch16(); }\n")
            with mock.patch.object(casts, "REPO", Path(td)):
                self.assertEqual(len(casts.self_recursion()), 1)
                f.write_text("inline u16* Scratch16() { "
                             "return reinterpret_cast<u16*>(g_scratch); }\n")
                self.assertEqual(casts.self_recursion(), [])

    def test_different_arity_overload_forwarding_is_not_self_recursion(self):
        from rom1.verify import casts
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "src").mkdir()
            (Path(td) / "include").mkdir()
            f = Path(td) / "include/Probe.h"
            f.write_text(
                "inline int Blt(HDC dc) { return Blt(dc, 0, 0); }\n"
            )
            with mock.patch.object(casts, "REPO", Path(td)):
                self.assertEqual(casts.self_recursion(), [])

    def test_unreasoned_cast_is_open_and_reasoned_is_parked(self):
        from rom1.verify import casts
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "src").mkdir()
            (Path(td) / "include").mkdir()
            f = Path(td) / "src/Probe.cpp"
            with mock.patch.object(casts, "REPO", Path(td)):
                f.write_text("u16* p = reinterpret_cast<u16*>(g_x);\n")
                _forced, openv = casts.scan_ledger()
                self.assertEqual(sum(len(v) for v in openv.values()), 1)
                f.write_text("u16* p = reinterpret_cast<u16*>(g_x); "
                             "// byte-forced: no reloc, bare imm\n")
                _forced, openv = casts.scan_ledger()
                self.assertEqual(sum(len(v) for v in openv.values()), 0)

    def test_a_cast_in_prose_is_not_a_site(self):
        from rom1.verify import casts
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "src").mkdir()
            (Path(td) / "include").mkdir()
            (Path(td) / "src/P.cpp").write_text(
                "// reinterpret_cast<u16*>(g_x) would be wrong here\n")
            with mock.patch.object(casts, "REPO", Path(td)):
                forced, openv = casts.scan_ledger()
                self.assertEqual((sum(forced.values()),
                                  sum(len(v) for v in openv.values())), (0, 0))


class EnumDomainControls(unittest.TestCase):
    def _audit(self, files):
        from rom1.verify import enum_domains
        with tempfile.TemporaryDirectory() as td:
            paths = []
            for name, text in files.items():
                p = Path(td) / name
                p.write_text(text)
                paths.append(p)
            real = Path(td)
            with mock.patch.object(enum_domains, "source_files",
                                   lambda: iter(paths)), \
                 mock.patch.object(enum_domains, "REPO", real):
                return enum_domains.audit()

    def test_split_width_disagreement_is_fatal(self):
        fatal, _w, _d = self._audit({
            "A.h": "GZ_ENUM_BEGIN_SPLIT(Tool, u8)\nTOOL_GAUNTLETZ = 0,\n"
                   "GZ_ENUM_END_SPLIT(Tool)\n",
            "B.h": "GZ_ENUM_STORAGE(Tool, i32) m_tool;\n"})
        self.assertTrue(any("two beliefs" in f for f in fatal))

    def test_matching_split_width_passes(self):
        fatal, _w, _d = self._audit({
            "A.h": "GZ_ENUM_BEGIN_SPLIT(Tool, u8)\nTOOL_GAUNTLETZ = 0,\n"
                   "GZ_ENUM_END_SPLIT(Tool)\n",
            "B.h": "GZ_ENUM_STORAGE(Tool, u8) m_tool;\n"})
        self.assertEqual(fatal, [])

    def test_bare_header_enum_is_fatal_and_tag_type_exempt(self):
        fatal, _w, _d = self._audit({
            "A.h": "enum Tool { TOOL_A = 1, TOOL_B = 2 };\n"})
        self.assertTrue(any("bare `enum Tool`" in f for f in fatal))
        fatal, _w, _d = self._audit({
            "A.h": "enum ENoSeed { NO_SEED };\n"})
        self.assertEqual(fatal, [])

    def test_range_test_against_a_member_is_fatal(self):
        fatal, _w, _d = self._audit({
            "A.h": "GZ_ENUM_BEGIN(Pickup)\nPICKUP_WINGZ = 22,\n"
                   "GZ_ENUM_END(Pickup)\n",
            "B.cpp": "if (n > PICKUP_WINGZ) return 0;\n"})
        self.assertTrue(any("names a MEMBER" in f for f in fatal))


class ConstantControls(unittest.TestCase):
    def _scan(self, source, *, flags=None):
        from rom1.verify import constants
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "src").mkdir()
            path = root / "src/Probe.cpp"
            path.write_text(source)
            entry = {"directory": str(root), "file": "src/Probe.cpp",
                     "arguments": ["clang-cl", "/c", "src/Probe.cpp", "/TP"]}
            patch = (mock.patch.object(constants, "_flags", return_value=flags)
                     if flags is not None else mock.patch.object(
                         constants, "_flags", wraps=constants._flags))
            with patch:
                return constants.scan_entries([entry], repo=root, jobs=1)

    def test_typed_pointer_bool_and_enum_sites_are_proven(self):
        source = ("#define NULL 0\n"
                  "enum Kind { KIND_NONE = 0, KIND_ONE = 1 };\n"
                  "bool BoolReturn() { return 0; }\n"
                  "int* PtrReturn() { return 0; }\n"
                  "void Takes(bool b, int* p);\n"
                  "void Probe(Kind kind) { bool b = 1; int* p = 0; "
                  "Takes(0, 0); if (p == 0) {} if (b == 0) {} "
                  "if (kind == 0) {} }\n"
                  "int Arithmetic(int n) { return n + 0; }\n")
        sites, errors = self._scan(source)
        self.assertEqual(errors, [])
        replacements = [s.replacement for s in sites if s.proven]
        self.assertEqual(replacements.count("NULL"), 4)
        self.assertEqual(replacements.count("false"), 3)
        self.assertEqual(replacements.count("true"), 1)
        self.assertEqual(replacements.count("KIND_NONE"), 1)
        arithmetic = [s for s in sites
                      if s.function.startswith("Arithmetic") and s.spelling == "0"]
        self.assertEqual(len(arithmetic), 1)
        self.assertFalse(arithmetic[0].proven)

    def test_named_spellings_and_explicit_ingest_cast_pass(self):
        source = ("enum Kind { KIND_NONE = 0 };\n"
                  "#define NULL 0\n"
                  "bool B() { return false; }\n"
                  "int* P() { return NULL; }\n"
                  "Kind K(int n) { return static_cast<Kind>(0); }\n"
                  "Kind KN(int n) { return static_cast<Kind>(-1); }\n")
        sites, errors = self._scan(source)
        self.assertEqual(errors, [])
        self.assertEqual([s for s in sites if s.proven], [])

    def test_outer_result_cast_does_not_hide_pointer_call_argument(self):
        source = ("#define NULL 0\n"
                  "struct Node {};\n"
                  "void* Create(int* context);\n"
                  "Node* Probe() {\n"
                  "  return static_cast<Node*>(Create(0));\n"
                  "}\n")
        sites, errors = self._scan(source)
        self.assertEqual(errors, [])
        pointer_zeroes = [s for s in sites
                          if s.function.startswith("Probe") and s.value == 0]
        self.assertEqual(len(pointer_zeroes), 1)
        self.assertEqual(pointer_zeroes[0].replacement, "NULL")

    def test_call_arguments_do_not_supply_comparison_operand_type(self):
        source = ("enum Kind { KIND_NONE = 0 };\n"
                  "int IntResult(Kind kind);\n"
                  "int IntWithBool(bool value);\n"
                  "void Probe(Kind kind, bool value) {\n"
                  "  if (IntResult(kind) == 0) {}\n"
                  "  if (IntWithBool(value) != 1) {}\n"
                  "}\n")
        sites, errors = self._scan(source)
        self.assertEqual(errors, [])
        comparisons = [s for s in sites
                       if s.function.startswith("Probe") and s.value in (0, 1)]
        self.assertEqual(len(comparisons), 2)
        self.assertEqual([s for s in comparisons if s.proven], [])

    def test_direct_enum_and_bool_operands_survive_expression_wrappers(self):
        source = ("enum Kind { KIND_NONE = 0, KIND_ONE = 1 };\n"
                  "Kind KindResult();\n"
                  "bool BoolResult();\n"
                  "void Probe(Kind kind, int value) {\n"
                  "  if (KindResult() == 0) {}\n"
                  "  if ((kind) != 1) {}\n"
                  "  if (static_cast<Kind>(value) == 0) {}\n"
                  "  if (BoolResult() == 0) {}\n"
                  "}\n")
        sites, errors = self._scan(source)
        self.assertEqual(errors, [])
        replacements = [s.replacement for s in sites
                        if s.function.startswith("Probe") and s.proven]
        self.assertEqual(replacements.count("KIND_NONE"), 2)
        self.assertEqual(replacements.count("KIND_ONE"), 1)
        self.assertEqual(replacements.count("false"), 1)

    def test_pointer_zero_without_visible_null_is_not_a_fix(self):
        sites, errors = self._scan("int* P() { return 0; }\n")
        self.assertEqual(errors, [])
        self.assertEqual([s for s in sites if s.proven], [])
        self.assertTrue(any("NULL is not visible" in s.reason for s in sites))

    def test_conditional_pointer_and_integer_boolean_aliases_are_proven(self):
        source = ("#define NULL 0\n"
                  "typedef int BOOL;\n"
                  "typedef int b32;\n"
                  "int* Pick(bool use, int* value) { return use ? value : 0; }\n"
                  "BOOL WinBool() { return 1; }\n"
                  "void Takes(BOOL win, b32 project);\n"
                  "void Probe(BOOL win) { b32 project = 0; Takes(0, 1); "
                  "if (win == 0) {} project = 1; }\n")
        sites, errors = self._scan(source)
        self.assertEqual(errors, [])
        replacements = [s.replacement for s in sites if s.proven]
        self.assertEqual(replacements.count("NULL"), 1)
        self.assertEqual(replacements.count("false"), 3)
        self.assertEqual(replacements.count("true"), 3)

    def test_expected_type_does_not_retype_nested_numeric_expressions(self):
        source = ("typedef int BOOL;\n"
                  "BOOL ReturnArithmetic(int n) { return n + 0; }\n"
                  "void Takes(BOOL value);\n"
                  "void Probe(int n) { Takes(n + 0); }\n")
        sites, errors = self._scan(source)
        self.assertEqual(errors, [])
        self.assertEqual([s for s in sites if s.proven], [])

    def test_proven_fixer_uses_offsets_and_rejects_stale_source(self):
        from rom1.verify import constants
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = "typedef int BOOL; BOOL F() { return 0; }\n"
            sites, errors = self._scan(source)
            self.assertEqual(errors, [])
            path = root / "src/Probe.cpp"
            path.parent.mkdir(parents=True)
            path.write_text(source)
            applied = constants.apply_proven(sites, repo=root)
            self.assertEqual(applied, 1)
            self.assertEqual(path.read_text(),
                             "typedef int BOOL; BOOL F() { return false; }\n")
            with self.assertRaises(RuntimeError):
                constants.apply_proven(sites, repo=root)

    def test_legacy_boolean_macro_gate_ignores_comments_and_strings(self):
        from rom1.verify import constants
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "src/Probe.cpp"
            path.parent.mkdir(parents=True)
            path.write_text("int a = TRUE; // FALSE\nconst char* s = \"TRUE\";\n")
            self.assertEqual(
                constants.legacy_boolean_spellings(repo=root),
                ["src/Probe.cpp:1:9: TRUE -> true"])

    def test_numeric_review_groups_preserve_context_without_claiming_semantics(self):
        source = ("void Sink(int value);\n"
                  "int Probe(int value) {\n"
                  "  int payload[] = { 10, 20 };\n"
                  "  Sink(30);\n"
                  "  Sink(0);\n"
                  "  if (value < 40) return (value & 0xff) + 50;\n"
                  "  return payload[value];\n"
                  "}\n")
        sites, errors = self._scan(source)
        self.assertEqual(errors, [])
        groups = {s.value: s.review_group for s in sites
                  if s.function.startswith("Probe")}
        self.assertEqual(groups[10], "initializer-payload")
        self.assertEqual(groups[20], "initializer-payload")
        self.assertEqual(groups[30], "call-argument")
        self.assertEqual(groups[0], "call-argument")
        self.assertEqual(groups[40], "comparison-or-bound")
        self.assertEqual(groups[0xff], "bitwise-or-packing")
        self.assertEqual(groups[50], "arithmetic")
        self.assertEqual([s for s in sites if s.proven], [])

    def test_consumer_rejects_missing_cl_driver_mode(self):
        _sites, errors = self._scan("int F() { return 0; }\n", flags=["/TP"])
        self.assertEqual(len(errors), 1)
        self.assertIn("requires --driver-mode=cl", errors[0])


class LabelStyleControls(unittest.TestCase):
    def _scan(self, text):
        from rom1.verify import label_style
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "Probe.cpp"
            p.write_text(text)
            return label_style.scan(p), label_style.compgen_order(p)

    def test_off_canon_and_volatile_ordinal_fail(self):
        hits, _o = self._scan("RVA(0x12345, 0x10)\n"           # 5-digit addr
                              "RVA_COMPGEN(0x00012345, 0x10, _$E123)\n")
        self.assertTrue(any("off-canon" in why for _l, why, _t in hits))
        self.assertTrue(any("volatile" in why for _l, why, _t in hits))

    def test_unblessed_marker_fails_and_blessed_passes(self):
        hits, _o = self._scan("// @fold-TODO: merge with CFoo\n")
        self.assertEqual(len(hits), 1)
        hits, _o = self._scan("// @early-stop cfg wall, branch counts differ\n")
        self.assertEqual(hits, [])

    def test_compgen_out_of_rva_order_fails(self):
        _h, order = self._scan("RVA(0x00001000, 0x10)\n"
                               "RVA_COMPGEN(0x00003000, 0x10, ??_GX@@UAEPAXI@Z)\n"
                               "RVA(0x00002000, 0x10)\n")
        self.assertEqual(len(order), 1)

    def test_canonical_labels_pass(self):
        hits, order = self._scan("RVA(0x00001000, 0x10)\n"
                                 "RVA_COMPGEN(0x00001400, 0x0, ??_GX@@UAEPAXI@Z)\n"
                                 "RVA(0x00002000, 0x1f)\n"
                                 "RVA_DYNINIT(0x00003000, 0x1f, "
                                 "CActRegPool<CGrunt>::s_table)\n")
        self.assertEqual((hits, order), ([], []))


class IncludeOrderControls(unittest.TestCase):
    def test_duplicate_and_disorder_are_caught_conservingly(self):
        from rom1.verify import include_order as io
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "Probe.cpp"
            p.write_text("#include <rva.h>\n#include <Zed.h>\n"
                         "#include <Abc.h>\n#include <Zed.h>\n\nint x;\n")
            head, entries, tail = io.parse(p)
            headers = [h for _c, h in entries]
            dropped = [h for i, h in enumerate(headers) if h in headers[:i]]
            self.assertEqual(dropped, ["Zed.h"])
            want = io.render(head, entries, tail, None)
            self.assertNotEqual(want,
                                p.read_text().splitlines())   # out of order
            io.assert_conserved(p, p.read_text().splitlines(), want, dropped)

    def test_a_lost_line_aborts_the_rewrite(self):
        from rom1.verify import include_order as io
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "Probe.cpp"
            p.write_text("#include <A.h>\n// @early-stop\nint x;\n")
            before = p.read_text().splitlines()
            butchered = ["#include <A.h>", "int x;"]     # marker vanished
            with self.assertRaises(SystemExit):
                io.assert_conserved(p, before, butchered, [])


# --------------------------------------------------------------------------- #
# normal tier (synthetic Models)                                              #
# --------------------------------------------------------------------------- #
def _binding(rva, name, unit="probe", channel="src", kind="", size=0x10,
             space="text", aliases=()):
    from rom1.model import Binding
    return Binding(rva, size, kind, space, name, unit, channel,
                   tuple(aliases), ())


def _model(functions=(), data=(), violations=()):
    from rom1.model import Model
    return Model(list(functions), list(data), list(violations))


class UniqueNamesControls(unittest.TestCase):
    def test_one_name_at_two_rvas_is_fatal(self):
        from rom1.verify import unique_names
        m = _model([_binding(0x1000, "?F@@YAXXZ"),
                    _binding(0x2000, "?F@@YAXXZ")])
        with mock.patch("rom1.model.resolve", return_value=m):
            bad, _n = unique_names.findings()
        self.assertTrue(any("name-injectivity" in b for b in bad))

    def test_model_violation_is_fatal_and_clean_passes(self):
        from rom1.verify import unique_names
        m = _model([_binding(0x1000, "?F@@YAXXZ")], violations=["boom"])
        with mock.patch("rom1.model.resolve", return_value=m):
            bad, _n = unique_names.findings()
        self.assertTrue(any("model violation" in b for b in bad))
        m = _model([_binding(0x1000, "?F@@YAXXZ"),
                    _binding(0x2000, "?G@@YAXXZ")])
        with mock.patch("rom1.model.resolve", return_value=m):
            bad, _n = unique_names.findings()
        self.assertEqual(bad, [])

    def test_zero_claims_never_pass_vacuously(self):
        from rom1.verify import unique_names
        with mock.patch("rom1.model.resolve", return_value=_model()):
            bad, _n = unique_names.findings()
        self.assertTrue(any("vacuously" in b for b in bad))

    def test_a_fid_label_repeat_is_not_a_finding(self):
        from rom1.verify import unique_names
        m = _model([_binding(0x1000, "??_G__non_rtti_object@@UAEPAXI@Z",
                             channel="functions_static_libs"),
                    _binding(0x2000, "??_G__non_rtti_object@@UAEPAXI@Z",
                             channel="functions_static_libs"),
                    _binding(0x3000, "?F@@YAXXZ")])
        with mock.patch("rom1.model.resolve", return_value=m):
            bad, _n = unique_names.findings()
        self.assertEqual(bad, [])


class LibraryOverlapControls(unittest.TestCase):
    def test_src_claim_on_a_static_libs_row_is_loud(self):
        from rom1.retail_labels import Claim
        from rom1.verify import library_overlap
        alias = Claim(0x1000, "??0CFile@@QAE@XZ", "func",
                      "functions_static_libs", None, "", {})
        m = _model([_binding(0x1000, "?Open@CFileIO@@QAEHXZ",
                             aliases=[alias])])
        with mock.patch("rom1.model.resolve", return_value=m):
            bad, _n = library_overlap.findings()
        self.assertEqual(len(bad), 1)
        m = _model([_binding(0x1000, "?Open@CFileIO@@QAEHXZ")])
        with mock.patch("rom1.model.resolve", return_value=m):
            bad, _n = library_overlap.findings()
        self.assertEqual(bad, [])


class TuOrderControls(unittest.TestCase):
    def test_descending_file_order_is_a_violation(self):
        from rom1.verify.tu_order import Entry, check_intra
        seq = [Entry(0x2000, 0x10, 1, "A::f", "t"),
               Entry(0x1000, 0x10, 2, "A::g", "t")]
        self.assertTrue(check_intra({"t": seq}))
        seq = [Entry(0x1000, 0x10, 1, "A::f", "t"),
               Entry(0x2000, 0x10, 2, "A::g", "t")]
        self.assertEqual(check_intra({"t": seq}), {})

    def test_overlapping_spans_are_a_violation(self):
        from rom1.verify.tu_order import Entry, check_intra
        seq = [Entry(0x1000, 0x200, 1, "A::f", "t"),
               Entry(0x1100, 0x10, 2, "A::g", "t")]
        self.assertTrue(check_intra({"t": seq}))

    def test_interleaving_tus_are_a_violation(self):
        from rom1.verify.tu_order import Entry, check_inter
        a = [Entry(0x1000, 0x10, 1, "A::f", "a"),
             Entry(0x3000, 0x10, 2, "A::g", "a")]
        b = [Entry(0x2000, 0x10, 1, "B::f", "b"),
             Entry(0x4000, 0x10, 2, "B::g", "b")]
        self.assertTrue(check_inter({"a": a, "b": b}))

    def test_the_tu_key_accepts_the_project_unit_spelling(self):
        """`--tu` keys on the .cpp STEM (`Grunt`) while every other --unit
        flag takes the unit (`grunt`); the correct unit name answered "no
        such TU"."""
        import contextlib
        import io

        from rom1.verify import tu_order as to
        seq = [to.Entry(0x1000, 0x10, 1, "CGrunt::f", "src/Grunt.cpp")]
        with mock.patch.object(to, "load_in_file_order",
                               return_value={"Grunt": seq}), \
             mock.patch.object(to, "load_exiles", return_value={}):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(to.main(["--tu", "grunt"]), 0)
            self.assertIn("Grunt  (1 functions", out.getvalue())
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(to.main(["--tu", "zzz"]), 2)
            self.assertIn("no such TU: zzz", err.getvalue())
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(to.main(["--tu", "grun"]), 2)
            self.assertIn("did you mean: Grunt", err.getvalue())

    def test_a_stale_exile_row_fails(self):
        from rom1.verify.tu_order import verify_exiles
        exiles = {0x184610: ("MenuItem", "MenuPage", "CMenuItem::GetUpName")}
        bad = verify_exiles(exiles, {}, {}, {})     # nothing pins/emits/hosts
        self.assertEqual(len(bad), 2)               # no owner pin + no host span
        bad = verify_exiles(exiles, {0x184610: "MenuItem"},
                            {"MenuPage": (0x184000, 0x185000)}, {})
        self.assertEqual(bad, [])


class DataTuOrderControls(unittest.TestCase):
    def test_a_def_inside_a_foreign_band_is_a_crossing(self):
        from rom1.verify import data_tu_order as dto
        m = _model(data=[
            _binding(0x1000, "?g_a@@3HA", unit="alpha", space="data"),
            _binding(0x3000, "?g_b@@3HA", unit="alpha", space="data"),
            _binding(0x2000, "?g_x@@3HA", unit="beta", space="data")])
        with mock.patch("rom1.model.resolve", return_value=m), \
             mock.patch.object(dto, "_unit_basename",
                               return_value={"alpha": "Alpha.cpp",
                                             "beta": "Beta.cpp"}), \
             mock.patch.object(dto, "load_baseline", return_value=set()):
            self.assertTrue(dto.gate_findings())
        m = _model(data=[
            _binding(0x1000, "?g_a@@3HA", unit="alpha", space="data"),
            _binding(0x1100, "?g_b@@3HA", unit="alpha", space="data"),
            _binding(0x2000, "?g_x@@3HA", unit="beta", space="data")])
        with mock.patch("rom1.model.resolve", return_value=m), \
             mock.patch.object(dto, "_unit_basename",
                               return_value={"alpha": "Alpha.cpp",
                                             "beta": "Beta.cpp"}), \
             mock.patch.object(dto, "load_baseline", return_value=set()):
            self.assertEqual(dto.gate_findings(), [])

    def test_different_storage_bands_do_not_cross(self):
        from rom1.verify import data_tu_order as dto
        m = _model(data=[
            _binding(0x1000, "?g_a@@3HA", unit="alpha", space="data"),
            _binding(0x3000, "?g_b@@3HA", unit="alpha", space="data"),
            _binding(0x2000, "?g_x@@3HA", unit="beta", space="bss")])
        with mock.patch("rom1.model.resolve", return_value=m), \
             mock.patch.object(dto, "_unit_basename", return_value={}), \
             mock.patch.object(dto, "load_baseline", return_value=set()):
            self.assertEqual(dto.gate_findings(), [])


class UndefinedClosureControls(unittest.TestCase):
    def _run(self, bdef, bund, tnames, baseline=frozenset()):
        from rom1.verify import undefined_closure as uc
        with mock.patch.object(uc, "live_base_objs", return_value=["x"]), \
             mock.patch.object(uc, "_sym_sets",
                               side_effect=[(bdef, bund), (tnames, set())]), \
             mock.patch.object(uc, "lib_symbols", return_value=set()), \
             mock.patch.object(uc, "_rtti_classes", return_value=set()), \
             mock.patch.object(uc, "source_library_shadows",
                               return_value=[]), \
             mock.patch.object(uc, "_read_baseline",
                               return_value=set(baseline)):
            return uc.analyse()

    def test_pure_phantom_class_is_a_fake_view(self):
        phantom, _sh, _dec = self._run(
            bdef={"?Run@CReal@@QAEXXZ"},
            bund={"?M@CPhantomView@@QAEXXZ"},
            tnames=set())
        self.assertIn("CPhantomView", phantom)

    def test_a_real_class_with_bodies_is_not_a_phantom(self):
        phantom, _sh, _dec = self._run(
            bdef={"?Run@CGrunt@@QAEXXZ"},
            bund={"?Walk@CGrunt@@QAEXXZ"},     # unreconstructed, not fake
            tnames=set())
        self.assertEqual(dict(phantom), {})

    def test_declared_only_alias_is_debt_unless_retail_names_it(self):
        _p, _s, declared = self._run(
            bdef=set(), bund={"?Check4_2ce8@@YGHH@Z"}, tnames=set())
        self.assertIn("?Check4_2ce8@@YGHH@Z", declared)
        _p, _s, declared = self._run(
            bdef=set(), bund={"?Check4_2ce8@@YGHH@Z"},
            tnames={"?Check4_2ce8@@YGHH@Z"})   # retail namespace has it
        self.assertEqual(declared, set())


# --------------------------------------------------------------------------- #
# full tier                                                                   #
# --------------------------------------------------------------------------- #
class VtableTierControls(unittest.TestCase):
    def test_virtuality_is_read_off_the_mangled_name(self):
        from rom1.verify.vtables import classify_storage, split_mangled
        nm, quals, st = split_mangled("?RenderFrame@CFaderFlat@@UAEXH@Z")
        self.assertEqual((nm, quals[0], classify_storage(st)),
                         ("RenderFrame", "CFaderFlat", "virtual"))
        nm, quals, st = split_mangled("?Gap_17f660@@YAXXZ")
        self.assertEqual(classify_storage(st), "free function")
        nm, quals, st = split_mangled("??1CGrunt@@UAE@XZ")
        self.assertEqual((nm, quals[0], classify_storage(st)),
                         ("??1", "CGrunt", "virtual"))
        self.assertIsNone(split_mangled("_memcpy"))

    def test_wiring_defect_fails_and_inherited_virtual_passes(self):
        from rom1.verify.vtables import (base_closure, classify_storage,
                                           split_mangled)
        classes = {"CFaderFlat": (2, ["CFader"]), "CFader": (2, [])}
        allowed = base_closure("CFaderFlat", classes)
        # inherited slot bound to the base's virtual: allowed
        _n, quals, st = split_mangled("?OnInit@CFader@@UAEXXZ")
        self.assertIn(quals[0], allowed)
        self.assertEqual(classify_storage(st), "virtual")
        # a free function at the slot: the WIRING defect
        _n, _q, st = split_mangled("?Gap_17f660@@YAXXZ")
        self.assertNotEqual(classify_storage(st), "virtual")
        # a virtual of a FOREIGN class: MISBOUND
        _n, quals, st = split_mangled("?Render@CImage@@UAEXXZ")
        self.assertNotIn(quals[0], allowed)

    def test_under_virtualized_class_is_counted(self):
        from rom1.verify.vtables import resolved_virtuals
        classes = {"CShell": (1, [])}
        self.assertLess(resolved_virtuals("CShell", classes), 5)
        classes = {"CReal": (3, ["CCmdTarget"])}   # 3 own + 8 credited
        self.assertGreaterEqual(resolved_virtuals("CReal", classes), 11)

    def test_slot_resolution_honours_the_raw_target_first(self):
        from rom1.verify.vtables import resolve_slot
        syms = {0x1000: ("?Unload@CPool@@UAEXXZ", "pool"),
                0x2000: ("?FreeAll@CPool@@QAEXXZ", "pool")}
        # raw = a real 5-byte `jmp FreeAll` override: the override IS Unload
        self.assertEqual(resolve_slot(syms, 0x1000, 0x2000)[1],
                         "?Unload@CPool@@UAEXXZ")
        # anonymous ILT thunk at raw: chase to the body
        self.assertEqual(resolve_slot(syms, 0x5555, 0x2000)[1],
                         "?FreeAll@CPool@@QAEXXZ")
        self.assertIsNone(resolve_slot(syms, 0x5555, 0x6666))


class AssertRelocsControls(unittest.TestCase):
    def test_a_misdirected_referent_is_caught(self):
        """Poison ONE symbol's rva resolution and the multiset audit must
        report a WRONG row where the clean run reports none."""
        from rom1.core.paths import BUILD
        from rom1.verify import assert_relocs as ar
        if not (BUILD / "objdiff/base/scenarioconfig.obj").is_file():
            self.skipTest("base objs absent (unbuilt tree)")
        clean, _seen = ar.audit(unit_filter="scenarioconfig")
        if clean:
            self.skipTest("scenarioconfig not clean on this tree state - control "
                          "needs a green substrate")
        real = ar.Resolver.resolve_base

        def poisoned(self, name, typ, addend):
            out = real(self, name, typ, addend)
            if "CButeMgr" in name and out:
                return {v + 0x10 for v in out}     # shift every CButeMgr ref
            return out
        with mock.patch.object(ar.Resolver, "resolve_base", poisoned):
            bad, _seen = ar.audit(unit_filter="scenarioconfig")
        self.assertTrue(any("WRONG" in p for _u, _n, p in bad))

    def test_a_fabricated_symbol_is_fake(self):
        from rom1.verify import assert_relocs as ar
        resolver = mock.Mock()
        resolver.rva_of = lambda name: set()
        self.assertTrue(ar._is_fake("?M@CPhantom@@QAEXXZ", set(), resolver,
                                    set()))
        self.assertFalse(ar._is_fake("?M@CPhantom@@QAEXXZ",
                                     {"?M@CPhantom@@QAEXXZ"}, resolver,
                                     set()))
        self.assertFalse(ar._is_fake("??_C@_01ABC@x?$AA@", set(), resolver,
                                     set()))


class DataRelocsControls(unittest.TestCase):
    def test_an_any_comdat_number_is_not_an_associative_ordinal(self):
        """Integration control for the section-manifest consumer.

        cl 5 writes an `Any` COMDAT's own section number into the aux Number
        field.  Passing it through as an association produces an invalid
        `selection=2, associative_ordinal=N` manifest row which the delinker
        must reject.
        """
        import struct

        from rom1.delink import coffx, data_manifest

        header_size = 20
        section_size = 40
        raw_offset = header_size + section_size
        symbol_offset = raw_offset + 4
        header = struct.pack(
            "<HHIIIHH",
            0x14C,
            1,
            0,
            symbol_offset,
            2,
            0,
            0,
        )
        section = struct.pack(
            "<8sIIIIIIHHI",
            b".data\0\0\0",
            0,
            0,
            4,
            raw_offset,
            0,
            0,
            0,
            0,
            0xC0301040,
        )
        symbol = struct.pack("<8sIhHBB", b".data\0\0\0", 0, 1, 0, 3, 1)
        # Length=4, Number=1, Selection=Any.  Number is not an association.
        aux = struct.pack("<IHHIHB3x", 4, 0, 0, 0, 1, 2)
        payload = header + section + b"\0" * 4 + symbol + aux + struct.pack("<I", 4)

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "probe.obj"
            path.write_bytes(payload)
            parsed = coffx.Obj(path).section_table[0]

        self.assertEqual(parsed["comdat"], 2)
        self.assertEqual(parsed["assoc"], 0)
        row = dict(parsed, object="probe.c", ordinal=1, rva=0x1000,
                   storage="data", provenance="selftest")
        line = data_manifest.section_manifest_bytes([row]).decode().splitlines()[1]
        self.assertEqual(line.split("\t")[7:10], ["2", "-", "data"])

    def test_an_injected_wrong_vtable_slot_is_caught(self):
        """The ported negative control: redirect one vtable slot's relocation
        in a copy of a real normalized base obj - the sieve must return WRONG
        (and a deleted record must return MISSING)."""
        import shutil
        import struct as st

        from rom1.delink.coffx import Obj
        from rom1.verify import data_relocs as dr
        from rom1.walls import pairscan
        src_pair = pairscan.pairs({"projectile"}).get("projectile")
        if not src_pair:
            self.skipTest("normalized projectile pair absent (unbuilt tree)")
        base_rows, *_rest = dr.scan("projectile")
        if base_rows:
            self.skipTest("projectile not clean on this tree state")
        with tempfile.TemporaryDirectory() as td:
            b = Path(td) / "base" / "projectile.obj"
            t = Path(td) / "target" / "projectile.c.obj"
            b.parent.mkdir()
            t.parent.mkdir()
            shutil.copy(src_pair[0], b)
            shutil.copy(src_pair[1], t)
            # find a vtable COMDAT DIR32 in the base copy and retarget it at
            # a different symbol index
            obj = Obj(b)
            edited = False
            for secnum in range(1, obj.nsec + 1):
                members = obj.section_members(secnum)
                if not any(n.startswith("??_7") for _v, n, _s in members):
                    continue
                sec = obj.section_table[secnum - 1]
                ptr, count = sec["reloc_offset"], sec["reloc_count"]
                if not ptr or count < 2:
                    continue
                buf = bytearray(obj.buf)
                # swap the symbol indices of the first two relocations
                s0 = st.unpack_from("<I", buf, ptr + 4)[0]
                s1 = st.unpack_from("<I", buf, ptr + 10 + 4)[0]
                if s0 == s1:
                    continue
                st.pack_into("<I", buf, ptr + 4, s1)
                st.pack_into("<I", buf, ptr + 10 + 4, s0)
                b.write_bytes(bytes(buf))
                edited = True
                break
            if not edited:
                self.skipTest("no editable vtable COMDAT found")
            with mock.patch.object(dr.pairscan, "pairs",
                                   lambda units=None: {"projectile": (b, t)}):
                rows, *_r = dr.scan("projectile")
        self.assertTrue(any(r.verdict in ("WRONG", "MISSING", "EXTRA")
                            for r in rows))


class AllocSizeControls(unittest.TestCase):
    def test_disp0_store_covers_the_ebp_form(self):
        from rom1.verify.alloc_size import _disp0_store
        # C7 06 imm32  -> mov [esi], imm32 (mod=00)
        self.assertEqual(_disp0_store(b"\xc7\x06AAAA", 0), (True, 6))
        # C7 45 00 imm32 -> mov [ebp+0x0], imm32 (mod=01 disp8=0) - the form
        # whose omission mis-attributed three CSBI_ImageSet sites
        self.assertEqual(_disp0_store(b"\xc7\x45\x00AAAA", 0), (True, 7))
        # SIB and non-zero disp are NOT plain [reg]
        self.assertEqual(_disp0_store(b"\xc7\x04\x24AAAA", 0)[0], False)
        self.assertEqual(_disp0_store(b"\xc7\x45\x04AAAA", 0)[0], False)

    def test_most_derived_uses_the_rtti_spine(self):
        from rom1.verify import alloc_size
        sw = object.__new__(alloc_size.Sweep)
        with mock.patch.object(alloc_size, "rtti_ancestors",
                               return_value={"CProjectile": {"CMovingLogic",
                                                             "CGameObject"},
                                             "CMovingLogic": {"CGameObject"}}):
            got = alloc_size.Sweep._most_derived(
                sw, {"CProjectile", "CMovingLogic"})
            self.assertEqual(got, "CProjectile")
            self.assertIsNone(alloc_size.Sweep._most_derived(
                sw, {"CProjectile", "CUnrelated"}))


class LinkTierControls(unittest.TestCase):
    def test_linked_image_only_admits_literal_100_percent_objects(self):
        """The 99.995 navigation threshold rounds a tiny object-local residue
        to EXACT, but the link audit must not relabel it as a link defect."""
        from rom1.verify import link_tier as lt
        pct = {
            ("play", "?DrawDebugStatsFull@CPlay@@QAEXXZ"): 99.99791,
            ("play", "?DrawDebugStats@CPlay@@QAEXXZ"): 100.0,
        }
        self.assertEqual(
            lt._byte_exact_symbols(pct),
            {"?DrawDebugStats@CPlay@@QAEXXZ"},
        )

    def test_unresolved_txt_content_fails(self):
        from rom1.verify import link_tier as lt
        with tempfile.TemporaryDirectory() as td:
            cand = Path(td) / "ALLODS.candidate.EXE"
            cand.write_bytes(b"MZ")
            unres = Path(td) / "u.txt"
            unres.write_text("?Lost@CFoo@@QAEXXZ\n")
            with mock.patch.object(lt, "CAND", cand), \
                 mock.patch.object(lt, "UNRESOLVED", unres), \
                 mock.patch("rom1.verify.undefined_closure._sym_sets",
                            return_value=(set(), set())), \
                 mock.patch("rom1.verify.undefined_closure.live_base_objs",
                            return_value=[]), \
                 mock.patch("rom1.verify.undefined_closure.lib_symbols",
                            return_value=set()):
                bad = lt.link_defect_findings()
        self.assertTrue(any("unresolved external" in b for b in bad))

    def test_a_stale_candidate_never_misattributes(self):
        import time as _t

        from rom1.verify import link_tier as lt
        with tempfile.TemporaryDirectory() as td:
            cand = Path(td) / "c.exe"
            cand.write_bytes(b"MZ")
            cmap = Path(td) / "c.map"
            cmap.write_text("x")
            objdir = Path(td) / "objdiff/base"
            objdir.mkdir(parents=True)
            newer = objdir / "a.obj"
            _t.sleep(0.01)
            newer.write_bytes(b"x")
            with mock.patch.object(lt, "CAND", cand), \
                 mock.patch.object(lt, "CMAP", cmap), \
                 mock.patch.object(lt, "BUILD", Path(td)):
                out = lt.image_diff_findings()
        self.assertTrue(out and "STALE" in out[0])


# --------------------------------------------------------------------------- #
# walls sieves                                                                #
# --------------------------------------------------------------------------- #
class JccScanControls(unittest.TestCase):
    """The condition-code sieve. Its whole false-positive population is the
    jump-table payload past the last `ret`, so that exclusion gets a negative
    control, and each of the three verdicts gets a demonstrated case."""

    @staticmethod
    def _lines(asms, ref=None, self_at=()):
        from types import SimpleNamespace
        return [SimpleNamespace(addr=i * 4, asm=a,
                                ref=ref if i in self_at else None)
                for i, a in enumerate(asms)]

    def test_jump_table_payload_past_the_last_ret_is_not_a_branch(self):
        from rom1.walls.jccscan import codes
        body = ["cmp eax,0x4", "je 0x20", "ret 0x8",
                # everything below is table/padding objdump decodes as code
                "js 0x40", "jo 0x44", "jp 0x48"]
        self.assertEqual(dict(codes(self._lines(body))), {"je": 1})

    def test_a_table_byte_decoding_as_ret_does_not_re_admit_the_payload(self):
        """The control the last-`ret` cut alone FAILS. A 0xc3 inside the table
        decodes as `ret`, so `max(ret)` lands in the middle of the data and
        every branch-shaped table byte after it is counted. Observed on
        CRom1Mgr::HandleCommand 0x862f0: the phantom `ret` read the row as
        OPERATOR d=187 where the code is POLARITY d=8. The table base is taken
        from the self-referent dispatch instead."""
        from rom1.walls.jccscan import code_region, codes
        me = "?HandleCommand@CRom1Mgr@@UAEHHW4Rom1CommandId@@H@Z"
        body = ["cmp eax,0x4",
                "jmp DWORD PTR [ecx*4+0x0010]",   # dispatch: table base 0x10
                "je 0x20", "ret 0x8",
                "jne 0x40", "ret", "jne 0x48"]    # index 4.. == addr 0x10..
        lines = self._lines(body, ref=me, self_at=(1,))
        # the last `ret` is index 5, inside the table; the cut must precede it
        self.assertEqual([x.asm for x in code_region(lines, me)][-1], "ret 0x8")
        self.assertEqual(dict(codes(lines, me)), {"je": 1})
        # and without the owning name the tool must not silently over-trim
        self.assertEqual(dict(codes(lines)), {"je": 1, "jne": 1})

    def test_a_signedness_transposition_is_reported_as_SIGNED(self):
        from rom1.walls.jccscan import classify, codes
        ours = codes(self._lines(["cmp eax,ecx", "jl 0x10", "ret"]))
        retail = codes(self._lines(["cmp eax,ecx", "jb 0x10", "ret"]))
        rec = classify(ours, retail)
        self.assertEqual(rec["kind"], "SIGNED")
        self.assertEqual(rec["signed"], [("jl", "jb")])

    def test_equality_against_ordered_is_reported_as_OPERATOR(self):
        from rom1.walls.jccscan import classify, codes
        ours = codes(self._lines(["je 0x8", "je 0xc", "ret"]))
        retail = codes(self._lines(["jl 0x8", "jle 0xc", "ret"]))
        self.assertEqual(classify(ours, retail)["kind"], "OPERATOR")

    def test_a_transposed_je_jne_count_is_reported_as_POLARITY(self):
        from rom1.walls.jccscan import classify, codes
        ours = codes(self._lines(["je 0x8", "je 0xc", "ret"]))
        retail = codes(self._lines(["jne 0x8", "jne 0xc", "ret"]))
        self.assertEqual(classify(ours, retail)["kind"], "POLARITY")

    def test_equal_multisets_report_nothing_rather_than_a_clean_bill(self):
        from rom1.walls.jccscan import classify, codes
        same = codes(self._lines(["je 0x8", "jl 0xc", "ret"]))
        self.assertIsNone(classify(same, same))

    def test_a_cold_block_after_the_last_ret_is_KEPT(self):
        """The mirror of the test above, and the error the last-`ret` cut made
        in the other direction: cl places cold blocks AFTER the last `ret`,
        entered by a forward branch and leaving by a `jmp` back into the body.
        Measured 2026-08-23, cutting them discarded 5524/6147 instructions over
        the todo queue - 531/599 of them condition codes - and asymmetrically
        on 41 rows.  What separates a cold block from a byte index table is
        that something BRANCHES to it."""
        from rom1.walls.jccscan import codes
        body = ["cmp eax,0x4", "je 0x14", "ret",
                # 0xc: table payload - nothing branches here
                "js 0x40",
                # 0x10: reached by the `je 0x14`... which is the NEXT line
                "jne 0x8", "jmp 0x0",
                # and the padding after it is data again
                "jo 0x44"]
        lines = self._lines(body)
        self.assertEqual(lines[4].addr, 0x10)
        lines[1].asm = "je 0x10"
        self.assertEqual(dict(codes(lines)), {"je": 1, "jne": 1})


class DiagnosePriorClassControls(unittest.TestCase):
    """`walls diagnose` names the FIRST divergence; a review names the CAUSE.
    On 8 of the queue's 53 review-only rows those disagree - the review traced
    a branch delta to register allocation, which diagnose can only ever read as
    CFG (`CGruntPuddle`'s own review says so: "the automatic CFG label is
    downstream codegen").  Nothing told the matcher, so diagnose says it."""

    @staticmethod
    def _row(cls):
        return {"status": "bounded", "wall_class": cls, "evidence": "x"}

    def test_a_disagreeing_review_is_surfaced_with_both_labels(self):
        from rom1.walls.diagnose import prior_class_note
        note = prior_class_note(self._row("regalloc"), False, "cfg")
        self.assertIn("bounded/regalloc", note)
        self.assertIn("not cfg", note)
        self.assertIn("STALE", note)

    def test_an_agreeing_review_is_still_pointed_at(self):
        from rom1.walls.diagnose import prior_class_note
        note = prior_class_note(self._row("cfg"), True, "cfg")
        self.assertIn("agrees", note)
        self.assertIn("current", note)

    def test_no_review_prints_nothing(self):
        from rom1.walls.diagnose import prior_class_note
        self.assertIsNone(prior_class_note(None, False, "cfg"))


class PriorsBlockControls(unittest.TestCase):
    """`walls priors` reads the verdict block above a pin.  Reading only the
    CONTIGUOUS block made one blank line hide a whole verdict, so a row with a
    33-line `@early-stop` on it reported `no comment above the pin` and reached
    a worklist labelled unadjudicated.  The gap rule that fixes it can also
    MANUFACTURE a verdict out of a formatter directive, so both directions get a
    control, and both are taken from the tree rather than invented."""

    def test_one_blank_line_does_not_hide_the_verdict(self):
        """POSITIVE control, carrying the property under test: the real
        Rom1MgrCmd.cpp spelling - block, blank line, pin."""
        from rom1.walls.priors import block_above
        src = ["// @early-stop", "// 313 branches on both sides.", "",
               "RVA(0x000862f0, 0x4369)"]
        self.assertEqual(block_above(src, 4),
                         ["// @early-stop", "// 313 branches on both sides."])

    def test_two_blank_lines_are_still_a_section_break(self):
        from rom1.walls.priors import block_above
        src = ["// a note about something else", "", "",
               "RVA(0x000862f0, 0x4369)"]
        self.assertEqual(block_above(src, 4), [])

    def test_a_formatter_directive_alone_is_not_a_verdict(self):
        """NEGATIVE control.  MultiStartDlg.cpp:119 is the tree's only pin whose
        gap-1 block is `// clang-format on` closing the table above it - the one
        row the gap rule would otherwise turn into a written verdict."""
        from rom1.walls.priors import block_above
        src = ["};", "// clang-format on", "", "RVA(0x000c1750, 0x88)"]
        self.assertEqual(block_above(src, 4), [])

    def test_a_directive_does_not_suppress_the_prose_beside_it(self):
        from rom1.walls.priors import block_above
        src = ["// clang-format off", "// @early-stop", "RVA(0x1, 0x2)"]
        self.assertEqual(block_above(src, 3), ["// @early-stop"])

    def test_the_contiguous_case_is_unchanged(self):
        from rom1.walls.priors import block_above
        src = ["// @early-stop", "RVA(0x1, 0x2)"]
        self.assertEqual(block_above(src, 2), ["// @early-stop"])

    def test_a_gapped_block_is_not_read_across_code(self):
        from rom1.walls.priors import block_above
        src = ["// the previous function's note", "}", "", "RVA(0x1, 0x2)"]
        self.assertEqual(block_above(src, 4), [])

    def test_a_compgen_pin_resolves_to_its_definition_name(self):
        """`RVA_COMPGEN` pins a COMDAT where it is EMITTED; the body, and any
        verdict beside it, is at the definition.  CPlay::CPlay 0x8c9d0 is pinned
        in Rom1Mgr.cpp and defined in Play.h under a 12-line `@early-stop`."""
        from rom1.walls.priors import source_name
        self.assertEqual(source_name("??0CPlay@@QAE@XZ"), "CPlay::CPlay")
        self.assertEqual(source_name("??1CState@@UAE@XZ"), "CState::~CState")
        self.assertEqual(source_name("?Render@CImage@@UAEHXZ"), "CImage::Render")

    def test_a_compiler_generated_thunk_resolves_to_nothing(self):
        """NEGATIVE control.  `??_G` scalar deleting destructors, `??_E` and the
        `??_L` vector ctor iterator have no source spelling at all, so guessing a
        name would attach whatever comment sits near a same-named symbol."""
        from rom1.walls.priors import source_name
        for m in ("??_GCRgn@@UAEPAXI@Z", "??_ECPlay@@UAEPAXI@Z",
                  "??_L@YGXPAXIHP6EX0@Z1@Z", "__ehreg$?Foo@@YAXXZ"):
            self.assertIsNone(source_name(m), m)

    def test_a_qualified_CALL_is_not_mistaken_for_a_definition(self):
        """NEGATIVE control, taken from the tree: `~CPlay`'s body is the single
        line `CPlay::ReleaseResources();`, so a name-only search would hand back
        the destructor's comment as that method's verdict."""
        from rom1.walls.priors import is_definition
        self.assertFalse(is_definition("    CPlay::ReleaseResources();",
                                       "CPlay::ReleaseResources"))
        self.assertFalse(is_definition("    return CPlay::Render();",
                                       "CPlay::Render"))
        self.assertTrue(is_definition("inline CPlay::CPlay() {", "CPlay::CPlay"))
        self.assertTrue(is_definition("i32 CImage::Render(CDDrawWorker* w)",
                                      "CImage::Render"))


class InlineModelGapArgumentControls(unittest.TestCase):
    """CLAUDE.md points every inline/call-set wall at `walls inline-model
    --gap`, but its only form took a spec JSON of front-end `cb` estimates, so
    `--gap 0x08b960` answered `spec JSON missing` and the documented lever could
    not be invoked at an address at all.  The address form has to be reachable,
    and a mistyped spec path must NOT silently become an address."""

    @staticmethod
    def _err(argv):
        import contextlib
        import io
        from rom1.walls import inline_model
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf), contextlib.suppress(SystemExit):
            inline_model.main(argv)
        return buf.getvalue()

    def test_a_missing_spec_path_still_says_spec_json_missing(self):
        """NEGATIVE control: a typo'd `.json` must not be read as an rva."""
        self.assertIn("spec JSON missing", self._err(["--gap", "nope.json"]))

    def test_an_unresolvable_address_reports_the_address_not_the_spec(self):
        """POSITIVE control carrying the property: a non-`.json` argument takes
        the address path, so its failure names the address."""
        err = self._err(["--gap", "0xdeadbee"])
        self.assertNotIn("spec JSON missing", err)

    @staticmethod
    def _repeated_site_gap(symbol_state):
        import contextlib
        import io
        from types import SimpleNamespace

        from rom1.delink import coffx
        from rom1.walls import diagnose as D
        from rom1.walls import inline_model

        caller = "?DeactivateOutside@CWwdSpatialMgr@@QAEHHH@Z"
        callee = "?RemoveAll@CDDrawChildGroup@@QAEXPAU__POSITION@@PAUCGameObject@@@Z"
        binding = SimpleNamespace(unit="u", name=caller, rva=0x168500)

        class FakeObj:
            def __init__(self, path):
                self.path = path

            def iter_symbols(self):
                if symbol_state == "absent":
                    return []
                return [(0, 0, 1 if symbol_state == "defined" else 0)]

            def sym_name(self, _index):
                return callee

        with tempfile.TemporaryDirectory() as td:
            norm = Path(td)
            (norm / "base").mkdir()
            (norm / "target").mkdir()
            (norm / "base/u.obj").touch()
            (norm / "target/u.c.obj").touch()
            with mock.patch.object(D, "NORM", norm), \
                 mock.patch.object(D, "_locate", return_value=(binding, "")), \
                 mock.patch.object(D, "_find_function", side_effect=[
                     (b"base", {}, 4), (b"target", {}, 4)]), \
                 mock.patch.object(D, "_jump_table_bytes", return_value=set()), \
                 mock.patch.object(D, "_skeleton", side_effect=[
                     (b"base", 2, 0, 0, 1, ""),
                     (b"target", 4, 0, 0, 1, "")]), \
                 mock.patch.object(D, "_call_targets", side_effect=[
                     [(callee, 0)] * 2, [(callee, 0)] * 4]), \
                 mock.patch.object(coffx, "Obj", FakeObj), \
                 contextlib.redirect_stdout(io.StringIO()) as out:
                if inline_model.gap_from_rva("0x168500") != 0:
                    raise AssertionError("gap_from_rva failed")
        return out.getvalue()

    def test_an_undefined_symbol_does_not_prove_tail_sharing(self):
        """NEGATIVE control: a declined header inline can remain undefined,
        so the symbol table alone cannot turn a call delta into tail sharing."""
        text = self._repeated_site_gap("undefined")
        self.assertIn("AMBIGUOUS: UNDEFINED external", text)
        self.assertNotIn("NOT A CANDIDATE", text)
        self.assertNotIn("tail-merged in base", text)

    def test_an_absent_symbol_allows_a_fully_expanded_header_inline(self):
        """Integration control for CRom1Mgr::Run's pcount/out_waiting shape:
        base can expand every local site and therefore have no symbol row."""
        text = self._repeated_site_gap("absent")
        self.assertIn("symbol absent from the base obj", text)
        self.assertIn("consistent with full", text)
        self.assertNotIn("NOT A CANDIDATE", text)

    def test_a_fewer_call_delta_to_a_defined_comdat_can_be_expansion(self):
        """Negative control: keep the old diagnosis for an inline-visible
        definition emitted by the caller's own object."""
        text = self._repeated_site_gap("defined")
        self.assertIn("INLINE-VISIBLE", text)
        self.assertIn("Expansion is possible", text)
        self.assertNotIn("tail-merged in base", text)


class ReviewCountClaimControls(unittest.TestCase):
    """`walls recheck` re-measures the COUNT certifications a review states.  A
    review that says "base/retail agree on 24 calls" is an assertion and nothing
    re-ran it: `PlaceObjectFull` carried exactly that while the base had drifted
    to 25.  Every sentence here is taken verbatim from
    config/codex_wall_reviews.tsv, and the negatives are the two the first pass
    got wrong in each direction."""

    @staticmethod
    def _units(evidence):
        from rom1.walls.recheck import claims
        stated, _skipped = claims(evidence)
        return {(u, n) for u, n, _s in stated}

    def test_the_known_positive_is_read_through_its_semicolon(self):
        """POSITIVE control carrying the property under test: the certification
        that actually drifted.  Its agreement and its divergence share ONE
        sentence, so splitting on `.` alone reads the `vs` and throws the whole
        assertion away - which is how it escaped the first pass."""
        self.assertEqual(
            self._units(
                "Base/retail now agree at 24 calls, 96 branches, and 64 relocs; "
                "base has 15 vs retail 16 returns because the grouped preview "
                "keeps world in EBP on one arm."
            ),
            {("calls", 24), ("branches", 96), ("relocs", 64)},
        )

    def test_a_connective_is_not_a_unit_qualifier(self):
        """NEGATIVE control from 0x065e80: `returns 2/2 and relocs 249/249`
        otherwise reads as "relocs 2" and invents a failure out of a hold."""
        self.assertEqual(
            self._units("stores 90/90, returns 2/2 and relocs 249/249 exact."),
            {("returns", 2), ("relocs", 249)},
        )

    def test_the_unit_may_precede_the_pair(self):
        """0x0f42f0 writes it the other way round."""
        self.assertEqual(
            self._units("Calls 31/31 and ordered relocs 312/312."),
            {("calls", 31), ("relocs", 312)},
        )

    def test_a_two_spelling_measurement_is_not_a_certification(self):
        """NEGATIVE control from 0x163db0, whose own review states retail has 3
        returns to the base's 2: here `both` is two SOURCE spellings compared
        against each other, not base against retail."""
        self.assertEqual(
            self._units(
                "An explicit forward null-success goto and the exact authored "
                "shape suggested by retail both compile byte-identically at "
                "77.50 with 30 instructions, 3 branches and 2 returns."
            ),
            set(),
        )

    def test_a_rejected_frontier_is_not_a_certification(self):
        """NEGATIVE control from 0x13f020: a candidate that was REJECTED."""
        self.assertEqual(
            self._units(
                "Best structural frontier had 320/319 instructions, 32/32 "
                "branches and 21/21 relocs but emitted bank arithmetic before "
                "both Locks, so it was rejected."
            ),
            set(),
        )

    def test_a_disposable_probe_is_not_a_certification(self):
        """NEGATIVE control from 0x17a460: measured under `inline_depth(0)`,
        which the committed tree does not carry."""
        self.assertEqual(
            self._units(
                "Disposable inline_depth(0) at those expressions proves 59/59 "
                "calls, 43/43 branches, 65/65 relocs."
            ),
            set(),
        )

    def test_a_one_sided_count_is_never_read_as_agreement(self):
        """0x02a570 states its branch delta; asserting it back would test the
        parser's word order, not the tree."""
        self.assertEqual(
            self._units(
                "Retail homes coordList at entry and reloads it on both sides "
                "of RemoveAll, requiring the sole merge jump (38 vs 37 branches)."
            ),
            set(),
        )


class SourceClaimGateControls(unittest.TestCase):
    """The SECOND written-verdict store: the `//` block above an `RVA()` pin.

    `walls priors` has always read both stores and only the ledger was ever
    re-measured, which is how nine notes came to state something the pair no
    longer held - four of them a FRAME difference that later work had closed,
    so a reader would have gone hunting for a frame that already matches.

    The three-way verdict is the point of these controls.  BROKEN (the two
    sides stopped agreeing) is a defect and reaches the gate; DRIFT (they still
    agree, but not at the stated number) is a RETIRED RULER and must NOT, because
    several of these notes were written against a tool that counted CONDITIONAL
    branches where the pair reader counts every branch.  Collapsing the two
    would fail builds on arithmetic nobody got wrong.
    """

    RVA = 0x078A50
    SITE = ("src/Allods/TriggerMgr.cpp", 427)
    NAME = "?PlaceObjectFull@CTriggerMgr@@QAEHPAVCGrunt@@HH@Z"

    def _run(self, note, counts):
        import types as _types

        from rom1.walls import recheck
        b = _types.SimpleNamespace(rva=self.RVA, unit="triggermgrplace",
                                   name=self.NAME)
        with mock.patch("rom1.walls.priors._pin_sites",
                        return_value={self.RVA: [self.SITE]}), \
             mock.patch("rom1.walls.priors._comment_above",
                        return_value=[f"// {note}"]), \
             mock.patch("rom1.walls.diagnose.named_functions",
                        return_value={}), \
             mock.patch("rom1.walls.diagnose._locate", return_value=(b, "")), \
             mock.patch.object(recheck, "measure",
                               return_value=(counts, "inline")):
            return recheck.source_gate_findings(), recheck.source_sweep()

    AGREE = "Block topology and branch sequence agree exactly, 4 rets on both sides."
    HOLDING = {"calls": (24, 24), "branches": (96, 96), "returns": (4, 4),
               "relocs": (64, 64), "insns": (300, 300), "bytes": (0x400, 0x400)}
    SPLIT = dict(HOLDING, returns=(3, 4))
    DRIFTED = dict(HOLDING, returns=(5, 5))

    def test_a_note_whose_sides_still_agree_is_silent(self):
        """NEGATIVE control: the claim measures exactly, so nothing is a finding."""
        out, sweep = self._run(self.AGREE, self.HOLDING)
        self.assertEqual(out, [])
        self.assertEqual([v[0] for v in sweep[0]["verdicts"]], ["HOLD"])

    def test_a_note_whose_sides_stopped_agreeing_reaches_the_gate(self):
        """POSITIVE control carrying the property under test end to end."""
        out, sweep = self._run(self.AGREE, self.SPLIT)
        self.assertEqual([v[0] for v in sweep[0]["verdicts"]], ["BROKEN"])
        self.assertEqual(len(out), 1, out)
        self.assertIn("states both sides at 4 returns", out[0])
        self.assertIn("base 3 / target 4", out[0])
        self.assertIn(f"{self.SITE[0]}:{self.SITE[1]}", out[0])

    def test_a_retired_ruler_is_DRIFT_and_never_a_finding(self):
        """NEGATIVE control for the distinction the gate is built on: the sides
        agree at 5 where the note says 4, so the CLAIM holds and only the number
        is from another instrument.  It must be visible in the sweep and absent
        from the gate."""
        out, sweep = self._run(self.AGREE, self.DRIFTED)
        self.assertEqual([v[0] for v in sweep[0]["verdicts"]], ["DRIFT"])
        self.assertEqual(out, [])

    def test_a_residue_sentence_is_not_an_agreement(self):
        """`residue is 2 insns: retail loads BOTH operands ...` states a
        DIVERGENCE and happens to contain an agreement trigger.  Reading it as a
        claim invented three failures on the first sweep."""
        note = ("residue is 2 insns: retail loads BOTH operands of the second "
                "difference where cl folds one into a single fsubr.")
        out, sweep = self._run(note, self.HOLDING)
        self.assertEqual(sweep, [])
        self.assertEqual(out, [])

    def test_an_unmeasurable_pair_is_not_a_pass(self):
        """A note whose pair cannot be read has not been re-measured, and a gate
        that stays silent about that reports a green it did not verify."""
        import types as _types

        from rom1.walls import recheck
        b = _types.SimpleNamespace(rva=self.RVA, unit="triggermgrplace",
                                   name=self.NAME)
        with mock.patch("rom1.walls.priors._pin_sites",
                        return_value={self.RVA: [self.SITE]}), \
             mock.patch("rom1.walls.priors._comment_above",
                        return_value=[f"// {self.AGREE}"]), \
             mock.patch("rom1.walls.diagnose.named_functions",
                        return_value={}), \
             mock.patch("rom1.walls.diagnose._locate", return_value=(b, "")), \
             mock.patch.object(recheck, "measure",
                               return_value="normalized pair missing"):
            out = recheck.source_gate_findings()
        self.assertEqual(len(out), 1, out)
        self.assertIn("unmeasured", out[0])


class ReviewClaimGateControls(unittest.TestCase):
    """The `review-claims` tier row - the certifications re-measured on EVERY
    build.  It exists because the MAX gate structurally cannot see this class
    of drift: c1c1616a gave `PlaceObjectFull` the 16th `ret` retail has and
    silently lost a cross-jump elsewhere (calls +1, branches -1, relocs +1),
    the SCORE ROSE, and the source hash did not move, so neither the ledger nor
    a source reader had anything to look at.  The recognizer controls above
    prove the parser; these drive `gate_findings`, which is what the tier
    calls."""

    RVA = 0x078A50

    def _findings(self, evidence, counts, *, resolves=True, measurable=True):
        import types as _types

        from rom1.walls import recheck
        row = {"src_hash": "f96c455cab0e", "status": "open",
               "wall_class": "inline", "evidence": evidence}
        b = _types.SimpleNamespace(
            rva=self.RVA, unit="triggermgrplace",
            name="?PlaceObjectFull@CTriggerMgr@@QAEHPAVCGrunt@@HH@Z")
        located = (b, "") if resolves else (
            None, f"no CLAIMED function starts at 0x{self.RVA:x}")
        measured = ((counts, "inline") if measurable
                    else "normalized pair missing for triggermgrplace")
        with mock.patch("rom1.walls.reviews.load",
                        return_value={self.RVA: row}), \
             mock.patch("rom1.walls.reviews.current", return_value={}), \
             mock.patch("rom1.walls.diagnose._locate", return_value=located), \
             mock.patch.object(recheck, "source_gate_findings", return_value=[]), \
             mock.patch.object(recheck, "measure", return_value=measured):
            return recheck.gate_findings()

    #: the drifted pair c1c1616a actually produced, against the certification
    #: the review still carried
    DRIFTED = {"calls": (25, 24), "branches": (95, 96), "returns": (16, 16),
               "relocs": (65, 64), "insns": (300, 300), "bytes": (0x400, 0x400)}
    HOLDING = {"calls": (24, 24), "branches": (96, 96), "returns": (15, 16),
               "relocs": (64, 64), "insns": (300, 300), "bytes": (0x400, 0x400)}
    CERT = ("Base/retail now agree at 24 calls, 96 branches, and 64 relocs; "
            "base has 15 vs retail 16 returns because the grouped preview "
            "keeps world in EBP on one arm.")

    def test_the_known_positive_reaches_the_gate(self):
        """POSITIVE control carrying the property under test end to end: the
        certification that drifted, measured against the pair that drifted it.
        A parser control alone would not prove the GATE reads it."""
        out = self._findings(self.CERT, self.DRIFTED)
        self.assertEqual(len(out), 3, out)
        self.assertTrue(all(f"0x{self.RVA:06x}" in f for f in out))
        self.assertEqual(
            {f.split("both sides at ")[1].split(" - ")[0] for f in out},
            {"24 calls, now base 25 / target 24",
             "96 branches, now base 95 / target 96",
             "64 relocs, now base 65 / target 64"},
        )

    def test_a_holding_certification_is_silent(self):
        """The clean pass.  The stated `15 vs 16` returns divergence is NOT a
        claim, so a pair that still shows it must not fail the gate."""
        self.assertEqual(self._findings(self.CERT, self.HOLDING), [])

    def test_a_review_row_that_names_no_claimed_function_fails(self):
        """A review whose row no longer exists is a dangling ledger entry, not
        a hold: nothing was measured, so nothing may pass."""
        out = self._findings(self.CERT, self.HOLDING, resolves=False)
        self.assertEqual(len(out), 1, out)
        self.assertIn("names no claimed function", out[0])

    def test_an_unreadable_pair_is_not_a_pass(self):
        """A gate that SKIPS is not a gate that PASSES: a stated count whose
        normalized pair cannot be read is reported, not assumed green."""
        out = self._findings(self.CERT, None, measurable=False)
        self.assertEqual(len(out), 1, out)
        self.assertIn("unmeasurable", out[0])
        # ... but a review that certifies NO count has nothing to measure.
        self.assertEqual(
            self._findings("Regalloc wall: retail keeps world in EBP.",
                           None, measurable=False), [])

    def test_a_non_certification_sentence_cannot_fail_the_gate(self):
        """NEGATIVE control, the three sentence classes the parser must not
        read as a certification of the committed pair: two source spellings
        measured against each other, a REJECTED frontier, and a disposable
        `inline_depth(0)` probe.  Each is paired with counts that contradict
        its numbers - a gate that read them would fire here."""
        contradicting = {"calls": (1, 2), "branches": (1, 2),
                         "returns": (1, 2), "relocs": (1, 2),
                         "insns": (1, 2), "bytes": (1, 2)}
        for sentence in (
            "An explicit forward null-success goto and the exact authored "
            "shape suggested by retail both compile byte-identically at 77.50 "
            "with 30 instructions, 3 branches and 2 returns.",
            "Best structural frontier had 320/319 instructions, 32/32 "
            "branches and 21/21 relocs but emitted bank arithmetic before "
            "both Locks, so it was rejected.",
            "Disposable inline_depth(0) at those expressions proves 59/59 "
            "calls, 43/43 branches, 65/65 relocs.",
        ):
            self.assertEqual(self._findings(sentence, contradicting), [],
                             sentence)

    def test_the_tier_runs_it(self):
        """The row is REGISTERED, and it is this gate the runner calls - a
        gate nothing invokes is documentation."""
        import contextlib
        import io

        from rom1.verify import tiers
        self.assertIn("review-claims", dict(tiers.TIERS["normal"]))
        with mock.patch("rom1.walls.recheck.gate_findings",
                        return_value=["planted drift"]) as g:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                failed = tiers.run(["normal"])
        g.assert_called_once()
        self.assertGreaterEqual(failed, 1)
        self.assertIn("review-claims: FAIL", out.getvalue())
        # ONE implementation: the registered gate module IS the walls tool the
        # campaign runs by hand, not a second copy that could drift from it.
        from rom1.verify import _GATES
        self.assertEqual(_GATES["review-claims"], "rom1.walls.recheck")
        self.assertEqual(tiers._rerun_command("review-claims"),
                         "rom1 verify review-claims")


class StoreScanFrameControls(unittest.TestCase):
    """`walls storescan` compares member-store ORDER, so its key has to be a
    MEMBER offset.  Excluding the literal `esp` base was not enough: cl builds
    a local aggregate's address in an ordinary register and fills it through
    that, and those displacements are esp offsets the two sides do not share -
    the same incomparable key `walls valuetemp` was corrected for.  No exact
    row can show this: an exact row has the SAME frame on both sides."""

    @staticmethod
    def _lines(asms):
        from types import SimpleNamespace
        return [SimpleNamespace(addr=i * 4, asm=a, ref=None)
                for i, a in enumerate(asms)]

    def _runs(self, asms):
        from rom1.walls.storescan import store_runs
        return store_runs(self._lines(asms), 3)

    def test_a_run_through_a_member_pointer_is_a_member_run(self):
        runs = self._runs(["mov DWORD PTR [esi+0x4],eax",
                           "mov DWORD PTR [esi+0x8],ecx",
                           "mov DWORD PTR [esi+0xc],edx"])
        self.assertEqual([r["frame"] for r in runs], [False])

    def test_a_run_through_an_lea_from_esp_is_a_FRAME_FILL(self):
        runs = self._runs(["lea esi,[esp+0x20]",
                           "mov DWORD PTR [esi+0x4],eax",
                           "mov DWORD PTR [esi+0x8],ecx",
                           "mov DWORD PTR [esi+0xc],edx"])
        self.assertEqual([r["frame"] for r in runs], [True])

    def test_the_taint_survives_a_copy_and_a_constant_bias(self):
        runs = self._runs(["lea eax,[esp+0x20]", "mov esi,eax", "add esi,0x10",
                           "mov DWORD PTR [esi+0x4],eax",
                           "mov DWORD PTR [esi+0x8],ecx",
                           "mov DWORD PTR [esi+0xc],edx"])
        self.assertEqual([r["frame"] for r in runs], [True])

    def test_a_fresh_definition_clears_the_taint(self):
        runs = self._runs(["lea esi,[esp+0x20]", "mov esi,DWORD PTR [ecx+0x8]",
                           "mov DWORD PTR [esi+0x4],eax",
                           "mov DWORD PTR [esi+0x8],ecx",
                           "mov DWORD PTR [esi+0xc],edx"])
        self.assertEqual([r["frame"] for r in runs], [False])

    def test_a_one_sided_frame_fill_does_not_shift_the_member_pairing(self):
        """The second half of the defect.  Runs are paired POSITIONALLY, so a
        local fill present on one side only re-indexes every member run after
        it - and then two unrelated runs get compared."""
        from rom1.walls.storescan import permuted
        member = ["mov DWORD PTR [edi+0x10],eax",
                  "mov DWORD PTR [edi+0x14],ecx",
                  "mov DWORD PTR [edi+0x18],edx"]
        ours = self._runs(["lea esi,[esp+0x20]",
                           "mov DWORD PTR [esi+0x0],eax",
                           "mov DWORD PTR [esi+0x4],ecx",
                           "mov DWORD PTR [esi+0x8],edx",
                           "call 0x0"] + member)
        retail = self._runs(member)
        self.assertEqual(len(ours), 2)
        self.assertEqual(len(retail), 1)
        self.assertEqual(permuted(ours, retail), [])   # and no false hit
        # the same member run, genuinely permuted, still reports
        swapped = self._runs(["mov DWORD PTR [edi+0x14],eax",
                              "mov DWORD PTR [edi+0x10],ecx",
                              "mov DWORD PTR [edi+0x18],edx"])
        self.assertEqual(len(permuted(ours, swapped)), 1)

    def test_an_immediate_stored_into_the_frame_leaves_the_value_screen(self):
        from rom1.walls.storescan import imm_map
        lines = self._lines(["lea esi,[esp+0x20]",
                             "mov DWORD PTR [esi+0x4],0x2a",
                             "mov DWORD PTR [edi+0x8],0x2a"])
        self.assertEqual(sorted(imm_map(lines)), ["DWORD+0x8"])


class PairscanControls(unittest.TestCase):
    def test_rep_movsd_folds_and_movsx_does_not_count(self):
        from rom1.walls.aggregate_copies import REP_MOVS
        self.assertTrue(REP_MOVS.match("rep movs"))
        self.assertTrue(REP_MOVS.match("rep movsd"))
        self.assertFalse(REP_MOVS.match("movs"))       # bare table byte decode
        self.assertFalse(REP_MOVS.match("movsx"))      # sign-extend load
        # and the decoder really produces the folded spelling for F3 A5
        try:
            from rom1.delink.coffx import Obj  # noqa: F401 (env probe)
            from rom1.tool import objdump
            text = objdump.disassemble(b"\xf3\xa5\xc3", vma=0)
        except Exception as exc:  # noqa: BLE001
            self.skipTest(f"objdump unavailable: {exc}")
        self.assertIn("rep movs", text)

    def test_aggregate_copy_sieve_excludes_proven_current_dips(self):
        from rom1.walls import aggregate_copies
        row = {"unit": "u", "symbol": "?f@@YAXXZ", "cur": 75.0,
               "proven": True}
        with mock.patch("rom1.walls.pairscan.require_pairs"), \
             mock.patch("rom1.walls.inventory.build", return_value=[row]), \
             mock.patch("rom1.walls.pairscan.pairs") as pairs:
            self.assertEqual(aggregate_copies.scan(), [])
        pairs.assert_not_called()

    def test_aggregate_copy_cli_reports_a_source_cfg_lead(self):
        import contextlib
        import io

        from rom1.walls import aggregate_copies
        hit = (-1, "butemgr", 77.03, 2, 1,
               "?SetString@CButeMgr@@QAEXPBD0ABVCString@@@Z")
        out = io.StringIO()
        with mock.patch.object(aggregate_copies, "scan", return_value=[hit]), \
             mock.patch("rom1.walls.check_unit"), \
             contextlib.redirect_stdout(out):
            self.assertEqual(aggregate_copies.main([]), 0)
        text = out.getvalue()
        self.assertIn("base has more surviving copy blocks", text)
        self.assertIn("source/CFG leads: 1", text)
        self.assertNotIn("we copy an object retail does not", text)

    def test_local_labels_are_not_function_boundaries(self):
        from rom1.walls.pairscan import is_local_label
        self.assertTrue(is_local_label("$L27"))
        self.assertTrue(is_local_label("$loop_restart$32243"))
        self.assertFalse(is_local_label("?Advance@CAni@@QAEXXZ"))

    def test_canon_folds_static_suffix_and_vector_dtor(self):
        from rom1.walls.pairscan import canon
        self.assertEqual(canon("_s_QUESTZ$Sdata_data_87db2c_0"), "_s_QUESTZ")
        self.assertEqual(canon("??_EzPTree@@UAEPAXI@Z"),
                         "??_GzPTree@@UAEPAXI@Z")


class EhFrameControls(unittest.TestCase):
    PROLOGUE = [
        (0, "push", "0xffffffff"),
        (2, "push", "0x0"),
        (7, "mov", "eax,DWORD PTR fs:0x0"),
        (13, "push", "eax"),
        (14, "mov", "DWORD PTR fs:0x0,esp"),
        (21, "sub", "esp,0x8"),
        (24, "push", "esi"),
    ]

    def test_the_full_sequence_is_required(self):
        from rom1.walls.eh_frame import has_eh
        self.assertTrue(has_eh(self.PROLOGUE))
        no_push = [i for i in self.PROLOGUE if i[2] != "0xffffffff"]
        self.assertFalse(has_eh(no_push))              # fs store alone != EH
        no_store = [i for i in self.PROLOGUE
                    if not i[2].startswith("DWORD PTR fs:0x0,")]
        self.assertFalse(has_eh(no_store))

    def test_presence_mismatch_classifies(self):
        from rom1.walls.eh_frame import classify
        plain = [(0, "push", "esi"), (1, "ret", "")]
        self.assertEqual(classify(plain, self.PROLOGUE), "TARGET_ONLY")
        self.assertEqual(classify(self.PROLOGUE, plain), "BASE_ONLY")
        self.assertEqual(classify(plain, plain), "NEITHER")

    def test_state_stores_are_counted_at_the_slot(self):
        from rom1.walls.eh_frame import eh_states
        insns = self.PROLOGUE + [
            (30, "mov", "DWORD PTR [esp+0x14],0x0"),
            (38, "call", "0x100"),
            (43, "mov", "BYTE PTR [esp+0x14],0x1"),
            (48, "mov", "DWORD PTR [esp+0x14],0xffffffff"),
        ]
        slot, states = eh_states(insns)
        self.assertEqual(slot, "[esp+0x14]")
        self.assertEqual(len(states), 3)
        self.assertEqual(sorted(s for _o, s in states if s is not None),
                         [-1, 0, 1])

    def test_inline_cut_vs_exit_merge_vs_object(self):
        from rom1.walls.eh_frame import cause, ctor_delta
        only_t, only_b, resited = ctor_delta(
            [(0, "??1CString@@QAE@XZ")],
            [(0, "??1CString@@QAE@XZ"), (5, "??0CRect@@QAE@XZ")])
        self.assertEqual(cause("TARGET_ONLY", 1, only_t, only_b, resited),
                         "INLINE_CUT")
        only_t, only_b, resited = ctor_delta(
            [(0, "??1CString@@QAE@XZ")] * 2,
            [(0, "??1CString@@QAE@XZ")] * 8)
        self.assertEqual(cause("TARGET_ONLY", 1, only_t, only_b, resited),
                         "EXIT_MERGE")
        self.assertEqual(cause("TARGET_ONLY", 1, [], [], []),
                         "MISSING_OBJECT")
        self.assertEqual(cause("BASE_ONLY", -1, [], [], []), "EXTRA_OBJECT")
        self.assertEqual(cause("BOTH", 1, [], [], []), "STATE_FLOW")

    def test_states_cli_does_not_call_state_flow_a_missing_object(self):
        import contextlib
        import io

        from rom1.walls import eh_frame
        row = dict(unit="grunt", name="?StepArrivalDrop@CGrunt@@QAEHXZ",
                   rva="0x04b370", fuzzy=0.0, size=2960, verdict="BOTH",
                   cause="STATE_FLOW", extra_ctors=[], our_ctors=[], resited=[],
                   base_insn=877, tgt_insn=853, slot="[esp+0x68]",
                   states=[-1, 0, 1], base_states=7, tgt_states=8,
                   first=0x2e1, last=0xa39, unwind=True)
        out = io.StringIO()
        with mock.patch.object(eh_frame.pairscan, "require_pairs"), \
             mock.patch.object(eh_frame, "scan", return_value=[row]), \
             mock.patch("rom1.walls.check_unit"), \
             contextlib.redirect_stdout(out):
            self.assertEqual(eh_frame.main(["--states"]), 0)
        text = out.getvalue()
        self.assertIn("STATE_FLOW", text)
        self.assertNotIn("MISSING_OBJECT", text)


class GlobalRefsControls(unittest.TestCase):
    def test_addend_past_the_symbol_is_dropped(self):
        import collections

        from rom1.walls import global_refs as gr
        relocs = [(0x10, "_g_dir", gr.DIR32, 0x2B0),   # unsized-datum fallback
                  (0x20, "_g_dir", gr.DIR32, 0x0)]     # a real read
        obj = mock.Mock()
        with mock.patch.object(gr.pairscan, "fn_relocs",
                               return_value=relocs):
            dropped = collections.Counter()
            c = gr._refs(obj, 1, 0, 0x100, gr.DIR32, dropped,
                         {"_g_dir": 12})
        self.assertEqual(c["_g_dir"], 1)
        self.assertEqual(sum(dropped.values()), 1)


class StaleMarkerControls(unittest.TestCase):
    def test_marker_resolution_prefers_plain_rva(self):
        from rom1.walls.stale_markers import RVA, RVA_COMPGEN
        self.assertTrue(RVA.search("RVA(0x00012340, 0x10)"))
        self.assertIsNone(RVA.search("RVA_COMPGEN(0x00012340, 0x10, X)"))
        self.assertTrue(RVA_COMPGEN.search("RVA_COMPGEN(0x00012340, 0x10, X)"))

    def test_header_inline_definition_has_a_qualified_owner(self):
        from rom1.walls.stale_markers import QUALIFIED_DEF
        m = QUALIFIED_DEF.search("inline CPlay::CPlay() {")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "CPlay::CPlay")


class WallReviewControls(unittest.TestCase):
    def test_exact_requires_a_hash_valid_100_percent_bank(self):
        from rom1.walls import reviews

        rows = {0x1000: (100.0, 100.0, "same")}
        with mock.patch("rom1.walls.inventory.baseline_rows", return_value=rows):
            self.assertTrue(reviews.exact_is_banked(0x1000, "same"))
            self.assertFalse(reviews.exact_is_banked(0x1000, "different"))
            self.assertFalse(reviews.exact_is_banked(0x2000, "same"))

    def test_source_edit_invalidates_a_personal_review(self):
        from types import SimpleNamespace

        from rom1.walls import reviews
        saved = {
            0x1000: {
                "src_hash": "old", "status": "bounded",
                "wall_class": "cfg", "evidence": "checked",
            },
            0x2000: {
                "src_hash": "same", "status": "open",
                "wall_class": "inline", "evidence": "inspect site",
            },
        }
        funcs = [
            SimpleNamespace(rva=0x1000, unit="u", name="changed"),
            SimpleNamespace(rva=0x2000, unit="u", name="unchanged"),
        ]
        hashes = {("u", "changed"): "new", ("u", "unchanged"): "same"}

        def fingerprinter():
            return lambda unit, name: hashes[(unit, name)], None, set()

        with mock.patch.object(reviews, "load", return_value=saved), \
             mock.patch("rom1.model.resolve",
                        return_value=SimpleNamespace(functions=funcs)), \
             mock.patch("rom1.verify.fingerprints.fingerprinter",
                        side_effect=fingerprinter):
            self.assertEqual(set(reviews.current()), {0x2000})

    def test_todo_excludes_only_hash_valid_terminal_reviews(self):
        from types import SimpleNamespace
        from rom1.walls import inventory

        names = {
            0x1000: "?Bounded@CThing@@QAEHXZ",
            0x2000: "?Open@CThing@@QAEHXZ",
            0x3000: "?New@CThing@@QAEHXZ",
            0x4000: "?Proven@CThing@@QAEHXZ",
            0x5000: "?Exact@CThing@@QAEHXZ",
        }
        funcs = [
            SimpleNamespace(unit="u", name=name, rva=rva, size=0x10)
            for rva, name in names.items()
        ]
        scores = {("u", name): 75.0 for name in names.values()}
        scores[("u", "__ehunwind$?Open@CThing@@QAEHXZ$0")] = 50.0
        baseline = {
            rva: (75.0, 100.0 if rva == 0x4000 else 75.0, f"h{rva:x}")
            for rva in names
        }
        reviewed = {
            0x1000: {
                "status": "bounded", "wall_class": "cfg", "evidence": "done",
            },
            0x2000: {
                "status": "open", "wall_class": "inline",
                "evidence": "inspect site",
            },
            0x5000: {
                "status": "exact", "wall_class": "cfg", "evidence": "100%",
            },
        }
        with mock.patch.object(inventory, "report_scores",
                               return_value=("report", scores)), \
             mock.patch.object(inventory, "baseline_rows", return_value=baseline), \
             mock.patch("rom1.model.resolve",
                        return_value=SimpleNamespace(functions=funcs)), \
             mock.patch("rom1.walls.reviews.current", return_value=reviewed):
            rows = inventory.build(todo=True)
        self.assertEqual([row["rva"] for row in rows], ["0x002000", "0x003000"])
        self.assertEqual(rows[0]["review_status"], "open")
        self.assertEqual(rows[1]["review_status"], "")

    def test_headroom_is_hist_minus_the_BANK_not_hist_minus_cur(self):
        """THE distinction that decides whether a row is a question at all.

        `cur` below the BANK is this exact source scoring lower than it
        already has - TU composition, no action. The BANK below `hist` is a
        source EDIT that gave the peak up. Read the wrong way,
        `CGruntSelectedSprite::Update` (cur 84.85, bank 99.24, hist 99.24)
        is the biggest opportunity in the queue; read the right way there is
        nothing to do, and 20 of the 66 rows whose hist beats their cur are
        that shape.
        """
        from types import SimpleNamespace
        from rom1.walls import inventory

        names = {0x1000: "?TuNoise@C@@QAEHXZ", 0x2000: "?EditGaveItUp@C@@QAEHXZ"}
        funcs = [SimpleNamespace(unit="u", name=n, rva=r, size=0x10)
                 for r, n in names.items()]
        scores = {("u", "?TuNoise@C@@QAEHXZ"): 84.85,
                  ("u", "?EditGaveItUp@C@@QAEHXZ"): 70.12}
        baseline = {0x1000: (99.24, 99.24, "h1"),     # bank == hist
                    0x2000: (70.12, 77.52, "h2")}     # bank below hist
        with mock.patch.object(inventory, "report_scores",
                               return_value=("report", scores)), \
             mock.patch.object(inventory, "baseline_rows", return_value=baseline), \
             mock.patch("rom1.model.resolve",
                        return_value=SimpleNamespace(functions=funcs)):
            rows = {r["symbol"]: r for r in inventory.build()}
        self.assertEqual(rows["?TuNoise@C@@QAEHXZ"]["lost"], 0.0)
        self.assertTrue(rows["?TuNoise@C@@QAEHXZ"]["regressed"])
        self.assertAlmostEqual(rows["?EditGaveItUp@C@@QAEHXZ"]["lost"], 7.40, 2)
        self.assertFalse(rows["?EditGaveItUp@C@@QAEHXZ"]["regressed"])


class TierRunnerControls(unittest.TestCase):
    def test_a_crashing_gate_is_a_failure_not_a_skip(self):
        import contextlib
        import io

        from rom1.verify import tiers

        def boom():
            raise RuntimeError("tool broke")
        with mock.patch.dict(tiers.TIERS, {"fast": [("probe", boom)]}):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                failed = tiers.run(["fast"])
        self.assertEqual(failed, 1)
        self.assertIn("gate crashed", out.getvalue())

    def test_a_clean_gate_passes(self):
        import contextlib
        import io

        from rom1.verify import tiers
        with mock.patch.dict(tiers.TIERS, {"fast": [("probe", lambda: [])]}):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tiers.run(["fast"]), 0)


# --------------------------------------------------------------------------- #
# the data-access map: layout oracle, every category, every suppression       #
# --------------------------------------------------------------------------- #
def _layout(types=()):
    from rom1.verify.layout import Layout
    return Layout({"types": list(types), "units": {}, "tree_hash": "ctrl"})


def _prim(t, sz):
    return {"k": "prim", "t": t, "sz": sz}


def _arr(el, n, t="T[]"):
    return {"k": "arr", "t": t, "sz": el["sz"] * n, "n": n, "el": el}


def _claim(rva, node, name="?g_probe@@3HA", extent=None, channel="src",
           unit="probe"):
    from rom1.verify.access_map import Claim
    return Claim(rva=rva, name=name, unit=unit, channel=channel, kind="",
                 section=".data", space="data",
                 extent=extent if extent is not None else (node or {}).get("sz")
                 or 4, node=node, pct=100.0)


def _access(target, width=4, form="direct", rw="r", mnemonic="mov", text="",
            insn=0x1000, fpu="", ext="", scale=0, base_reg="", disp=0):
    from rom1.verify.access_map import Access
    return Access(insn_rva=insn, insn_len=6, mnemonic=mnemonic, site_rva=insn,
                  target_rva=target, width=width, rw=rw, form=form,
                  base_reg=base_reg, index_reg="eax" if scale else "",
                  scale=scale, disp=disp, fpu=fpu, ext=ext, origin="reloc",
                  text=text or f"{mnemonic} probe", owner=None)


def _findings(claims, accesses, rows=(), layout=None, cells=()):
    """Categories fired by one synthetic claim set - hermetic, no image."""
    from rom1.verify import data_access as da
    img = mock.Mock()
    img.pe.data_regions.return_value = {"rdata": (0, 0), "data": (0, 1 << 30),
                                        "bss": (0, 0),
                                        "idata": (0x2C3000, 0x2C6C00)}
    img.section_name.return_value = ".data"
    img.u32.return_value = 0x2C4CCC
    model = mock.Mock()
    model.functions = []
    spine = da.Spine(img, model, layout or _layout(), sorted(claims,
                                                             key=lambda c: c.rva),
                     list(rows))
    owners = mock.Mock()
    owners.at.return_value = None
    found, _st = da.derive_findings(spine, list(accesses), list(cells), owners)
    return found


def _cats(rows):
    return {r[0] for r in rows}


class LayoutOracleControls(unittest.TestCase):
    def test_an_array_element_offset_is_absolute(self):
        """The measured own-goal: resolving +0x4 of `int[32]` returned the
        ELEMENT-relative 0, so every array offset past the first read as
        'lands INSIDE field [1]' - 42 fabricated width findings."""
        lay = _layout()
        node = _arr(_prim("int", 4), 32, "int[32]")
        f = lay.field_at(node, 4)
        self.assertEqual((f.off, f.size, f.path, f.tag), (4, 4, "[1]", ""))
        self.assertEqual(lay.field_at(node, 0x7C).off, 0x7C)
        self.assertEqual(lay.field_at(node, 0x80).tag, "out")

    def test_a_union_is_laid_out_but_never_adjudicated(self):
        lay = _layout()
        u = {"k": "rec", "t": "U", "sz": 8, "u": 1,
             "m": [[0, ".a", _prim("int", 4)], [0, ".b", _prim("float", 4)]]}
        self.assertFalse(lay.field_at(u, 0).resolved)

    def test_the_vptr_slot_is_tagged_not_reported_as_a_hole(self):
        lay = _layout()
        poly = {"k": "rec", "t": "CFoo", "sz": 8, "poly": 1,
                "m": [[0, ".__vfptr", _prim("void *", 4)],
                      [4, ".m_x", _prim("int", 4)]]}
        self.assertEqual(lay.field_at(poly, 0).path, ".__vfptr")
        plain = {"k": "rec", "t": "CBar", "sz": 8,
                 "m": [[4, ".m_x", _prim("int", 4)]]}
        self.assertEqual(lay.field_at(plain, 0).tag, "hole")

    def test_the_harvest_joins_every_src_claim_on_this_tree(self):
        """The oracle is only worth its verdicts if it actually reaches the
        claims: a silent join failure would look exactly like a clean tree."""
        from rom1.core.paths import BUILD
        from rom1.model import resolve
        from rom1.verify.layout import CACHE, harvest
        if not CACHE.is_file() or not (BUILD / "objdiff/base").is_dir():
            self.skipTest("layout cache absent (unbuilt tree)")
        lay, _p = harvest()
        miss = [b.name for b in resolve().data
                if b.channel == "src" and not lay.var(b.unit, b.name)]
        self.assertEqual(miss[:5], [])


class DataAccessCategoryControls(unittest.TestCase):
    def test_a_narrow_declaration_is_caught(self):
        c = _claim(0x1000, _prim("unsigned char", 1), extent=1)
        self.assertIn("width", _cats(_findings([c], [_access(0x1000, 4)])))

    def test_the_and_mask_narrow_load_is_suppressed(self):
        """cl 5.0 reads a u16 global 4 bytes wide and masks the register; the
        2-byte STORE is what proves the field is 2 bytes (g_sfDeviceIndex)."""
        c = _claim(0x1000, _prim("unsigned short", 2), extent=2)
        acc = [_access(0x1000, 4, insn=0x1000),
               _access(0x1000, 2, rw="w", insn=0x1010)]
        self.assertNotIn("width", _cats(_findings([c], acc)))
        wide_store = [_access(0x1000, 4, insn=0x1000),
                      _access(0x1000, 4, rw="w", insn=0x1010)]
        self.assertIn("width", _cats(_findings([c], wide_store)))

    def test_a_double_moved_as_two_dwords_is_suppressed(self):
        c = _claim(0x1000, _prim("double", 8), extent=8)
        acc = [_access(0x1000, 4), _access(0x1004, 4, insn=0x1010)]
        self.assertNotIn("width", _cats(_findings([c], acc)))

    def test_a_string_op_width_is_not_a_field_width(self):
        c = _claim(0x1000, _prim("unsigned short", 2), extent=2)
        acc = [_access(0x1000, 4, mnemonic="stosd", rw="w",
                       text="rep stos DWORD PTR es:[edi],eax")]
        self.assertNotIn("width", _cats(_findings([c], acc)))

    def test_a_block_move_over_a_byte_ARRAY_is_suppressed_a_scalar_is_not(self):
        arr = _claim(0x1000, _arr(_prim("char", 1), 8, "char[8]"), extent=8)
        self.assertNotIn("width", _cats(_findings([arr], [_access(0x1000, 4)])))
        scalar = _claim(0x1000, _prim("char", 1), extent=1)
        self.assertIn("width", _cats(_findings([scalar], [_access(0x1000, 4)])))

    def test_an_x87_access_on_an_integer_field_is_caught(self):
        c = _claim(0x1000, _prim("int", 4), extent=4)
        acc = [_access(0x1000, 4, mnemonic="fld", fpu="f32")]
        self.assertIn("width", _cats(_findings([c], acc)))

    def test_an_index_into_a_single_element_array_is_an_undercount(self):
        one = _claim(0x1000, _arr(_prim("int", 4), 1, "int[1]"), extent=4)
        acc = [_access(0x1000, 4, form="indexed", scale=4,
                       text="mov eax,DWORD PTR [eax*4+0x401000]")]
        self.assertIn("undercount", _cats(_findings([one], acc)))
        many = _claim(0x1000, _arr(_prim("int", 4), 8, "int[8]"), extent=32)
        self.assertNotIn("undercount", _cats(_findings([many], acc)))

    def test_a_pair_array_declared_as_scalars_is_a_stride_finding(self):
        c = _claim(0x1000, _arr(_prim("int", 4), 32, "int[32]"), extent=128)
        acc = [_access(0x1000, 4, form="indexed", scale=8,
                       text="mov edx,DWORD PTR [edx*8+0x401000]")]
        self.assertIn("stride", _cats(_findings([c], acc)))

    def test_an_indexed_base_just_before_a_claim_is_not_unmodelled_data(self):
        """`[ecx + &g_buf - 4]` is g_buf's own 1-based spelling; the same
        address touched DIRECTLY is a real unclaimed byte."""
        c = _claim(0x1010, _arr(_prim("char", 1), 16, "char[16]"), extent=16)
        idx = [_access(0x100C, 1, form="indexed", rw="w", base_reg="ecx",
                       text="mov BYTE PTR [ecx+0x40100c],al")]
        self.assertNotIn("unclaimed", _cats(_findings([c], idx)))
        direct = [_access(0x100C, 1, rw="w", text="mov BYTE PTR ds:0x40100c,al")]
        self.assertIn("unclaimed", _cats(_findings([c], direct)))

    def test_a_source_claim_on_an_iat_slot_is_an_import(self):
        c = _claim(0x2C43C0, _prim("int", 4), name="?g_val_2c43c0@@3HA")
        acc = [_access(0x2C43C0, 4, form="iat", mnemonic="call",
                       text="call DWORD PTR ds:0x6c43c0")]
        self.assertIn("import-slot", _cats(_findings([c], acc)))
        lib = _claim(0x2C43C0, None, name="??_7CFoo@@6B@",
                     channel="data_vtables")
        self.assertNotIn("import-slot", _cats(_findings([lib], acc)))

    def test_a_claim_nothing_names_is_a_phantom_candidate(self):
        c = _claim(0x1000, _prim("int", 4))
        self.assertIn("unaccessed", _cats(_findings([c], [])))
        self.assertNotIn("unaccessed", _cats(_findings([c], [_access(0x1000)])))

    def test_one_access_crossing_two_claims_is_one_object(self):
        a = _claim(0x1000, _prim("int", 4), name="?g_a@@3HA")
        b = _claim(0x1004, _prim("int", 4), name="?g_b@@3HA")
        acc = [_access(0x1000, 8, mnemonic="fld", fpu="f64")]
        self.assertIn("adjacent", _cats(_findings([a, b], acc)))

    def test_the_gate_reports_gated_rows_and_honours_the_accept_list(self):
        """A report-only category must not break the build, a gated one must,
        and a documented exception must stay silent while its evidence holds
        (a STALE accept is itself reported)."""
        from rom1.verify import data_access as da
        fired = [("shortfall", "high", 0x1000, "?g_x@@3HA", 0x1004, "d", "e"),
                 ("undercount", "high", 0x3000, "?g_z@@3PAHA",
                  0x3000, "d", "e")]
        with mock.patch.object(da, "ACCEPTED_MISMODELS",
                               frozenset({("undercount", 0x3000)})), \
                mock.patch.object(da, "analysis",
                                  return_value=(None, None, None, None, fired,
                                                None, None)):
            out = da.gate_findings()
            self.assertEqual(len(out), 1)
            self.assertIn("shortfall", out[0])
        with mock.patch.object(da, "ACCEPTED_MISMODELS",
                               frozenset({("undercount", 0x3000)})), \
                mock.patch.object(da, "analysis",
                                  return_value=(None, None, None, None, [],
                                                None, None)):
            stale = da.gate_findings()
        self.assertTrue(any("STALE accept" in s for s in stale))

    def test_the_injected_defects_are_all_caught_on_the_real_tree(self):
        """The whole-tree harness: nine planted defects, each a class this
        campaign has shipped. A sieve returning 0 rows because it is BLIND is
        indistinguishable from a clean tree - this is what tells them apart."""
        from rom1.core.paths import BUILD
        from rom1.verify import data_access as da
        if not (BUILD / "gen/bindings.tsv").is_file():
            self.skipTest("no bindings (unbuilt tree)")
        missed = [f"{tag}->{want}" for tag, want, _label, caught
                  in da.run_selftest() if not caught]
        self.assertEqual(missed, [])


class DataCoverageControls(unittest.TestCase):
    def test_band_completion_cannot_cross_a_label_only_model_claim(self):
        from types import SimpleNamespace
        from rom1.delink.data_manifest import _model_barrier
        binding = SimpleNamespace(channel="data_vtables", rva=0x1010,
                                  size=0x10, name="??_7CFoo@@6B@")
        model = SimpleNamespace(data=[binding])
        self.assertIs(_model_barrier(model, 0x1000, 0x1040), binding)
        self.assertIsNone(_model_barrier(model, 0x1020, 0x1040))

    def _row(self, **kw):
        row = {"rva": 0x1000, "length": 16, "section": ".data",
               "verdict": "NONZERO", "addressed": 1, "touched": 8, "sites": 2,
               "payload_nonzero": 8, "relocs": 0, "prev_object": "probe",
               "prev_name": "?g_a@@3HA", "next_object": "probe",
               "next_name": "?g_b@@3HA", "first_bytes": "01"}
        row.update(kw)
        return row

    def test_a_touched_nonzero_gap_inside_one_unit_fails(self):
        from rom1.verify import data_coverage as dc
        self.assertEqual(len(dc.gate_rows([self._row()])), 1)

    def test_the_library_frontier_and_the_iat_do_not(self):
        from rom1.verify import data_coverage as dc
        self.assertEqual(dc.gate_rows([self._row(prev_object="library_data",
                                                 next_object="library_data")]),
                         [])
        self.assertEqual(dc.gate_rows([self._row(prev_object="probe",
                                                 next_object="other")]), [])
        self.assertEqual(dc.gate_rows([self._row(section=".idata")]), [])
        self.assertEqual(dc.gate_rows([self._row(touched=0, sites=0)]), [])
        self.assertEqual(dc.gate_rows([self._row(verdict="ZERO-GAP",
                                                 payload_nonzero=0)]), [])

    def test_linker_pooled_boundaries_do_not_claim_the_gap_between_them(self):
        from rom1.verify import data_coverage as dc
        self.assertEqual(dc.gate_rows([
            self._row(prev_linear=False, next_linear=False)
        ]), [])

    def test_a_folded_comdat_is_not_an_overlap_but_two_extents_are(self):
        from rom1.verify import data_coverage as dc
        folded = [{"rva": 0x1000, "size": 8, "name": "??_7C@@6B@",
                   "object": "a", "storage": "rdata"},
                  {"rva": 0x1000, "size": 8, "name": "??_7C@@6B@",
                   "object": "b", "storage": "rdata"}]
        self.assertEqual(dc.overlaps(folded), [])
        clash = folded + [{"rva": 0x1004, "size": 8, "name": "?g_x@@3HA",
                           "object": "c", "storage": "data"}]
        self.assertEqual(len(dc.overlaps(clash)), 1)


# --------------------------------------------------------------------------- #
# the DATA_COMPGEN negative-control set (real base objs)                      #
# --------------------------------------------------------------------------- #
class DataCompgenControls(unittest.TestCase):
    """The 16 controls from the extraction campaign: every malformed /
    unverifiable pin is REFUSED (never silently dropped, never admitted)."""

    def _cases(self):
        from rom1.core.paths import BUILD
        from rom1.model import resolve

        def owner_obj(rva, fallback):
            unit = next((b.unit for b in resolve().data
                         if b.rva == rva and b.unit), fallback)
            return BUILD / f"objdiff/base/{unit}.obj"

        # the owning TU is derived from the Model, not hardcoded - the pins
        # legitimately migrate when a fold re-homes their use sites
        obj = owner_obj(0x1E9A40, "grunt")
        str_obj = owner_obj(0x20D168, "fortconquered")
        return obj, str_obj, [
            ("positive f64", 'x = DATA_COMPGEN(0x001e9a40, 750.0);', obj, 1),
            ("positive str", 'x = DATA_COMPGEN(0x0020d168, "!");', str_obj, 1),
            ("wrong rva (right value, other slot)",
             'x = DATA_COMPGEN(0x001e9a48, 750.0);', obj, 0),
            ("value this TU never emitted",
             'x = DATA_COMPGEN(0x001e9a40, 751.0);', obj, 0),
            ("string this TU never emitted",
             'x = DATA_COMPGEN(0x0020d168, "nowhere");', str_obj, 0),
            ("string at the wrong rva",
             'x = DATA_COMPGEN(0x0020d16a, "!");', str_obj, 0),
            ("identifier value",
             'x = DATA_COMPGEN(0x001e9a40, g_thing);', obj, 0),
            ("integer value", 'x = DATA_COMPGEN(0x001e9a40, 750);', obj, 0),
            ("wide string", 'x = DATA_COMPGEN(0x0020d168, L"!");', str_obj, 0),
            ("non-canonical address",
             'x = DATA_COMPGEN(0x1e9a40, 750.0);', obj, 0),
            ("one argument", 'x = DATA_COMPGEN(0x001e9a40);', obj, 0),
            ("same rva, two values",
             'x = DATA_COMPGEN(0x001e9a40, 750.0) '
             '+ DATA_COMPGEN(0x001e9a40, 1.0);', obj, 1),
            ("f32 spelling of an f64 slot",
             'x = DATA_COMPGEN(0x001e9a40, 750.0f);', obj, 0),
            ("two pins on one line",
             'x = DATA_COMPGEN(0x001e9a40, 750.0) '
             '/ DATA_COMPGEN(0x001e9a58, 0.01);', obj, 2),
            ("wrapped over lines",
             'x = DATA_COMPGEN(0x001e9a58,\n        0.01);', obj, 1),
            ("commented out",
             '// x = DATA_COMPGEN(0x001e9a40, 750.0);', obj, 0),
        ]

    def test_the_sixteen_controls(self):
        from rom1.retail_labels.source import blank_comments, compgen_claims
        obj, str_obj, cases = self._cases()
        if not obj.is_file() or not str_obj.is_file():
            self.skipTest("base objs absent (unbuilt tree) - the "
                          "DATA_COMPGEN controls need grunt.obj + "
                          "fortconquered.obj")
        bad = []
        for label, text, o, want in cases:
            claims, problems = compgen_claims(blank_comments(text), "ctrl", o)
            ok = len(claims) == want and (want
                                          or all("FATAL" in p
                                                 for p in problems))
            if not ok:
                bad.append(f"{label}: claims={len(claims)} want={want} "
                           f"problems={problems[:1]}")
        self.assertEqual(bad, [])


class LedgerPrecisionControls(unittest.TestCase):
    """Below-best must read the same on a live float and on its banked copy.

    The bank stores cur_pct to 4 decimals. While the regress test compared
    the raw float and the carried test the stored one, a row whose dip is
    exactly EPS was regressed AND never-carried at once - banking could not
    clear it and the build gate stayed red forever (seen live on
    StepDiggerBehavior, best 68.1947 vs cur 68.18469).
    """

    def test_raw_and_banked_readings_agree(self):
        from rom1.verify.baseline import at_ledger_precision, below_best
        best = 68.1947
        for raw in (68.18469, 68.1847, 68.18471, 68.0, 68.1947, 70.0):
            self.assertEqual(
                below_best(raw, best),
                below_best(at_ledger_precision(raw), best),
                f"{raw} reads differently once banked - unclearable gate")

    def test_a_dip_the_ledger_cannot_see_is_not_a_regression(self):
        from rom1.verify.baseline import below_best
        self.assertFalse(below_best(68.18469, 68.1947))   # rounds to the edge
        self.assertTrue(below_best(68.1840, 68.1947))     # genuinely below

    def test_a_real_dip_is_still_fresh_after_banking(self):
        from rom1.verify.classify import currency
        base = {("u", "f"): {"best": 90.0, "cur": 90.0, "fp": "h", "tries": 1}}
        got = currency({("u", "f"): 80.0}, base, [("u", "f", 80.0, 90.0)])
        self.assertEqual((got["regress_fresh"], got["regress_carried"]), (1, 0))

    def test_a_banked_dip_is_carried(self):
        from rom1.verify.classify import currency
        base = {("u", "f"): {"best": 90.0, "cur": 80.0, "fp": "h", "tries": 1}}
        got = currency({("u", "f"): 80.0}, base, [("u", "f", 80.0, 90.0)])
        self.assertEqual((got["regress_fresh"], got["regress_carried"]), (0, 1))


# --------------------------------------------------------------------------- #
# investigation surfaces (sema / walls / lsp / ghidra): a navigator that
# answers CONFIDENTLY and WRONGLY is worse than one that fails, so each of
# these is the control for a defect that shipped.
# --------------------------------------------------------------------------- #
class SemaReportSourceControls(unittest.TestCase):
    """sema read build/objdiff/report.json - the BANKED reference copy, not
    the report `rom1 compare` writes. `sema match 0x153810` answered 99.57%
    while walls/verify read 99.89% off the same build."""

    def test_sema_reads_the_same_reports_in_the_same_order_as_verify(self):
        from rom1.sema.report import REPORTS as sema_reports
        from rom1.verify.scores import REPORTS as verify_reports
        self.assertEqual(tuple(sema_reports), tuple(verify_reports))

    def test_the_current_report_wins_over_the_banked_one(self):
        from rom1.sema import report as rep
        with tempfile.TemporaryDirectory() as td:
            new, old = Path(td) / "new.json", Path(td) / "old.json"
            old.write_text('{"units": [], "measures": {}}')
            with mock.patch.object(rep, "REPORTS", (new, old)):
                self.assertEqual(rep.report_path(), old)   # only the bank
                new.write_text('{"units": [], "measures": {}}')
                self.assertEqual(rep.report_path(), new)   # current wins


class SemaPipeControls(unittest.TestCase):
    """`rom1 sema vtable --list | head` exited 120 with 'Exception ignored
    on flushing sys.stdout' - the BrokenPipeError fires at interpreter exit,
    after run()'s handler could ever see it."""

    def test_a_closed_reader_is_a_clean_exit(self):
        import os

        from rom1 import sema
        r, w = os.pipe()
        os.close(r)                                  # the reader is gone
        saved = os.dup(1)
        try:
            os.dup2(w, 1)
            os.close(w)
            mod = mock.Mock()
            mod.main.side_effect = lambda argv: (print("x" * 200_000), 0)[1]
            with mock.patch("importlib.import_module", return_value=mod):
                rc = sema.run("rom1.sema.rva", [])
        finally:
            os.dup2(saved, 1)
            os.close(saved)
        self.assertEqual(rc, 0)


class SemaMapControls(unittest.TestCase):
    """`sema map at <unmapped>` printed 'no admitted row covers this address'
    and exited 0, against sema's own rc convention (1 = answered-NO)."""

    def test_an_uncovered_address_is_answered_no(self):
        from rom1.sema import map as smap
        idx = mock.Mock()
        idx.covering.return_value = None
        idx.preceding_func.return_value = None
        with mock.patch.object(smap, "index", return_value=idx), \
             mock.patch("rom1.sema.image.retail") as retail:
            retail.return_value.section_of.return_value = None
            lines, rc = smap.at(0xDEADBEEF)
        self.assertEqual(rc, 1)
        self.assertIn("outside every section", "\n".join(lines))


class SemaXrefControls(unittest.TestCase):
    """A relocated vtable/callback reference to a linker-thunk entry must
    keep the final body live.  The old tree followed only rel32 edges after
    entering the thunk and confidently printed ``no caller``."""

    def test_a_reference_to_a_thunk_entry_reaches_the_forwarded_body(self):
        from rom1.sema import xref

        idx = mock.Mock()
        thunk = mock.Mock(rva=0x2000, size=0x10, kind="thunk")
        idx.owner.side_effect = lambda site: thunk if site == 0x2005 else None

        img = mock.Mock()
        img.call_index = {0x1000: [(0x2005, 0xE9)]}
        img.jmp_target.side_effect = lambda site: 0x1000 if site == 0x2005 else None
        img.refs_to_range.side_effect = lambda lo, hi: (
            [(0x3000, 0x2005)] if (lo, hi) == (0x2005, 0x2006) else [])

        with mock.patch.object(xref, "index", return_value=idx), \
             mock.patch.object(xref, "retail", return_value=img), \
             mock.patch.object(xref, "site_where", return_value="in vtable"):
            lines = xref.caller_tree(0x1000)
            self.assertTrue(xref.is_effectively_reached(0x1000, 0x20))

        text = "\n".join(lines)
        self.assertIn("<- ref", text)
        self.assertIn("via 1 thunk", text)

    def test_an_unreferenced_thunk_does_not_make_the_body_live(self):
        from rom1.sema import xref

        idx = mock.Mock()
        thunk = mock.Mock(rva=0x2000, size=0x10, kind="thunk")
        idx.owner.return_value = thunk
        img = mock.Mock()
        img.call_index = {0x1000: [(0x2005, 0xE9)]}
        img.jmp_target.return_value = 0x1000
        img.refs_to_range.return_value = []

        with mock.patch.object(xref, "index", return_value=idx), \
             mock.patch.object(xref, "retail", return_value=img):
            self.assertFalse(xref.is_effectively_reached(0x1000, 0x20))


class DeadCodeControls(unittest.TestCase):
    def test_missing_and_stale_markers_both_fail(self):
        from rom1.verify import dead_code

        sites = {0x1000: ("a.cpp", 4), 0x2000: ("b.cpp", 8)}
        marked = {0x2000: [("b.cpp", 6)]}
        findings = dead_code.compare(marked, sites, {0x1000, 0x2000}, {0x1000})
        self.assertTrue(any("missing" in f for f in findings))
        self.assertTrue(any("stale" in f for f in findings))

    def test_a_proven_marker_is_clean_and_requires_its_proof_line(self):
        from rom1.verify import dead_code

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "probe.cpp"
            path.write_text("// @dead-code\n"
                            "// Zero-ref: no retail reachability.\n"
                            "RVA(0x00001000, 0x1)\n"
                            "void Probe() {}\n")
            marked, sites, problems = dead_code.source_markers([path])
            self.assertEqual(problems, [])
            self.assertEqual(dead_code.compare(marked, sites, {0x1000},
                                               {0x1000}), [])
            path.write_text("// @dead-code\n"
                            "RVA(0x00001000, 0x1)\n"
                            "void Probe() {}\n")
            _marked, _sites, problems = dead_code.source_markers([path])
            self.assertTrue(any("proof" in f for f in problems))


class SemaGapControls(unittest.TestCase):
    """The same-file gap view must trim only edge padding and keep executable
    categories separate; otherwise the derived reconstruction queue can lose a
    tiny body or bury one under the repeated compiler/runtime bands."""

    def test_edge_padding_is_trimmed_without_eating_body_bytes(self):
        from rom1.sema import gaps
        rva, body = gaps._trim(0x1000, b"\x90\xcc\xc3\x90")
        self.assertEqual((rva, body), (0x1002, b"\xc3"))

    def test_gap_kinds_preserve_tiny_and_substantive_bodies(self):
        from rom1.sema import gaps
        with mock.patch.object(gaps, "_switch_table", return_value=False):
            self.assertEqual(gaps._kind(b"\xe9\x00\x00\x00\x00", None), "thunk")
            self.assertEqual(gaps._kind(b"\x33\xc0\xc3", None), "trivial")
            self.assertEqual(gaps._kind(b"\x55" * 9, None), "substantive")
            self.assertEqual(gaps._kind(b"\x55" * 0x100, None), "band")

    def test_aligned_padding_separates_multiple_missing_functions(self):
        from rom1.sema import gaps
        payload = b"\xc3" + b"\x90" * 15 + b"\xcc" * 16 + b"\xc2\x04\x00\x90"
        self.assertEqual(
            gaps._split(0x17400, payload),
            [(0x17400, b"\xc3"), (0x17420, b"\xc2\x04\x00")],
        )

    def test_xc_table_distinguishes_initializer_thunks_from_bodies(self):
        from rom1.sema import gaps

        class FakePe:
            image_base = 0x400000

            def read(self, rva, size):
                if rva == gaps.XC_START:
                    slots = [0x410000, 0x420000]
                    return struct.pack("<2I", *slots) + bytes(size - 8)
                if rva == 0x10000:
                    return b"\xe9\xfb\x00\x00\x00"
                if rva == 0x20000:
                    return b"\xc3\x90\x90\x90\x90"
                return None

        self.assertEqual(
            gaps._dyninit_roles(FakePe()),
            {0x10000: "dyninit-thunk", 0x10100: "dyninit-body", 0x20000: "dyninit-body"},
        )

    def test_initializer_owner_follows_relocated_data_not_neighbours(self):
        from rom1.sema import gaps
        img = mock.Mock()
        img.relocs_in.return_value = [(0x17D86, 0x229E18), (0x17D90, 0x229E1C)]
        idx = mock.Mock()
        idx.data_owner.side_effect = [mock.Mock(unit="customleveldlg"),
                                      mock.Mock(unit="customleveldlg")]
        self.assertEqual(
            gaps._dyninit_owner(0x17D80, 0x1A, img, idx),
            "customleveldlg",
        )

    def test_existing_non_source_claim_is_not_reported_as_a_gap(self):
        from rom1.sema import gaps
        binding = mock.Mock(rva=0x21280, size=0x10, channel="functions_static_libs")
        self.assertTrue(gaps._covered(0x21280, 0x10, [binding]))
        self.assertFalse(gaps._covered(0x21260, 0x8, [binding]))


class WallsUnitFilterControls(unittest.TestCase):
    """A misspelt --unit answered '0 mismatches' / '0 function(s) below 100%'
    - a typo that reads as a clean sieve."""

    def test_an_unknown_unit_is_refused(self):
        from rom1 import walls
        with mock.patch("rom1.manifest.units",
                        return_value=[{"unit": "cimage"}]):
            with self.assertRaises(SystemExit) as cm:
                walls.check_unit("cimag")
            self.assertEqual(cm.exception.code, 2)
            self.assertEqual(walls.check_unit("cimage"), "cimage")
            self.assertIsNone(walls.check_unit(None))


class WallsEmptyBuildControls(unittest.TestCase):
    """With no normalized pair on disk the sieves printed 'aggregate-copy
    mismatches: 0' / 'paired functions: 0' and exited 0 - an unbuilt tree
    reading as a clean sieve."""

    def test_no_pair_is_refused_not_answered(self):
        from rom1.walls import pairscan
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(pairscan, "NORM", Path(td)):
                with self.assertRaises(SystemExit) as cm:
                    pairscan.require_pairs()
                self.assertEqual(cm.exception.code, 2)

    def test_a_real_pair_passes_through(self):
        from rom1.walls import pairscan
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "base").mkdir()
            (root / "target").mkdir()
            (root / "base/cimage.obj").write_bytes(b"")
            (root / "target/cimage.c.obj").write_bytes(b"")
            with mock.patch.object(pairscan, "NORM", root):
                self.assertEqual(list(pairscan.require_pairs()), ["cimage"])


class EhFrameTsvControls(unittest.TestCase):
    """`--calibrate` returned before the `--tsv` writer, so asking for both
    silently produced no file."""

    ROW = dict(unit="u", name="?f@@YAXXZ", rva="0x001000", fuzzy=100.0,
               size=16, verdict="BOTH", cause="EXTRA_OBJECT", extra_ctors=[],
               our_ctors=[], resited=[], base_insn=4, tgt_insn=4,
               slot="[esp+0x4]", states=[0], base_states=1, tgt_states=1,
               first=0, last=4, unwind=True)

    def test_calibrate_still_writes_the_tsv(self):
        import contextlib
        import io

        from rom1.walls import eh_frame
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "eh.tsv"
            with mock.patch.object(eh_frame, "scan", return_value=[self.ROW]), \
                 mock.patch.object(eh_frame.pairscan, "require_pairs"), \
                 contextlib.redirect_stdout(io.StringIO()):
                eh_frame.main(["--calibrate", "--tsv", str(out)])
            self.assertTrue(out.is_file(), "--tsv was swallowed by --calibrate")
            self.assertIn("verdict", out.read_text().splitlines()[0])


class WallsDiagnoseTargetControls(unittest.TestCase):
    """diagnose took only the rva or the exact mangled name, and answered
    every miss with the same 'no claimed function for X'."""

    def _model(self, *names):
        fns = [_binding(0x153810 + i * 0x10, n) for i, n in enumerate(names)]
        return mock.Mock(functions=fns)

    def test_a_readable_spelling_resolves(self):
        from rom1.walls import diagnose as D
        name = "?RenderFrameClipped@CImage@@QAEXH@Z"
        with mock.patch("rom1.model.resolve", return_value=self._model(name)):
            b, why = D._locate("CImage::RenderFrameClipped")
            self.assertIsNotNone(b, why)
            self.assertEqual(b.name, name)

    def test_a_miss_names_the_accepted_spellings(self):
        from rom1.walls import diagnose as D
        with mock.patch("rom1.model.resolve", return_value=self._model()):
            b, why = D._locate("NoSuchThing")
            self.assertIsNone(b)
            self.assertIn("CClass::Member", why)
            b, why = D._locate("0xdeadbeef")
            self.assertIsNone(b)
            self.assertIn("sema rva", why)

    def test_a_relocation_free_call_to_function_start_is_self_recursion(self):
        from rom1.walls import diagnose as D
        asm = "   2ba:\te8 00 00 00 00\tcall 0x0\n"
        self.assertEqual(D._call_targets({}, asm, "?f@@YAXXZ"), [("?f@@YAXXZ", 0)])

    def test_a_relocated_call_is_not_counted_twice_as_self_recursion(self):
        from rom1.walls import diagnose as D
        asm = "   2ba:\te8 00 00 00 00\tcall 0x0\n"
        rel = {0x2bb: ("?f@@YAXXZ", 0)}
        self.assertEqual(D._call_targets(rel, asm, "?f@@YAXXZ"), [("?f@@YAXXZ", 0)])

    def test_diagnose_does_not_route_relocation_free_self_recursion_to_inline(self):
        import contextlib
        import io
        from types import SimpleNamespace

        from rom1.walls import diagnose as D
        name = "?ImportDirectoryTree@CRezArchive@@QAEHXZ"
        binding = SimpleNamespace(unit="u", name=name, rva=0x13B300)
        asm = "   0:\te8 fb ff ff ff\tcall 0x0\n"
        with tempfile.TemporaryDirectory() as td:
            norm = Path(td)
            (norm / "base").mkdir()
            (norm / "target").mkdir()
            (norm / "base/u.obj").touch()
            (norm / "target/u.c.obj").touch()
            found = [
                (b"base", {1: (name, 0)}, 4),
                (b"target", {}, 4),
            ]
            skeletons = [
                (b"base", 1, 0, 0, 1, asm),
                (b"target", 1, 0, 0, 1, asm),
            ]
            with mock.patch.object(D, "NORM", norm), \
                 mock.patch.object(D, "_locate", return_value=(binding, "")), \
                 mock.patch.object(D, "Obj", side_effect=lambda path: path), \
                 mock.patch.object(D, "_find_function", side_effect=found), \
                 mock.patch.object(D, "_jump_table_bytes", return_value=set()), \
                 mock.patch.object(D, "_skeleton", side_effect=skeletons), \
                 contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(D.diagnose("0x13b300"), 0)
        self.assertIn("REGALLOC/SCHEDULING", out.getvalue())
        self.assertNotIn("INLINE/CALL-SET", out.getvalue())

    def test_diagnose_names_a_repeated_call_site_delta(self):
        import contextlib
        import io
        from types import SimpleNamespace

        from rom1.walls import diagnose as D
        name = "?StepArrivalDrop@CGrunt@@QAEHHHHHHH@Z"
        callee = "?RemoveHead@CPtrList@@QAEPAXXZ"
        binding = SimpleNamespace(unit="u", name=name, rva=0x4B370)
        run = [f"{i:x}:\t90\tmov eax,0x{i:x}" for i in range(1, 11)]
        base_asm = "\n".join(run + ["b:\t74 00\tje 0xd"]
                             + run + ["17:\t75 00\tjne 0x19"])
        skeletons = [
            (b"base", 3, 0, 0, 1, base_asm),
            (b"target", 4, 0, 0, 1, ""),
        ]
        with tempfile.TemporaryDirectory() as td:
            norm = Path(td)
            (norm / "base").mkdir()
            (norm / "target").mkdir()
            (norm / "base/u.obj").touch()
            (norm / "target/u.c.obj").touch()
            with mock.patch.object(D, "NORM", norm), \
                 mock.patch.object(D, "_locate", return_value=(binding, "")), \
                 mock.patch.object(D, "Obj", side_effect=lambda path: path), \
                 mock.patch.object(D, "_find_function", side_effect=[
                     (b"base", {}, 4), (b"target", {}, 4)]), \
                 mock.patch.object(D, "_jump_table_bytes", return_value=set()), \
                 mock.patch.object(D, "_skeleton", side_effect=skeletons), \
                 mock.patch.object(D, "_call_targets", side_effect=[
                     [(callee, 0)] * 3, [(callee, 0)] * 4]), \
                 contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(D.diagnose("0x4b370"), 0)
        text = out.getvalue()
        self.assertIn("INLINE/CALL-SET", text)
        self.assertIn("REPEATED-SITE DELTA: target 4, base 3", text)
        self.assertIn(callee, text)
        self.assertIn("site-positioned inline-budget residue", text)
        self.assertNotIn("is a CFG reconstruction question", text)


class InlineModelFlagControls(unittest.TestCase):
    """--spec was documented, parsed, and then fell through to
    `error: need --selftest, --spec/--gap FILE, or --measure-cb TU`."""

    def test_spec_predicts_instead_of_erroring(self):
        import contextlib
        import io

        from rom1.walls import inline_model
        with tempfile.TemporaryDirectory() as td:
            spec = Path(td) / "s.json"
            spec.write_text('{"caller_cb": 120, "sites": ['
                            + ",".join(['{"name": "fill", "cb": 150}'] * 9)
                            + "]}")
            with contextlib.redirect_stdout(io.StringIO()) as out:
                rc = inline_model.main(["--spec", str(spec)])
        text = out.getvalue()
        self.assertEqual(rc, 0)
        self.assertEqual(text.count("EXPAND fill"), 6)     # the oracle shape
        self.assertEqual(text.count("call   fill"), 3)

    def test_a_malformed_spec_is_explained(self):
        from rom1.walls import inline_model
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "b.json"
            bad.write_text("{}")
            with self.assertRaises(SystemExit):
                inline_model.main(["--spec", str(bad)])
            with self.assertRaises(SystemExit):
                inline_model.main(["--gap", str(Path(td) / "absent.json")])


class ExeMapWriteControls(unittest.TestCase):
    """`python3 -m rom1.sema.exe_map --help` ignored the flag and rewrote
    docs/exe-map/ - a help request with a side effect on the tracked tree."""

    def test_help_does_not_write(self):
        import contextlib
        import io

        from rom1.sema import exe_map
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                exe_map.main(["--help"])
        self.assertEqual(cm.exception.code, 0)

    def test_check_writes_nothing(self):
        import contextlib
        import io

        from rom1.sema import exe_map
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(exe_map, "core_rows",
                                   return_value=[{"unit": "u", "name": "n",
                                                  "rva": 0x1000, "size": 4}]), \
                 mock.patch.object(exe_map, "unit_sources", return_value={}), \
                 mock.patch.object(exe_map, "OUT_DIR", Path(td) / "out"), \
                 contextlib.redirect_stdout(io.StringIO()):
                exe_map.main(["--check"])
            self.assertFalse((Path(td) / "out").exists())


class ToolDriverMessageControls(unittest.TestCase):
    """A missing file / unparsable address reached the user as a traceback."""

    def test_objdump_refuses_a_missing_blob_and_a_bad_vma(self):
        from rom1.tool import objdump
        with tempfile.TemporaryDirectory() as td:
            blob = Path(td) / "b.bin"
            blob.write_bytes(b"\x90\xc3")
            self.assertEqual(objdump.main([str(Path(td) / "absent.bin")]), 2)
            self.assertEqual(objdump.main([str(blob), "--vma", "zz"]), 2)

    def test_ghidra_verify_refuses_a_non_address(self):
        from rom1.ghidra import project
        self.assertEqual(project.main(["verify", "zzz"]), 2)

    def test_lsp_point_names_the_missing_file(self):
        from rom1.lsp.query import parse_point
        with self.assertRaises(SystemExit) as cm:
            parse_point("include/NoSuchHeader.h:12")
        self.assertIn("no such file", str(cm.exception))
        self.assertIsNone(parse_point("CGrunt::GetAI"))   # still a symbol


# --------------------------------------------------------------------------- #
# the runner and the CLI surface (2026-08-16 review)                          #
# --------------------------------------------------------------------------- #
class TierRunnerExitControls(unittest.TestCase):
    """SystemExit is a BaseException: a gate reporting a missing input by
    raising it used to abort the whole tier, silently skipping every gate
    after it - the run looked short, not failed."""

    def _run(self, gates):
        import contextlib
        import io

        from rom1.verify import tiers
        with mock.patch.dict(tiers.TIERS, {"fast": gates}):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                failed = tiers.run(["fast"])
        return failed, out.getvalue()

    def test_a_gate_that_raises_systemexit_is_a_failure_not_an_abort(self):
        def bail():
            raise SystemExit("no report.json - run `rom1 compare` first")
        seen = []
        failed, text = self._run([("probe", bail),
                                  ("after", lambda: seen.append(1) or [])])
        self.assertEqual(failed, 1)
        self.assertIn("could not run", text)
        self.assertIn("no report.json", text)
        self.assertEqual(seen, [1])          # the NEXT gate still ran

    def test_the_rerun_hint_names_a_command_that_exists(self):
        from rom1.verify import _ALIASES, _GATES, tiers
        for tier, rows in tiers.TIERS.items():
            for name, _fn in rows:
                hint = tiers._rerun_command(name)
                gate = hint.rsplit(" ", 1)[-1]
                self.assertIn(gate, _GATES,
                              f"[{tier}] {name}: hint {hint!r} names no gate")
        # the row this got wrong: the `vtable-bans` label runs verify.BANS, so
        # the mechanical name.replace('-','_') named a module that does not
        # exist (`python3 -m rom1.verify.vtable_bans`).
        self.assertEqual(_ALIASES["vtable-bans"], "bans")
        self.assertEqual(tiers._rerun_command("vtable-bans"),
                         "rom1 verify bans")

    def test_every_tier_label_is_runnable_as_a_verb(self):
        """A tier label nobody can type is a dead end at the exact moment the
        gate fails."""
        from rom1.verify import (_ALIASES, _GATES, _QUERY_ONLY, _STANDALONE,
                                   tiers)
        for tier, rows in tiers.TIERS.items():
            for name, _fn in rows:
                verb = _ALIASES.get(name, name)
                self.assertIn(verb, _GATES,
                              f"[{tier}] {name} runs in a tier but "
                              f"`rom1 verify {name}` reaches nothing")
        # and the help listing's own claim: every non-oracle gate IS tier-run
        labels = {n for rows in tiers.TIERS.values() for n, _f in rows}
        in_a_tier = {_ALIASES.get(n, n) for n in labels}
        for gate in _GATES:
            if gate in _QUERY_ONLY or gate in _STANDALONE:
                continue
            self.assertIn(gate, in_a_tier,
                          f"{gate} is advertised as tier-run but no tier "
                          f"lists it (add it to a tier, or declare it in "
                          f"_QUERY_ONLY or _STANDALONE)")

    def test_the_alias_verb_actually_dispatches(self):
        import contextlib
        import io

        from rom1 import verify
        with mock.patch("rom1.verify.bans.main", return_value=0) as m:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(verify.main(["vtable-bans"]), 0)
        m.assert_called_once()


class ReportInputControls(unittest.TestCase):
    """A bad --report is an operator error, not a traceback."""

    def test_missing_malformed_and_foreign_json_all_say_what_to_do(self):
        from rom1.verify import scores
        with tempfile.TemporaryDirectory() as td:
            gone = Path(td) / "gone.json"
            with self.assertRaises(SystemExit) as e:
                scores.load(gone)
            self.assertIn("gone.json", str(e.exception))

            trunc = Path(td) / "trunc.json"
            trunc.write_text('{"units": [')
            with self.assertRaises(SystemExit) as e:
                scores.load(trunc)
            self.assertIn("not valid JSON", str(e.exception))
            self.assertIn("rom1 compare", str(e.exception))

            foreign = Path(td) / "other.json"
            foreign.write_text('{"hello": 1}')
            with self.assertRaises(SystemExit) as e:
                scores.load(foreign)
            self.assertIn("not an objdiff report", str(e.exception))

    def test_an_unknown_tier_is_rejected_before_any_work(self):
        """`check --tier bogus` used to run the whole MAX gate first, so the
        typo surfaced behind a wall of regression output."""
        from rom1.verify import verbs
        with mock.patch.object(verbs, "_report",
                               side_effect=AssertionError("ran the gate")):
            with self.assertRaises(SystemExit) as e:
                verbs.cmd_check(["--tier", "bogus"])
        self.assertIn("unknown tier", str(e.exception))

    def test_a_real_report_still_loads(self):
        from rom1.verify import scores
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "r.json"
            p.write_text('{"units": [], "measures": {}}')
            self.assertEqual(scores.load(p)["units"], [])


class GateCliSurfaceControls(unittest.TestCase):
    """Every `rom1 verify <gate>` answers --help and REJECTS a typo; none
    of them treats an unknown flag as 'run anyway'."""

    def test_every_gate_module_parses_its_argv(self):
        import contextlib
        import importlib
        import io

        from rom1.verify import _GATES
        for gate, module in sorted(_GATES.items()):
            mod = importlib.import_module(module)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                with self.assertRaises(SystemExit) as e:
                    mod.main(["--help"])
            self.assertEqual(e.exception.code, 0, f"{gate} --help")
            # RENDERING it is the check: argparse %-expands help strings, so
            # an unescaped `%` in one (`100%-clean`) raises inside --help.
            self.assertIn("usage:", out.getvalue(), f"{gate} --help")
            self.assertIn("options:", out.getvalue(), f"{gate} --help")
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as e:
                    mod.main(["--definitely-not-a-flag"])
            self.assertEqual(e.exception.code, 2, f"{gate} unknown flag")

    def test_no_gate_flag_is_a_silent_no_op(self):
        """A flag argparse accepts and nothing ever READS is worse than no
        flag: it looks like it worked. (`verify vtables --list` was one.)"""
        import ast
        import importlib
        import re

        from rom1.verify import _GATES

        def unread(src):
            """dests argparse defines that no `<ns>.<dest>` ever reads."""
            tree = ast.parse(src)
            dests, namespaces = [], set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) \
                        and isinstance(node.func, ast.Attribute) \
                        and node.func.attr == "add_argument":
                    opts = [a.value for a in node.args
                            if isinstance(a, ast.Constant)]
                    dest = next((kw.value.value for kw in node.keywords
                                 if kw.arg == "dest"
                                 and isinstance(kw.value, ast.Constant)), None)
                    if dest is None and opts:
                        longs = [o for o in opts if o.startswith("--")] or opts
                        dest = longs[0].lstrip("-").replace("-", "_")
                    if dest and dest != "help":
                        dests.append(dest)
                if isinstance(node, ast.Assign) \
                        and isinstance(node.value, ast.Call) \
                        and isinstance(node.value.func, ast.Attribute) \
                        and node.value.func.attr == "parse_args":
                    namespaces |= {t.id for t in node.targets
                                   if isinstance(t, ast.Name)}
            # `args` covers the do_*(args) handlers data_access hands off to
            names = namespaces | {"args"}
            return dests, [d for d in dests
                           if not any(re.search(rf"\b{n}\.{d}\b", src)
                                      for n in names)]

        # the detector must actually SEE flags, or an empty `dead` proves
        # nothing (this scan found `vtables --list` before it was removed)
        probe = ('import argparse\nap = argparse.ArgumentParser()\n'
                 'ap.add_argument("--used", action="store_true")\n'
                 'ap.add_argument("--dead", action="store_true")\n'
                 'a = ap.parse_args()\nprint(a.used)\n')
        self.assertEqual(unread(probe), (["used", "dead"], ["dead"]))

        seen, dead = 0, []
        for gate, module in sorted(_GATES.items()):
            src = Path(importlib.import_module(module).__file__).read_text()
            dests, bad = unread(src)
            seen += len(dests)
            dead += [f"{gate} --{d.replace('_', '-')}" for d in bad]
        self.assertGreater(seen, 30, "the flag scan found almost nothing")
        self.assertEqual(dead, [])

    def test_every_gate_flag_documents_itself(self):
        """`--help` listing a bare flag name tells the reader nothing; the
        one place a flag's meaning is guaranteed to be found is `help=`."""
        import ast
        import importlib

        from rom1.verify import _GATES
        bare = []
        for gate, module in sorted(_GATES.items()):
            src = Path(importlib.import_module(module).__file__).read_text()
            for node in ast.walk(ast.parse(src)):
                if isinstance(node, ast.Call) \
                        and isinstance(node.func, ast.Attribute) \
                        and node.func.attr == "add_argument" \
                        and not any(kw.arg == "help" for kw in node.keywords):
                    opts = [a.value for a in node.args
                            if isinstance(a, ast.Constant)]
                    bare.append(f"{gate} {'/'.join(opts)}")
        self.assertEqual(bare, [])

    def test_model_help_does_not_run_the_join(self):
        """`rom1 model --help` used to resolve the whole Model and REWRITE
        build/gen/bindings.tsv as a side effect of asking for help."""
        import contextlib
        import io

        import rom1.model as model
        with mock.patch.object(model, "resolve") as res, \
             mock.patch.object(model, "serialize") as ser:
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as e:
                    model.main(["--help"])
        self.assertEqual(e.exception.code, 0)
        res.assert_not_called()
        ser.assert_not_called()


# --------------------------------------------------------------------------- #
# never vacuous: a gate that measured NOTHING may not report OK               #
# --------------------------------------------------------------------------- #
class VacuityControls(unittest.TestCase):
    def test_tu_order_refuses_an_empty_scan(self):
        from rom1.verify import tu_order as to
        with mock.patch.object(to, "load_in_file_order", return_value={}), \
             mock.patch.object(to, "load_exiles", return_value={}), \
             mock.patch.object(to, "load_emitted_claims", return_value={}), \
             mock.patch.object(to, "_load_baseline", return_value=({}, 0)):
            findings, _s = to.gate_findings()
        self.assertTrue(any("vacuous" in f for f in findings))

    def test_data_tu_order_refuses_zero_defs(self):
        from rom1.verify import data_tu_order as dto
        with mock.patch.object(dto, "crossings", return_value=(set(), 0, [])), \
             mock.patch.object(dto, "load_baseline", return_value=set()):
            self.assertTrue(any("vacuous" in f for f in dto.gate_findings()))
        with mock.patch.object(dto, "crossings", return_value=(set(), 42, [])), \
             mock.patch.object(dto, "load_baseline", return_value=set()):
            self.assertEqual(dto.gate_findings(), [])

    def test_caller_callee_refuses_an_empty_call_graph(self):
        from rom1.verify import caller_callee as cc
        rc = mock.Mock()
        rc.tgt = set()
        with mock.patch.object(cc, "_summary", return_value=(rc, [], {})):
            self.assertTrue(any("vacuous" in f for f in cc.gate_findings()))

    def test_caller_callee_follows_inline_forwarding_members(self):
        from rom1.verify.caller_callee import _resolve_source_calls
        wrapper = "?ApplyName@CWapX@@QAEXPBD@Z"
        real = "?ApplyName@CWwdGameObjectA@@QAEXPBD@Z"
        rvas, leaves = _resolve_source_calls(
            wrapper, {wrapper: {real}}, {real: 0x150540})
        self.assertEqual(rvas, {0x150540})
        self.assertEqual(leaves, set())

    def test_caller_callee_keeps_unresolved_forwarding_leaves(self):
        from rom1.verify.caller_callee import _resolve_source_calls
        wrapper = "?Run@CRealInline@@QAEXXZ"
        phantom = "?Run@CPhantomView@@QAEXXZ"
        rvas, leaves = _resolve_source_calls(
            wrapper, {wrapper: {phantom}}, {})
        self.assertEqual(rvas, set())
        self.assertEqual(leaves, {phantom})

    def test_caller_callee_consumer_reconciles_an_inline_forwarder(self):
        from rom1.verify import caller_callee as cc
        caller = "?Ctor@COwner@@QAEXXZ"
        wrapper = "?ApplyName@CWapX@@QAEXPBD@Z"
        real = "?ApplyName@CWwdGameObjectA@@QAEXPBD@Z"
        ir = {caller: {wrapper}, wrapper: {real}, real: set()}
        rc = cc.Recon.__new__(cc.Recon)
        rc.m2rva = {caller: 0x1000, real: 0x150540}
        with mock.patch("rom1.tool.clang.compdb",
                        return_value={"/probe/src/Probe.cpp": []}), \
             mock.patch.object(cc, "_tu_edges",
                               return_value=("/probe/src/Probe.cpp", ir)):
            edges, defined, unresolved, failed = rc._base_graph(jobs=1)
        self.assertEqual(edges, {(0x1000, 0x150540)})
        self.assertEqual(defined, {0x1000, 0x150540})
        self.assertEqual(unresolved, {})
        self.assertEqual(failed, [])

    def test_assert_relocs_refuses_zero_audited_functions(self):
        from rom1.verify import assert_relocs as ar
        with mock.patch.object(ar, "audit", return_value=([], 0)):
            self.assertTrue(any("NOTHING was audited" in f
                                for f in ar.gate_findings()))
        with mock.patch.object(ar, "audit", return_value=([], 1200)):
            self.assertEqual(ar.gate_findings(), [])

    def test_data_relocs_refuses_zero_scanned_pairs(self):
        from collections import Counter

        from rom1.verify import data_relocs as dr
        with mock.patch.object(dr, "scan",
                               return_value=([], [], [], Counter(), {}, [])), \
             mock.patch.object(dr, "units_without_a_target", return_value=[]), \
             mock.patch.object(dr, "orphan_payloads", return_value=[]):
            self.assertTrue(any("0 base/target pairs" in f
                                for f in dr.gate_findings()))

    def test_alloc_size_refuses_an_empty_layout_harvest(self):
        from rom1.verify import alloc_size as az
        sw = mock.Mock()
        sw.rows.return_value = []
        with mock.patch.object(az, "Sweep", return_value=sw), \
             mock.patch.object(az, "computed_sizes", return_value=({}, set())), \
             mock.patch.object(az, "def_counts", return_value={}), \
             mock.patch.object(az, "classify_rows",
                               return_value=([], [], [], [], [], [])):
            self.assertTrue(any("0 class sizes" in f
                                for f in az.gate_findings()))
        with mock.patch.object(az, "Sweep", return_value=sw), \
             mock.patch.object(az, "computed_sizes",
                               return_value=({"CFoo": 8}, set())), \
             mock.patch.object(az, "def_counts", return_value={}), \
             mock.patch.object(az, "classify_rows",
                               return_value=([], [], [], [], [], [])):
            self.assertEqual(az.gate_findings(), [])

    def test_library_overlap_does_not_call_its_vacuity_guard_a_double_claim(self):
        import contextlib
        import io

        from rom1.verify import library_overlap as lo
        with mock.patch.object(lo, "findings",
                               return_value=(["parsed 0 src claims"], 0)):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(lo.main([]), 1)
        self.assertIn("0 src claims", err.getvalue())
        self.assertNotIn("double-claim(s). Each", err.getvalue())


class LibSymbolCacheControls(unittest.TestCase):
    """The toolchain .LIB symbol cache is keyed on the ARCHIVE SET.

    Measured 2026-08-16: an unkeyed cache written under toolchain r2 was
    still answering under r3 (46,866 live symbols vs 56,474 cached), so
    `verify link-tier` called 42 resolvable Win32 imports "a guaranteed
    unresolved external" while the candidate link reported ZERO unresolved.
    """

    def _archive(self, path: Path, names: list[str]) -> None:
        import struct as st
        body = st.pack(">I", len(names)) + b"\0" * (4 * len(names)) \
            + b"".join(n.encode() + b"\0" for n in names)
        head = b"/" + b" " * 15 + b"0" * 12 + b" " * 20 \
            + f"{len(body):<10d}".encode() + b"`\n"
        path.write_bytes(b"!<arch>\n" + head + body)

    def test_a_toolchain_change_invalidates_the_cache(self):
        from rom1.verify import undefined_closure as uc
        with tempfile.TemporaryDirectory() as td:
            r2, r3 = Path(td) / "r2/lib", Path(td) / "r3/lib"
            r2.mkdir(parents=True)
            r3.mkdir(parents=True)
            self._archive(r2 / "OLD.LIB", ["_OnlyInR2@4"])
            self._archive(r3 / "NEW.LIB", ["_OnlyInR3@4"])
            cache = Path(td) / "lib_symbols.txt"
            with mock.patch.object(uc, "LIB_CACHE", cache):
                with mock.patch.dict("os.environ",
                                     {"MSVC_DIR": str(r2.parent)},
                                     clear=False):
                    os.environ.pop("DXSDK_DIR", None)
                    first = uc.lib_symbols()
                self.assertIn("_OnlyInR2@4", first)
                with mock.patch.dict("os.environ",
                                     {"MSVC_DIR": str(r3.parent)},
                                     clear=False):
                    os.environ.pop("DXSDK_DIR", None)
                    second = uc.lib_symbols()
        self.assertIn("_OnlyInR3@4", second)
        self.assertNotIn("_OnlyInR2@4", second)   # the r2 answer is retired

    def test_an_unreachable_toolchain_keeps_the_last_answer(self):
        """Outside the dev shell $MSVC_DIR is unset; returning an empty set
        would make every consumer call the whole CRT unresolvable."""
        from rom1.verify import undefined_closure as uc
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td) / "lib_symbols.txt"
            cache.write_text("# libs deadbeef\n_CloseHandle@4\n")
            with mock.patch.object(uc, "LIB_CACHE", cache), \
                 mock.patch.object(uc, "_toolchain_libs", return_value=[]):
                self.assertEqual(uc.lib_symbols(), {"_CloseHandle@4"})


class LinkTierRunnabilityControls(unittest.TestCase):
    def test_a_missing_map_is_a_finding_not_a_silent_skip(self):
        """With no .map the image diff cannot run at all - and main()'s
        success line claims every exact body is byte-identical in the linked
        image, which would then be a claim about a check that never ran."""
        from rom1.verify import link_tier as lt
        with tempfile.TemporaryDirectory() as td:
            cand = Path(td) / "c.exe"
            cand.write_bytes(b"MZ")
            with mock.patch.object(lt, "CAND", cand), \
                 mock.patch.object(lt, "CMAP", Path(td) / "absent.map"):
                out = lt.image_diff_findings()
        self.assertTrue(out and "could not run" in out[0])

    def test_a_missing_retail_section_is_fatal_and_reloc_is_exempt(self):
        """The third link-tier check had no control at all."""
        from rom1.verify import link_tier as lt
        with tempfile.TemporaryDirectory() as td:
            cand = Path(td) / "c.exe"
            cand.write_bytes(b"MZ")
            with mock.patch.object(lt, "CAND", cand), \
                 mock.patch.object(lt, "census",
                                   return_value=[(".text", 0x1000, 0x1000),
                                                 (".rsrc", 0x2000, 0),
                                                 (".reloc", 0x400, 0)]):
                bad = lt.census_findings()
        self.assertEqual(len(bad), 1)
        self.assertIn(".rsrc", bad[0])       # .reloc is deliberately exempt

    def test_no_candidate_at_all_stays_one_finding(self):
        from rom1.verify import link_tier as lt
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(lt, "CAND", Path(td) / "none.exe"), \
                 mock.patch.object(lt, "CMAP", Path(td) / "none.map"):
                self.assertEqual(lt.image_diff_findings(), [])
                self.assertEqual(lt.census_findings(), [])


# --------------------------------------------------------------------------- #
# function source fingerprint name bridge                                     #
# --------------------------------------------------------------------------- #
class FingerprintNameControls(unittest.TestCase):
    def test_function_pointer_return_keeps_the_declared_method_name(self):
        from rom1.verify.fingerprints import _qualified_of
        demangled = ("public: void (__cdecl * __thiscall "
                     "CVariantSlot::Add(class zErrHandling *, "
                     "void (__cdecl *)(char *, int)))(char *, int)")
        self.assertEqual(_qualified_of(demangled), "CVariantSlot::Add")

    def test_ordinary_method_name_is_unchanged(self):
        from rom1.verify.fingerprints import _qualified_of
        self.assertEqual(
            _qualified_of("public: int __thiscall CFileIO::Open(char const *)"),
            "CFileIO::Open")


# --------------------------------------------------------------------------- #
# the MAX ledger: the bank rules themselves (the file is project state)       #
# --------------------------------------------------------------------------- #
class BankRatchetControls(unittest.TestCase):
    """bank_rows is what edits config/match_baseline.tsv. Every rule that
    protects a banked MAX gets a control here; nothing writes the ledger."""

    def _bank(self, cur, base, fps=None, rvas=None, library=()):
        from rom1.verify import verbs
        fps = fps or {}
        with mock.patch.object(verbs, "library_rvas", return_value=set(library)):
            return verbs.bank_rows(cur, base,
                                   lambda u, f: fps.get((u, f), "h1"),
                                   rvas or {})

    def _row(self, best=90.0, cur=90.0, fp="h1", addr=0x1000, hist=None,
             state="", tries=1):
        return {"best": best, "cur": cur, "tries": tries, "fp": fp,
                "addr": addr, "hist": best if hist is None else hist,
                "state": state}

    def test_a_dip_never_lowers_a_best_while_the_source_is_unchanged(self):
        key = ("u", "f")
        new, stats, reset, _drop = self._bank(
            {key: 70.0}, {key: self._row(best=90.0, cur=90.0)},
            rvas={key: 0x1000})
        self.assertEqual(new[key]["best"], 90.0)     # MAX held
        self.assertEqual(new[key]["cur"], 70.0)
        self.assertEqual(new[key]["hist"], 90.0)
        self.assertEqual(reset, [])

    def test_a_real_source_edit_resets_best_but_never_hist(self):
        key = ("u", "f")
        new, _s, reset, _d = self._bank(
            {key: 70.0}, {key: self._row(best=90.0, fp="old")},
            fps={key: "new"}, rvas={key: 0x1000})
        self.assertEqual(new[key]["best"], 70.0)
        self.assertEqual(new[key]["hist"], 90.0)     # the all-time peak holds
        self.assertEqual(len(reset), 1)

    def test_a_fallback_fingerprint_is_not_an_edit(self):
        from rom1.verify.fingerprints import FALLBACK
        key = ("u", "f")
        new, _s, reset, _d = self._bank(
            {key: 70.0}, {key: self._row(best=90.0, fp="real")},
            fps={key: FALLBACK + "abc"}, rvas={key: 0x1000})
        self.assertEqual(new[key]["best"], 90.0)
        self.assertEqual(new[key]["fp"], "real")     # the real hash is kept
        self.assertEqual(reset, [])

    def test_the_rva_moving_is_the_only_rva_keyed_reset(self):
        key = ("u", "f")
        new, stats, _r, _d = self._bank(
            {key: 55.0}, {key: self._row(best=90.0, addr=0x1000)},
            rvas={key: 0x2000})
        self.assertEqual(stats["rebounds"], 1)
        self.assertEqual(new[key]["best"], 55.0)     # a different BODY
        self.assertEqual(new[key]["hist"], 90.0)

    def test_a_unit_move_migrates_the_high_water_by_rva(self):
        old, new_key = ("olda", "f"), ("newb", "f")
        new, stats, _r, _d = self._bank(
            {new_key: 80.0}, {old: self._row(best=95.0, addr=0x1000)},
            rvas={new_key: 0x1000})
        self.assertEqual(stats["moved"], 1)
        self.assertEqual(new[new_key]["best"], 95.0)
        self.assertNotIn(old, new)

    def test_an_unscored_body_is_preserved_absent_and_round_trips(self):
        from rom1.verify import baseline as bl
        key = ("u", "f")
        new, stats, _r, dropped = self._bank(
            {}, {key: self._row(best=100.0, addr=0x1000)}, rvas={})
        self.assertEqual(stats["preserved_absent"], 1)
        self.assertEqual(new[key]["state"], "absent")
        self.assertEqual(new[key]["best"], 100.0)
        self.assertEqual(dropped, [])
        self.assertEqual(bl.load(bl.render(new)), new)     # survives the file

    def test_an_absent_row_is_dropped_once_its_rva_is_claimed_elsewhere(self):
        key, other = ("u", "f"), ("u", "g")
        new, stats, _r, dropped = self._bank(
            {other: 100.0}, {key: self._row(best=100.0, addr=0x1000)},
            rvas={other: 0x1000})
        # 0x1000 is now claimed under another name: keeping the row would pin
        # a phantom, and the high-water travelled with the body (moved).
        self.assertEqual(stats["moved"] + len(dropped), 1)
        self.assertNotIn("absent", {r.get("state") for r in new.values()})

    def test_banking_twice_changes_nothing(self):
        key = ("u", "f")
        base = {key: self._row(best=90.0, cur=90.0)}
        first, _s, _r, _d = self._bank({key: 95.0}, base, rvas={key: 0x1000})
        second, stats, _r, _d = self._bank({key: 95.0}, first,
                                           rvas={key: 0x1000})
        self.assertEqual(first, second)
        self.assertEqual(stats["raised"], 0)

    def test_the_ledger_round_trips_through_render_and_load(self):
        from rom1.verify import baseline as bl
        rows = {("u", "f"): self._row(best=99.1234, cur=98.7654, hist=100.0),
                ("u", "g"): self._row(best=100.0, cur=100.0, addr=None,
                                      state="absent")}
        self.assertEqual(bl.load(bl.render(rows)), rows)

    def test_render_keeps_the_explicit_state_field(self):
        from rom1.verify import baseline as bl
        rows = {("u", "scored"): self._row(),
                ("u", "gone"): self._row(state="absent")}
        function_lines = [line for line in bl.render(rows).splitlines()
                          if line.startswith("u\t") and line.count("\t") > 2]
        scored = next(line for line in function_lines if "\tscored\t" in line)
        absent = next(line for line in function_lines if "\tgone\t" in line)
        self.assertTrue(scored.endswith("\t"))
        self.assertTrue(absent.endswith("\tabsent"))


class BankPreconditionControls(unittest.TestCase):
    def test_an_unstaged_build_input_refuses_and_names_the_paths(self):
        from rom1.verify import verbs
        with mock.patch.object(verbs, "unstaged_bank_inputs",
                               return_value=["src/Allods/Grunt.cpp"]):
            with self.assertRaises(SystemExit) as e:
                verbs.require_bankable_tree("write the baseline")
        msg = str(e.exception)
        self.assertIn("src/Allods/Grunt.cpp", msg)
        self.assertIn("--dirty", msg)

    def test_dirty_warns_loudly_and_proceeds(self):
        import contextlib
        import io

        from rom1.verify import verbs
        with mock.patch.object(verbs, "unstaged_bank_inputs",
                               return_value=["include/Rom1/Grunt.h"]):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                verbs.require_bankable_tree("write the baseline",
                                            allow_dirty=True)
        self.assertIn("WARNING", err.getvalue())
        self.assertIn("include/Rom1/Grunt.h", err.getvalue())

    def test_a_clean_tree_is_silent(self):
        from rom1.verify import verbs
        with mock.patch.object(verbs, "unstaged_bank_inputs", return_value=[]):
            verbs.require_bankable_tree("write the baseline")

    def test_a_stale_report_is_called_out(self):
        import contextlib
        import io

        from rom1.verify import verbs
        with tempfile.TemporaryDirectory() as td:
            report = Path(td) / "report.json"
            report.write_text("{}")
            objs = Path(td) / "build/objdiff/base"
            objs.mkdir(parents=True)
            obj = objs / "a.obj"
            obj.write_bytes(b"x")
            os.utime(obj, (report.stat().st_mtime + 600,) * 2)
            with mock.patch.object(verbs, "REPO", Path(td)):
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    verbs._warn_stale_report(report)
        self.assertIn("STALE", err.getvalue())
        self.assertIn("rom1 build", err.getvalue())


# --------------------------------------------------------------------------- #
# the CONSUMER, not the recognizer: what the tier actually calls              #
# --------------------------------------------------------------------------- #
class GateConsumerControls(unittest.TestCase):
    """A recognizer control proves a helper; the tier calls the GATE. These
    drive the exact entry point tiers.TIERS holds."""

    def test_include_order_the_tier_calls_audit_not_parse(self):
        from rom1.verify import include_order as io
        from rom1.verify import tiers

        def with_file(text):
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                (root / "src").mkdir()
                p = root / "src/Probe.cpp"
                p.write_text(text)
                with mock.patch.object(io, "repo_files", return_value=[p]), \
                     mock.patch.object(io, "REPO", root):
                    return tiers._include_order()
        dirty = with_file("#include <rva.h>\n#include <Zed.h>\n"
                          "#include <Abc.h>\n#include <Zed.h>\n\nint x;\n")
        self.assertTrue(any("duplicate include" in f for f in dirty))
        clean = with_file("#include <rva.h>\n\n#include <Abc.h>\n"
                          "#include <Zed.h>\n\nint x;\n")
        self.assertEqual(clean, [])

    def test_caller_callee_fires_above_the_floor_and_is_silent_at_it(self):
        from rom1.verify import caller_callee as cc
        rc = mock.Mock()
        rc.tgt = {(1, 2)}
        rc.name = lambda r: "?F@@YAXXZ"
        rc.unit = lambda r: "u"
        miss = [(0x1000 + i, 0x2000, "FAKE-VIEW", "CView") for i in range(5)]
        summary = (rc, miss, {"FAKE-VIEW": 5})
        with mock.patch.object(cc, "_summary", return_value=summary), \
             mock.patch("rom1.verify.board.load_baseline",
                        return_value={"caller-callee FAKE-VIEW": 4}):
            over = cc.gate_findings()
        self.assertTrue(over and "exceeds the committed floor 4" in over[0])
        with mock.patch.object(cc, "_summary", return_value=summary), \
             mock.patch("rom1.verify.board.load_baseline",
                        return_value={"caller-callee FAKE-VIEW": 5}):
            self.assertEqual(cc.gate_findings(), [])

    def test_vtables_gate_renders_every_defect_class(self):
        from rom1.verify import vtables as vt
        wiring = [("WIRING", 0x100, "CFader", 3, 0x2000,
                   "?Gap_17f660@@YAXXZ", "u", "not a virtual")]
        with mock.patch.object(vt, "analyse",
                               return_value=([], [], [], wiring, [], 1, 1)):
            self.assertTrue(any("vtable-slot-binding [WIRING]" in f
                                for f in vt.gate_findings()))
        gaps = [(0x1234, 16, "rtti", "CGhost", 0)]
        with mock.patch.object(vt, "analyse",
                               return_value=(gaps, [], [], [], [], 1, 1)):
            self.assertTrue(any("vtable-coverage" in f
                                for f in vt.gate_findings()))
        virt = [("CShell", 0x300, 9, 2, "under-virtualized")]
        with mock.patch.object(vt, "analyse",
                               return_value=([], virt, [], [], [], 1, 1)):
            self.assertTrue(any("vtable-virtuality" in f
                                for f in vt.gate_findings()))
        with mock.patch.object(vt, "analyse",
                               return_value=([], [], [], [], [], 1, 1)):
            self.assertEqual(vt.gate_findings(), [])

    def test_alloc_size_catches_a_planted_sizeof_error_on_the_real_tree(self):
        """The whole-tree control: take a class whose retail `push <n>`
        immediate ALREADY agrees with clang's sizeof, shift the computed side
        by 4, and require the live gate to name it. A gate that is blind
        returns the same 0 rows as a clean tree."""
        from rom1.core.paths import BUILD
        from rom1.verify import alloc_size as az
        if not (BUILD / "gen/class_sizes.json").is_file():
            self.skipTest("class_sizes cache absent (unbuilt tree)")
        comp, conflicts = az.computed_sizes()
        if not comp:
            self.skipTest("libclang harvest empty")
        rows = az.Sweep().rows()
        _b, _s, _m, _u, _un, ok = az.classify_rows(rows, comp, conflicts,
                                                   az.def_counts())
        if not ok:
            self.skipTest("no agreeing class to poison on this tree state")
        victim = sorted(o[0] for o in ok)[0]
        poisoned = dict(comp)
        poisoned[victim] += 4
        with mock.patch.object(az, "computed_sizes",
                               return_value=(poisoned, conflicts)):
            out = az.gate_findings()
        self.assertTrue(any(victim in f for f in out),
                        f"a 4-byte sizeof error on {victim} was not caught")


class PipelineErrorControls(unittest.TestCase):
    """The pipeline verbs answer a broken environment with a MESSAGE.

    `rom1 delink` used to let the delinker's ToolError escape as a
    traceback, and the tool's own words name a symptom ("relocation alias
    owner is absent: _length_code$S") whose real cause is a stale
    vostok-delinker on $PATH.
    """

    def _delink(self, exc):
        import contextlib
        import io

        from rom1.delink import run as dr
        with mock.patch.object(dr, "run", side_effect=exc):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                rc = dr.main([])
        return rc, err.getvalue()

    def test_a_stale_delinker_is_named_not_just_echoed(self):
        from rom1.tool import ToolError
        rc, text = self._delink(ToolError(
            "vostok-delinker failed (rc=1):\nrelocation alias owner is "
            "absent: _length_code$S"))
        self.assertEqual(rc, 1)
        self.assertIn("_length_code$S", text)      # the tool's own words kept
        self.assertIn("STALE vostok-delinker", text)
        self.assertIn("which vostok-delinker", text)

    def test_a_missing_delinker_binary_is_a_message_not_a_traceback(self):
        rc, text = self._delink(
            FileNotFoundError(2, "No such file or directory",
                              "vostok-delinker"))
        self.assertEqual(rc, 1)
        self.assertIn("nix develop", text)

    def test_an_unhinted_failure_still_prints_the_tools_words(self):
        from rom1.tool import ToolError
        rc, text = self._delink(ToolError("vostok-delinker failed (rc=9)"))
        self.assertEqual(rc, 1)
        self.assertIn("rc=9", text)

    def test_rsrc_separates_could_not_run_from_a_real_deviation(self):
        """A missing era rc.exe is not a verdict on Allods.rc: reporting it as
        `check FAILED` reads as 'the resources diverge from retail'."""
        import contextlib
        import io

        from rom1.rsrc import check as rc_check
        from rom1.tool import ToolError
        with mock.patch.object(rc_check.rc_tool, "compile",
                               side_effect=ToolError("rc.exe not found")):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                code = rc_check.check()
        self.assertEqual(code, 2)                  # 2 = could not run
        self.assertIn("COULD NOT RUN", err.getvalue())
        self.assertIn("not a verdict", err.getvalue())
        with mock.patch.object(rc_check.rc_tool, "compile",
                               side_effect=PermissionError(13, "denied")):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                code = rc_check.check(out="/root/denied.res")
        self.assertEqual(code, 2)
        self.assertIn("--out", err.getvalue())

    def test_rsrc_rejects_an_unknown_subcommand_by_name(self):
        import contextlib
        import io

        from rom1 import rsrc
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(rsrc.main(["bogus"]), 2)
        self.assertIn("unknown subcommand 'bogus'", err.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(rsrc.main(["--help"]), 0)
        self.assertIn("rsrc check", out.getvalue())


class FloorAbsenceControls(unittest.TestCase):
    """A ratchet with no floor must FAIL, never pass.

    board and casts used to fail OPEN: deleting the two files in
    config/cleanliness/ made the whole fast tier permanently green, while
    caller-callee and undefined-closure already refused to pass vacuously.
    """

    def test_board_reports_a_ratcheted_metric_with_no_floor(self):
        from rom1.verify import board
        with mock.patch.object(board, "load_baseline", return_value={}):
            found = board.gate([("unexplained casts", 9999)])
        self.assertTrue(found, "a ratcheted metric with no floor passed")
        self.assertIn("no committed floor", found[0])

    def test_board_still_ratchets_when_the_floor_exists(self):
        from rom1.verify import board
        with mock.patch.object(board, "load_baseline",
                               return_value={"unexplained casts": 10}):
            self.assertTrue(board.gate([("unexplained casts", 11)]))
            self.assertEqual(board.gate([("unexplained casts", 10)]), [])

    def test_casts_reports_a_missing_floor(self):
        from rom1.verify import board, casts
        with mock.patch.object(board, "load_baseline", return_value={}), \
             mock.patch.object(casts, "self_recursion", return_value=[]), \
             mock.patch.object(casts, "scan_ledger", return_value=({}, {"a.cpp": [1]})):
            found = casts.gate_findings()
        self.assertTrue(found, "an absent cast floor passed the gate")
        self.assertIn("no committed floor", found[0])


class LinkClosureScanSetControls(unittest.TestCase):
    """The closure check must scan the link line we actually use.

    graph.link substitutes our synthesized import libs into LINK_LIBS, so
    mss32/smackw32 imports resolve at link time; scanning only the
    toolchain reported 26 of them as guaranteed-unresolved.
    """

    def test_synthesized_import_libs_are_in_the_scan_set(self):
        from rom1.graph import implib
        from rom1.verify import undefined_closure as uc
        made = [p for p in implib.on_disk() if p.is_file()]
        if not made:
            self.skipTest("no synthesized import libs on disk")
        scanned = set(uc._toolchain_libs())
        for p in made:
            self.assertIn(p, scanned, f"{p.name} is on the link line but unscanned")


class TsvAtomicWriteControls(unittest.TestCase):
    """A concurrent reader never sees a half-written table.

    Observed live: a gate crashed with `no header row` while a build edge
    rewrote build/gen/claims/grunt.tsv in place.
    """

    def test_write_replaces_atomically(self):
        import os
        from rom1.core import tsv
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "t.tsv"
            tsv.write(path, ["# b"], ["a", "b"], [["1", "2"]])
            before = path.read_text()
            seen = []
            real_replace = os.replace

            def spy(src, dst):
                # the destination must still hold the OLD table right up to
                # the instant of replacement - never a truncated one
                seen.append(Path(dst).read_text())
                return real_replace(src, dst)

            with mock.patch("os.replace", spy):
                tsv.write(path, ["# b"], ["a", "b"], [["3", "4"]])
            self.assertEqual(seen, [before])
            self.assertIn("3\t4", path.read_text())

    def test_no_temp_file_survives(self):
        from rom1.core import tsv
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "t.tsv"
            tsv.write(path, ["# b"], ["a"], [["1"]])
            self.assertEqual([p.name for p in Path(d).iterdir()], ["t.tsv"])


class SourceNameRewriteControls(unittest.TestCase):
    """The rewrite rules are COMPLETE, proven once per build over the corpus.

    Labelling spells every claim from source (core.msvc_names), so a rule gap
    can no longer hide as a silent per-claim drop - it has to fail here. The
    control is the same assertion the dropped per-claim authority check made,
    lifted to the whole claim set: for EVERY extracted source claim, the name
    equals the emitting base object's own symbol modulo the volatile ordinals
    both sides mask. Reading the objects is fine HERE; it is a test, not the
    extraction path.
    """

    @staticmethod
    def _corpus():
        from rom1.core.paths import BUILD
        from rom1.retail_labels import fragments
        base = BUILD / "objdiff/base"
        claims = [c for c in fragments.all_claims() if c.channel == "src"]
        return base, claims

    #: every decoration cl 5.0 could have chosen instead - if one of THESE is
    #: in the object, the claim named the right body and spelled it wrong.
    @staticmethod
    def _alternate_spellings(name: str) -> set[str]:
        import re
        out = set()
        for n in {name, re.sub(r"@@([0-9])P", r"@@\1Q", name)}:
            for m in {n, n.removesuffix("$S"), n + "$S"}:
                out |= {m, "_" + m, m.removeprefix("_")}
        return out - {name}

    def test_every_source_claim_is_cls_own_spelling(self):
        from rom1.core.coff import Coff
        from rom1.core.msvc_names import mask
        from rom1.model import unmaterialized
        base, claims = self._corpus()
        if not claims:
            self.skipTest("no extracted claims - run `rom1 labels --all`")
        objs: dict[str, tuple[set[str], set[str]] | None] = {}
        for unit in {c.unit for c in claims}:
            path = base / f"{unit}.obj"
            if not path.is_file():
                objs[unit] = None
                continue
            coff = Coff(path)
            objs[unit] = ({mask(n) for n in coff.code_names()},
                          {mask(n) for n in coff.all_names()})
        absent = sorted(u for u, v in objs.items() if v is None)
        if absent:
            self.skipTest(f"{len(absent)} unit(s) have no base obj "
                          f"(e.g. {absent[0]}) - run `rom1 build`")
        # A header inline's macro reaches every including TU, but cl
        # materializes the COMDAT only where it is odr-used - so a claim with
        # no symbol in ITS OWN unit is expected. The rewrite is in question
        # only when NO unit claiming that (kind, rva, name) carries it.
        claimed, proven = {}, set()
        for c in claims:
            code, every = objs[c.unit]
            key = (c.kind, c.rva, mask(c.name))
            claimed.setdefault(key, []).append(c)
            if key[2] in (code if c.kind == "func" else every):
                proven.add(key)
        # ... and a gap is a SPELLING defect only if some other decoration of
        # the same claim IS in one of those objects. A gap with no spelling at
        # all is a missing body - a modelling question the Model reports.
        misspelled, bodiless = [], []
        for key in sorted(set(claimed) - proven):
            cs = claimed[key]
            alts = self._alternate_spellings(cs[0].name)
            hit = next((a for c in cs for a in sorted(alts)
                        if a in objs[c.unit][1]), None)
            row = f"{key[0]} 0x{key[1]:06x} {cs[0].name}"
            (misspelled if hit else bodiless).append(
                f"{row} -> cl spells it {hit}" if hit else row)
        self.assertFalse(
            misspelled,
            f"{len(misspelled)} of {len(claimed)} source claim(s) are spelled "
            f"differently by cl - the rewrite rules are incomplete "
            f"(first: {misspelled[0] if misspelled else ''})")
        # the bodiless class must stay LOUD somewhere: a claim with no other
        # spelling at its rva is a Model violation, one WITH another spelling
        # is recorded as that binding's alias. Nothing may be silent.
        gaps = {(c.kind, c.rva, mask(c.name)) for c in unmaterialized(
            [c for cs in claimed.values() for c in cs])}
        aliased = {rva for kind, rva, _n in proven if kind == "func"}
        unreported = sorted(
            k for k in set(claimed) - proven - gaps
            if k[0] == "func" and k[1] not in aliased)
        self.assertFalse(
            unreported,
            f"{len(unreported)} claim(s) match no object symbol and are "
            f"reported by nothing (first: {unreported[0] if unreported else ''})")

    def test_a_missing_rewrite_rule_fails_that_control(self):
        """The negative control: misspell every claim, so the control fails.

        A gate that would pass an incomplete rewrite is not a gate."""
        import io
        from rom1.retail_labels import fragments

        _base, claims = self._corpus()
        if not claims:
            self.skipTest("no extracted claims - run `rom1 labels --all`")

        def poisoned():
            out = []
            for c in claims:
                # A leading underscore is among _alternate_spellings, so the
                # object's real spelling is guaranteed to be observed as the
                # alternative even in a very small bootstrap corpus.
                name = c.name[1:] if c.name.startswith("_") else "_" + c.name
                out.append(c._replace(name=name))
            return out

        with mock.patch.object(fragments, "all_claims", poisoned):
            case = SourceNameRewriteControls(
                "test_every_source_claim_is_cls_own_spelling")
            result = unittest.TextTestRunner(stream=io.StringIO()).run(
                unittest.TestSuite([case]))
        self.assertEqual(len(result.failures), 1,
                         "a broken rewrite rule did not fail the corpus control")
        self.assertIn("rewrite rules are incomplete", result.failures[0][1])

    def test_masking_never_merges_two_object_symbols(self):
        """The mask is only sound while it is injective per object."""
        from rom1.core.coff import Coff
        from rom1.core.msvc_names import mask
        base, _claims = self._corpus()
        objs = sorted(base.glob("*.obj"))
        if not objs:
            self.skipTest("no base objs")
        collisions = []
        for path in objs:
            try:
                names = Coff(path).all_names()
            except ValueError:
                continue
            seen: dict[str, str] = {}
            for name in sorted(names):
                other = seen.setdefault(mask(name), name)
                if other != name:
                    collisions.append(f"{path.stem}: {other} / {name}")
        self.assertFalse(collisions,
                         f"{len(collisions)} object symbol pair(s) mask "
                         f"together (first: {collisions[0] if collisions else ''})")

    def test_the_rewrite_rules_are_the_measured_ones(self):
        from rom1.core import msvc_names as m
        # the i386 COFF global prefix, applied to what LLVM did not mangle
        self.assertEqual(m.func("?Foo@C@@QAEXXZ"), "?Foo@C@@QAEXXZ")
        self.assertEqual(m.func("_stdcall_thing@8", decorated=True),
                         "_stdcall_thing@8")
        self.assertEqual(m.func("ordinary"), "_ordinary")
        # clang's array storage class
        self.assertEqual(m.data("?g_cmdBitTable@@3QBGB", internal=False),
                         "?g_cmdBitTable@@3PBGB")
        # TU-local storage: `_` and `$S` arrive together, whatever the mangling
        self.assertEqual(m.data("s_MAIN", internal=True), "_s_MAIN$S")
        self.assertEqual(m.data("_kDegToRad", internal=True, decorated=True),
                         "_kDegToRad$S")
        self.assertEqual(m.data("?s_x@?1??F@@QAEHXZ@4HA", internal=True),
                         "_?s_x@?1??F@@QAEHXZ@4HA$S")
        # the mask meets cl's own object on both ordinals
        self.assertEqual(m.mask("_?s_x@?BA@??F@@QAEHXZ@4HA$S35536"),
                         "_?s_x@?1??F@@QAEHXZ@4HA$S")
        self.assertEqual(m.mask("_?$S47@?1??G@@QAEHXZ@4EA$S20267"),
                         "_?$S@?1??G@@QAEHXZ@4EA$S")
        # an rva-keyed name is NOT an ordinal: it must survive masking
        self.assertEqual(m.mask("$S2277272"), "$S2277272")
        self.assertEqual(m.mask(m.discriminate("_s_x$S", 0x244970)), "_s_x$S")


class ReadmeFreshnessControls(unittest.TestCase):
    """README's derived block must not be able to go stale.

    It is a pure function of the current report + the banked ledger, but it
    used to move only at `bank` (a deliberate manual act), so ordinary builds
    left it describing an older tree and readers quoted numbers that were no
    longer true - three times in one session. `check` runs on every build and
    now re-renders it write-if-changed; the ledger stays manual.
    """

    def test_check_rewrites_a_stale_block(self):
        from rom1.verify import readme as rm, verbs
        if not rm.README.is_file():
            self.skipTest("no README")
        before = rm.README.read_text()
        # Anchor on a token the block ALWAYS carries. The original anchor was
        # the `(unmatched)` row, which stopped existing the day the last
        # unclaimed reconstruction target got modelled - a freshness control
        # must not assert a row that only appears while work is outstanding.
        anchor = "Overall (vs full engine)"
        self.assertIn(anchor, before, "the block lost its headline line")
        try:
            with tempfile.TemporaryDirectory() as td:
                report = Path(td) / "report.json"
                report.write_text('{"units":[],"measures":{}}')
                rm.README.write_text(before.replace(anchor, anchor + "-STALE", 1))
                verbs.refresh_readme_block(report)
                fresh = rm.README.read_text()
                self.assertIn(anchor, fresh)
                self.assertNotIn(anchor + "-STALE", fresh)  # stale text is GONE
        finally:
            rm.README.write_text(before)

    def test_refresh_is_idempotent(self):
        from rom1.verify import readme as rm, verbs
        if not rm.README.is_file():
            self.skipTest("no README")
        before = rm.README.read_text()
        try:
            with tempfile.TemporaryDirectory() as td:
                report = Path(td) / "report.json"
                report.write_text('{"units":[],"measures":{}}')
                verbs.refresh_readme_block(report)
                self.assertFalse(verbs.refresh_readme_block(report),
                                 "a second refresh reported a change")
        finally:
            rm.README.write_text(before)

    def test_readme_is_not_a_bank_input(self):
        # writing it must never be able to block `bank`
        from rom1.verify.verbs import BANK_INPUT_PATHS
        self.assertNotIn("README.md", BANK_INPUT_PATHS)


# --------------------------------------------------------------------------- #
# the build loop (2026-08-16 review)                                          #
# --------------------------------------------------------------------------- #
def _coff(nsec: int = 0, symptr: int = 0, nsym: int = 0, machine: int = 0x14C,
          sections: list[tuple[int, int]] = (), tail: bytes = b"") -> bytes:
    """A hand-built COFF header (+ `sections` as (size, ptr) pairs)."""
    import struct
    out = bytearray(struct.pack("<HHIIIHH", machine, nsec, 0, symptr, nsym, 0, 0))
    for size, ptr in sections:
        raw = bytearray(40)
        struct.pack_into("<II", raw, 16, size, ptr)
        out += raw
    return bytes(out) + tail


class ClEdgeObjectIntegrityControls(unittest.TestCase):
    """The `cl` edge published an incomplete object and called the edge built.

    Two `rom1 build` runs in one tree are not serialised by anything, and
    the driver staged every unit at the SAME `.tmp/<unit>.obj` and installed
    through the same `<unit>.obj.install`. Measured 3/3: one run's cl deleted
    the other's staged object between its `compile()` and its `install()` ("cl
    produced no object (rc=0)", with an EMPTY diagnostic - the compiler blamed
    for a collision) and the shared `.install` rename raised FileNotFoundError
    as a traceback. The shared temp also makes `os.replace` non-atomic across
    processes, and a real build did fail in rom1.compare.normalize with
    "COFF string table is not final" over an object that a census then found
    invalid. Nothing checked the payload before installing it either.
    """

    def test_a_truncated_object_is_refused_not_installed(self):
        from rom1.graph import cc
        from rom1.tool import ToolError
        # one section header promising 0x1000 bytes at 0x40 in a 60-byte file
        torn = _coff(nsec=1, sections=[(0x1000, 0x40)])
        self.assertIsNotNone(cc.coff_defect(torn))
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "unit.obj"
            with self.assertRaises(ToolError):
                cc.install(torn, out)
            self.assertFalse(out.exists(), "a torn object was installed anyway")

    def test_a_truncated_string_table_is_refused(self):
        from rom1.graph import cc
        import struct
        # symbol table present, string-table length dword promises past EOF
        body = _coff(nsec=0, symptr=20, nsym=1,
                     tail=b"\0" * 18 + struct.pack("<I", 0x1000))
        self.assertIn("string table", cc.coff_defect(body) or "")

    def test_a_complete_object_passes(self):
        from rom1.graph import cc
        self.assertIsNone(cc.coff_defect(_coff()))
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "unit.obj"
            self.assertTrue(cc.install(_coff(), out))
            self.assertFalse(cc.install(_coff(), out), "rewrote unchanged bytes")
            self.assertEqual(list(Path(td).iterdir()), [out])   # no temp left

    def test_install_does_not_use_the_shared_temp_name(self):
        """A sibling build holding `<unit>.obj.install` must not break us."""
        from rom1.graph import cc
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "unit.obj"
            (Path(td) / "unit.obj.install").mkdir()       # the old, shared name
            self.assertTrue(cc.install(_coff(), out))
            self.assertTrue(out.is_file())

    def test_the_staging_path_is_per_process(self):
        from rom1.graph import cc
        seen = {}

        def fake(src, staged, flags):
            seen["staged"] = Path(staged)
            Path(staged).write_bytes(_coff())
            return ""

        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "u.c"
            src.write_text("int main(void){return 0;}\n")
            with mock.patch("rom1.tool.cl.compile", fake):
                cc.compile_unit(src, Path(td) / "base" / "u.obj", [])
        parts = seen["staged"].parts
        self.assertIn(str(os.getpid()), parts, f"shared staging dir: {parts}")
        self.assertIn(".tmp", parts)

    def test_an_unwritable_object_tree_is_a_message(self):
        import contextlib
        import io
        from rom1.graph import cc
        with tempfile.TemporaryDirectory() as td:
            ro = Path(td) / "ro"
            ro.mkdir()
            ro.chmod(0o500)
            try:
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    rc = cc.main(["--out", str(ro / "u.obj"), "--src", str(ro),
                                  "--unit", "u", "--", "/c"])
            finally:
                ro.chmod(0o700)
        self.assertEqual(rc, 1)          # a message + rc 1, never a traceback
        self.assertIn("cannot write", err.getvalue())


class ToolDriverEnvironmentControls(unittest.TestCase):
    """Outside `nix develop` the drivers raised bare Python exceptions.

    `$MSVC_DIR` unset reached the user as a RuntimeError traceback from
    rom1.core.paths (no tool main() catches it), and an absent
    wine/winepath/llvm-pdbutil/vostok-delinker as a FileNotFoundError out of
    subprocess - including from `rom1 tool wine --verify`, whose whole job
    is to answer "is wine set up?".
    """

    def _no_path(self):
        return mock.patch("shutil.which", lambda _p: None)

    def test_clang_ir_accepts_vc5_unsigned_long_case_label(self):
        """Exercise the extraction parser, not merely the flag list.

        VC5 accepts DirectX SDK constants such as 0x80040200L in a signed-int
        switch. Clang treats that conversion as a hard C++11 narrowing error
        unless the shared compatibility flag reaches emit_ir().
        """
        from rom1.tool import clang

        if not shutil.which(os.environ.get("ROM1_CLANG") or "clang"):
            self.skipTest("clang unavailable")
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "case_probe.cpp"
            src.write_text(
                "int probe(int value) {\n"
                "    switch (value) { case 0x80040200L: return 1; }\n"
                "    return 0;\n"
                "}\n"
            )
            ir = clang.emit_ir(str(src), clang.MS_FLAGS)
        self.assertIsNotNone(ir)
        self.assertIn("probe", ir)

    def test_missing_msvc_dir_is_a_toolerror(self):
        from rom1.tool import ToolError, wine
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MSVC_DIR", None)
            with self.assertRaises(ToolError) as cm:
                wine.era_tool("cl.exe")
        self.assertIn("MSVC_DIR", str(cm.exception))

    def test_the_rc_release_hint_is_only_on_rc(self):
        from rom1.tool import ToolError, wine
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(wine, "toolchain_root", lambda: Path(td)):
                with self.assertRaises(ToolError) as rc_exc:
                    wine.era_tool("rc.exe")
                with self.assertRaises(ToolError) as cl_exc:
                    wine.era_tool("cl.exe")
        self.assertIn("r3", str(rc_exc.exception))
        self.assertNotIn("rc.exe", str(cl_exc.exception))

    def test_absent_wine_is_named_not_a_traceback(self):
        from rom1.tool import ToolError, wine
        with self._no_path():
            for call in (lambda: wine.winepath("/tmp"),
                         lambda: wine.require("wine")):
                with self.assertRaises(ToolError) as cm:
                    call()
                self.assertIn("nix develop", str(cm.exception))

    def test_wine_verify_without_wine_returns_a_message(self):
        import contextlib
        import io
        from rom1.tool import wine
        with self._no_path(), mock.patch.object(sys, "argv",
                                                ["rom1 tool wine", "--verify"]):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                rc = wine.main()
        self.assertEqual(rc, 1)
        self.assertIn("not found on PATH", err.getvalue())

    def test_wine_with_no_action_is_not_a_silent_success(self):
        import contextlib
        import io
        from rom1.tool import wine
        for argv in (["rom1 tool wine"], ["rom1 tool wine", "--force"]):
            with mock.patch.object(sys, "argv", argv):
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    rc = wine.main()
            self.assertEqual(rc, 2, argv)
            self.assertIn("--init", err.getvalue())

    def test_absent_native_tools_are_named(self):
        from rom1.tool import ToolError, delinker, pdbutil
        with self._no_path():
            with self.assertRaises(ToolError) as cm:
                delinker.delink("a.pdb", "b.exe", "/tmp/out")
            self.assertIn("vostok-delinker", str(cm.exception))
            with self.assertRaises(ToolError) as cm:
                pdbutil.dump("a.pdb")
            self.assertIn("llvm-pdbutil", str(cm.exception))

    def test_a_stalled_native_tool_is_a_message(self):
        import subprocess
        from rom1.tool import ToolError, pdbutil
        with mock.patch("shutil.which", lambda p: "/bin/" + p), \
                mock.patch("subprocess.run",
                           side_effect=subprocess.TimeoutExpired("x", 1)):
            with self.assertRaises(ToolError) as cm:
                pdbutil.dump("a.pdb")
        self.assertIn("did not finish", str(cm.exception))

    def test_implib_without_the_retail_image_is_a_message(self):
        import contextlib
        import io
        from rom1.graph import implib
        with mock.patch.object(sys, "argv", ["implib", "--list"]), \
                mock.patch.object(implib, "import_table",
                                  side_effect=FileNotFoundError(
                                      2, "No such file or directory",
                                      "ALLODS.EXE")):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                rc = implib.main()
        self.assertEqual(rc, 1)
        self.assertIn("retail image", err.getvalue())


class LabelGraphDependencyControls(unittest.TestCase):
    def test_a_header_is_an_input_of_both_compile_and_label_edges(self):
        """An inline RVA name can change while its TU emits no changed bytes.

        The cl edge then restats its object, so only a direct header dependency
        can make the label extractor refresh the retail claim.
        """
        from rom1.graph import emit

        class OneHeader:
            def headers(self, _source):
                return ["include/Test/InlineClaim.h"]

            def scanned(self):
                return {"src/Test/Owner.cpp", "include/Test/InlineClaim.h"}

        unit = {"unit": "owner", "source": "src/Test/Owner.cpp",
                "flags": "retail", "cflags": ["/nologo", "/c"]}
        manifest = {"flags": {"retail": ["/nologo", "/c"]}}
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(emit, "load_units",
                                  return_value=(manifest, [unit])), \
                mock.patch.object(emit, "prune_orphan_artifacts",
                                  return_value=0), \
                mock.patch.object(emit, "write_toolchain_id",
                                  return_value=False), \
                mock.patch.object(emit, "Scanner", return_value=OneHeader()), \
                mock.patch.object(emit, "era_rc_available", return_value=False), \
                mock.patch.object(emit, "retail_exe", return_value=Path(
                                  "/nix/store/probe-ALLODS.EXE")):
            out = Path(td) / "build.ninja"
            emit.emit(out)
            graph_text = out.read_text()

        def edge(prefix):
            start = graph_text.index(prefix)
            end = graph_text.index("\n\n", start)
            return graph_text[start:end]

        compile_edge = edge("build build/objdiff/base/owner.obj: cl")
        label_edge = edge("build build/gen/claims/owner.tsv: labels")
        delink_edge = edge("build build/objdiff/.delink.stamp: delink")
        self.assertIn("include/Test/InlineClaim.h", compile_edge)
        self.assertIn("include/Test/InlineClaim.h", label_edge)
        self.assertIn("/nix/store/probe-ALLODS.EXE", delink_edge)
        self.assertNotIn("build/exe/ALLODS.EXE", delink_edge)


class LinkVerbTargetControls(unittest.TestCase):
    """`rom1 link <anything>` died on `unknown target build/gen/allods.res`.

    The `.res` edge exists only when the toolchain carried rc.exe at CONFIGURE
    time; the verb asked ninja for it unconditionally, so on a pre-r3 pin every
    flagged form - `--help` included - failed before reaching the parser, and
    `--help` also ran a full build first.
    """

    def test_manifest_targets_reads_the_emitted_edges(self):
        from rom1.graph import verbs
        with tempfile.TemporaryDirectory() as td:
            man = Path(td) / "build.ninja"
            man.write_text("rule cl\n  command = x\n"
                           "build a/b.obj: cl src.c | dep.h\n"
                           "build one two: phony $\n    three\n")
            with mock.patch.object(verbs.graph, "NINJA", str(man)), \
                    mock.patch.object(verbs, "REPO", Path("/")):
                got = verbs.manifest_targets()
        self.assertEqual(got, {"a/b.obj", "one", "two"})
        self.assertNotIn("build/gen/allods.res", got)

    def test_a_missing_manifest_is_an_empty_set_not_a_traceback(self):
        from rom1.graph import verbs
        with mock.patch.object(verbs.graph, "NINJA", "no/such/build.ninja"):
            self.assertEqual(verbs.manifest_targets(), set())

    def test_help_answers_the_parser_without_building(self):
        import contextlib
        import io
        from rom1.graph import verbs
        with mock.patch.object(verbs, "ninja",
                               side_effect=AssertionError("built for --help")), \
                mock.patch.object(verbs, "configure_if_needed",
                                  side_effect=AssertionError("configured")):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                with self.assertRaises(SystemExit) as cm:
                    verbs.link_main(["--help"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("--engine-lib", out.getvalue())

    def test_the_res_target_is_only_requested_when_it_exists(self):
        import contextlib
        import io
        from rom1 import graph
        from rom1.graph import verbs
        asked = []
        with mock.patch.object(verbs, "compiler_ready", return_value=True), \
                mock.patch.object(verbs, "configure_if_needed", lambda *a, **k: None), \
                mock.patch.object(verbs, "ninja",
                                  lambda t, **k: asked.append(list(t)) or 1):
            with mock.patch.object(verbs, "manifest_targets", lambda: {"base"}):
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    verbs.link_main(["--dry-run"])
            self.assertEqual(asked[-1], ["base"])
            self.assertIn("no build/gen/allods.res edge", err.getvalue())
            with mock.patch.object(verbs, "manifest_targets",
                                   lambda: {"base", graph.RESOURCE_RES}):
                verbs.link_main(["--dry-run"])
            self.assertEqual(asked[-1], ["base", graph.RESOURCE_RES])

    def test_a_resourceless_candidate_says_so(self):
        """A candidate with no .rsrc has no MFC dialogs; the only note used to
        live in a generated manifest comment nobody reads."""
        import contextlib
        import io
        from rom1.graph import implib, link as gl
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "cand.EXE"
            obj = Path(td) / "u.obj"
            obj.write_bytes(_coff())

            def fake_link(args, **kw):
                out.write_bytes(b"MZ")
                out.with_suffix(".map").write_text("")
                return ""

            with mock.patch.object(gl, "winepath", str), \
                    mock.patch.object(implib, "ensure_all", lambda *a, **k: []), \
                    mock.patch("rom1.tool.link.link", fake_link):
                with contextlib.redirect_stdout(io.StringIO()) as sout:
                    gl.candidate(out, Path(td), explicit=[str(obj)])
        self.assertIn("NO .rsrc", sout.getvalue())


class ImplibScaffoldControls(unittest.TestCase):
    """The synthesis cleaned up `<stem>.exp`, a name link.exe never writes.

    The .exp is named after the /IMPLIB path, and synthesis links through
    `<stem>.lib.tmp`, so the real leftovers were `mss32.lib.exp` and
    `smackw32.lib.exp` - both still sitting in build/lib/ weeks later.
    """

    def test_the_cleanup_names_the_exp_link_actually_writes(self):
        import inspect
        from rom1.graph import implib
        src = inspect.getsource(implib.synthesize)
        self.assertIn('tmp_lib.with_suffix(".exp")', src)

    def test_the_temp_lib_derives_the_observed_exp_name(self):
        from rom1.graph import implib
        lib = Path(implib.OUT_DIR) / "mss32.lib"
        tmp_lib = lib.with_suffix(".lib.tmp")
        self.assertEqual(tmp_lib.with_suffix(".exp").name, "mss32.lib.exp")


class ConfigureWriteControls(unittest.TestCase):
    """`rom1 configure --out <unwritable>` raised FileNotFoundError from the
    manifest mkdir instead of naming the path it could not write."""

    def test_an_unwritable_manifest_path_is_a_message(self):
        import contextlib
        import io
        from rom1.graph import emit
        with contextlib.redirect_stderr(io.StringIO()) as err:
            rc = emit.main(["--out", "/proc/no/such/dir/build.ninja"])
        self.assertEqual(rc, 1)
        self.assertIn("cannot write", err.getvalue())

    def test_empty_manifest_requires_explicit_bootstrap_state(self):
        from rom1.graph import emit
        profiles = {"flags": {"cpp": ["/nologo", "/c"]}}
        with mock.patch("rom1.manifest.load", return_value=profiles):
            with self.assertRaises(SystemExit):
                emit.load_units()
        profiles["build"] = {"bootstrap": True}
        with mock.patch("rom1.manifest.load", return_value=profiles):
            _manifest, units = emit.load_units()
        self.assertEqual(units, [])

    def test_bootstrap_state_must_be_removed_for_the_first_unit(self):
        from rom1.graph import emit
        manifest = {
            "build": {"bootstrap": True},
            "flags": {"cpp": ["/nologo", "/c"]},
            "unit": [{"unit": "first", "source": "src/First.cpp",
                      "flags": "cpp"}],
        }
        with mock.patch("rom1.manifest.load", return_value=manifest):
            with self.assertRaises(SystemExit):
                emit.load_units()


class CompdbStalenessControls(unittest.TestCase):
    """`--check` answered "coverage: 300/300" for a database whose toolchain
    include dirs no longer exist. A toolchain re-pin moves $MSVC_DIR and no
    ninja edge can see it, so the stored /nix/store path outlives its store
    entry; every clang consumer then silently loses its headers."""

    def test_a_dead_include_dir_is_reported(self):
        from rom1.graph import compdb
        db = {"/x/a.cpp": ["/imsvc", "/nix/store/gone-toolchain/msvc/include",
                           "/I", "/nix/store/gone-toolchain/dx/Include"]}
        self.assertEqual(
            compdb.dead_include_dirs(db),
            ["/nix/store/gone-toolchain/dx/Include",
             "/nix/store/gone-toolchain/msvc/include"])

    def test_live_dirs_are_not_reported(self):
        from rom1.graph import compdb
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(compdb.dead_include_dirs({"x": ["/imsvc", td]}), [])

    def test_a_flag_without_its_operand_is_not_a_crash(self):
        from rom1.graph import compdb
        self.assertEqual(compdb.dead_include_dirs({"x": ["/imsvc"]}), [])


class DecodeNormalizationControls(unittest.TestCase):
    """`semdiff._decode` is the substrate under every paired sieve, and it owns
    the two normalizations none of them can do afterwards: the function's own
    jump/index TABLE is data, and a relocation naming the function ITSELF on a
    real instruction is a self-transfer the delinked side does not relocate at
    all.  The second one was found by the exact-row reflexivity control, where
    two byte-identical recursive functions read as a `selection` residual."""

    #: `call rel32` (self-relocated at +1), `ret`, two `nop`, then two
    #: self-relocated dwords - a jump table objdump decodes as instructions
    BODY = bytes([0xe8, 0, 0, 0, 0, 0xc3, 0x90, 0x90,
                  0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88])
    REL = {1: ("Self", 0), 8: ("Self", 0), 12: ("Self", 0)}

    def test_without_the_name_the_table_decodes_as_three_instructions(self):
        """The negative control: one of them is a `ja`, which is exactly the
        phantom condition code `walls jccscan` counts."""
        from rom1.walls.semdiff import _decode
        lines = _decode(self.BODY, self.REL)
        self.assertEqual([x.addr for x in lines], [0, 5, 6, 7, 8, 0xa, 0xe])
        self.assertTrue(any(x.asm.startswith("ja ") for x in lines))
        self.assertEqual(lines[0].ref, "Self")

    def test_the_table_is_dropped_and_the_self_call_keeps_its_instruction(self):
        from rom1.walls.semdiff import _decode
        lines = _decode(self.BODY, self.REL, "Self")
        self.assertEqual([x.addr for x in lines], [0, 5, 6, 7])
        self.assertTrue(lines[0].asm.startswith("call "))
        # the referent means "here" and only our own object spells it
        self.assertIsNone(lines[0].ref)


class SemDiffControls(unittest.TestCase):
    """`walls semdiff` screens a pair at OPERAND level, so its filters ARE the
    tool: a filter that stops working turns every scheduling artifact into a
    reported bug and the sweep becomes unreadable.  A screen nobody has seen
    both PASS a known-equal pair and FLAG a real swap is not a screen."""

    @staticmethod
    def _lines(asms, ref=None):
        from rom1.walls.semdiff import Line
        return [Line(i * 4, a, ref) for i, a in enumerate(asms)]

    def test_a_known_equal_pair_screens_clean(self):
        """Register mirror, frame size, cross-jump duplication and a byte-
        continuation line - four observed false-positive classes at once."""
        from rom1.walls.semdiff import exclusive, features
        base = self._lines([
            "sub esp,0xc", "mov eax,DWORD PTR [esi+0x1ec]",
            "and ecx,0xffffffe0", "mov DWORD PTR [esi+0x2f0],eax",
            "call 0x1234", "ret 0x10",
        ])
        target = self._lines([
            "sub esp,0x10", "mov edx,DWORD PTR [esi+0x1ec]",
            "and al,0xffffffe0", "mov DWORD PTR [esi+0x2f0],edx",
            "call 0x1234", "83 c4 10", "call 0x1234", "ret 0x10",
        ])
        fb, ft = features(base), features(target)
        self.assertEqual(exclusive(fb, ft), [])          # nothing reported
        self.assertEqual(fb["disp"]["+0x1ec"], ft["disp"]["+0x1ec"])

    def test_a_swapped_member_is_flagged(self):
        from rom1.walls.semdiff import exclusive, features
        base = self._lines(["mov eax,DWORD PTR [esi+0x1f0]"])
        target = self._lines(["mov eax,DWORD PTR [esi+0x1ec]"])
        keys = {(k, key) for k, key, _u, _v in exclusive(features(base),
                                                         features(target))}
        self.assertIn(("disp", "+0x1f0"), keys)
        self.assertIn(("disp", "+0x1ec"), keys)

    def test_a_dropped_conversion_is_flagged(self):
        """cl never adds or drops an fild to schedule - the projectile
        spawn-coordinate bug was exactly this delta."""
        from rom1.walls.semdiff import features
        fb = features(self._lines(["fld QWORD PTR [esi+0x8]"]))
        ft = features(self._lines(["fild DWORD PTR [esi+0x5c]",
                                   "fld QWORD PTR [esi+0x8]"]))
        self.assertEqual(fb["fp"]["fild"], 0)
        self.assertEqual(ft["fp"]["fild"], 1)

    def test_a_jump_table_never_reaches_the_multisets(self):
        """A function's own index table decodes as junk with huge
        displacements; counting it swamps every real key."""
        from rom1.walls.semdiff import features
        me = "?Fn@C@@QAEHXZ"
        junk = self._lines(["mov cl,BYTE PTR [eax+0xd1c]",
                            "add BYTE PTR [edx-0x70ffffff],bl"], ref=me)
        self.assertEqual(sum(features(junk, me)["disp"].values()), 0)
        self.assertEqual(sum(features(junk, "?Other@@QAEXXZ")["disp"].values()),
                         2)

    def test_the_referent_sequence_sees_a_masked_swap(self):
        """Relocated operands are masked in the scored bytes, so a swapped
        pair of string keys is invisible to every value-level multiset."""
        from rom1.walls.semdiff import Line, referent_runs
        b = [Line(0, "push 0x0", "??_C@_0A@AAA@KEY_A"),
             Line(4, "push 0x0", "??_C@_0A@BBB@KEY_B")]
        t = [Line(0, "push 0x0", "??_C@_0A@BBB@KEY_B"),
             Line(4, "push 0x0", "??_C@_0A@AAA@KEY_A")]
        self.assertNotEqual(referent_runs(b), referent_runs(t))


class EhRegistrationRenameControls(unittest.TestCase):
    """`_eh_funclet_owners` renames a delinked `push <undefined FUN_<rva>>` to
    `__ehreg$<owner>` so the two sides co-name their EH machinery.  On the
    delinked side that is the ONLY structure available, and a
    `push <$E atexit thunk>; call _atexit` has exactly the same shape - it was
    renamed on 12 sites in the tree, asserting a registration stub that does
    not exist (`0x153800` is `mov ecx,&clip; jmp ~CResolveNode`).  The
    discriminator is the instruction that makes a pushed record ACTIVE."""

    def test_the_registration_prologue_is_recognized(self):
        from rom1.compare.canonicalize import _installs_seh_frame
        # push <stub> / mov eax,fs:[0] / push eax / mov fs:[0],esp
        body = bytes.fromhex("64a10000000050" "64892500000000")
        self.assertTrue(_installs_seh_frame(body, 0))

    def test_the_interleaved_registration_prologue_is_recognized(self):
        """363 of the 911 real sites load `fs:[0]` BEFORE the push, so the
        window has to start at `push eax`, not at the `fs` prefix."""
        from rom1.compare.canonicalize import _installs_seh_frame
        self.assertTrue(_installs_seh_frame(
            bytes.fromhex("50" "64892500000000"), 0))

    def test_an_atexit_thunk_push_is_rejected(self):
        from rom1.compare.canonicalize import _installs_seh_frame
        # push <$E thunk> / call _atexit / add esp,4 / mov edx,[..]
        self.assertFalse(_installs_seh_frame(
            bytes.fromhex("e80000000083c4048b150000000000000000000000000000"), 0))

    def test_a_static_guard_push_is_rejected(self):
        from rom1.compare.canonicalize import _installs_seh_frame
        # the CButeMgr shape: or dl,al / mov [guard],... then the atexit call
        self.assertFalse(_installs_seh_frame(
            bytes.fromhex("0ad0c705000000000000000000000000000000000000"), 0))


class ResidueClassifierControls(unittest.TestCase):
    """`walls residue` names what a masked residual IS.  Its whole value is
    that a scheduling coin and a wrong constant land in different buckets, so
    a classifier nobody has seen put a KNOWN coin in a coin bucket AND a KNOWN
    source bug in an actionable one is not a classifier."""

    @staticmethod
    def _lines(asms, ref=None):
        from rom1.walls.semdiff import Line
        return [Line(i * 4, a, ref) for i, a in enumerate(asms)]

    def _kind(self, base, target):
        from rom1.walls.residue import classify, masked, residual_of
        mb, mt = masked(self._lines(base)), masked(self._lines(target))
        return classify(residual_of(mb, mt)[1], mb, mt)[0]

    def test_a_lone_immediate_is_not_hidden_by_the_mask(self):
        from rom1.walls.residue import masked
        self.assertEqual(len(masked(self._lines(["cmp eax,0x1e"]))), 1)

    def test_a_pure_register_rotation_is_not_actionable(self):
        self.assertEqual(self._kind(
            ["mov ebx,DWORD PTR [esi+0x84]", "sub ebx,0x20"],
            ["mov eax,DWORD PTR [esi+0x84]", "sub eax,0x20"]), "regname")

    def test_a_moved_instruction_is_a_schedule_coin(self):
        self.assertEqual(self._kind(
            ["mov eax,DWORD PTR [esi]", "cmp eax,0x1", "push esi"],
            ["cmp eax,0x1", "push esi", "mov eax,DWORD PTR [esi]"]), "schedule")

    def test_a_relocated_call_addend_is_position_state(self):
        """The rel32 of a RELOCATED call moves whenever anything above it
        does; leaving it in read as an immediate difference on 8 rows."""
        from rom1.walls.residue import masked
        self.assertEqual(masked(self._lines(["call 0xe4"], "?F@@YAXXZ")),
                         masked(self._lines(["call 0xe0"], "?F@@YAXXZ")))

    def test_the_accumulator_and_form_is_one_instruction(self):
        """cl takes `and al,0xe0` for `and eax,0xffffffe0`; seven ctors were
        mislabelled `immediate` before this mirror was normalized."""
        self.assertEqual(self._kind(["and ecx,0xffffffe0"],
                                    ["and al,0xe0"]), "regname")

    def test_add_of_a_negative_is_the_same_subtraction(self):
        """`add ecx,0xfffffff9` IS `sub ecx,0x7`, and cl picks between them on
        its own - measured going BOTH ways against retail in one tree, so it
        is not even a source lever, only noise in the immediate bucket."""
        self.assertEqual(self._kind(["add ecx,0xfffffff9"],
                                    ["sub ecx,0x7"]), "none")

    def test_the_add_sub_mirror_still_sees_a_real_constant(self):
        self.assertEqual(self._kind(["add ecx,0xffffffe0"],
                                    ["sub ecx,0x21"]), "immediate")

    def test_a_wrong_constant_is_flagged(self):
        self.assertEqual(self._kind(["cmp eax,0x1e"],
                                    ["cmp eax,0x9"]), "immediate")

    def test_a_wrong_member_offset_is_flagged(self):
        self.assertEqual(self._kind(["mov eax,DWORD PTR [esi+0x180]"],
                                    ["mov eax,DWORD PTR [esi+0x17c]"]),
                         "displacement")

    def test_a_forced_zero_displacement_is_an_encoding(self):
        """`[ebp+0x0]` IS `[ecx]`: EBP as a base cannot encode without a
        displacement byte, and register-stripping erases which base it was.
        A quarter of the `displacement` bucket was this one encoding."""
        self.assertEqual(self._kind(["mov eax,DWORD PTR [ebx]"],
                                    ["mov eax,DWORD PTR [ebp+0x0]"]),
                         "regname")

    def test_a_baseless_scaled_index_zero_is_an_encoding(self):
        """`lea edi,[ebp*8+0x0]` IS `shl`-free `[eax*8]` under a base: with no
        base register the ModRM demands a disp32."""
        self.assertEqual(self._kind(["lea edi,[eax*8+0x0]"],
                                    ["lea ecx,[edx*8+0x0]"]), "regname")

    def test_a_split_sub_object_address_is_not_a_layout_bug(self):
        """`lea eax,[esi+0x20]` then `[eax+0x4]` addresses what `[esi+0x24]`
        addresses.  Register-stripping cannot prove the sum, so the RECT
        CImage::RenderImage writes through a pointer read as four wrong member
        offsets."""
        self.assertEqual(self._kind(
            ["mov DWORD PTR [esi+0x20],eax", "mov DWORD PTR [esi+0x24],ecx",
             "mov DWORD PTR [esi+0x28],edx"],
            ["lea edi,[esi+0x20]", "mov DWORD PTR [edi],eax",
             "mov DWORD PTR [edi+0x4],ecx", "mov DWORD PTR [edi+0x8],edx"]),
            "subobject")

    def test_a_lone_pair_is_never_cleared_as_a_sub_object(self):
        """A single offset against a single other offset is exactly the
        wrong-field signature this bucket exists to find, and SOME constant
        always reconciles two numbers - so the run has to be at least two."""
        self.assertEqual(self._kind(
            ["lea edi,[esi+0x4]", "mov eax,DWORD PTR [esi+0x180]"],
            ["lea edi,[esi+0x4]", "mov eax,DWORD PTR [esi+0x17c]"]),
            "displacement")

    def test_lea_for_arithmetic_is_the_same_register_choice(self):
        """cl takes the three-operand `lea` for exactly one reason: the
        destination is not the source.  That is the register pick `reg_key`
        already erases, so `lea esi,[eax+0x1]` IS `inc esi` and
        `lea ecx,[eax+eax*1]` IS `add eax,eax`.  Un-mirrored, the lea's
        displacement read as a member offset (RandRange, UpdateMgrScroll,
        CRandomAmbientSound::Update, DrawBorderRaw, _zvec::GrowTo)."""
        self.assertEqual(self._kind(["inc esi"], ["lea esi,[eax+0x1]"]),
                         "regname")
        self.assertEqual(self._kind(["add eax,eax"], ["lea ecx,[eax+eax*1]"]),
                         "regname")

    def test_the_lea_mirror_still_sees_a_real_offset(self):
        """Only the +1 and the doubling fold; a genuine `lea` of a member
        address stays visible."""
        self.assertEqual(self._kind(["lea eax,[esi+0x10]"],
                                    ["lea eax,[esi+0x14]"]), "displacement")

    def test_the_three_byte_lea_pad_is_a_nop(self):
        """`lea ecx,[ecx+0x0]` is cl's 3-byte alignment pad, the same padding
        a `nop` is (CKitchenSlime::LoadSprites, CGrunt::ArrivalRecycle)."""
        self.assertEqual(self._kind(["nop"], ["lea ecx,[ecx+0x0]"]), "regname")

    def test_the_accumulator_memory_form_is_one_access(self):
        """`a1 <addr>` prints `mov eax,ds:0x0`; the general `8b 0d <addr>`
        prints `mov ecx,DWORD PTR ds:0x0`.  Same load, and cl takes the short
        form only when the value lands in EAX."""
        from rom1.walls.residue import classify, masked, residual_of
        from rom1.walls.semdiff import Line
        g = "?g_errOutOfMem@@3PADA"
        mb = masked([Line(0, "mov ecx,DWORD PTR ds:0x0", g)])
        mt = masked([Line(0, "mov eax,ds:0x0", g)])
        self.assertEqual(classify(residual_of(mb, mt)[1], mb, mt)[0], "regname")

    def test_one_datum_under_two_spellings_is_one_referent(self):
        """`canon_ref` fires only on an operand carrying exactly one absolute
        token, which makes the fold asymmetric: a one-token load becomes
        `@<addr>` while a two-token compare keeps its symbol.  Same datum, and
        the bucket whose whole job is identity must not call it two."""
        from rom1.walls.residue import ref_key
        name = "?g_logicTypesRegistered@@3HA"
        addr = ref_key(name)
        if not addr.startswith("@"):
            self.skipTest("model does not resolve the control symbol")
        self.assertEqual(ref_key(addr), addr)
        self.assertEqual(ref_key("?unnamed"), "?unnamed")
        self.assertEqual(ref_key("?NotASymbol@@3HA"), "?NotASymbol@@3HA")

    def test_a_spent_zero_register_is_the_immediate(self):
        """cl parks a zero in a callee-saved register when it needs one
        repeatedly, then spends it where an immediate would go.  Measured both
        ways in one tree, so it is noise: `CStaticHazard::UpdateActiveState` and
        `RunCustomWorldDialog` carry the immediate where retail carries the
        register, `CMulti::PollSession` the reverse."""
        from rom1.walls.residue import classify, masked, residual_of
        from rom1.walls.semdiff import Line
        base = [Line(0, "xor ebx,ebx", None), Line(2, "push ebx", None),
                Line(3, "call 0x40", "?Hit@@YAHXZ"), Line(8, "test eax,eax", None)]
        tgt = [Line(0, "xor ebx,ebx", None), Line(2, "push ebx", None),
               Line(3, "call 0x40", "?Hit@@YAHXZ"), Line(8, "cmp eax,ebx", None)]
        mb, mt = masked(base), masked(tgt)
        self.assertEqual(residual_of(mb, mt)[0], 0)

    def test_a_two_value_compare_is_not_a_spent_zero(self):
        """The fold reads a dataflow fact, not a spelling.  Register-stripping
        turns a real compare between two live values into the same `cmp r,r`
        text, so an unproven register must never be spent."""
        from rom1.walls.residue import masked, residual_of
        from rom1.walls.semdiff import Line
        base = [Line(0, "mov ebx,DWORD PTR [esi+0x8]", None),
                Line(3, "test eax,eax", None)]
        tgt = [Line(0, "mov ebx,DWORD PTR [esi+0x8]", None),
               Line(3, "cmp eax,ebx", None)]
        mb, mt = masked(base), masked(tgt)
        self.assertGreater(residual_of(mb, mt)[0], 0)

    def test_a_zero_retired_on_one_path_is_not_spent_on_another(self):
        """A linear walk was WRONG here: an early-return epilogue's `pop ebx`
        retires a zero the blocks after it still hold, because they are not
        reached through that epilogue.  The meet is over real edges."""
        from rom1.walls.residue import zero_regs
        from rom1.walls.semdiff import Line
        # 0: xor ebx,ebx / 2: jne 0x8 / 4: pop ebx / 5: ret / 8: cmp eax,ebx
        fn = [Line(0, "xor ebx,ebx", None), Line(2, "jne 0x8", None),
              Line(4, "pop ebx", None), Line(5, "ret", None),
              Line(8, "cmp eax,ebx", None)]
        z = zero_regs(fn)
        self.assertIn("ebx", z[4])
        self.assertNotIn("ebx", z[2 + 1])

    def test_a_jump_table_arm_spends_nothing(self):
        """An instruction whose only predecessor is an indirect jump has no
        named edge, so it starts from the empty set rather than inheriting a
        zero the table's other arms happen to hold."""
        from rom1.walls.residue import zero_regs
        from rom1.walls.semdiff import Line
        fn = [Line(0, "xor ebx,ebx", None),
              Line(2, "jmp DWORD PTR [eax*4+0x40]", None),
              Line(9, "cmp ecx,ebx", None)]
        self.assertEqual(zero_regs(fn)[2], frozenset())

    def test_a_wrong_referent_is_flagged(self):
        """Relocated operands are masked in the scored bytes, so a global
        bound to the wrong symbol is invisible to the byte diff."""
        from rom1.walls.residue import classify, masked, residual_of
        mb = masked(self._lines(["mov ebx,0x0"], "?g_a@@3HA"))
        mt = masked(self._lines(["mov ebx,0x0"], "?g_b@@3HA"))
        self.assertEqual(classify(residual_of(mb, mt)[1], mb, mt)[0],
                         "referent")

    def test_a_recomputed_global_load_is_not_an_identity_row(self):
        """Retail reads `g_gameReg` twice where cl keeps one copy: both sides
        NAME the symbol, so the count difference is CSE, not a wrong claim.
        Un-normalized this read `referent` on CTriggerMgr::
        LoadGruntResurrectTuning and on five `g_p01` loads in FlashTable."""
        from rom1.walls.residue import classify, masked, residual_of
        from rom1.walls.semdiff import Line
        g = "?g_gameReg@@3PAVCRom1Mgr@@A"
        mb = masked([Line(0, "mov ebx,0x0", g), Line(4, "push ebx", None)])
        mt = masked([Line(0, "mov ebx,0x0", g), Line(4, "mov ecx,0x0", g),
                     Line(8, "push ebx", None)])
        self.assertNotEqual(classify(residual_of(mb, mt)[1], mb, mt)[0],
                            "referent")

    def test_two_non_names_for_one_address_are_not_a_referent_row(self):
        """objdiff calls our unnamed symbol `$anon_data_<sha>_0`; the delinker,
        with no claim on the address, calls retail's `FUN_<va>`. Eleven of the
        fifteen `referent` rows were one `$E` dynamic-init helper under two
        non-names."""
        from rom1.walls.residue import classify, masked, residual_of
        mb = masked(self._lines(["push 0x0"], "$anon_data_deadbeef_0"))
        mt = masked(self._lines(["push 0x0"], "FUN_004183b0"))
        self.assertEqual(classify(residual_of(mb, mt)[1], mb, mt)[0], "none")

    def test_a_missing_arm_temp_is_the_register_case(self):
        """docs/patterns/arm-result-temp-controls-copies-and-shared-store.md:
        retail's arm ends in `mov <callee-saved>,<scratch>` and the base is
        exactly that many instructions short."""
        self.assertEqual(self._kind(
            ["mov edi,DWORD PTR [esi+0x80]"],
            ["mov ecx,DWORD PTR [esi+0x80]", "mov edi,ecx"]), "arm-copy")

    def test_a_shared_store_the_arms_should_own_is_the_memory_case(self):
        from rom1.walls.residue import store_census, masked
        base = masked(self._lines(["mov DWORD PTR [esi+0x4c],ecx"]))
        target = masked(self._lines(["mov DWORD PTR [esi+0x4c],edx",
                                     "mov DWORD PTR [esi+0x4c],ecx"]))
        sb, st = store_census(base), store_census(target)
        self.assertEqual((sb["r+0x4c"], st["r+0x4c"]), (1, 2))

    def test_the_store_census_keys_on_the_destination_only(self):
        """`mov [esi+0x4c],ecx` and `mov [esi+0x4c],edx` are ONE store; keying
        on the whole instruction would hide every per-arm duplicate."""
        from rom1.walls.residue import store_census, masked
        c = store_census(masked(self._lines(["mov DWORD PTR [esi+0x4c],ecx",
                                             "mov DWORD PTR [esi+0x4c],edx"])))
        self.assertEqual(c["r+0x4c"], 2)
        self.assertEqual(len(c), 1)

    def test_a_jump_table_never_reaches_the_residual(self):
        """A function's own index table decodes as junk with huge
        displacements; one table produced 500 residual lines on a single row
        before it was filtered."""
        from rom1.walls.residue import masked
        me = "?Fn@C@@QAEHXZ"
        junk = self._lines(["add BYTE PTR [eax+0x1e000001],cl",
                            "add BYTE PTR [edx-0x47fffffc],bl"], ref=me)
        self.assertEqual(masked(junk, me), [])
        self.assertEqual(len(masked(junk, "?Other@@QAEXXZ")), 2)

    def test_a_byte_continuation_line_is_dropped(self):
        from rom1.walls.residue import masked
        self.assertEqual(masked(self._lines(["83 c4 10"])), [])

    def test_a_stack_store_is_not_a_member_store(self):
        from rom1.walls.residue import store_census, masked
        self.assertEqual(
            store_census(masked(self._lines(["mov DWORD PTR [esp+0x10],ecx"]))),
            {})

    def test_a_lea_of_its_own_base_is_the_same_addition(self):
        """`lea ecx,[ecx+0x240]` IS `add ecx,0x240` - LEA does not write flags,
        which is the only reason cl picks between them, and it was measured
        going BOTH ways against retail in one tree (CTriggerMgr::Load carries
        the lea where retail has the add; CBootyState::EnterState the add where
        retail has the lea). Ten rows of the immediate bucket were this."""
        self.assertEqual(self._kind(["lea ecx,[ecx+0x240]"],
                                    ["add ecx,0x240"]), "none")
        self.assertEqual(self._kind(["lea edx,[edx-0x132]"],
                                    ["sub edx,0x132"]), "none")
        self.assertEqual(self._kind(["lea esi,[esi+esi*1]"],
                                    ["add esi,esi"]), "none")

    def test_a_lea_into_a_different_register_is_not_an_addition(self):
        """`lea ecx,[eax+0x240]` KEEPS eax; only the dst == base form is the
        mirror, and the 3-byte `lea ecx,[ecx+0x0]` NOP is not an `add` at all."""
        from rom1.walls.residue import masked
        self.assertNotEqual(self._kind(["lea ecx,[eax+0x240]"],
                                       ["add ecx,0x240"]), "none")
        self.assertEqual(masked(self._lines(["lea ecx,[ecx+0x0]"])),
                         ["lea ecx,[ecx+0x0]"])

    def test_the_high_byte_accumulator_form_is_one_instruction(self):
        """`and dh,0xef` masks bits 8..15 and touches nothing else, so it IS
        `and edx,0xffffefff`. CRom1MapMgr::BuildCellAttributes read `immediate`
        on this mirror alone."""
        self.assertEqual(self._kind(["and edx,0xffffefff"],
                                    ["and dh,0xef"]), "none")

    def test_the_high_byte_mirror_still_sees_a_real_mask(self):
        """`and edx,0xf` clears bits 4..31; `and dh,0xf` clears only 12..15."""
        self.assertEqual(self._kind(["and edx,0xf"],
                                    ["and dh,0xf"]), "immediate")

    def test_a_one_past_the_end_pointer_is_one_address_under_two_names(self):
        """A loop's end sentinel `&g_lut16[0x100]` is an address the delinker
        resolves against whatever symbol STARTS there, while cl names it
        against the array: `cmp esi,0x200|g_lut16` against `cmp esi,0x0|g_rUp`,
        and 0x283ca0 + 0x200 == 0x283ea0. Seven `immediate` rows were this."""
        import rom1.walls.residue as R
        saved, R._SYMS = R._SYMS, {"?g_lut16@@3PAGA": 0x283ca0,
                                   "?g_rUp@@3HA": 0x283ea0}
        try:
            from rom1.walls.semdiff import Line
            mb = R.masked([Line(0, "cmp esi,0x200", "?g_lut16@@3PAGA")])
            mt = R.masked([Line(0, "cmp esi,0x0", "?g_rUp@@3HA")])
            self.assertEqual(mb, mt)
        finally:
            R._SYMS = saved

    def test_a_constant_stored_through_a_relocated_address_is_not_an_addend(self):
        """`mov DWORD PTR ds:g_x,0x55` carries TWO absolute tokens and only one
        of them is the relocation's addend, so the fold declines - which is
        what keeps a genuinely wrong stored constant in `immediate`."""
        import rom1.walls.residue as R
        saved, R._SYMS = R._SYMS, {"?g_x@@3HA": 0x1000}
        try:
            from rom1.walls.semdiff import Line
            mb = R.masked([Line(0, "mov DWORD PTR ds:0x0,0x55", "?g_x@@3HA")])
            mt = R.masked([Line(0, "mov DWORD PTR ds:0x0,0x66", "?g_x@@3HA")])
            self.assertEqual(R.classify(R.residual_of(mb, mt)[1], mb, mt)[0],
                             "immediate")
        finally:
            R._SYMS = saved

    def test_the_objdiff_content_hash_is_not_an_identity(self):
        """`_kMsToSeconds$Sdata_rdata_<sha>_0` names the SECTION's content, and
        the section pools other constants, so ONE float hashes differently on
        the two sides - the two standing CFader `referent` rows."""
        import rom1.walls.residue as R
        saved, R._SYMS = R._SYMS, {}
        try:
            a = "_k$Sdata_rdata_%s_0" % ("a" * 64)
            b = "_k$Sdata_rdata_%s_0" % ("b" * 64)
            self.assertEqual(R.masked(self._lines(["fld DWORD PTR ds:0x0"], a)),
                             R.masked(self._lines(["fld DWORD PTR ds:0x0"], b)))
        finally:
            R._SYMS = saved


class LoopBodyControls(unittest.TestCase):
    """`walls loopscan` measures the LOOP BOUNDARY, which is the one thing a
    masked comparison cancels: masking address operands erases branch
    displacements, so an instruction that moved across the boundary reads as a
    schedule coin even though it now runs N times instead of once.  A sieve
    nobody has seen separate that KNOWN hoist from a KNOWN coin is not a sieve,
    so both directions are controlled here."""

    @staticmethod
    def _lines(asms, refs=None):
        """One instruction per 4 bytes, so a branch operand `0xN` names the
        instruction at index N/4."""
        from rom1.walls.semdiff import Line
        refs = refs or {}
        return [Line(i * 4, a, refs.get(i)) for i, a in enumerate(asms)]

    def _spans(self, asms, refs=None):
        from rom1.walls.loopscan import loops
        return [lp["span"] for lp in loops(self._lines(asms, refs))]

    def test_a_backward_branch_closes_a_body_of_its_instruction_span(self):
        self.assertEqual(self._spans(
            ["mov eax,DWORD PTR [esi]", "inc eax", "jne 0x0"]), [2])

    def test_a_forward_branch_is_not_a_loop(self):
        self.assertEqual(self._spans(
            ["jne 0x8", "inc eax", "mov eax,DWORD PTR [esi]"]), [])

    def test_a_relocated_branch_leaves_the_function(self):
        """A tail `jmp` into another symbol carries a relocation; its operand
        is not an offset in this stream and must not close a body."""
        self.assertEqual(self._spans(["inc eax", "jmp 0x0"],
                                     {1: "?Other@@YAXXZ"}), [])

    def test_the_boundary_moves_while_the_instruction_text_does_not(self):
        """The headline control.  Both sides hold the IDENTICAL instructions
        and differ only in the branch TARGET - precisely what masking cancels -
        yet the load runs every iteration on one side and once on the other."""
        from rom1.walls.framescan import masked
        from rom1.walls.loopscan import loops, pair
        body = ["mov eax,DWORD PTR [esi]", "add ebx,eax"]
        inside = self._lines([*body, "jne 0x0"])
        outside = self._lines([*body, "jne 0x4"])
        self.assertEqual(masked(inside, ""), masked(outside, ""))
        pairs, unpaired = pair(loops(inside), loops(outside))
        self.assertEqual(unpaired, 0)
        self.assertEqual([(a["span"], b["span"]) for a, b in pairs], [(2, 1)])

    def test_the_findprocessbyname_shape_is_a_body_delta(self):
        """The known positive: a struct re-zeroed inside the walk loop.  A
        `rep stos` is ONE instruction carrying unbounded work, so a delta of
        one is signal, and `extra` has to name it."""
        from rom1.walls.loopscan import extra, loops, pair
        ref = {1: "?Step@@YAXXZ"}
        ours = self._lines(["mov eax,DWORD PTR [esp+0x4]", "call 0x0",
                            "rep stos DWORD PTR es:[edi],eax", "jne 0x0"], ref)
        retail = self._lines(["mov eax,DWORD PTR [esp+0x4]", "call 0x0",
                              "jne 0x0"], ref)
        pairs, _ = pair(loops(ours), loops(retail))
        a, b = pairs[0]
        self.assertEqual((a["span"], b["span"]), (3, 2))
        self.assertEqual(extra(a["mnem"], b["mnem"]), ["rep"])

    def test_a_register_rotation_inside_the_body_is_not_a_hoist(self):
        """The known negative.  `walls residue` calls this `regname`; it must
        not reach this sieve at all, because the boundary did not move."""
        from rom1.walls.loopscan import loops, pair
        ours = self._lines(["mov ebx,DWORD PTR [esi+0x84]", "sub ebx,0x20",
                            "jne 0x0"])
        retail = self._lines(["mov eax,DWORD PTR [esi+0x84]", "sub eax,0x20",
                              "jne 0x0"])
        pairs, _ = pair(loops(ours), loops(retail))
        self.assertEqual([a["span"] - b["span"] for a, b in pairs], [0])

    def test_a_reschedule_inside_the_body_is_not_a_hoist(self):
        """The second known negative: the same instructions in a different
        order.  Counting the span is what makes this inert."""
        from rom1.walls.loopscan import loops, pair
        ours = self._lines(["mov eax,DWORD PTR [esi]", "cmp eax,0x1",
                            "push esi", "jne 0x0"])
        retail = self._lines(["cmp eax,0x1", "push esi",
                              "mov eax,DWORD PTR [esi]", "jne 0x0"])
        pairs, _ = pair(loops(ours), loops(retail))
        self.assertEqual([a["span"] - b["span"] for a, b in pairs], [0])

    def test_an_inlined_callee_does_not_shift_the_pairing(self):
        """The alignment control.  When one side is missing a loop, a
        positional zip reports the SURVIVING loop against the wrong
        neighbour - a fabricated hit.  Pairing on the body's call referents
        has to send the missing loop to `unpaired` instead."""
        from rom1.walls.loopscan import loops, pair
        ours = self._lines(
            ["mov eax,0x1", "call 0x0", "nop", "nop", "nop", "jne 0x0",
             "call 0x0", "nop", "jne 0x18"],
            {1: "?A@@YAXXZ", 6: "?B@@YAXXZ"})
        retail = self._lines(["call 0x0", "nop", "jne 0x0"],
                             {0: "?B@@YAXXZ"})
        self.assertEqual([lp["span"] for lp in loops(ours)], [5, 2])
        pairs, unpaired = pair(loops(ours), loops(retail))
        self.assertEqual(unpaired, 1)
        self.assertEqual([(a["span"], b["span"]) for a, b in pairs], [(2, 2)])


class ValueTempLivenessControls(unittest.TestCase):
    """`walls valuetemp` finds an inlined accessor's by-value struct temp by the
    DEAD stores it leaves, so its whole result rests on the liveness rule.  A
    whole-function read SET gets that wrong in both directions, and both errors
    are silent: an address-taken aggregate names only its BASE, so its interior
    fields read as dead (a fabricated hit), while a slot overwritten before its
    address is taken reads as live (a missed hit).  Only the EVENT ORDER on the
    slot separates them, and both directions are controlled here."""

    @staticmethod
    def _ins(*asm):
        """One instruction per 4 bytes; `temps` reads offsets only for order."""
        out = []
        for i, text in enumerate(asm):
            mn, _, ops = text.partition(" ")
            out.append((i * 4, mn, ops))
        return out

    def test_the_overwritten_temp_is_dead_even_though_the_slot_escapes(self):
        """The known positive (CGrunt::RectContains).  Retail materialises the
        by-value Coord, then overwrites BOTH halves with the real value and
        takes the slot's address - so the temp is dead and the `lea` observes
        only its successor."""
        from rom1.walls.valuetemp import temps
        self.assertEqual(temps(self._ins(
            "mov edx,DWORD PTR [ecx+0x180]", "mov DWORD PTR [esp+0x14],edx",
            "mov edx,DWORD PTR [ecx+0x17c]", "mov DWORD PTR [esp+0x10],edx",
            "mov eax,DWORD PTR [ecx+0x184]", "mov DWORD PTR [esp+0x10],eax",
            "mov eax,DWORD PTR [ecx+0x188]", "mov DWORD PTR [esp+0x14],eax",
            "lea edx,[esp+0x10]", "push edx")), {("mem", 0x17C)})

    def test_an_address_taken_aggregates_interior_fields_are_not_dead(self):
        """The known negative (CBattlezMapConfig::ScanRegion).  Two adjacent
        RECTs are built and one is pushed by address; the second RECT's
        right/bottom stores are fed by an adjacent member pair and are never
        named again, which is exactly the temp's signature - but the `lea`
        covering their object observes them."""
        from rom1.walls.valuetemp import temps
        self.assertEqual(temps(self._ins(
            "mov ecx,DWORD PTR [eax+0x10]", "mov edx,DWORD PTR [eax+0xc]",
            "mov DWORD PTR [esp+0x64],ecx", "mov DWORD PTR [esp+0x60],edx",
            "lea eax,[esp+0x58]", "push eax")), set())

    def test_a_pair_nothing_ever_reads_is_dead(self):
        """The second form the mechanism produces: no killing store, no read."""
        from rom1.walls.valuetemp import temps
        self.assertEqual(temps(self._ins(
            "mov eax,DWORD PTR [esi+0x38]", "mov DWORD PTR [esp+0x20],eax",
            "mov ecx,DWORD PTR [esi+0x3c]", "mov DWORD PTR [esp+0x24],ecx",
            "ret")), {("mem", 0x38)})

    def test_a_push_between_the_store_and_its_read_is_not_a_second_slot(self):
        """ESP tracking.  After a `push`, the SAME slot is spelled +4 higher;
        an untracked scan reads that as a different slot and calls the store
        dead."""
        from rom1.walls.valuetemp import temps
        self.assertEqual(temps(self._ins(
            "mov eax,DWORD PTR [esi+0x8]", "mov DWORD PTR [esp+0x10],eax",
            "mov ecx,DWORD PTR [esi+0xc]", "mov DWORD PTR [esp+0x14],ecx",
            "push ebx", "mov edx,DWORD PTR [esp+0x14]")), set())

    def test_a_call_restores_the_frame_level(self):
        """The argument pushes are gone once the call returns - the callee pops
        them under `__thiscall`/`__stdcall`.  Carrying them forward drifts the
        delta upward for the rest of the body, so the SAME slot read after the
        call scores as a different one and the pair reads dead."""
        from rom1.walls.valuetemp import temps
        self.assertEqual(temps(self._ins(
            "sub esp,0x10", "push ebx",
            "mov eax,DWORD PTR [esi+0x8]", "mov DWORD PTR [esp+0x4],eax",
            "mov ecx,DWORD PTR [esi+0xc]", "mov DWORD PTR [esp+0x8],ecx",
            "push 0x1", "push 0x2", "call 0x0",
            "mov edx,DWORD PTR [esp+0x4]")), set())

    def test_the_frame_level_counts_saves_that_follow_sub_esp(self):
        """cl 5.0 puts `sub esp,N` on either side of the callee-save pushes, so
        the prologue cannot be cut at the first non-push; an ARGUMENT push ends
        it, and only ebx/ebp/esi/edi are saved, each once."""
        from rom1.walls.valuetemp import _frame_level
        self.assertEqual(_frame_level(self._ins(
            "sub esp,0x14", "mov eax,DWORD PTR [esp+0x18]", "push ebx",
            "push ebp", "lea eax,[eax+eax*2]", "push esi", "push edi",
            "mov DWORD PTR [esp+0x14],ecx", "je 0x0")), 0x24)

    def test_an_argument_push_ends_the_prologue(self):
        from rom1.walls.valuetemp import _frame_level
        self.assertEqual(_frame_level(self._ins(
            "sub esp,0x10", "push ebx", "push 0x1", "push 0x2",
            "call 0x0")), 0x14)

    def test_a_reused_slot_does_not_lend_its_source_to_an_earlier_store(self):
        """Deadness belongs to ONE STORE.  cl reuses a slot, so taking the
        slot's first store for the verdict and its first MEMBER-sourced store
        for the identity reports a member pair that was never dead - the
        surviving stores here are the ones the `lea` keeps live."""
        from rom1.walls.valuetemp import temps
        self.assertEqual(temps(self._ins(
            "xor eax,eax", "mov DWORD PTR [esp+0x20],eax",
            "xor ecx,ecx", "mov DWORD PTR [esp+0x24],ecx",
            "mov edx,DWORD PTR [esi+0x8]", "mov DWORD PTR [esp+0x20],edx",
            "mov ebx,DWORD PTR [esi+0xc]", "mov DWORD PTR [esp+0x24],ebx",
            "lea eax,[esp+0x20]", "push eax", "call 0x0")), set())

    def test_a_local_aggregate_copy_is_counted_not_compared(self):
        """A pair read from another FRAME slot is keyed on a frame offset, which
        the two sides do not agree on.  The identical copy at two different
        frame offsets read as an asymmetry in BOTH directions at once, so these
        never enter the comparison."""
        from rom1.walls.valuetemp import _pairs
        out, prov, local = _pairs(self._ins(
            "mov ecx,DWORD PTR [esp+0x40]", "mov edx,DWORD PTR [esp+0x44]",
            "mov DWORD PTR [esp+0x20],ecx", "mov DWORD PTR [esp+0x24],edx",
            "ret"))
        self.assertEqual((out, prov, local), (set(), {}, 1))

    def test_a_pointer_read_from_a_global_is_tagged_as_one(self):
        """The second mechanism the sieve reports: a load through a pointer read
        from a global blocks the dead-store elimination the same load through a
        pointer parameter allows, so the row has to say which it was."""
        from rom1.walls.valuetemp import _pairs
        _out, prov, _local = _pairs(self._ins(
            "mov eax,ds:0x0", "mov esi,DWORD PTR [eax+0x4]",
            "mov ecx,DWORD PTR [esi+0x8]", "mov DWORD PTR [esp+0x20],ecx",
            "mov edx,DWORD PTR [esi+0xc]", "mov DWORD PTR [esp+0x24],edx",
            "ret"))
        self.assertEqual(prov, {("mem", 0x8): "glob"})

    def test_a_pointer_taken_from_an_argument_is_not_a_global(self):
        from rom1.walls.valuetemp import _pairs
        _out, prov, _local = _pairs(self._ins(
            "sub esp,0x10", "mov esi,DWORD PTR [esp+0x14]",
            "mov ecx,DWORD PTR [esi+0x8]", "mov DWORD PTR [esp+0x0],ecx",
            "mov edx,DWORD PTR [esi+0xc]", "mov DWORD PTR [esp+0x4],edx",
            "ret"))
        self.assertEqual(prov, {("mem", 0x8): "param"})

    def test_the_gx_preamble_pushes_are_frame(self):
        """A /GX function pushes -1, the handler and the old fs:0 chain before
        anything else, and cl 5.0 gives it no ebp frame - so the callee-save
        rule alone cuts its prologue at the first instruction and reports a
        level of zero.  The registration install ends the preamble."""
        from rom1.walls.valuetemp import _frame_level
        self.assertEqual(_frame_level(self._ins(
            "push 0xffffffff", "push 0x0", "mov eax,fs:0x0", "push eax",
            "mov DWORD PTR fs:0x0,esp", "sub esp,0x5c", "push ebx", "push ebp",
            "push esi", "mov esi,ecx", "je 0x0")), 0x74)


class EhActionControls(unittest.TestCase):
    """`walls ehactions` reports structure; neither count nor action shape is
    sufficient by itself to call source cleanup defective."""

    def test_a_count_delta_is_not_an_action_defect(self):
        from difflib import SequenceMatcher
        from rom1.walls.ehactions import classify
        b = ["[ebp-0x30] -> ??3@YAXPAX@Z"] * 9
        t = ["[ebp-0x30] -> ??3@YAXPAX@Z"] * 12
        ops = [o for o in SequenceMatcher(None, b, t).get_opcodes()
               if o[0] != "equal"]
        self.assertEqual(classify(b, t, ops), "count")

    def test_a_changed_dtor_is_an_action_shape_difference(self):
        from difflib import SequenceMatcher
        from rom1.walls.ehactions import classify
        b = ["[ebp-0x30] -> ??1CString@@QAE@XZ"]
        t = ["[ebp-0x30] -> ??3@YAXPAX@Z"]
        ops = [o for o in SequenceMatcher(None, b, t).get_opcodes()
               if o[0] != "equal"]
        self.assertEqual(classify(b, t, ops), "shape")

    def test_a_new_slot_among_inserts_is_an_action_shape_difference(self):
        from difflib import SequenceMatcher
        from rom1.walls.ehactions import classify
        b = ["[ebp-0x30] -> ??3@YAXPAX@Z"]
        t = ["[ebp-0x30] -> ??3@YAXPAX@Z", "[ebp-0x44] -> ??3@YAXPAX@Z"]
        ops = [o for o in SequenceMatcher(None, b, t).get_opcodes()
               if o[0] != "equal"]
        self.assertEqual(classify(b, t, ops), "shape")

    def test_saved_receiver_plus_member_offset_is_decoded(self):
        """PlayMovieEntry's retail CFecFile cleanup reloads a saved receiver and
        then adds the CFile member offset; this must not print ``no slot``."""
        from rom1.walls.ehactions import action
        body = bytes.fromhex("8b4df081c124010000e900000000")
        self.assertEqual(
            action(body, {10: "??1CFile@@UAE@XZ"}),
            "*[ebp-0x10]+0x124 -> ??1CFile@@UAE@XZ")

    def test_decoder_stops_at_the_first_transfer(self):
        """Zero-extent base labels can expose bytes beyond one funclet; later
        instructions must not mutate the first action's receiver."""
        from rom1.walls.ehactions import action
        body = bytes.fromhex("8d4df0e90000000081c100010000")
        self.assertEqual(
            action(body, {4: "??1CString@@QAE@XZ"}),
            "[ebp-0x10] -> ??1CString@@QAE@XZ")

    def test_the_canonical_map_skips_sectionless_rows(self):
        """The base side names funclets `$L<n>`, so their `__ehunwind$`
        identity lives only in the normalizer's symbols.tsv - and a row with
        `section_ordinal = 0` has no bytes to cut."""
        from rom1.walls import ehactions
        with tempfile.TemporaryDirectory() as td:
            side = Path(td) / "base"
            side.mkdir()
            (side / "u.symbols.tsv").write_text(
                "canonical_name\tsection_ordinal\tsection_offset\n"
                "__ehunwind$?P@@QAEXXZ$0\t481\t0x0\n"
                "__ehunwind$?P@@QAEXXZ$1\t481\t0xb\n"
                "$dup$__ehunwind$?P@@QAEXXZ$2\t0\t0x0\n"
                "?Unrelated@@QAEXXZ\t481\t0x40\n")
            with mock.patch.object(ehactions, "NORM", Path(td)):
                got = ehactions._canonical_map("base", "u", "?P@@QAEXXZ")
        self.assertEqual(got, {0: (481, 0x0), 1: (481, 0xB)})

    def test_the_census_separates_a_frame_shift_from_a_dtor_change(self):
        """The band's biggest bucket is the SAME destructors at a different
        frame slot - the parent's frame layout showing up a second time, not
        an unwind question. It must not be reported as a structural row."""
        from rom1.walls.ehactions import census_verdict
        b = ["[ebp-0x3c] -> ??1CString@@QAE@XZ"] * 3
        t = ["[ebp-0x30] -> ??1CString@@QAE@XZ"] * 3
        self.assertEqual(census_verdict(b, t), "slot-shift")
        self.assertEqual(census_verdict(b, b), "equal")
        self.assertEqual(
            census_verdict(b, t[:2]), "count")
        self.assertEqual(
            census_verdict(b, ["[ebp-0x3c] -> ??1CString@@QAE@XZ",
                               "[ebp-0x3c] -> ??1CString@@QAE@XZ",
                               "[ebp-0x3c] -> ??1CPtrList@@UAE@XZ"]),
            "dtor-identity")


class RetailReceiverScreenControls(unittest.TestCase):
    """`walls thisscan --retail` decides a dropped receiver from the retail
    image alone. Two filters carry the whole screen and both are measured."""

    def test_a_consumed_ecx_is_an_argument_not_a_receiver(self):
        """cl routinely materialises a PUSHED argument through ECX. 273 of the
        275 ECX definitions in the 2026-08-23 sweep were this."""
        from rom1.walls.thisscan import _retail_receiver
        lines = [(0x10, "mov ecx,DWORD PTR [ebx+0x8]"),
                 (0x13, "push ecx"),
                 (0x14, "call 0x2000")]
        self.assertTrue(_retail_receiver(lines, 0x14)["consumed"])
        lines = [(0x10, "mov ecx,DWORD PTR [ebx+0x8]"),
                 (0x13, "push eax"),
                 (0x14, "call 0x2000")]
        self.assertFalse(_retail_receiver(lines, 0x14)["consumed"])

    def test_arithmetic_landing_in_ecx_is_not_an_object(self):
        """`and ecx,0x3` reaches the call unconsumed and is still not a
        receiver - measured on `?FileExists@@YAHPBD@Z`, the screen's only
        other dead-ECX site image-wide."""
        from rom1.walls.thisscan import OBJECT_KINDS, _retail_receiver
        lines = [(0x10, "and ecx,0x3"), (0x13, "call 0x2000")]
        r = _retail_receiver(lines, 0x13)
        self.assertFalse(r["consumed"])
        self.assertNotIn(r["kind"], OBJECT_KINDS)
        lines = [(0x10, "mov ecx,edi"), (0x12, "call 0x2000")]
        self.assertIn(_retail_receiver(lines, 0x12)["kind"], OBJECT_KINDS)

    def test_a_call_or_branch_ends_the_window(self):
        """ECX is volatile across a call, and a definition on the other side
        of a branch does not reach the site."""
        from rom1.walls.thisscan import _retail_receiver
        for barrier in ("call 0x9000", "je 0x9000", "ret"):
            lines = [(0x08, "mov ecx,esi"), (0x0a, barrier),
                     (0x0f, "call 0x2000")]
            self.assertIsNone(_retail_receiver(lines, 0x0F), barrier)

    def test_a_recursive_call_is_not_an_asymmetry(self):
        """Our obj relocates a self-call and names the function; the delinked
        target resolves it inside its own section and leaves no relocation. So
        the census read `n/0` on the caller's OWN name and every self-recursive
        function looked asymmetric - ten of the thirteen inverse sites in the
        whole-image sweep, all of them on rows scoring 100.00."""
        from rom1.walls.thisscan import _census
        me = "?Parse@CButeMgr@@QAE_NXZ"
        sites = [{"direct": True, "ref": me, "recv": {"kind": "regcopy"}},
                 {"direct": True, "ref": "?Other@@YAXXZ", "recv": None}]
        tot, _rec, _det = _census(sites, me)
        self.assertEqual(dict(tot), {"?Other@@YAXXZ": 1})


class MatchReferenceControls(unittest.TestCase):
    """`rom1 match --reference <bad path>` raised FileNotFoundError AFTER a
    full build - the work was done and the run ended in a traceback."""

    def test_an_unreadable_reference_is_a_message(self):
        import contextlib
        import io
        from rom1.graph import verbs
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "nope.json"
            with mock.patch.object(verbs, "compiler_ready", return_value=True), \
                    mock.patch.object(verbs, "configure_if_needed", lambda *a, **k: None), \
                    mock.patch.object(verbs, "ninja", lambda *a, **k: 0), \
                    mock.patch.object(verbs, "object_census", dict), \
                    mock.patch("rom1.tool.objdiff.load",
                               lambda p: (_ for _ in ()).throw(FileNotFoundError(p))
                               if str(p) == str(missing) else {"measures": {},
                                                               "units": []}), \
                    mock.patch("rom1.compare.run.print_summary",
                               lambda *a, **k: None), \
                    mock.patch.object(Path, "exists", lambda self: True):
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    with contextlib.redirect_stdout(io.StringIO()):
                        rc = verbs.match_main(["--reference", str(missing)])
        self.assertEqual(rc, 2)
        self.assertIn("--reference", err.getvalue())


class ToolchainIsADeclaredInput(unittest.TestCase):
    """The era toolchain and the delinker used to be pure environment.

    Consequence chain, all silent: re-pinning $MSVC_DIR recompiled only the
    units that happened to be dirty and left the rest built by the previous
    cl (a mixed object set, the worst failure a byte-matching project has),
    swapping the delinker gave `ninja: no work to do`, and because the `rc`
    edge only exists when rc.exe was present at CONFIGURE time, a pre-r3 pin
    silently produced a candidate image with no `.rsrc` at all.
    """

    def test_the_identity_names_all_three_inputs(self):
        from rom1.graph.emit import toolchain_id
        with mock.patch.dict(os.environ, {"MSVC_DIR": "/m", "DXSDK_DIR": "/d"}):
            got = toolchain_id()
        self.assertIn("MSVC_DIR=/m", got)
        self.assertIn("DXSDK_DIR=/d", got)
        self.assertIn("delinker=", got)

    def test_an_unset_variable_is_recorded_not_skipped(self):
        """Unset -> set is itself a change the edges must see."""
        from rom1.graph.emit import toolchain_id
        with mock.patch.dict(os.environ, {"DXSDK_DIR": "/d"}, clear=True):
            got = toolchain_id()
        self.assertIn("MSVC_DIR=-", got)

    def test_the_id_is_written_if_changed(self):
        """It is an input of all 300 cl edges: an unconditional rewrite would
        recompile the tree every time anything else re-ran configure."""
        from rom1.graph.emit import write_toolchain_id
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "toolchain.id"
            self.assertTrue(write_toolchain_id(p))     # created
            before = p.stat().st_mtime_ns
            self.assertFalse(write_toolchain_id(p))    # unchanged
            self.assertEqual(p.stat().st_mtime_ns, before)
            p.write_text("MSVC_DIR=/elsewhere\n")
            self.assertTrue(write_toolchain_id(p))     # moved

    def test_a_repin_is_detected(self):
        from rom1.graph import verbs
        from rom1.graph.emit import toolchain_id
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "toolchain.id"
            with mock.patch.dict(os.environ, {"MSVC_DIR": "/one"}):
                p.write_text(toolchain_id())
                with mock.patch.object(verbs, "REPO", Path(td)), \
                        mock.patch.object(verbs.graph, "TOOLCHAIN_ID", "toolchain.id"):
                    self.assertFalse(verbs.toolchain_repinned())
                    with mock.patch.dict(os.environ, {"MSVC_DIR": "/two"}):
                        self.assertTrue(verbs.toolchain_repinned())

    def test_the_emitted_manifest_declares_it_on_the_cl_edges(self):
        """The integration control. Recognising the file is not the claim -
        the claim is that the COMPILE edges depend on it, which is what makes
        a re-pin invalidate the object set."""
        from rom1 import graph
        from rom1.core.paths import REPO
        ninja = (REPO / graph.NINJA)
        if not ninja.exists():
            self.skipTest("no emitted manifest (run `rom1 configure`)")
        text = ninja.read_text()
        self.assertIn(graph.TOOLCHAIN_ID, text)
        cl_edges = [ln for ln in text.splitlines()
                    if ln.startswith("build build/objdiff/base/") and ": cl " in ln]
        if not cl_edges:
            from rom1 import manifest
            data = manifest.load()
            if data.get("build", {}).get("bootstrap") and not data.get("unit"):
                self.skipTest("explicit pre-first-TU bootstrap manifest")
        self.assertTrue(cl_edges, "no cl edges in the manifest")
        # Edge lines are wrapped by the writer, so join the continuations.
        joined, buf = [], ""
        for ln in text.splitlines():
            buf += ln.rstrip("$")
            if not ln.endswith("$"):
                joined.append(buf); buf = ""
        declaring = [ln for ln in joined
                     if ln.startswith("build build/objdiff/base/")
                     and ": cl " in ln and graph.TOOLCHAIN_ID in ln]
        self.assertEqual(len(declaring), len(cl_edges),
                         "every cl edge must declare the toolchain identity")


def _asm_lines(asms, refs=None):
    """One instruction per 4 bytes, so a branch operand `0xN` names the
    instruction at index N/4."""
    from rom1.walls.semdiff import Line
    refs = refs or {}
    return [Line(i * 4, a, refs.get(i)) for i, a in enumerate(asms)]


class ArithmeticSignednessControls(unittest.TestCase):
    """`walls signscan` reads the signedness of a division, modulo, shift or
    narrow load off the instruction cl chose.  The sequences below are the
    real cl 5.0 SP3 /O2 output for the named C expression, so a change in the
    classifier that stops separating them is a regression against the
    compiler, not against a fixture."""

    SDIV10 = ["mov ecx,DWORD PTR [esp+0x4]", "mov eax,0x66666667", "imul ecx",
              "mov eax,edx", "sar eax,0x2", "mov ecx,eax", "shr ecx,0x1f",
              "add eax,ecx", "ret"]
    UDIV10 = ["mov eax,0xcccccccd", "mul DWORD PTR [esp+0x4]", "mov eax,edx",
              "shr eax,0x3", "ret"]
    SMOD16 = ["mov eax,DWORD PTR [esp+0x4]", "cdq", "xor eax,edx",
              "sub eax,edx", "and eax,0xf", "xor eax,edx", "sub eax,edx"]
    UMOD16 = ["mov eax,DWORD PTR [esp+0x4]", "and eax,0xf"]

    def _dec(self, ours, theirs):
        from rom1.walls.signscan import decisive, features
        return decisive(features(_asm_lines(ours)),
                        features(_asm_lines(theirs)))

    def test_signed_and_unsigned_division_are_separated(self):
        d = self._dec(self.SDIV10, self.UDIV10)
        self.assertEqual(d.get("imul"), (1, 0))
        self.assertEqual(d.get("mul"), (0, 1))

    def test_the_signed_sign_extract_is_not_read_as_an_unsigned_shift(self):
        """`shr r,0x1f` is step five of the SIGNED magic sequence.  Counting
        it inverts the reading: the signed form would look MORE unsigned than
        the unsigned form."""
        from rom1.walls.signscan import features
        self.assertEqual(features(_asm_lines(self.SDIV10))[("shr", "0x1f")], 0)

    def test_signed_and_unsigned_modulo_are_separated(self):
        self.assertEqual(self._dec(self.SMOD16, self.UMOD16).get("cdq"), (1, 0))

    def test_the_same_lowering_on_both_sides_is_silent(self):
        self.assertEqual(self._dec(self.SDIV10, self.SDIV10), {})

    def test_an_interleaved_instruction_does_not_break_the_reading(self):
        """The measured false positive: cl schedules an unrelated load into
        the middle of the modulo sequence (`cdq / xor / mov ecx,[ebx+0x18] /
        sub / and`).  A sequence MATCHER called that a lost modulo; counting
        position-independent anchors does not."""
        scheduled = ["mov eax,DWORD PTR [esp+0x4]", "cdq", "xor eax,edx",
                     "mov ecx,DWORD PTR [ebx+0x18]", "sub eax,edx",
                     "and eax,0xf", "xor eax,edx", "sub eax,edx"]
        self.assertEqual(self._dec(self.SMOD16, scheduled), {})

    def test_the_mask_living_in_a_register_does_not_break_the_reading(self):
        """The second measured false positive: cl parks the constant 1 in EBX
        and writes `and eax,ebx`, so the modulus is not an immediate at all."""
        in_ebx = [a.replace("and eax,0xf", "and eax,ebx") for a in self.SMOD16]
        self.assertEqual(self._dec(self.SMOD16, in_ebx), {})

    def test_a_two_operand_imul_is_not_a_division(self):
        from rom1.walls.signscan import features
        self.assertEqual(features(_asm_lines(["imul eax,ecx,0x1c"]))["imul"], 0)

    def test_the_divisor_is_recovered_from_the_magic_and_the_shift(self):
        """Every pair is a real cl 5.0 emission; the same magic serves both
        signednesses for 9 and 30, which is why the MNEMONIC decides and the
        constant does not."""
        from rom1.walls.signscan import divisor
        for magic, shift, want in ((0x66666667, 2, 10), (0xcccccccd, 3, 10),
                                   (0x38e38e39, 1, 9), (0x88888889, 4, 30),
                                   (0x55555556, 0, 3), (0xaaaaaaab, 1, 3)):
            self.assertEqual(divisor(magic, shift), want, hex(magic))

    def test_a_swap_needs_both_directions(self):
        """Two more `sar` on one side and two more `shr` on the same side is
        a bigger function, not a signedness flip."""
        from rom1.walls.signscan import decisive, features
        big = features(_asm_lines(["sar eax,0x10", "sar eax,0x10",
                                   "shr ecx,0x10", "shr ecx,0x10"]))
        small = features(_asm_lines(["sar eax,0x10", "shr ecx,0x10"]))
        self.assertEqual(decisive(big, small), {})
        flip = features(_asm_lines(["shr eax,0x10", "shr eax,0x10"]))
        two = features(_asm_lines(["sar eax,0x10", "sar eax,0x10"]))
        self.assertTrue(decisive(two, flip))


class MemberOffsetControls(unittest.TestCase):
    """`walls offsetscan` says the two sides name a different FIELD.  Every
    control here is a measured false positive from building it: the sweep read
    119 rows before the relocation and scaled-index exclusions, 152 before the
    order-permutation suppression was widened from a positional window to the
    aligned run, 53 before the base-register agreement rule and 37 after the
    suppression stopped keying on the base register."""

    @staticmethod
    def _bad(ours, theirs, orefs=None, trefs=None):
        """Both sides are PADDED with `nop`s: a mismatch within EDGE of an
        aligned run's boundary is suppressed as an alignment slip, so a
        fixture that starts at the boundary would measure the padding rule
        rather than the reading under test."""
        from rom1.walls.offsetscan import EDGE, mismatches
        pad = ["nop"] * (EDGE + 1)
        shift = len(pad)
        bump = lambda d: {k + shift: v for k, v in (d or {}).items()}
        bad, _aligned, _total, swapped, _edged, _tiny = mismatches(
            _asm_lines(pad + ours + pad, bump(orefs)),
            _asm_lines(pad + theirs + pad, bump(trefs)))
        return bad, swapped

    def test_the_same_instruction_reading_a_different_field_fires(self):
        """The shape that built the sieve: CTriggerMgr::LoadTileArrivalFx read
        the puddle's gauge award at +0x68 where retail reads +0x64."""
        ours = ["mov ecx,DWORD PTR [ebx+0x68]", "push ecx", "call 0x0"]
        retail = ["mov edx,DWORD PTR [ebx+0x64]", "push edx", "call 0x0"]
        bad, _ = self._bad(ours, retail)
        self.assertEqual([(m["ours_disp"], m["retail_disp"]) for m in bad],
                         [(0x68, 0x64)])

    def test_a_base_subobject_copy_of_the_same_pointer_fires(self):
        """The other half of that row: CUserLogic::m_object at +0x10 against
        CWapX::m_wwdObject at +0x38.  They hold the same pointer, so nothing
        misbehaves and only the displacement shows it."""
        bad, _ = self._bad(["mov ebx,DWORD PTR [ebx+0x10]"],
                           ["mov ebx,DWORD PTR [ebx+0x38]"])
        self.assertEqual(len(bad), 1)

    def test_a_rotated_register_at_the_same_field_is_silent(self):
        bad, _ = self._bad(["mov ecx,DWORD PTR [ebx+0x64]"],
                           ["mov edx,DWORD PTR [ebx+0x64]"])
        self.assertEqual(bad, [])

    def test_two_accesses_in_the_opposite_order_are_suppressed(self):
        """Both sides touch BOTH fields, so the aligner paired them crosswise:
        a schedule question, storescan's channel, not a wrong member."""
        ours = ["mov eax,DWORD PTR [ebx+0x5c]", "mov edx,DWORD PTR [ebx+0x60]"]
        retail = ["mov eax,DWORD PTR [ebx+0x60]", "mov edx,DWORD PTR [ebx+0x5c]"]
        bad, swapped = self._bad(ours, retail)
        self.assertEqual(bad, [])
        self.assertEqual(swapped, 2)

    def test_the_suppression_ignores_the_base_register(self):
        """The permutation partner is often reached through a register the
        allocator rotated, so keying the suppression on (base, disp) asks a
        question about allocation instead of about the field."""
        ours = ["mov eax,DWORD PTR [ecx+0x5c]", "mov edx,DWORD PTR [ecx+0x60]"]
        retail = ["mov eax,DWORD PTR [ecx+0x60]", "mov edx,DWORD PTR [eax+0x5c]"]
        bad, _ = self._bad(ours, retail)
        self.assertEqual(bad, [])

    def test_different_base_registers_are_not_comparable(self):
        bad, _ = self._bad(["mov ecx,DWORD PTR [esi+0x22c]"],
                           ["mov ecx,DWORD PTR [eax+0x8]"])
        self.assertEqual(bad, [])

    def test_a_frame_slot_is_not_a_field(self):
        bad, _ = self._bad(["mov eax,DWORD PTR [esp+0x10]"],
                           ["mov eax,DWORD PTR [esp+0x18]"])
        self.assertEqual(bad, [])

    def test_ebp_is_a_field_without_a_frame_and_a_slot_with_one(self):
        """/O2 omits the frame pointer in 669 of 671 retail bodies, so in a
        frameless body `[ebp+N]` is a heap field."""
        bad, _ = self._bad(["mov eax,DWORD PTR [ebp+0x10]"],
                           ["mov eax,DWORD PTR [ebp+0x18]"])
        self.assertEqual(len(bad), 1)
        framed_ours = ["mov eax,DWORD PTR [ebp+0x10]"]
        framed_retail = ["mov eax,DWORD PTR [ebp+0x18]"]
        from rom1.walls.offsetscan import EDGE, mismatches
        prologue = ["push ebp", "mov ebp,esp"] + ["nop"] * (EDGE + 1)
        bad, _a, _t, _s, _e, _n = mismatches(
            _asm_lines(prologue + framed_ours + ["nop"] * (EDGE + 1)),
            _asm_lines(prologue + framed_retail + ["nop"] * (EDGE + 1)))
        self.assertEqual(bad, [])

    def test_a_relocated_operand_is_a_link_time_address(self):
        """`mov cl,BYTE PTR [eax+<index table>]` - the displacement is the
        table's address, which objdiff masks and the referent channel owns."""
        bad, _ = self._bad(["mov cl,BYTE PTR [eax+0x126c]"],
                           ["mov cl,BYTE PTR [eax+0x1348]"],
                           orefs={0: "$L1"}, trefs={0: "$L1"})
        self.assertEqual(bad, [])

    def test_a_relocated_immediate_leaves_the_displacement_readable(self):
        """A relocation sits in exactly ONE operand.  `mov DWORD PTR
        [this+N],OFFSET ??_7X@@6B@` - the vptr stamp - keeps a real member
        offset in the memory operand, so a vptr stamped into the wrong
        subobject moves two bytes and must not be dropped with the tables."""
        bad, _ = self._bad(["mov DWORD PTR [esi+0x70],0x0"],
                           ["mov DWORD PTR [esi+0x0],0x0"],
                           orefs={0: "??_7CObject@@6B@"},
                           trefs={0: "??_7CObject@@6B@"})
        self.assertEqual([(m["ours_disp"], m["retail_disp"]) for m in bad],
                         [(0x70, 0x0)])

    def test_a_line_referring_to_its_own_function_is_table_data(self):
        """The function's own index table decodes as instructions, and one of
        those can decode with an immediate operand.  A self-referent line is
        its own table whichever operand the relocation appears to own."""
        own = "?LoadTileArrivalFx@CTriggerMgr@@QAEHHHHH@Z"
        from rom1.walls.offsetscan import EDGE, mismatches
        pad = ["nop"] * (EDGE + 1)
        bad, _a, _t, _s, _e, _n = mismatches(
            _asm_lines(pad + ["mov DWORD PTR [eax+0x126c],0x0"] + pad,
                       {len(pad): own}),
            _asm_lines(pad + ["mov DWORD PTR [eax+0x1348],0x0"] + pad,
                       {len(pad): own}),
            own)
        self.assertEqual(bad, [])

    def test_a_run_too_short_to_corroborate_is_counted_apart(self):
        """A run of 2*EDGE instructions or fewer has no interior, so the EDGE
        rule discards it wholesale.  That is "nothing here can be
        corroborated", not "the pairing slipped at a boundary"."""
        from rom1.walls.offsetscan import EDGE, mismatches
        # one aligned instruction between two `replace` blocks: the whole run
        # is the boundary
        ours = ["mov eax,0x1", "mov ecx,DWORD PTR [esi+0x24]", "mov eax,0x2"]
        retail = ["mov eax,0x3", "mov ecx,DWORD PTR [esi+0x3c]", "mov eax,0x4"]
        bad, _a, _t, _s, edged, tiny = mismatches(_asm_lines(ours),
                                                  _asm_lines(retail))
        self.assertEqual(bad, [])
        self.assertEqual((edged, tiny), (0, 1))
        # a long run keeps the EDGE reading: same mismatch, real interior
        pad = ["nop"] * 8
        bad, _a, _t, _s, edged, tiny = mismatches(
            _asm_lines(["mov ecx,DWORD PTR [esi+0x24]"] + pad),
            _asm_lines(["mov ecx,DWORD PTR [esi+0x3c]"] + pad))
        self.assertEqual(bad, [])
        self.assertEqual((edged, tiny), (1, 0))

    def test_a_scaled_index_off_an_absolute_address_is_not_a_field(self):
        bad, _ = self._bad(["mov eax,DWORD PTR [ecx*4+0x127c]"],
                           ["mov eax,DWORD PTR [ecx*4+0x1358]"])
        self.assertEqual(bad, [])

    def test_an_indirect_jump_through_a_table_is_not_a_field(self):
        bad, _ = self._bad(["jmp DWORD PTR [ecx+0x127c]"],
                           ["jmp DWORD PTR [ecx+0x1358]"])
        self.assertEqual(bad, [])

    def test_a_clearing_run_reads_as_a_set_question_not_a_field_one(self):
        """A run of literally identical stores carries no information about
        which store pairs with which, so the alignment zips two lists.  The
        real question is which FIELDS each side clears."""
        from rom1.walls.offsetscan import EDGE, kind, mismatches
        pad = ["nop"] * (EDGE + 1)
        ours = pad + [f"mov DWORD PTR [esi+{off:#x}],edi"
                      for off in range(0x1b8, 0x1b8 + 6 * 4, 4)] + pad
        retail = pad + [f"mov DWORD PTR [esi+{off:#x}],edi"
                        for off in range(0x810, 0x810 + 6 * 4, 4)] + pad
        bad, _a, _t, _s, _e, _n = mismatches(_asm_lines(ours), _asm_lines(retail))
        self.assertEqual(kind(bad), "run")
        self.assertEqual(kind([]), "clean")


class VptrStampControls(unittest.TestCase):
    """`walls vptrscan` says a constructor stamped a vtable into the WRONG
    subobject, or stamped the wrong vtable.  Both defects move two bytes and
    no other channel reads them - `offsetscan` suppressed the whole line until
    2026-08-23 because the relocation made it look like a masked address."""

    @staticmethod
    def _stamp(disp, ref):
        """One `mov DWORD PTR [esi+disp],OFFSET ref`, as the sweep records it:
        (offset, displacement, base register, referent, frame?)."""
        return (0, disp, "esi", ref, False)

    @staticmethod
    def _cmp(ours, retail):
        from rom1.walls.vptrscan import compare
        key = ("u", "f")
        rows, _aligned, off, sym = compare({key: ours}, {key: retail}, {key})
        return rows, off, sym

    def test_a_vptr_in_the_wrong_subobject_fires(self):
        """An embedded polymorphic member's vptr one slot off: every virtual
        call through it dispatches on whatever the neighbouring field holds."""
        _rows, off, sym = self._cmp([self._stamp(0x70, "??_7CObject@@6B@")],
                                    [self._stamp(0x74, "??_7CObject@@6B@")])
        self.assertEqual((off, sym), (1, 0))

    def test_the_wrong_vtable_at_the_right_offset_fires(self):
        """The object's dynamic type is another class, so every slot resolves
        elsewhere.  Read from the DISPLACEMENT-keyed alignment, because the
        referent-keyed one cannot see a defect in its own key."""
        _rows, off, sym = self._cmp([self._stamp(0, "??_7CObject@@6B@")],
                                    [self._stamp(0, "??_7CWwdGridIter@@6B@")])
        self.assertEqual((off, sym), (0, 1))

    def test_identical_stamps_are_silent(self):
        rows, off, sym = self._cmp([self._stamp(0x70, "??_7CObject@@6B@")],
                                   [self._stamp(0x70, "??_7CObject@@6B@")])
        self.assertEqual((rows, off, sym), ([], 0, 0))

    def test_a_stamp_COUNT_divergence_withholds_rather_than_guesses(self):
        """THE headline control.  cl inlines a member ctor on one side only,
        so one side has an extra stamp - four live rows are exactly that.
        Keying an alignment on a sequence that is not the same LENGTH re-pairs
        the neighbours and invents defects: re-pointing ONE relocation in a
        real object produced two wrong offsets that were not there."""
        ours = [self._stamp(0, "??_7CMovingLogic@@6B@"),
                self._stamp(0, "??_7CGruntCoordList@@6B@"),
                self._stamp(0, "??_7CGrunt@@6B@")]
        retail = [self._stamp(0, "??_7CMovingLogic@@6B@"),
                  self._stamp(0, "??_7CGrunt@@6B@")]
        rows, off, sym = self._cmp(ours, retail)
        self.assertEqual((off, sym), (0, 0))
        self.assertEqual(rows[0]["withheld"], ["offset", "vtable"])

    def test_a_frame_relative_stamp_is_framescans_channel(self):
        """A stack-constructed object's `[esp+N]` is a slot number, which is an
        output of cl's allocator, not a subobject offset."""
        _rows, off, sym = self._cmp([(0, 0x10, "esp", "??_7CFileMem@@6B@", True)],
                                    [(0, 0x24, "esp", "??_7CFileMem@@6B@", True)])
        self.assertEqual((off, sym), (0, 0))

    def test_the_backwards_direction_gives_the_same_verdict(self):
        ours = [self._stamp(0x70, "??_7CObject@@6B@")]
        retail = [self._stamp(0x74, "??_7CObject@@6B@")]
        self.assertEqual(self._cmp(ours, retail)[1:],
                         self._cmp(retail, ours)[1:])

    def test_the_backwards_decode_rejects_what_is_not_a_stamp(self):
        """`C7 /0` with mod=11 is a register destination and any other `reg`
        field is a different instruction; neither carries a member offset."""
        from rom1.walls.vptrscan import decode_store
        # C7 46 70 imm32 : mov DWORD PTR [esi+0x70],imm32
        self.assertEqual(decode_store(bytes.fromhex("c74670") + b"\0\0\0\0", 3),
                         ("esi", None, 0x70))
        # C7 C6 imm32 : mov esi,imm32 - a register destination
        self.assertIsNone(decode_store(bytes.fromhex("c7c6") + b"\0\0\0\0", 2))
        # B8 imm32 : mov eax,imm32 - materialized, stored later
        self.assertIsNone(decode_store(bytes.fromhex("b8") + b"\0\0\0\0", 1))

    @staticmethod
    def _slots(hexbytes):
        from rom1.walls.vptrscan import dispatches
        p = bytes.fromhex(hexbytes)
        return [d[3] for d in dispatches(p, 0, len(p), set(), {"esp"})]

    def test_an_indirect_dispatch_names_its_vtable_slot(self):
        """The companion reading: `mov eax,[ecx] / call DWORD PTR [eax+0x2c]`
        is slot 11, and one byte decides which virtual function runs.
        offsetscan drops every call/jmp line by construction, so nothing else
        reads it."""
        self.assertEqual(self._slots("8b01ff502c"), [0x2c])

    def test_a_register_call_and_an_absolute_call_have_no_slot(self):
        self.assertEqual(self._slots("ffd0"), [])
        self.assertEqual(self._slots("ff15aabbccdd"), [])

    def test_a_slot_displacement_is_a_pointer_index(self):
        """THE headline control for the byte scan: `ff` occurs inside other
        instructions' operands, and unfiltered the sweep read `call [reg+83]`
        and `call [reg+0x90909090]` as slots and reported three same-count
        'defects' that were every one a misalignment."""
        self.assertEqual(self._slots("ff5053"), [])
        self.assertEqual(self._slots("ff9090909090"), [])

    def test_the_two_sides_are_not_byte_symmetric(self):
        """Why every differing row is re-read off a DECODED stream. These are
        `CRezArchiveDir`'s destructor's own bytes at +0x9c: our base object has the
        `call rel32` displacement zeroed by its relocation, the delinked target
        resolves the SELF-call internally and leaves a negative one - and four
        `ff` bytes decode as `call DWORD PTR [edi+0xe8]`. That row is
        byte-identical to retail at 100.00 and still read as a retail-only
        slot 58."""
        #  mov ecx,edi / call <self> / push edi / call ??3@YAXPAX@Z
        self.assertEqual(self._slots("8bcf e800000000 57 e800000000"
                                     .replace(" ", "")), [])
        self.assertEqual(self._slots("8bcf e85fffffff 57 e800000000"
                                     .replace(" ", "")), [0xe8])


class ByValueAggregateControls(unittest.TestCase):
    """`walls aggscan` says a callee's parameter is ONE object where we
    declared scalars.  cl 5.0 hands an aggregate wider than a register by
    opening a hole and copying into it, and four `push`es is a different
    shape - which is how `AddToList3` was caught taking a level record's rect
    as four `i32`."""

    @staticmethod
    def _holes(hexbytes, rel=None):
        from rom1.walls.aggscan import holes
        payload = bytes.fromhex(hexbytes)
        return holes(payload, 0, len(payload), rel or {})

    #: sub esp,0x10 / mov ecx,esp / mov [ecx],0 / mov [ecx+4],eax
    #: / mov [ecx+8],eax / mov [ecx+0xc],eax / call / ret
    BLOCK = "83ec108bccc70100000000894104894108894 10ce800000000c3".replace(" ", "")

    def test_a_by_value_block_fires(self):
        self.assertEqual([n for _o, n, _r, _c in self._holes(self.BLOCK)], [16])

    def test_four_pushes_of_four_scalars_are_silent(self):
        """The whole signature question: this is the shape a wrong declaration
        produces, and it must not read as a block."""
        self.assertEqual(self._holes("6a006a006a006a00e800000000c3"), [])

    def test_a_reservation_nothing_is_copied_into_is_the_frame(self):
        """THE headline control.  framescan owns the prologue reservation.
        Testing for the COPIES rather than for position is what let the sweep
        keep six callees whose only block sits before the first call."""
        self.assertEqual(self._holes("83ec108bcc33c0e800000000c3"), [])

    def test_a_non_dword_reservation_is_a_byte_misalignment(self):
        """`83 EC 02` occurs inside the displacement of
        `mov DWORD PTR [ebx+0x2ec],0x1f401`.  cl never moves ESP by a
        non-dword amount, so the filter costs nothing."""
        self.assertEqual(self._holes("c783ec02000001f40100c3"), [])

    def test_the_callee_is_read_through_an_unconditional_jmp(self):
        """cl TAIL-MERGES the argument build: predecessors fill the hole and
        jump to one shared call.  Stopping at the first `call` byte named
        `CTriggerMgr::CellDispatch` for two blocks that jump to
        `CGrunt::PlaySound`."""
        from rom1.walls.aggscan import callee
        # jmp +5 over a junk `call` byte, landing on the real call
        payload = bytes.fromhex("eb05") + b"\xe8\0\0\0\0" + b"\xe8\0\0\0\0\xc3"
        self.assertEqual(callee(payload, 0, len(payload), {8: ("?Real@@YAXXZ", 20)}),
                         "?Real@@YAXXZ")


class AddressEscapeControls(unittest.TestCase):
    """`walls escapescan` says our source is missing an `&`.  Every control
    here is a measured FALSE POSITIVE from building it: the census read 51
    rows before the frame-register control, 15 before the callee key, 3 before
    the branch control and 5 after the convention and constructor controls."""

    @staticmethod
    def _esc(asms, refs=None):
        from rom1.walls.escapescan import escapes
        return escapes(_asm_lines(asms, refs))

    def test_esp_relative_address_reaching_a_call_is_an_escape(self):
        arg, _this = self._esc(["lea eax,[esp+0x10]", "push eax", "call 0x0"],
                               {2: "?Sink@@YAXPAH@Z"})
        self.assertEqual(arg["?Sink@@YAXPAH@Z"], 1)

    def test_ebp_is_a_value_register_without_an_ebp_prologue(self):
        """THE headline control.  /O2 omits the frame pointer in 669 of 671
        retail bodies, so `lea eax,[ebp+0x4]` is a field of whatever heap
        object EBP happens to hold.  Reading it as `&local` is what made the
        first census three times too big."""
        arg, _this = self._esc(["mov ebp,DWORD PTR ds:0x0",
                                "lea eax,[ebp+0x4]", "push eax", "call 0x0"],
                               {3: "?AddHead@CPtrList@@QAEPAXPAX@Z"})
        self.assertEqual(sum(arg.values()), 0)

    def test_ebp_counts_when_the_prologue_really_builds_a_frame(self):
        arg, _this = self._esc(["push ebp", "mov ebp,esp", "sub esp,0x10",
                                "lea eax,[ebp-0x4]", "push eax", "call 0x0"],
                               {5: "?Sink@@YAXPAH@Z"})
        self.assertEqual(arg["?Sink@@YAXPAH@Z"], 1)

    def test_a_push_the_branch_carries_away_is_not_this_calls_argument(self):
        """Retail's shared-return idiom pushes `&result` and JUMPS to a block
        the two arms share.  Attributing that push to the next call in linear
        order invented an escape in GetMapBaseName."""
        arg, _this = self._esc(["lea edx,[esp+0xc]", "push edx", "jmp 0x28",
                                "mov ecx,esi", "call 0x0"],
                               {4: "?Other@@QAEXXZ"})
        self.assertEqual(sum(arg.values()), 0)

    def test_ecx_is_a_receiver_only_at_a_thiscall_callee(self):
        """`_fopen`, `__imp__PtInRect@12` and `?Format@CString@@QAAXPBDZZ`
        (the `A` is __cdecl) never read ECX, so a frame address left in it is
        a leftover."""
        stream = ["lea ecx,[esp+0x10]", "call 0x0"]
        _arg, cdecl = self._esc(stream, {1: "_fopen"})
        self.assertEqual(sum(cdecl.values()), 0)
        _arg, varargs = self._esc(stream, {1: "?Format@CString@@QAAXPBDZZ"})
        self.assertEqual(sum(varargs.values()), 0)
        _arg, thiscall = self._esc(stream, {1: "?Empty@CString@@QAEXXZ"})
        self.assertEqual(thiscall["?Empty@CString@@QAEXXZ"], 1)

    def test_a_constructor_hands_the_same_address_back_in_eax(self):
        """Reusing the ctor's EAX and re-`lea`ing the slot are the same
        address, so the two spellings must not read as a source difference."""
        ctor = "??0ofstream@@QAE@PBDHH@Z"
        reuse, _ = self._esc(["lea ecx,[esp+0x40]", "call 0x0", "push eax",
                              "call 0x0"], {1: ctor, 3: "?Encode@C@@QAEXPAX@Z"})
        relea, _ = self._esc(["lea ecx,[esp+0x40]", "call 0x0",
                              "lea edx,[esp+0x40]", "push edx", "call 0x0"],
                             {1: ctor, 4: "?Encode@C@@QAEXPAX@Z"})
        self.assertEqual(reuse["?Encode@C@@QAEXPAX@Z"],
                         relea["?Encode@C@@QAEXPAX@Z"])

    def test_a_non_constructor_return_is_not_a_frame_address(self):
        """The rule above was first written for EVERY call, which promptly
        called `CString::GetBuffer`'s heap pointer a frame address."""
        arg, _this = self._esc(["lea ecx,[esp+0x18]", "call 0x0", "push eax",
                                "call 0x0"],
                               {1: "?GetBuffer@CString@@QAEPADH@Z",
                                3: "??6ostream@@QAEAAV0@E@Z"})
        self.assertEqual(arg["??6ostream@@QAEAAV0@E@Z"], 0)

    def test_only_an_exclusive_delta_is_reported(self):
        """A shared callee whose count merely differs is cross-jump merge
        degree - the same caveat aggregate-copies carries."""
        from collections import Counter

        from rom1.walls.escapescan import exclusive
        merged = exclusive(Counter({"??1CString@@QAE@XZ": 12}),
                           Counter({"??1CString@@QAE@XZ": 3}))
        self.assertEqual(merged, {})
        real = exclusive(Counter({"?Width@CRect@@QBEHXZ": 0}),
                         Counter({"?Width@CRect@@QBEHXZ": 5}))
        self.assertEqual(real, {"?Width@CRect@@QBEHXZ": (0, 5)})


class DeclinedMemoryOptimizationControls(unittest.TestCase):
    """`walls reloadscan` claims a repeated load is a source re-read.  It is
    only that if the repetition really straddles the thing that forbids the
    optimization, so each channel's boundary is controlled here."""

    @staticmethod
    def _chan(asms, refs=None):
        from rom1.walls.reloadscan import channels
        return channels(_asm_lines(asms, refs))

    def test_a_second_load_with_a_call_between_is_a_reload(self):
        across, _loop, _shape = self._chan(
            ["mov eax,DWORD PTR [esi+0x6c]", "call 0x0",
             "mov eax,DWORD PTR [esi+0x6c]"], {1: "?Step@@YAXXZ"})
        self.assertEqual(across["+0x6c"], 1)

    def test_a_second_load_with_no_call_between_is_not(self):
        """cl keeps a value in a register across straight-line code, so two
        loads of one displacement with nothing between them is scheduling."""
        across, _loop, _shape = self._chan(
            ["mov eax,DWORD PTR [esi+0x6c]", "add eax,0x1",
             "mov ecx,DWORD PTR [esi+0x6c]"])
        self.assertEqual(sum(across.values()), 0)

    def test_a_store_is_not_a_read(self):
        across, _loop, _shape = self._chan(
            ["mov DWORD PTR [esi+0x6c],eax", "call 0x0",
             "mov DWORD PTR [esi+0x6c],ecx"], {1: "?Step@@YAXXZ"})
        self.assertEqual(sum(across.values()), 0)

    def test_lea_computes_an_address_and_reads_nothing(self):
        across, _loop, _shape = self._chan(
            ["lea eax,[esi+0x6c]", "call 0x0", "lea ecx,[esi+0x6c]"],
            {1: "?Step@@YAXXZ"})
        self.assertEqual(sum(across.values()), 0)

    def test_the_loop_channel_counts_only_the_body(self):
        _across, loop, shape = self._chan(
            ["mov eax,DWORD PTR [esi+0x10]", "mov ecx,DWORD PTR [esi+0x14]",
             "inc edx", "jne 0x4"])
        self.assertEqual(shape["loops"], 1)
        self.assertEqual(loop["+0x14"], 1)
        self.assertEqual(loop["+0x10"], 0)      # hoisted above the head

    def test_a_relocated_backward_branch_leaves_the_function(self):
        _across, _loop, shape = self._chan(
            ["mov eax,DWORD PTR [esi+0x10]", "jmp 0x0"],
            {1: "?Other@@YAXXZ"})
        self.assertEqual(shape["loops"], 0)

    def test_the_index_channel_separates_a_walk_from_a_subscript(self):
        _a, _l, walk = self._chan(["mov eax,DWORD PTR [esi]", "add esi,0x4",
                                   "dec ecx", "jne 0x0"])
        _a, _l, index = self._chan(["mov eax,DWORD PTR [esi+edx*4]", "inc edx",
                                    "dec ecx", "jne 0x0"])
        self.assertEqual((walk["stride"], walk["scaled"]), (1, 0))
        self.assertEqual((index["stride"], index["scaled"]), (0, 1))

    def test_an_array_element_read_carries_no_member_key(self):
        """`[base+idx*S+D]`'s displacement is a base offset the two sides fold
        differently the moment their addressing shape differs.
        `ClaimTilesAround` reads `[ecx+eax*1-0x4]` where retail reads
        `[base+idx*4]` - one field, keys `-0x4` and `+0x0` - and reported six
        exclusives that are one strength-reduction difference.  That belongs
        to the `iv` channel, which still sees it as scaled 2 against 21."""
        _across, _loop, shape = self._chan(
            ["mov ecx,DWORD PTR [ecx+eax*1-0x4]", "call 0x0",
             "mov edx,DWORD PTR [ecx+eax*1-0x4]"], {1: "?Step@@YAXXZ"})
        self.assertEqual(sum(_across.values()), 0)
        self.assertEqual(self._chan(["mov ecx,DWORD PTR [esi+eax*4]"])[2]
                         ["scaled"], 0)   # outside a loop it is only shape

    def test_a_frame_pointer_body_drops_its_frame_slots(self):
        """The other two of 671: an EBP prologue makes `[ebp-N]` a local, and
        a frame offset is not comparable across sides."""
        framed = ["push ebp", "mov ebp,esp", "mov eax,DWORD PTR [ebp-0x18]",
                  "call 0x0", "mov ecx,DWORD PTR [ebp-0x18]"]
        flat = ["mov esi,ecx", "mov eax,DWORD PTR [ebp-0x18]", "call 0x0",
                "mov ecx,DWORD PTR [ebp-0x18]"]
        self.assertEqual(sum(self._chan(framed, {3: "?S@@YAXXZ"})[0].values()), 0)
        self.assertEqual(self._chan(flat, {2: "?S@@YAXXZ"})[0]["-0x18"], 1)

    def test_a_uniformly_shifted_base_is_not_a_source_difference(self):
        """The measured false positive, and one a byte-identical control set
        CANNOT express: `CNetSession::Verify` is PROVEN at 100.00 and still
        reports six exclusives, because ours reads `[esi-0x14]/[esi-0x10]/
        [esi-0xc]` where retail reads `[esi-0x4]/[esi+0x4]/[esi+0x10]` - the
        same three fields under a base cl folded 0x10 away."""
        from collections import Counter

        from rom1.walls.reloadscan import base_fold
        ours = Counter({"-0x14": 1, "-0x10": 2, "-0xc": 1})
        retail = Counter({"-0x4": 1, "+0x0": 2, "+0x4": 1})
        self.assertEqual(base_fold(ours, retail), 0x10)
        self.assertEqual(base_fold(ours, ours), 0)

    def test_a_real_difference_is_not_called_a_base_fold(self):
        """The other direction: when the two sides agree on their keys and
        differ only in COUNT, no shift explains it better than none."""
        from collections import Counter

        from rom1.walls.reloadscan import base_fold
        ours = Counter({"+0x64": 4, "+0x68": 4, "+0x6c": 4, "+0x8": 12})
        retail = Counter({"+0x64": 1, "+0x68": 1, "+0x6c": 1, "+0x8": 16})
        self.assertEqual(base_fold(ours, retail), 0)

    def test_the_exclusive_floor_rejects_a_single_touch(self):
        from collections import Counter

        from rom1.walls.reloadscan import exclusive
        self.assertEqual(exclusive(Counter({"+0x8": 1}), Counter()), {})
        self.assertEqual(exclusive(Counter({"+0x8": 2}), Counter()),
                         {"+0x8": (2, 0)})
        self.assertEqual(exclusive(Counter({"+0x8": 5}), Counter({"+0x8": 4})),
                         {})


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        prog="rom1 verify selftest", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="name every control as it runs")
    ap.add_argument("-k", dest="patterns", action="append", default=[],
                    help="run only controls whose name contains this "
                         "substring (repeatable; comma-separated also works)")
    a = ap.parse_args(list(argv or []))
    verbosity = 2 if a.verbose else 1
    loader = unittest.TestLoader()
    wanted = [p.strip() for spec in a.patterns for p in spec.split(",")
              if p.strip()]
    if wanted:
        loader.testNamePatterns = [f"*{p}*" for p in wanted]
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
