"""Verify that the device console receives logs and sends line commands."""
import socket
import sys
import time
import unittest
from pathlib import Path
from threading import Event, Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from domain.communication import ConsoleThread


class ConsoleTests(unittest.TestCase):
    def test_tcp_log_and_command(self):
        stop = Event()
        commands = []
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            listener.settimeout(2)

            def serve():
                with listener.accept()[0] as connection:
                    connection.settimeout(2)
                    connection.sendall(b'[I][10][main] ready\r\n')
                    commands.append(connection.recv(128))

            server = Thread(target=serve)
            console = ConsoleThread(stop, listener.getsockname()[1])
            server.start()
            console.configure('127.0.0.1')
            console.start()
            try:
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline and 'ready' not in console.snapshot()[2]:
                    time.sleep(0.01)
                self.assertIn('ready', console.snapshot()[2])
                console.send_command('status')
                server.join(2)
                self.assertEqual(commands, [b'status\n'])
            finally:
                stop.set()
                console.join(2)
                server.join(2)
            self.assertFalse(console.is_alive())


if __name__ == '__main__':
    unittest.main()
