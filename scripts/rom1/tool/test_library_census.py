import unittest

from rom1.tool.library_census import match_confidence, mask_bytes, trim_padding


class LibraryCensusTest(unittest.TestCase):
    def test_mask_is_site_local(self):
        self.assertEqual(mask_bytes(bytes(range(10)), {2, 8}),
                         bytes((0, 1, 0, 0, 0, 0, 6, 7, 0, 0)))

    def test_padding_trim_does_not_drop_real_zero_tail(self):
        self.assertEqual(trim_padding(b"\x5d\xc3\x90\x90"), b"\x5d\xc3")
        self.assertEqual(trim_padding(b"\xe9\0\0\0\0"), b"\xe9\0\0\0\0")

    def test_high_confidence_requires_a_bijection(self):
        self.assertEqual(match_confidence(1, 1),
                         ("HIGH", "bijective union-reloc-mask exact extent"))
        confidence, evidence = match_confidence(1, 126)
        self.assertEqual(confidence, "AMBIG")
        self.assertIn("126 retail extents", evidence)
        self.assertEqual(match_confidence(2, 1),
                         ("AMBIG", "collision retained"))


if __name__ == "__main__":
    unittest.main()
