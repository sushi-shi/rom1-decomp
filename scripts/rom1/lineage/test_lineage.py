from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from rom1.lineage import discovery, ledger


def row(**changes):
    base = {
        "id": "candidate-one",
        "wave": "1",
        "source_commit": "845119c",
        "source_blob": "a" * 40,
        "source_path": "libs/example/example.cpp",
        "source_symbol": "*",
        "rom1_symbol": "CExample::Run",
        "rva": "0x1234",
        "module": "Example",
        "relation": "direct-family",
        "decision": "pending",
        "reason": "",
        "retail_evidence": "",
        "landed_commit": "",
    }
    base.update(changes)
    return base


class LedgerTests(unittest.TestCase):
    def test_non_adoption_requires_controlled_reason_and_retail_evidence(self):
        errors = ledger.validate_rows([row(decision="do-not-take")])
        self.assertTrue(any("controlled reason" in error for error in errors))
        self.assertTrue(any("retail evidence" in error for error in errors))

    def test_dash_is_an_explicit_empty_landed_commit(self):
        rejected = row(
            decision="do-not-take",
            reason="no-retail-owner",
            retail_evidence="no compatible retail owner",
            landed_commit="-",
        )
        self.assertFalse(ledger.validate_rows([rejected]))

    def test_complete_mode_rejects_pending_rows(self):
        self.assertFalse(ledger.validate_rows([row()]))
        self.assertTrue(any("pending decision remains" in error
                            for error in ledger.validate_rows([row()], complete=True)))

    def test_file_level_claim_covers_an_entity_discovery_for_same_blob(self):
        candidate = {
            "source_commit": "845119c",
            "source_blob": "a" * 40,
            "source_path": "libs/example/example.cpp",
            "source_symbol": "CExample::Run",
        }
        self.assertTrue(ledger.covered(candidate, [row()]))
        candidate["source_blob"] = "b" * 40
        self.assertFalse(ledger.covered(candidate, [row()]))

    def test_queue_is_dependency_wave_then_historical_max(self):
        rows = [row(id="late", wave="2", rva=""), row(id="early", wave="1", rva="")]
        self.assertEqual([item["id"] for item in ledger.queue_rows(rows)], ["early", "late"])


class DiscoveryTests(unittest.TestCase):
    def test_git_reader_preserves_legacy_windows_bytes(self):
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="legacy \x92 source", stderr=""
        )
        with mock.patch("subprocess.run", return_value=completed) as run:
            self.assertEqual(discovery._git(discovery.SRC, "show", "rev:path"),
                             "legacy \x92 source")
        self.assertEqual(run.call_args.kwargs["encoding"], "latin-1")

    def test_normalized_clone_ignores_identifier_and_literal_spelling(self):
        left = " ".join(f"if (value{i}) result{i} += {i};" for i in range(40))
        right = " ".join(f"if (other{i}) output{i} += {i + 100};" for i in range(40))
        self.assertTrue(discovery.structural_clone(left, right))

    def test_short_common_control_flow_is_not_a_clone(self):
        self.assertFalse(discovery.structural_clone("if (x) return 1;", "if (y) return 2;"))

    def test_different_api_vocabulary_is_not_a_clone(self):
        left = " ".join(f"WidgetType::ApplyAlpha(value{i});" for i in range(80))
        right = " ".join(f"FontEngine::LoadGlyph(other{i});" for i in range(80))
        self.assertFalse(discovery.structural_clone(left, right))

    def test_known_cross_game_entity_requires_its_landmarks(self):
        text = "NetStart_FillServiceList LB_ADDSTRING LB_SETITEMDATA GetServiceList"
        markers = discovery.ENTITY_MARKERS["NetStart_FillServiceList"]
        self.assertTrue(all(marker in text for marker in markers))
        self.assertFalse(all(marker in text.replace("GetServiceList", "") for marker in markers))


if __name__ == "__main__":
    unittest.main()
