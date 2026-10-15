"""Thread-safe UI event mailbox with coalesced high-frequency updates.

Callbacks affecting connection/state transitions are delivered in order.
Transient updates (log/match/warning) use a key; only the newest callback for
that key is retained while one UI dispatch is outstanding.
"""
from collections import deque
import threading


class UIEventMailbox:
    def __init__(self):
        self._lock = threading.Lock()
        self._queue = deque()
        self._coalesced = {}
        self._peak = 0
        self._replacements = 0

    def put(self, callback, *, key=None):
        with self._lock:
            if key is not None:
                if key in self._coalesced:
                    self._replacements += 1
                    self._coalesced[key] = callback
                    return
                self._coalesced[key] = callback
                self._queue.append((True, key))
            else:
                self._queue.append((False, callback))
            self._peak = max(self._peak, len(self._queue))

    def get_nowait(self):
        with self._lock:
            if not self._queue:
                raise IndexError("UI event mailbox is empty")
            keyed, item = self._queue.popleft()
            return self._coalesced.pop(item) if keyed else item

    def stats(self):
        with self._lock:
            return {
                "pending": len(self._queue),
                "peak_pending": self._peak,
                "coalesced_replacements": self._replacements,
            }

    def clear(self):
        with self._lock:
            self._queue.clear()
            self._coalesced.clear()
