import unittest

import main


class HmoTests(unittest.TestCase):
    def setUp(self):
        self.rows = main.load("sample_claims.csv")

    def test_outlier(self):
        self.assertIn("Prime Care Hospital", main.outliers(main.provider_kpis(self.rows)))

    def test_duplicate(self):
        self.assertEqual(main.duplicates(self.rows), [("C1003", "C1009")])


if __name__ == "__main__":
    unittest.main()
