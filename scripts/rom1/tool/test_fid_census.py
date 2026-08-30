from __future__ import annotations

import unittest
from types import SimpleNamespace

from rom1.tool.fid_census import _classify, _matches


class FakePe:
    def __init__(self, rva: int, payload: bytes):
        self.rva = rva
        self.payload = payload

    def read(self, rva: int, size: int) -> bytes | None:
        offset = rva - self.rva
        if offset < 0 or offset + size > len(self.payload):
            return None
        return self.payload[offset:offset + size]


def candidate(symbol: str, payload: bytes, reloc_sites=(), archive="TEST.LIB"):
    return SimpleNamespace(
        archive=archive, archive_hash="a" * 64, member=f"{symbol}.obj",
        member_hash="b" * 64, symbol=symbol, order=0, payload=payload,
        reloc_sites=frozenset(reloc_sites),
    )


class FidCensusTest(unittest.TestCase):
    def test_union_relocation_mask_ignores_only_relocation_operands(self):
        retail = bytes.fromhex("55 8b ec b8 11 22 33 44 68 aa bb cc dd c3")
        archive = bytes.fromhex("55 8b ec b8 99 88 77 66 68 01 02 03 04 c3")
        item = candidate("masked", archive, (4,))
        fixed = tuple(index for index in range(len(archive))
                      if not 4 <= index < 8)
        self.assertTrue(_matches(FakePe(0x1000, retail), 0x1000, item,
                                 fixed, [0x1009]))
        changed = bytearray(retail)
        changed[2] ^= 1
        self.assertFalse(_matches(FakePe(0x1000, bytes(changed)), 0x1000,
                                  item, fixed, [0x1009]))

    def test_high_confidence_requires_unique_identity_and_rva(self):
        body = bytes(range(24))
        first = candidate("first", body)
        second = candidate("second", body)
        fixed = tuple(range(len(body)))
        rows = _classify([
            ({"rva": 0x1000}, [(first, fixed, len(body)),
                               (second, fixed, len(body))]),
        ])
        self.assertEqual(rows[0]["confidence"], "AMBIG")
        self.assertEqual(rows[0]["rva_identity_count"], "2")

    def test_control_archive_collision_downgrades_candidate_only_report(self):
        body = bytes(range(24))
        wanted = candidate("gztell", body, archive="ZLIB.LIB")
        control = candidate("_ismbbkalnum", body, archive="LIBCMT.LIB")
        fixed = tuple(range(len(body)))
        rows = _classify(
            [({"rva": 0x162940}, [(wanted, fixed, len(body)),
                                    (control, fixed, len(body))])],
            include_identities={(wanted.archive, wanted.member,
                                 wanted.symbol, wanted.order)})
        self.assertEqual([(row["name"], row["confidence"]) for row in rows],
                         [("gztell", "AMBIG")])
        self.assertEqual(rows[0]["rva_identity_count"], "2")

    def test_all_match_report_retains_each_candidate_identity(self):
        body = bytes(range(24))
        first = candidate("first", body)
        second = candidate("second", body)
        fixed = tuple(range(len(body)))
        rows = _classify(
            [({"rva": 0x1000}, [(first, fixed, len(body)),
                                  (second, fixed, len(body))])],
            all_matches=True)
        self.assertEqual([row["name"] for row in rows], ["first", "second"])
        self.assertTrue(all(row["confidence"] == "AMBIG" for row in rows))


if __name__ == "__main__":
    unittest.main()
