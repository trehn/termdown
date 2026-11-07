from threading import Event, Thread
from time import monotonic, time

from .events import TIME_TICK


class Metronome:
    """
    Will put a TIME_TICK event into the given queue every second, at the
    moments when the fractional part of time() equals offset.
    """

    def __init__(self, queue, offset=0.0):
        self._offset = offset % 1.0
        self._queue = queue
        self._realigned = Event()
        self._thread = Thread(target=self._run, daemon=True)
        self._pause_time = None

    def _run(self):
        while True:
            # Sleep until the next tick, plus a small margin so we never wake
            # up just before it (which would e.g. make a countdown display the
            # previous second for another full second).
            sleep_time = (self._offset - time()) % 1.0 + 0.002
            if self._realigned.wait(sleep_time):
                # offset changed while we were sleeping, start over
                self._realigned.clear()
                continue
            if not self.is_paused:
                self._queue.put(TIME_TICK)

    def start(self):
        self._thread.start()

    def align(self, offset):
        """
        Make future ticks happen when the fractional part of time() equals
        offset.
        """
        self._offset = offset % 1.0
        self._realigned.set()

    def pause(self):
        """
        Toggles pause. Returns the duration of the pause when unpausing.
        """
        if self.is_paused:  # unpause
            duration = monotonic() - self._pause_time
            self._pause_time = None
            return duration
        else:  # pause
            self._pause_time = monotonic()

    def restart_pause(self):
        """
        If paused, forget about the time spent paused so far.
        """
        if self.is_paused:
            self._pause_time = monotonic()

    @property
    def is_paused(self):
        return self._pause_time is not None
