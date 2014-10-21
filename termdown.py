#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

VERSION = "1.6.0"

import curses
from datetime import datetime, timedelta
from math import ceil
try:
    from queue import Empty, Queue
except ImportError:
    from Queue import Empty, Queue
import re
from subprocess import Popen
from sys import exit
from threading import Event, Lock, Thread
from time import sleep
import unicodedata

import click
from dateutil.parser import parse
from pyfiglet import Figlet

DEFAULT_FONT = "univers"
TIMEDELTA_REGEX = re.compile(r'((?P<years>\d+)y ?)?'
                             r'((?P<days>\d+)d ?)?'
                             r'((?P<hours>\d+)h ?)?'
                             r'((?P<minutes>\d+)m ?)?'
                             r'((?P<seconds>\d+)s ?)?')
INPUT_PAUSE = 1
INPUT_RESET = 2
INPUT_EXIT = 3


def setup(stdscr):
    # curses
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_RED, -1)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_RED)
    curses.curs_set(False)
    stdscr.timeout(0)

    # prepare input thread mechanisms
    curses_lock = Lock()
    input_queue = Queue()
    quit_event = Event()
    return (curses_lock, input_queue, quit_event)


def draw_blink(stdscr, flipflop):
    """
    Flash terminal. Must be called at desired intervals with flipflop
    alternating between True and False.
    """
    y, x = stdscr.getmaxyx()
    for i in range(y):
        if flipflop:
            stdscr.addstr(i, 0, " " * (x-1), curses.color_pair(2))
        else:
            stdscr.addstr(i, 0, " " * (x-1))
    stdscr.refresh()


def draw_text(stdscr, text, color=0):
    """
    Draws text in the given color. Duh.
    """
    y, x = stdscr.getmaxyx()
    lines = pad_to_size(text, x-1, y-1).rstrip("\n").split("\n")
    i = 0
    for line in lines:
        stdscr.addstr(i, 0, line, curses.color_pair(color))
        i += 1
    stdscr.refresh()


def format_seconds(seconds, hide_seconds=False):
    """
    Returns a human-readable string representation of the given amount
    of seconds.
    """
    if seconds <= 60:
        return str(seconds)
    output = ""
    for period, period_seconds in (
        ('y', 31557600),
        ('d', 86400),
        ('h', 3600),
        ('m', 60),
        ('s', 1),
    ):
        if seconds >= period_seconds and not (hide_seconds and period == 's'):
            output += str(int(seconds / period_seconds))
            output += period
            output += " "
            seconds = seconds % period_seconds
    return output.strip()


def graceful_ctrlc(func):
    """
    Makes the decorated function terminate silently on CTRL+C.
    """
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except KeyboardInterrupt:
            pass
    return wrapper


NORMALIZE_TEXT_MAP = {
    "ä": "ae",
    "Ä": "Ae",
    "ö": "oe",
    "Ö": "Oe",
    "ü": "ue",
    "Ü": "Ue",
    "ß": "ss",
}


def normalize_text(input_str):
    for char, replacement in NORMALIZE_TEXT_MAP.items():
        input_str = input_str.replace(char, replacement)
    return "".join(
        [c for c in unicodedata.normalize('NFD', input_str) if
         unicodedata.category(c) != 'Mn']
    )


def pad_to_size(text, x, y):
    """
    Adds whitespace to text to center it within a frame of the given
    dimensions.
    """
    input_lines = text.rstrip().split("\n")
    longest_input_line = max(map(len, input_lines))
    number_of_input_lines = len(input_lines)
    x = max(x, longest_input_line)
    y = max(y, number_of_input_lines)
    output = ""

    padding_top = int((y - number_of_input_lines) / 2)
    padding_bottom = y - number_of_input_lines - padding_top
    padding_left = int((x - longest_input_line) / 2)

    output += padding_top * "\n"
    for line in input_lines:
        output += padding_left * " " + line + "\n"
    output += padding_bottom * "\n"

    return output


def parse_timestr(timestr):
    """
    Parse a string describing a point in time.
    """
    timedelta_secs = parse_timedelta(timestr)
    sync_start = datetime.now()

    if timedelta_secs:
        target = datetime.now() + timedelta(seconds=timedelta_secs)
    elif timestr.isdigit():
        target = datetime.now() + timedelta(seconds=int(timestr))
    else:
        try:
            target = parse(timestr)
        except:
            # unfortunately, dateutil doesn't raise the best exceptions
            raise ValueError("Unable to parse '{}'".format(timestr))

        # When I do "termdown 10" (the two cases above), I want a
        # countdown for the next 10 seconds. Okay. But when I do
        # "termdown 23:52", I want a countdown that ends at that exact
        # moment -- the countdown is related to real time. Thus, I want
        # my frames to be drawn at full seconds, so I enforce
        # microsecond=0.
        sync_start = sync_start.replace(microsecond=0)

    return (sync_start, target)


