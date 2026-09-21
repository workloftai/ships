import unittest
from widget import apply_discount, line_total
class TestDiscount(unittest.TestCase):
    def test_no_discount(self):
        self.assertEqual(apply_discount(100, 0), 100)
    def test_discount_applies(self):
        # 10% off 100 should be 90
        self.assertEqual(apply_discount(100, 10), 90)
    def test_line_total(self):
        self.assertEqual(line_total(2, 100, 10), 180)
if __name__ == "__main__":
    unittest.main(verbosity=2)
