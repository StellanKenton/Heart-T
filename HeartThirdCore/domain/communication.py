"""Read-only CDC communication with automatic reconnection."""
import logging
import time
from threading import Lock, Thread

import serial
from serial.tools import list_ports

LOG = logging.getLogger(__name__)


def available_ports():
    return [dict(port=p.device, label=f"{p.device} · {p.description}",
                 heart=p.vid == 0x0483 and p.pid == 0x5740)
            for p in list_ports.comports()]


class CommunicationThread(Thread):
    def __init__(self, ring, stop, baud=115200):
        super().__init__(name="communication")
        self.ring, self.stop, self.baud = ring, stop, baud
        self._lock = Lock()
        self._target = None
        self._generation = 0
        self._status = "未连接"

    def configure(self, target):
        with self._lock:
            self._target = target
            self._generation += 1

    def status(self):
        with self._lock:
            return self._status

    def _set_status(self, status):
        with self._lock:
            self._status = status

    def _selection(self):
        with self._lock:
            return self._target, self._generation

    def run(self):
        while not self.stop.is_set():
            target, generation = self._selection()
            if target is None:
                self._set_status("未连接")
                self.stop.wait(0.1)
                continue
            self.ring.new_session()
            try:
                self._set_status(f"正在连接 {target}")
                with serial.Serial(target, self.baud, timeout=0.1) as port:
                    self._set_status(f"已连接 {target}")
                    while not self.stop.is_set() and self._selection()[1] == generation:
                        data = port.read(min(max(port.in_waiting, 1), 4096))
                        if data:
                            self.ring.write(data)
            except (serial.SerialException, OSError) as error:
                LOG.warning("CDC connection failed: %s", error)
                if 'PermissionError' in str(error) or 'Access is denied' in str(error):
                    self._set_status(f"{target} 无法打开：可能被其他程序占用，请关闭其他串口窗口 · 1 秒后重试")
                else:
                    self._set_status(f"连接中断：{error} · 1 秒后重试")
                deadline = time.monotonic() + 1
                while (not self.stop.is_set() and self._selection()[1] == generation
                       and time.monotonic() < deadline):
                    self.stop.wait(0.1)