def parse_timedelta(deltastr):
    """
    Parse a string describing a period of time.
    """
    matches = TIMEDELTA_REGEX.match(deltastr)
    if not matches:
        return None
    components = {}
    for name, value in matches.groupdict().items():
        if value:
            components[name] = int(value)
    for period, hours in (('days', 24), ('years', 8766)):
        if period in components:
            components['hours'] = components.get('hours', 0) + \
                                  components[period] * hours
            del components[period]
    return int(timedelta(**components).total_seconds())


def print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo(VERSION)
    ctx.exit()


@graceful_ctrlc
def countdown(
        stdscr,
        font=DEFAULT_FONT,
        blink=False,
        quit_after=None,
        text=None,
        timespec=None,
        voice=None,
        no_seconds=False,
        no_text_magic=True,
        no_figlet=False,
        **kwargs
    ):
    try:
        sync_start, target = parse_timestr(timespec)
    except ValueError:
        click.echo("Unable to parse TIME value '{}'".format(timespec))
        exit(64)
    curses_lock, input_queue, quit_event = setup(stdscr)
    figlet = Figlet(font=font)
    input_thread = Thread(
        args=(stdscr, input_queue, quit_event, curses_lock),
        target=input_thread_body,
    )
    input_thread.start()

    seconds_left = int(ceil((target - datetime.now()).total_seconds()))

    try:
        while seconds_left > 0:
            countdown_text = format_seconds(seconds_left, hide_seconds=no_seconds)
            with curses_lock:
                stdscr.erase()
                draw_text(
                    stdscr,
                    countdown_text if no_figlet else figlet.renderText(countdown_text),
                    color=1 if seconds_left <= 3 else 0,
                )
            if seconds_left <= 10 and voice:
                Popen(["/usr/bin/say", "-v", voice, str(seconds_left)])

            # We want to sleep until this point of time has been
            # reached:
            sleep_target = sync_start + timedelta(seconds=1)

            # If sync_start has microsecond=0, it might happen that we
            # need to skip one frame (the very first one). This occurs
            # when the program has been startet at, say,
            # "2014-05-29 20:27:57.930651". Now suppose rendering the
            # frame took about 0.2 seconds. The real time now is
            # "2014-05-29 20:27:58.130000" and sleep_target is
            # "2014-05-29 20:27:58.000000" which is in the past! We're
            # already too late. We could either skip that frame
            # completely or we can draw it right now. I chose to do the
            # latter: Only sleep if haven't already missed our target.
            now = datetime.now()
            if sleep_target > now:
                try:
                    input_action = input_queue.get(True, (sleep_target - now).total_seconds())
                except Empty:
                    input_action = None
                if input_action == INPUT_PAUSE:
                    pause_start = datetime.now()
                    input_action = input_queue.get()
                    if input_action == INPUT_PAUSE:
                        sync_start += (datetime.now() - pause_start)
                        target += (datetime.now() - pause_start)
                if input_action == INPUT_EXIT:  # no elif here! input_action may have changed
                    break
                elif input_action == INPUT_RESET:
                    sync_start, target = parse_timestr(timespec)
                    seconds_left = int(ceil((target - datetime.now()).total_seconds()))
                    continue

            sync_start = sleep_target

            seconds_left = int(ceil((target - datetime.now()).total_seconds()))

            if seconds_left <= 0:
                # we could write this entire block outside the parent while
                # but that would leave us unable to reset everything

                with curses_lock:
                    curses.beep()

                if blink:
                    blink_reset = False
                    flip = True
                    slept = 0
                    extra_sleep = 0
                    while True:
                        with curses_lock:
                            draw_blink(stdscr, flip)
                        flip = not flip
                        try:
                            sleep_start = datetime.now()
                            input_action = input_queue.get(True, 0.5 + extra_sleep)
                        except Empty:
                            input_action = None
                        finally:
                            extra_sleep = 0
                            sleep_end = datetime.now()
                        if input_action == INPUT_PAUSE:
                            pause_start = datetime.now()
                            input_action = input_queue.get()
                            extra_sleep = (sleep_end - sleep_start).total_seconds()
                        if input_action == INPUT_EXIT:
                            # no elif here! input_action may have changed
                            return
                        elif input_action == INPUT_RESET:
                            sync_start, target = parse_timestr(timespec)
                            seconds_left = int(ceil((target - datetime.now()).total_seconds()))
                            blink_reset = True
                            break
                        slept += (sleep_end - sleep_start).total_seconds()
                        if quit_after and slept >= float(quit_after):
                            return
                    if blink_reset:
                        continue

                elif text:
                    if not no_text_magic:
                        text = normalize_text(text)
                    with curses_lock:
                        draw_text(stdscr, text if no_figlet else figlet.renderText(text))

                    text_reset = False
                    slept = 0
                    while True:
                        try:
                            sleep_start = datetime.now()
                            if quit_after:
                                input_action = input_queue.get(True, int(quit_after))
                            else:
                                input_action = input_queue.get(True, 47)
                        except Empty:
                            input_action = None
                        finally:
                            sleep_end = datetime.now()
                        if input_action == INPUT_EXIT:
                            return
                        elif input_action == INPUT_RESET:
                            sync_start, target = parse_timestr(timespec)
                            seconds_left = int(ceil((target - datetime.now()).total_seconds()))
                            text_reset = True
                            break
                        slept += (sleep_end - sleep_start).total_seconds()
                        if quit_after and slept >= float(quit_after):
                            return
                    if text_reset:
                        continue
    finally:
        quit_event.set()
        input_thread.join()


