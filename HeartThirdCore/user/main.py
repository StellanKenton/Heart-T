"""Assemble communication, analysis and the Qt main/HMI thread."""
import argparse
import hashlib
import logging
import sys
from pathlib import Path
from threading import Event

from PySide6.QtCore import QLockFile, QStandardPaths, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtQuickControls2 import QQuickStyle

from domain.analysis import AnalysisThread, SampleStore
from domain.communication import CommunicationThread, ConsoleThread
from domain.recording import RawCsvRecorder
from domain.ringbuffer import RingBuffer
from hmi.backend import Backend


def main(argv=None):
    parser = argparse.ArgumentParser(description="Heart-T 双通道原始数据监视器")
    parser.add_argument('--host', help='ESP32-S3 IP address or hostname')
    parser.add_argument('--quit-after', type=float, help='Exit after N seconds for smoke checks')
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
    QQuickStyle.setStyle('Basic')
    app = QGuiApplication([sys.argv[0]])
    app.setApplicationName('Heart-T')
    app.setOrganizationName('Cosmos')
    # Repeated launches activate the existing window before opening TCP sockets.
    identity = hashlib.sha256(str(Path(__file__).resolve().parents[1]).lower().encode()).hexdigest()[:16]
    server_name = 'Heart-T-' + identity
    client = QLocalSocket()
    client.connectToServer(server_name)
    if client.waitForConnected(500):
        client.disconnectFromServer()
        logging.info('Activated the existing Heart-T window')
        return 0
    instance_lock = QLockFile(str(Path(QStandardPaths.writableLocation(QStandardPaths.TempLocation))
                                  / (server_name + '.lock')))
    if not instance_lock.tryLock(0):
        logging.warning('Heart-T is already starting; use the existing window')
        return 1
    server = QLocalServer()
    QLocalServer.removeServer(server_name)
    if not server.listen(server_name):
        logging.error('Cannot create the application instance server: %s', server.errorString())
        return 1
    stop = Event()
    ring, store = RingBuffer(), SampleStore()
    recorder = RawCsvRecorder()
    communication = CommunicationThread(ring, stop)
    console = ConsoleThread(stop)
    analysis = AnalysisThread(ring, store, stop, recorder)
    backend = Backend(communication, store, console, recorder)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('backend', backend)
    engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parents[1] / 'hmi' / 'main.qml')))
    if not engine.rootObjects():
        return 1

    def activate_window():
        connection = server.nextPendingConnection()
        if connection is not None:
            connection.disconnectFromServer()
            connection.deleteLater()
        window = engine.rootObjects()[0]
        window.showNormal()
        window.raise_()
        window.requestActivate()

    server.newConnection.connect(activate_window)
    if args.host:
        communication.configure(args.host)
        console.configure(args.host)
    analysis.start()
    communication.start()
    console.start()
    if args.quit_after is not None:
        QTimer.singleShot(max(0, int(args.quit_after * 1000)), app.quit)
    try:
        return app.exec()
    finally:
        backend.timer.stop()
        stop.set()
        ring.close()
        communication.join()
        console.join()
        analysis.join()
        recorder.close()
