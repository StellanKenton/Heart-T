"""GUI-thread bridge; poll worker snapshots without queuing every sample."""
import json
import math

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from domain.communication import available_ports


class Backend(QObject):
    updated = Signal()
    portsChanged = Signal()
    axisChanged = Signal()
    waveformsChanged = Signal()
    consoleChanged = Signal()

    def __init__(self, communication, store, console=None):
        super().__init__()
        self.communication, self.store = communication, store
        self.console = console
        self._console_revision = -1
        self._console_status = '日志未连接'
        self._console_text = ''
        self._ports = []
        self._channels = dict(ch1=[], ch2=[], ecg=[])
        self._waveforms = json.dumps(self._channels)
        self._data = dict(latest1=0, latest2=0, latestEcg=0, ecgLower=-1000, ecgUpper=1000, ecgChannel=store.channel, frames=0,
                          ecgMode=0, missing=0, crc=0, duplicates=0, status="未连接")
        self._revision = -1
        self._paused = False
        self._axis = dict(lower=-200000, upper=200000, autoFit=True)
        self.refreshPorts()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(33)

    @Property('QVariantList', notify=portsChanged)
    def ports(self):
        return self._ports

    @Property('QVariantMap', notify=updated)
    def data(self):
        return self._data

    @Property(str, notify=waveformsChanged)
    def waveforms(self):
        return self._waveforms

    @Property('QVariantMap', notify=axisChanged)
    def axis(self):
        return self._axis

    @Property(str, notify=consoleChanged)
    def consoleStatus(self):
        return self._console_status

    @Property(str, notify=consoleChanged)
    def consoleText(self):
        return self._console_text

    def _fit_axis(self):
        values = self._channels['ch1'] + self._channels['ch2']
        if not values:
            return False
        lower, upper = min(values), max(values)
        margin = max((upper - lower) * 0.1, 1)
        lower, upper = math.floor(lower - margin), math.ceil(upper + margin)
        if (lower, upper) == (self._axis['lower'], self._axis['upper']):
            return False
        self._axis.update(lower=lower, upper=upper)
        return True

    @Slot(bool)
    def setAutoFit(self, enabled):
        self._axis['autoFit'] = enabled
        if enabled:
            self._fit_axis()
        self.axisChanged.emit()

    @Slot(str, str, result=bool)
    def setManualRange(self, lower, upper):
        try:
            lower, upper = float(lower), float(upper)
        except ValueError:
            return False
        span = upper - lower
        if not all(math.isfinite(value) for value in (lower, upper, span)) or span <= 0:
            return False
        self._axis.update(lower=lower, upper=upper, autoFit=False)
        self.axisChanged.emit()
        return True

    @Slot()
    def refreshPorts(self):
        self._ports = available_ports()
        self.portsChanged.emit()

    @Slot(str)
    def connectPort(self, port):
        if port:
            self._paused = False
            self.communication.configure(port)
            if self.console is not None:
                self.console.configure(port)

    @Slot()
    def disconnectPort(self):
        self.communication.configure(None)
        if self.console is not None:
            self.console.configure(None)

    @Slot(str)
    def sendCommand(self, command):
        if self.console is not None:
            self.console.send_command(command)

    @Slot(bool)
    def setPaused(self, paused):
        self._paused = paused

    @Slot(int)
    def setEcgChannel(self, channel):
        if channel not in (0, 1) or self._paused:
            return
        self.store.set_channel(channel)
        self._data['ecgChannel'] = channel
        self.updated.emit()
        self.poll()

    @Slot()
    def poll(self):
        if self.console is not None:
            revision, status_text, log_text = self.console.snapshot()
            if revision != self._console_revision:
                self._console_revision = revision
                self._console_status = status_text
                self._console_text = log_text
                self.consoleChanged.emit()
        snapshot = None if self._paused else self.store.snapshot(self._revision, include_filtered=True)
        status = self.communication.status()
        changed = status != self._data['status']
        self._data['status'] = status
        if snapshot is not None:
            revision, pairs, stats, filtered = snapshot
            self._revision = revision
            self._data.update(stats)
            self._channels['ch1'] = [pair[0] for pair in pairs]
            self._channels['ch2'] = [pair[1] for pair in pairs]
            self._channels['ecg'] = filtered
            # Keep small residual noise from expanding to the full plot height.
            lower, upper = (min(filtered), max(filtered)) if filtered else (0, 0)
            center = (lower + upper) / 2
            extent = max(1000, (upper - lower) * 0.55)
            self._data.update(latestEcg=filtered[-1] if filtered else 0,
                              ecgLower=math.floor(center - extent),
                              ecgUpper=math.ceil(center + extent))
            # Transfer once per frame; Canvas reads native JS arrays, not QVariant references.
            self._waveforms = json.dumps(self._channels, separators=(',', ':'))
            self.waveformsChanged.emit()
            self._data['latest1'], self._data['latest2'] = pairs[-1] if pairs else (0, 0)
            if self._axis['autoFit'] and self._fit_axis():
                self.axisChanged.emit()
            changed = True
        if changed:
            self.updated.emit()

    @Slot(int)
    def setEcgMode(self, mode):
        if mode not in (0, 1) or self._paused:
            return
        self.store.set_mode(mode)
        self._data['ecgMode'] = mode
        self.updated.emit()
        self.poll()
