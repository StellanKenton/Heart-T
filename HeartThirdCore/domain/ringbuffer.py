"""Bounded byte ring shared by the CDC producer and parser consumer."""
from threading import Condition


class RingBuffer:
    def __init__(self, capacity=65536):
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self._buffer = bytearray(capacity)
        self._head = self._tail = self._size = 0
        self._session = 0
        self._closed = False
        self._condition = Condition()

    def new_session(self):
        with self._condition:
            self._head = self._tail = self._size = 0
            self._session += 1
            self._condition.notify_all()

    def write(self, data):
        """Apply backpressure rather than silently discard bytes when full."""
        offset = 0
        with self._condition:
            while offset < len(data) and not self._closed:
                self._condition.wait_for(lambda: self._size < self.capacity or self._closed)
                if self._closed:
                    break
                count = min(len(data) - offset, self.capacity - self._size,
                            self.capacity - self._head)
                self._buffer[self._head:self._head + count] = data[offset:offset + count]
                self._head = (self._head + count) % self.capacity
                self._size += count
                offset += count
                self._condition.notify_all()
        return offset

    def read(self, limit=4096, timeout=0.1):
        with self._condition:
            self._condition.wait_for(lambda: self._size or self._closed, timeout)
            count = min(limit, self._size)
            first = min(count, self.capacity - self._tail)
            data = bytes(self._buffer[self._tail:self._tail + first])
            data += bytes(self._buffer[:count - first])
            self._tail = (self._tail + count) % self.capacity
            self._size -= count
            self._condition.notify_all()
            return self._session, data

    def close(self):
        with self._condition:
            self._closed = True
            self._condition.notify_all()
