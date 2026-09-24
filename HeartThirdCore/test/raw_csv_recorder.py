"""Standalone HMI for recording every received raw CH1/CH2 sample to CSV."""
import argparse
import csv
import logging
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock, Thread

from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.communication import CommunicationThread, available_ports
from domain.protocol import FrameParser
from domain.ringbuffer import RingBuffer


LOG = logging.getLogger(__name__)
SAMPLE_PERIOD_MS = 2
CSV_HEADER = (
    'record_type', 'sample_index', 'elapsed_ms', 'recorded_at', 'session',
    'frame_sequence', 'point_in_frame', 'ch1_raw', 'ch2_raw',
)


def iso_time(timestamp=None):
    """Return a local ISO-8601 timestamp with millisecond precision."""
    value = datetime.now(timezone.utc) if timestamp is None else timestamp
    return value.astimezone().isoformat(timespec='milliseconds')


class RawCsvRecorder:
    """Thread-safe CSV spool receiving parsed frames from the analysis worker."""

    def __init__(self, temporary_directory=None):
        self._lock = Lock()
        self._temporary_directory = temporary_directory
        self._file = None
        self._writer = None
        self._path = None
        self._recording = False
        self._can_save = False
        self._count = 0
        self._revision = 0
        self._session = 0
        self._latest = (0, 0)
        self._started_at = ''
        self._ended_at = ''
        self._saved_path = ''

    def start(self):
        with self._lock:
            if self._recording or self._can_save:
                return False
            handle = tempfile.NamedTemporaryFile(
                mode='w', encoding='utf-8-sig', newline='', suffix='.csv',
                prefix='heart_raw_', dir=self._temporary_directory, delete=False,
            )
            self._file = handle
            self._writer = csv.writer(handle, lineterminator='\n')
            self._path = Path(handle.name)
            self._writer.writerow(CSV_HEADER)
            self._count = 0
            self._session = 0
            self._latest = (0, 0)
            self._started_at = iso_time()
            self._ended_at = ''
            self._saved_path = ''
            self._writer.writerow(('start', '', 0, self._started_at, '', '', '', '', ''))
            self._recording = True
            self._revision += 1
            return True

    def stop(self):
        with self._lock:
            if not self._recording:
                return False
            self._ended_at = iso_time()
            elapsed = self._count * SAMPLE_PERIOD_MS
            self._writer.writerow(('end', '', elapsed, self._ended_at, '', '', '', '', ''))
            self._file.close()
            self._file = None
            self._writer = None
            self._recording = False
            self._can_save = True
            self._revision += 1
            return True

    def publish(self, parser, frames, reset=False):
        """Write each valid parsed sample; callable from the receiver worker."""
        del parser
        with self._lock:
            if reset:
                self._session += 1
            if not self._recording:
                return
            for sequence, samples in frames:
                for point, (ch1, ch2) in enumerate(samples):
                    elapsed = self._count * SAMPLE_PERIOD_MS
                    recorded_at = iso_time(datetime.fromtimestamp(
                        datetime.fromisoformat(self._started_at).timestamp() + elapsed / 1000,
                        timezone.utc,
                    ))
                    self._writer.writerow((
                        'sample', self._count, elapsed, recorded_at, self._session,
                        sequence, point, ch1, ch2,
                    ))
                    self._count += 1
                    self._latest = (ch1, ch2)
            if frames:
                self._revision += 1

    def save(self, destination):
        with self._lock:
            if not self._can_save or self._path is None:
                return False
            destination = Path(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self._path, destination)
            self._path.unlink()
            self._path = None
            self._saved_path = str(destination)
            self._can_save = False
            self._revision += 1
            return True

    def snapshot(self):
        with self._lock:
            return dict(
                revision=self._revision,
                recording=self._recording,
                canSave=self._can_save,
                sampleCount=self._count,
                latest1=self._latest[0],
                latest2=self._latest[1],
                startedAt=self._started_at,
                endedAt=self._ended_at,
                savedPath=self._saved_path,
            )

    def close(self):
        if self.snapshot()['recording']:
            self.stop()
        state = self.snapshot()
        if state['canSave'] and self._path is not None:
            LOG.warning('Unsaved recording retained at %s', self._path)


