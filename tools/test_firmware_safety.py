"""Regression tests for the real 16 MB boot failure and Flash overflow gates."""
import struct
import unittest
from validate_firmware import ROOT, check_image, read_partitions, validate_partitions


class SafetyTests(unittest.TestCase):
    def test_reviewed_ota_layout(self):
        rows = read_partitions(ROOT / "partitions-8mb.csv")
        self.assertEqual(max(p["offset"] + p["size"] for p in rows), 0x800000)

    def test_overflow_rejected(self):
        rows = read_partitions(ROOT / "partitions-8mb.csv")
        rows[-1]["size"] += 0x1000
        with self.assertRaisesRegex(ValueError, "exceeds physical"):
            validate_partitions(rows)

    def test_overlap_rejected(self):
        rows = read_partitions(ROOT / "partitions-8mb.csv")
        rows[-1]["offset"] -= 0x1000
        with self.assertRaisesRegex(ValueError, "overlap"):
            validate_partitions(rows)

    def test_16mb_header_rejected(self):
        data = bytearray(24)
        data[0], data[3] = 0xE9, 0x40
        struct.pack_into("<H", data, 12, 9)
        with self.assertRaisesRegex(ValueError, "8 MB"):
            check_image(data, "test")
        data[3] = 0x30
        self.assertEqual(check_image(data, "test")["chip_id"], 9)

    def test_nvs_page_count_preserved(self):
        rows = read_partitions(ROOT / "partitions-8mb.csv")
        rows[0]["size"] = 0x6000
        with self.assertRaisesRegex(ValueError, "NVS boundary"):
            validate_partitions(rows)

    def test_wrong_target_rejected(self):
        data = bytearray(24)
        data[0], data[3] = 0xE9, 0x30
        with self.assertRaisesRegex(ValueError, "ESP32-S3"):
            check_image(data, "test")


if __name__ == "__main__":
    unittest.main()
