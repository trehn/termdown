from math import ceil
from threading import Thread
from time import monotonic, sleep, time

from .events import TIME_TICK


class Metronome:
    """
    Will put a TIME_TICK event into the given queue every full second, delayed by offset.
    """

    def __init__(self, queue, offset=0):
        self._offset = offset
        self._queue = queue
        self._thread = Thread(target=self._run, daemon=True)
        self._pause_time = None

    def _run(self):
        while True:
            # Calculate the time to sleep until the next full second
            current_time = time()
            target_time = ceil(current_time) + self._offset
            sleep_time = target_time - current_time

            # If sleep_time is very small (e.g., we're just before the second),
            # we should wait for the next second.
            if sleep_time < 0.001:  # Small buffer to avoid missing the second
                sleep_time += 1.0

            sleep(sleep_time)
            if not self.is_paused:
                self._queue.put(TIME_TICK)

    def start(self):
        self._thread.start()

    def pause(self):
        if self.is_paused:  # unpause
            duration = monotonic() - self._pause_time
            self._pause_time = None
            if self._offset is not None:
                # If we're not running in clock mode, change the offset so the
                # next tick will be 1s from now.
                self._offset = time() % 1.0
            return duration
        else:  # pause
            self._pause_time = monotonic()

    @property
    def is_paused(self):
        return self._pause_time is not None
