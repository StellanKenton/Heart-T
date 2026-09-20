"""Verify raw CSV recording includes boundaries and every sample pair."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from raw_csv_recorder import CSV_HEADER, RawCsvRecorder


class RawCsvRecorderTests(unittest.TestCase):
    def test_start_samples_end_and_save(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = RawCsvRecorder(directory)
            self.assertTrue(recorder.start())
            self.assertFalse(recorder.start())
            recorder.publish(None, [(17, [(1, -2), (3, -4)])], reset=True)
            recorder.publish(None, [(18, [(5, -6)])])
            self.assertTrue(recorder.stop())
            destination = Path(directory) / 'result.csv'
            self.assertTrue(recorder.save(destination))
            with destination.open(encoding='utf-8-sig', newline='') as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(tuple(rows[0]), CSV_HEADER)
            self.assertEqual([row['record_type'] for row in rows],
                             ['start', 'sample', 'sample', 'sample', 'end'])
            self.assertEqual([row['sample_index'] for row in rows[1:4]], ['0', '1', '2'])
            self.assertEqual([row['elapsed_ms'] for row in rows[1:4]], ['0', '2', '4'])
            self.assertEqual([(row['ch1_raw'], row['ch2_raw']) for row in rows[1:4]],
                             [('1', '-2'), ('3', '-4'), ('5', '-6')])
            self.assertEqual([row['frame_sequence'] for row in rows[1:4]],
                             ['17', '17', '18'])
            self.assertEqual(recorder.snapshot()['savedPath'], str(destination))
            self.assertEqual(sorted(path.name for path in Path(directory).iterdir()),
                             ['result.csv'])

    def test_cannot_save_before_stop_or_overwrite_unsaved_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = RawCsvRecorder(directory)
            self.assertFalse(recorder.save(Path(directory) / 'early.csv'))
            self.assertTrue(recorder.start())
            self.assertTrue(recorder.stop())
            self.assertFalse(recorder.start())


if __name__ == '__main__':
    unittest.main()
