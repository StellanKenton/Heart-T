"""Check RR filtering and beat-to-beat heart-rate calculations."""

import unittest

import numpy as np

from data import EcgData, _calculate_rates, _detect_r_peaks


class RateCalculationTests(unittest.TestCase):
    def test_isolated_short_interval_is_rejected(self):
        intervals, rates, average = _calculate_rates(np.array([0, 1, 2, 2.4, 3.4, 4.4]))
        np.testing.assert_allclose(intervals, [1, 1, 0.4, 1, 1])
        self.assertTrue(np.isnan(rates[2]))
        np.testing.assert_allclose(rates[[0, 1, 3, 4]], 60)
        self.assertAlmostEqual(average, 60)

    def test_implausibly_long_interval_is_rejected(self):
        _, rates, average = _calculate_rates(np.array([0, 1, 2, 4.5, 5.5, 6.5]))
        self.assertTrue(np.isnan(rates[2]))
        self.assertAlmostEqual(average, 60)

    def test_sustained_rate_change_is_preserved(self):
        _, rates, average = _calculate_rates(np.array([0, 1, 2, 2.7, 3.4, 4.1, 4.8]))
        self.assertTrue(np.all(np.isfinite(rates)))
        np.testing.assert_allclose(rates[2:], 60 / 0.7)
        self.assertAlmostEqual(average, 60 / (4.8 / 6))

    def test_no_rr_interval_has_no_heart_rate(self):
        intervals, rates, average = _calculate_rates(np.array([0.0]))
        self.assertEqual(intervals.size, 0)
        self.assertEqual(rates.size, 0)
        self.assertIsNone(average)


class BeatMeasurementTests(unittest.TestCase):
    def test_r_detection_tracks_sharp_peaks_through_baseline_drift(self):
        times = np.arange(4000) / 500
        signal = 250 * times + 350 * np.sin(2 * np.pi * 0.18 * times)
        signal += 12000 * np.exp(-(times / 0.025) ** 2)
        expected = np.arange(0.8, 7.4, 0.7)
        for r in expected:
            signal += 4500 * np.exp(-((times - r) / 0.012) ** 2)
            signal -= 1900 * np.exp(-((times - r - 0.03) / 0.012) ** 2)
            signal += 900 * np.exp(-((times - r - 0.23) / 0.07) ** 2)
        np.testing.assert_allclose(times[_detect_r_peaks(signal)], expected, atol=0.006)

    def test_click_selects_one_beat_and_measures_q_s_qrs(self):
        times = np.arange(1500) / 500
        shape_times = np.array([0, 0.94, 0.96, 0.98, 1.00, 1.02, 1.04,
                                1.06, 1.08, 1.10, 1.12, 1.14, 3.0])
        shape_values = np.array([0, 0, -2, -2, 0, 4, 10, 4, 0, -2, -2, 0, 0])
        signal = np.interp(times, shape_times, shape_values)
        data = EcgData(times, signal, signal, np.array([520]), np.array([]),
                       np.array([]), None)

        beat = data.beat_near(1.06)
        self.assertIsNotNone(beat)
        self.assertLessEqual(times[beat.start], 0.75)
        self.assertGreaterEqual(times[beat.stop - 1], 1.35)
        self.assertAlmostEqual((times[beat.q_end] - times[beat.q_onset]) * 1000, 60, delta=8)
        self.assertAlmostEqual((times[beat.s_end] - times[beat.s_onset]) * 1000, 60, delta=8)
        self.assertAlmostEqual((times[beat.qrs_end] - times[beat.qrs_onset]) * 1000, 200, delta=8)
        self.assertIsNone(data.beat_near(1.30))

    def test_missing_q_uses_r_onset_for_qrs_width(self):
        times = np.arange(1000) / 500
        signal = np.interp(times, [0, 0.98, 1.00, 1.04, 1.08, 1.10, 1.12, 2],
                           [0, 0, 2, 10, 0, -2, 0, 0])
        data = EcgData(times, signal, signal, np.array([520]), np.array([]),
                       np.array([]), None)
        beat = data.beat_near(1.04)
        self.assertIsNone(beat.q_onset)
        self.assertIsNotNone(beat.qrs_onset)
        self.assertIsNotNone(beat.s_end)
        self.assertLess(beat.qrs_onset, beat.r)

    def test_local_widths_survive_sloping_baseline(self):
        times = np.arange(1500) / 500
        signal = np.interp(times, [0, 0.90, 0.93, 0.96, 0.97, 0.985, 1,
                                   1.02, 1.03, 1.06, 1.08, 1.12, 3],
                           [0, 0, -450, -450, 0, 1000, 4000,
                            0, -1500, -1500, 0, 0, 0]) + 300 * times
        data = EcgData(times, signal, signal, np.array([500]), np.array([]),
                       np.array([]), None)
        beat = data.beat_near(1)
        self.assertIsNotNone(beat.q_onset)
        self.assertIsNotNone(beat.s_end)
        self.assertAlmostEqual((times[beat.qrs_end] - times[beat.qrs_onset]) * 1000,
                               180, delta=10)

    def test_distant_pre_r_notch_is_not_counted_as_q(self):
        times = np.arange(1000) / 500
        signal = np.interp(times, [0, 0.84, 0.87, 0.89, 0.91, 0.925, 0.94,
                                   0.96, 0.98, 1, 1.02, 1.03, 1.08, 1.1, 2],
                           [0, 0, 2000, 300, 100, 200, 300,
                            600, 2000, 5000, 0, -2000, 0, 0, 0])
        data = EcgData(times, signal, signal, np.array([500]), np.array([]),
                       np.array([]), None)
        beat = data.beat_near(1)
        self.assertIsNone(beat.q_onset)
        self.assertIsNotNone(beat.qrs_end)


if __name__ == "__main__":
    unittest.main()
