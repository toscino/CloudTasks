"""
Unit tests for performance band calculation
"""
import unittest
from src.models.performance_reward import (
    compute_performance_band,
    band_cutoffs_for_goal,
    MIN_GOAL_FOR_BANDS,
)


class TestPerformanceBand(unittest.TestCase):
    def test_skip_low_goal(self):
        self.assertIsNone(compute_performance_band(100, MIN_GOAL_FOR_BANDS - 1))
        self.assertIsNone(compute_performance_band(0, 0))

    def test_below_goal(self):
        self.assertEqual(compute_performance_band(499, 500), 0)
        self.assertEqual(compute_performance_band(0, 500), 0)

    def test_top_band_at_two_x(self):
        self.assertEqual(compute_performance_band(1000, 500), 4)
        self.assertEqual(compute_performance_band(2000, 500), 4)

    def test_breakpoints_goal_500(self):
        """Goal 500 → bands at 500, 650, 800, 1000."""
        g = 500
        c = band_cutoffs_for_goal(g)
        self.assertEqual(c["band_1"], 650)
        self.assertEqual(c["band_2"], 800)
        self.assertEqual(c["two_x"], 1000)
        self.assertEqual(compute_performance_band(500, g), 1)
        self.assertEqual(compute_performance_band(649, g), 1)
        self.assertEqual(compute_performance_band(650, g), 2)
        self.assertEqual(compute_performance_band(799, g), 2)
        self.assertEqual(compute_performance_band(800, g), 3)
        self.assertEqual(compute_performance_band(999, g), 3)

    def test_scales_with_goal_100(self):
        g = 100
        c = band_cutoffs_for_goal(g)
        self.assertEqual(c["band_1"], 130)
        self.assertEqual(c["band_2"], 160)
        self.assertEqual(c["two_x"], 200)
        self.assertEqual(compute_performance_band(99, g), 0)
        self.assertEqual(compute_performance_band(100, g), 1)
        self.assertEqual(compute_performance_band(129, g), 1)
        self.assertEqual(compute_performance_band(130, g), 2)
        self.assertEqual(compute_performance_band(200, g), 4)


if __name__ == "__main__":
    unittest.main()
