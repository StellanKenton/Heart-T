"""Verify shared fitting, manual range validation and display pause semantics."""
import json
import tempfile
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtTest import QSignalSpy
from domain.analysis import SampleStore
from domain.protocol import FrameParser
from domain.recording import RawCsvRecorder
from hmi.backend import Backend
from test_receiver import frame


class AxisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.store = SampleStore()
        with patch('hmi.backend.available_ports', return_value=[]):
            self.backend = Backend(type('Communication', (), {'status': lambda self: '未连接'})(),
                                   self.store)
        self.backend.timer.stop()
        self.parser = FrameParser()

    def publish(self, pairs):
        frames = self.parser.feed(frame(self.parser.frames, pairs))
        self.store.publish(self.parser, frames)
        self.backend.poll()

    def test_default_channel_matches_vendor_board(self):
        self.assertEqual(self.backend.data['ecgChannel'], 1)

    def test_fit_uses_both_channels_with_padding(self):
        self.publish([(-100, 500)] * 5)
        self.assertEqual(self.backend.axis['lower'], -160)
        self.assertEqual(self.backend.axis['upper'], 560)

    def test_manual_range_persists_until_fit_enabled(self):
        self.assertTrue(self.backend.setManualRange('-20', '100'))
        self.publish([(-100, 500)] * 5)
        self.assertFalse(self.backend.axis['autoFit'])
        self.assertEqual((self.backend.axis['lower'], self.backend.axis['upper']), (-20, 100))
        self.backend.setAutoFit(True)
        self.assertEqual((self.backend.axis['lower'], self.backend.axis['upper']), (-160, 560))

    def test_invalid_limits_leave_range_unchanged(self):
        original = self.backend.axis.copy()
        for lower, upper in [('abc', '10'), ('nan', '10'), ('0', 'inf'),
                             ('5', '5'), ('10', '-10'), ('-1e308', '1e308')]:
            self.assertFalse(self.backend.setManualRange(lower, upper))
            self.assertEqual(self.backend.axis, original)

    def test_constant_data_and_pause(self):
        self.publish([(42, 42)] * 5)
        self.assertEqual((self.backend.axis['lower'], self.backend.axis['upper']), (41, 43))
        self.backend.setPaused(True)
        self.publish([(-100, 500)] * 5)
        self.assertEqual((self.backend.axis['lower'], self.backend.axis['upper']), (41, 43))
        self.backend.setPaused(False)
        self.backend.poll()
        self.assertEqual((self.backend.axis['lower'], self.backend.axis['upper']), (-160, 560))

    def test_waveforms_are_separate_from_scalar_status(self):
        self.publish([(-100, 500)] * 5)
        self.assertNotIn('ch1', self.backend.data)
        self.assertNotIn('ch2', self.backend.data)
        self.assertEqual(json.loads(self.backend.waveforms),
                         dict(ch1=[-100] * 5, ch2=[500] * 5, ecg=[0.0] * 5))

    def test_ecg_mode_pause_and_invalid_selection(self):
        self.publish([(n * 100, 0) for n in range(5)])
        self.backend.setEcgMode(1)
        self.assertEqual(self.backend.data['ecgMode'], 1)
        self.assertEqual(json.loads(self.backend.waveforms)['ecg'],
                         self.store.snapshot(include_filtered=True)[3])
        self.backend.setEcgMode(5)
        self.assertEqual(self.backend.data['ecgMode'], 1)
        self.backend.setPaused(True)
        self.backend.setEcgMode(0)
        self.assertEqual(self.backend.data['ecgMode'], 1)

    def test_unchanged_fit_and_snapshot_do_not_notify(self):
        self.backend.poll()
        axis = QSignalSpy(self.backend.axisChanged)
        waves = QSignalSpy(self.backend.waveformsChanged)
        self.publish([(-100, 500)] * 5)
        self.assertEqual(axis.count(), 1)
        self.assertEqual(waves.count(), 1)
        self.publish([(-100, 500)] * 5)
        self.assertEqual(axis.count(), 1)
        self.assertEqual(waves.count(), 2)
        self.backend.poll()
        self.assertEqual(waves.count(), 2)
        revision = self.store.snapshot()[0]
        self.assertIsNone(self.store.snapshot(revision))

    def test_main_window_recording_controls_export_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder = RawCsvRecorder(directory)
            with patch('hmi.backend.available_ports', return_value=[]):
                backend = Backend(self.backend.communication, self.store, recorder=recorder)
            backend.timer.stop()
            self.assertTrue(backend.startRecording())
            recorder.publish(None, [(7, [(12, -34)])])
            backend.poll()
            self.assertEqual(backend.recordingData['sampleCount'], 1)
            self.assertTrue(backend.stopRecording())
            destination = Path(directory) / 'export.csv'
            self.assertTrue(backend.saveCsv(QUrl.fromLocalFile(str(destination))))
            self.assertTrue(destination.is_file())
            self.assertFalse(backend.recordingData['canSave'])


if __name__ == '__main__':
    unittest.main()
