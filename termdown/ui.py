import curses
import os
from queue import Queue
from sys import stdout
from threading import Lock, Thread
from time import sleep

from pyfiglet import CharNotPrinted, Figlet

from .events import (
    INPUT_END,
    INPUT_EXIT,
    INPUT_LAP,
    INPUT_MINUS,
    INPUT_PAUSE,
    INPUT_PLUS,
    INPUT_RESET,
)
from .utils import pad_to_size


class Ui:
    def __init__(self, stdscr, args):
        self.curses_lock = Lock()
        self.input_queue = Queue()
        self.stdscr = stdscr
        self.figlet = Figlet(font=args.font)
        self._args = args

        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_RED, -1)
        curses.init_pair(2, curses.COLOR_RED, curses.COLOR_RED)
        curses.init_pair(3, curses.COLOR_BLUE, -1)
        curses.init_pair(4, -1, curses.COLOR_RED)
        try:
            curses.curs_set(False)
        except curses.error:
            # fails on some terminals
            pass
        stdscr.timeout(0)  # Set timeout for getch/getkey to 0 (non-blocking)
        stdscr.nodelay(True)  # Set nodelay mode (also non-blocking)

        if args.title and not args.no_figlet:
            try:
                args.title = self.figlet.renderText(args.title)
            except CharNotPrinted:
                args.title = ""

    def draw_text(self, text, color=0, fallback=None, end=None):
        """
        Draws text in the given color. Duh.
        """
        if fallback is None:
            fallback = text
        if not self._args.no_figlet:
            self.figlet.width = self.stdscr.getmaxyx()[1]
            try:
                text = self.figlet.renderText(text)
            except CharNotPrinted:
                pass

        y, x = self.stdscr.getmaxyx()
        effective_y = y if self._args.no_figlet_y_offset < 0 else 1
        y_delta = (
            0 if self._args.no_figlet_y_offset < 0 else self._args.no_figlet_y_offset
        )
        if self._args.title:
            self._args.title = pad_to_size(self._args.title, x, 1)
            if "\n" in self._args.title.rstrip("\n"):
                # hack to get more spacing between title and body for figlet
                self._args.title += "\n" * 5
            text = self._args.title + "\n" + pad_to_size(text, x, len(text.split("\n")))
        if end:
            end = pad_to_size(end, x, 1)
            text = pad_to_size(text, x, len(text.split("\n"))) + "\n" + end
        lines = pad_to_size(text, x, effective_y).rstrip("\n").split("\n")

        self.stdscr.erase()

        try:
            for i, line in enumerate(lines):
                self.stdscr.insstr(i + y_delta, 0, line, curses.color_pair(color))
        except Exception:
            lines = pad_to_size(fallback, x, effective_y).rstrip("\n").split("\n")
            try:
                for i, line in enumerate(lines[:]):
                    self.stdscr.insstr(i + y_delta, 0, line, curses.color_pair(color))
            except Exception:
                pass

        self.stdscr.refresh()

    def set_window_title(self, text):
        if not self._args.no_window_title:
            os.write(
                stdout.fileno(),
                "\033]2;{0}\007".format(text).encode(),
            )

    def start_input_thread(self):
        Thread(
            target=self._input_thread_body,
            daemon=True,
        ).start()

    def _input_thread_body(self):
        while True:
            try:
                with self.curses_lock:
                    key = self.stdscr.getkey()
            except Exception:
                key = None
            if key in ("q", "Q"):
                self.input_queue.put(INPUT_EXIT)
            elif key == " ":
                self.input_queue.put(INPUT_PAUSE)
            elif key in ("e", "E"):
                self.input_queue.put(INPUT_END)
            elif key in ("r", "R"):
                self.input_queue.put(INPUT_RESET)
            elif key in ("l", "L"):
                self.input_queue.put(INPUT_LAP)
            elif key == "+":
                self.input_queue.put(INPUT_PLUS)
            elif key == "-":
                self.input_queue.put(INPUT_MINUS)
            sleep(0.01)