class RecorderAnalysisThread(Thread):
    """Decode ring-buffer bytes and forward complete frames to the recorder."""

    def __init__(self, ring, recorder, stop):
        super().__init__(name='csv-recorder-analysis')
        self.ring = ring
        self.recorder = recorder
        self.stop = stop

    def run(self):
        session = None
        parser = FrameParser()
        while not self.stop.is_set():
            current, data = self.ring.read()
            reset = current != session
            if reset:
                session, parser = current, FrameParser()
            if data or reset:
                self.recorder.publish(parser, parser.feed(data), reset)


class RecorderBackend(QObject):
    """GUI-thread bridge for TCP target selection and recorder controls."""

    updated = Signal()
    portsChanged = Signal()

    def __init__(self, communication, recorder):
        super().__init__()
        self.communication = communication
        self.recorder = recorder
        self._ports = []
        self._revision = -1
        self._data = recorder.snapshot()
        self._data['connectionStatus'] = '未连接'
        self._data['message'] = ''
        self.refreshPorts()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(50)

    @Property('QVariantList', notify=portsChanged)
    def ports(self):
        return self._ports

    @Property('QVariantMap', notify=updated)
    def data(self):
        return self._data

    @Property(str, constant=True)
    def suggestedFileName(self):
        return 'heart_raw_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.csv'

    @Slot()
    def refreshPorts(self):
        self._ports = available_ports()
        self.portsChanged.emit()

    @Slot(str)
    def connectPort(self, port):
        if port:
            self.communication.configure(port)

    @Slot()
    def disconnectPort(self):
        self.communication.configure(None)

    @Slot(result=bool)
    def startRecording(self):
        result = self.recorder.start()
        self._data['message'] = '正在记录每个双通道原始采样点' if result else '请先保存上一段记录'
        self.poll()
        return result

    @Slot(result=bool)
    def stopRecording(self):
        result = self.recorder.stop()
        self._data['message'] = '记录已结束，请保存 CSV' if result else '当前没有正在进行的记录'
        self.poll()
        return result

    @Slot(QUrl, result=bool)
    def saveCsv(self, url):
        path = url.toLocalFile()
        if not path:
            self._data['message'] = '保存路径无效'
            self.updated.emit()
            return False
        if not path.lower().endswith('.csv'):
            path += '.csv'
        try:
            result = self.recorder.save(path)
        except OSError as error:
            LOG.error('Cannot save CSV: %s', error)
            result = False
            self._data['message'] = f'保存失败：{error}'
        else:
            self._data['message'] = f'已保存：{path}' if result else '请先结束记录'
        self.poll()
        return result

    @Slot()
    def poll(self):
        snapshot = self.recorder.snapshot()
        connection_status = self.communication.status()
        changed = (snapshot['revision'] != self._revision
                   or connection_status != self._data.get('connectionStatus'))
        message = self._data.get('message', '')
        self._revision = snapshot['revision']
        self._data = snapshot
        self._data['connectionStatus'] = connection_status
        self._data['message'] = message
        if changed:
            self.updated.emit()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Heart-T 双通道原始数据 CSV 采集测试程序')
    parser.add_argument('--host', help='ESP32-S3 IP address or hostname')
    parser.add_argument('--quit-after', type=float, help='Exit after N seconds for smoke checks')
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
    QQuickStyle.setStyle('Basic')
    app = QGuiApplication([sys.argv[0]])
    app.setApplicationName('Heart-T Raw CSV Recorder')
    stop = Event()
    ring = RingBuffer()
    recorder = RawCsvRecorder()
    communication = CommunicationThread(ring, stop)
    analysis = RecorderAnalysisThread(ring, recorder, stop)
    backend = RecorderBackend(communication, recorder)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('backend', backend)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).with_suffix('.qml'))))
    if not engine.rootObjects():
        return 1
    if args.host:
        communication.configure(args.host)
    analysis.start()
    communication.start()
    if args.quit_after is not None:
        QTimer.singleShot(max(0, int(args.quit_after * 1000)), app.quit)
    try:
        return app.exec()
    finally:
        backend.timer.stop()
        stop.set()
        ring.close()
        communication.join()
        analysis.join()
        recorder.close()


if __name__ == '__main__':
    raise SystemExit(main())
