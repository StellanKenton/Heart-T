"""Stream every parsed raw sample pair to a temporary CSV for later export."""
import csv
import logging
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


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
    """Thread-safe CSV spool receiving frames from the analysis worker."""

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
                tempPath=str(self._path) if self._path is not None else '',
            )

    def close(self):
        if self.snapshot()['recording']:
            self.stop()
        state = self.snapshot()
        if state['canSave']:
            LOG.warning('Unsaved recording retained at %s', state['tempPath'])