@graceful_ctrlc
def stopwatch(
    stdscr,
    font=DEFAULT_FONT,
    no_seconds=False,
    quit_after=None,
    no_figlet=False,
    **kwargs
):
    curses_lock, input_queue, quit_event = setup(stdscr)
    figlet = Figlet(font=font)
    input_thread = Thread(
        args=(stdscr, input_queue, quit_event, curses_lock),
        target=input_thread_body,
    )
    input_thread.start()

    try:
        sync_start = datetime.now()
        seconds_elapsed = 0
        while quit_after is None or seconds_elapsed < int(quit_after):
            countdown_text = format_seconds(seconds_elapsed, hide_seconds=no_seconds)
            with curses_lock:
                stdscr.erase()
                draw_text(
                    stdscr,
                    countdown_text if no_figlet else figlet.renderText(countdown_text),
                )
            sleep_target = sync_start + timedelta(seconds=seconds_elapsed + 1)
            now = datetime.now()
            if sleep_target > now:
                try:
                    input_action = input_queue.get(True, (sleep_target - now).total_seconds())
                except Empty:
                    input_action = None
                if input_action == INPUT_PAUSE:
                    pause_start = datetime.now()
                    input_action = input_queue.get()
                    if input_action == INPUT_PAUSE:
                        sync_start += (datetime.now() - pause_start)
                if input_action == INPUT_EXIT:  # no elif here! input_action may have changed
                    break
                elif input_action == INPUT_RESET:
                    sync_start = datetime.now()
                    seconds_elapsed = 0
            seconds_elapsed = int((datetime.now() - sync_start).total_seconds())
    finally:
        quit_event.set()
        input_thread.join()


def input_thread_body(stdscr, input_queue, quit_event, curses_lock):
    while not quit_event.is_set():
        try:
            with curses_lock:
                key = stdscr.getkey()
        except:
            key = None
        if key == "q":
            input_queue.put(INPUT_EXIT)
        elif key == " ":
            input_queue.put(INPUT_PAUSE)
        elif key == "r":
            input_queue.put(INPUT_RESET)
        sleep(0.01)


@click.command()
@click.option("-b", "--blink", default=False, is_flag=True,
              help="Flash terminal at end of countdown")
@click.option("-f", "--font", default=DEFAULT_FONT, metavar="FONT",
              help="Choose from http://www.figlet.org/examples.html")
@click.option("-q", "--quit-after", metavar="N",
              help="Quit N seconds after countdown (use with -b or -t) "
                   "or terminate stopwatch after N seconds")
@click.option("-s", "--no-seconds", default=False, is_flag=True,
              help="Don't show seconds until last minute")
@click.option("-t", "--text",
              help="Text to display at end of countdown")
@click.option("-v", "--voice", metavar="VOICE",
              help="Mac OS X only: spoken countdown (starting at 10), "
                   "choose VOICE from `say -v '?'`")
@click.option("--no-figlet", default=False, is_flag=True,
              help="Don't use ASCII art for display")
@click.option("--no-text-magic", default=False, is_flag=True,
              help="Don't try to replace non-ASCII characters (use with -t)")
@click.option("--version", is_flag=True, callback=print_version,
              expose_value=False, is_eager=True,
              help="Show version and exit")
@click.argument('timespec', required=False)
def main(**kwargs):
    """
    \b
    Starts a countdown to or from TIMESPEC. Example values for TIMESPEC:
    10, '1h 5m 30s', '12:00', '2020-01-01', '2020-01-01 14:00'.
    \b
    If TIMESPEC is not given, termdown will operate in stopwatch mode
    and count forward.
    \b
    Hotkeys:
    \tR\tReset
    \tSPACE\tPause (will delay absolute TIMESPEC)
    \tQ\tQuit
    """
    if kwargs['timespec']:
        curses.wrapper(countdown, **kwargs)
    else:
        curses.wrapper(stopwatch, **kwargs)


if __name__ == '__main__':
    main()
