import curses
import os
from queue import Queue
from sys import stdout
from threading import Lock, Thread
from time import sleep

from art import text2art

from .events import (
    INPUT_END,
    INPUT_EXIT,
    INPUT_LAP,
    INPUT_MINUS,
    INPUT_PAUSE,
    INPUT_PLUS,
    INPUT_RESET,
)
from .ttf import ttf_to_ascii
from .utils import pad_to_size


class Ui:
    def __init__(self, stdscr, args):
        self.curses_lock = Lock()
        self.input_queue = Queue()
        self.stdscr = stdscr
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

    def draw_text(self, text, color=0, end=None):
        """
        Draws text in the given color. Duh.
        """

        title = self._args.title or ""
        end = end or ""

        # build a list of possible fallbacks in descending order of preference
        variants = [
            (title + "\n\n" + text + "\n\n" + end).strip("\n"),
            (title + "\n\n" + text).strip("\n"),
            text,
            "E",
        ]

        if not self._args.no_art:
            if os.path.exists(self._args.font):
                ttf_args = (
                    self._args.font,
                    self._args.font_size,
                    self._args.font_charset,
                )
                art_title = ttf_to_ascii(title, *ttf_args)
                art_text = ttf_to_ascii(text, *ttf_args)
                art_end = ttf_to_ascii(end, *ttf_args)
            else:
                art_title = text2art(title, font=self._args.font)
                art_text = text2art(text, font=self._args.font)
                art_end = text2art(end, font=self._args.font)
            variants = [
                (art_title + "\n\n\n\n" + art_text + "\n\n\n\n" + art_end).strip("\n"),
                (art_title + "\n\n" + art_text + "\n\n" + art_end).strip("\n"),
                (art_title + "\n\n" + art_text + "\n\n" + end).strip("\n"),
                (title + "\n\n" + art_text + "\n\n" + end).strip("\n"),
            ] + variants

        y, x = self.stdscr.getmaxyx()
        for variant in variants:
            lines = pad_to_size(variant, x, y).rstrip("\n").split("\n")
            self.stdscr.erase()
            try:
                for i, line in enumerate(lines):
                    self.stdscr.insstr(i, 0, line, curses.color_pair(color))
            except Exception:
                continue
            else:
                break

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
