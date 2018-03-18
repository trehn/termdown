#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

VERSION = "1.13.0"

import curses
from datetime import datetime, timedelta
from functools import wraps
from math import ceil
try:
    from queue import Empty, Queue
except ImportError:
    from Queue import Empty, Queue
import re
import os
from os.path import abspath, dirname
from subprocess import Popen, STDOUT
try:
    from subprocess import DEVNULL
except ImportError:  # Python 2
    DEVNULL = open(os.devnull, 'wb')
from sys import exit, stderr, stdout
from threading import Event, Lock, Thread
from time import sleep
import unicodedata

import click
from dateutil import tz
from dateutil.parser import parse
from pyfiglet import CharNotPrinted, Figlet


click.disable_unicode_literals_warning = True

DEFAULT_FONT = "univers"
TIMEDELTA_REGEX = re.compile(r'((?P<years>\d+)y ?)?'
                             r'((?P<days>\d+)d ?)?'
                             r'((?P<hours>\d+)h ?)?'
                             r'((?P<minutes>\d+)m ?)?'
                             r'((?P<seconds>\d+)s ?)?')
INPUT_PAUSE = 1
INPUT_RESET = 2
INPUT_EXIT = 3
INPUT_LAP = 4


def setup(stdscr):
    # curses
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_RED, -1)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_RED)
    curses.init_pair(3, curses.COLOR_GREEN, -1)
    curses.init_pair(4, -1, curses.COLOR_RED)
    try:
        curses.curs_set(False)
    except curses.error:
        # fails on some terminals
        pass
    stdscr.timeout(0)

    # prepare input thread mechanisms
    curses_lock = Lock()
    input_queue = Queue()
    quit_event = Event()
    return (curses_lock, input_queue, quit_event)


def draw_text(stdscr, text, color=0, fallback=None, title=None):
    """
    Draws text in the given color. Duh.
    """
    if fallback is None:
        fallback = text
    y, x = stdscr.getmaxyx()
    if title:
        title = pad_to_size(title, x, 1)
        if "\n" in title.rstrip("\n"):
            # hack to get more spacing between title and body for figlet
            title += "\n" * 5
        text = title + "\n" + pad_to_size(text, x, len(text.split("\n")))
    lines = pad_to_size(text, x, y).rstrip("\n").split("\n")

    try:
        for i, line in enumerate(lines):
            stdscr.insstr(i, 0, line, curses.color_pair(color))
    except:
        lines = pad_to_size(fallback, x, y).rstrip("\n").split("\n")
        try:
            for i, line in enumerate(lines[:]):
                stdscr.insstr(i, 0, line, curses.color_pair(color))
        except:
            pass
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


def format_seconds_alt(seconds, start, hide_seconds=False):
    # make sure we always show at least 00:00:00
    start = max(start, 86400)
    output = ""
    total_seconds = seconds
    for period_seconds in (
        31557600,
        86400,
        3600,
        60,
        1,
    ):
        actual_period_value = int(seconds / period_seconds)
        if actual_period_value > 0:
            output += str(actual_period_value).zfill(2) + ":"
        elif start > period_seconds or total_seconds > period_seconds:
            output += "00:"
        seconds = seconds % period_seconds
    return output.rstrip(":")


def graceful_ctrlc(func):
    """
    Makes the decorated function exit with code 1 on CTRL+C.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            exit(1)
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

    output += padding_top * (" " * x + "\n")
    for line in input_lines:
        output += padding_left * " " + line + " " * (x - padding_left - len(line)) + "\n"
    output += padding_bottom * (" " * x + "\n")

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
    try:
        # try to convert target to naive local timezone
        target = target.astimezone(tz=tz.tzlocal()).replace(tzinfo=None)
    except ValueError:
        # parse() already returned a naive datetime, all is well
        pass
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


def verify_outfile(ctx, param, value):
    if value:
        if os.path.exists(value):
            raise click.BadParameter("File already exists: {}".format(value))
        if not os.access(dirname(abspath(value)), os.W_OK):
            raise click.BadParameter("Unable to write file: {}".format(value))
    return value


@graceful_ctrlc
def countdown(
    stdscr,
    alt_format=False,
    font=DEFAULT_FONT,
    blink=False,
    critical=3,
    quit_after=None,
    text=None,
    timespec=None,
    title=None,
    voice=None,
    voice_prefix=None,
    outfile=None,
    no_seconds=False,
    no_text_magic=True,
    no_figlet=False,
    no_window_title=False,
    **kwargs
):
    try:
        sync_start, target = parse_timestr(timespec)
    except ValueError:
        raise click.BadParameter("Unable to parse TIME value '{}'".format(timespec))
    curses_lock, input_queue, quit_event = setup(stdscr)
    figlet = Figlet(font=font)

    if title and not no_figlet:
        try:
            title = figlet.renderText(title)
        except CharNotPrinted:
            title = ""

    voice_cmd = None
    if voice:
        for cmd in ("/usr/bin/say", "/usr/bin/espeak"):
            if os.path.exists(cmd):
                voice_cmd = cmd
                break
        voice_prefix = voice_prefix or ""

    input_thread = Thread(
        args=(stdscr, input_queue, quit_event, curses_lock),
        target=input_thread_body,
    )
    input_thread.start()

    seconds_total = seconds_left = int(ceil((target - datetime.now()).total_seconds()))

    try:
        while seconds_left > 0 or blink or text:
            figlet.width = stdscr.getmaxyx()[1]
            if alt_format:
                countdown_text = format_seconds_alt(
                    seconds_left, seconds_total, hide_seconds=no_seconds)
            else:
                countdown_text = format_seconds(seconds_left, hide_seconds=no_seconds)
            if seconds_left > 0:
                with curses_lock:
                    if not no_window_title:
                        os.write(stdout.fileno(), "\033]2;{0}\007".format(countdown_text).encode())
                    if outfile:
                        with open(outfile, 'w') as f:
                            f.write("{}\n{}\n".format(countdown_text, seconds_left))
                    stdscr.erase()
                    try:
                        draw_text(
                            stdscr,
                            countdown_text if no_figlet else figlet.renderText(countdown_text),
                            color=1 if seconds_left <= critical else 0,
                            fallback=title + "\n" + countdown_text if title else countdown_text,
                            title=title,
                        )
                    except CharNotPrinted:
                        draw_text(stdscr, "E")
            if voice_cmd:
                announciation = None
                if seconds_left <= critical:
                    announciation = str(seconds_left)
                elif seconds_left in (5, 10, 20, 30, 60):
                    announciation = "{} {} seconds".format(voice_prefix, seconds_left)
                elif seconds_left in (300, 600, 1800):
                    announciation = "{} {} minutes".format(voice_prefix, int(seconds_left / 60))
                elif seconds_left == 3600:
                    announciation = "{} one hour".format(voice_prefix)
                if announciation:
                    Popen(
                        [voice_cmd, "-v", voice, announciation.strip()],
                        stdout=DEVNULL,
                        stderr=STDOUT,
                    )

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
            if sleep_target > now and seconds_left > 0:
                try:
                    input_action = input_queue.get(True, (sleep_target - now).total_seconds())
                except Empty:
                    input_action = None
                if input_action == INPUT_PAUSE:
                    pause_start = datetime.now()
                    with curses_lock:
                        stdscr.erase()
                        try:
                            draw_text(
                                stdscr,
                                countdown_text if no_figlet else figlet.renderText(countdown_text),
                                color=3,
                                fallback=countdown_text,
                            )
                        except CharNotPrinted:
                            draw_text(stdscr, "E")
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
                elif input_action == INPUT_LAP:
                    continue

            sync_start = sleep_target

            seconds_left = int(ceil((target - datetime.now()).total_seconds()))

            if seconds_left <= 0:
                # we could write this entire block outside the parent while
                # but that would leave us unable to reset everything

                with curses_lock:
                    curses.beep()

                if text and not no_text_magic:
                    text = normalize_text(text)

                if outfile:
                    with open(outfile, 'w') as f:
                        f.write("{}\n{}\n".format(text if text else "DONE", 0))

                rendered_text = text

                if text and not no_figlet:
                    try:
                        rendered_text = figlet.renderText(text)
                    except CharNotPrinted:
                        rendered_text = ""

                if blink or text:
                    base_color = 1 if blink else 0
                    blink_reset = False
                    flip = True
                    slept = 0
                    extra_sleep = 0
                    while True:
                        with curses_lock:
                            os.write(stdout.fileno(), "\033]2;{0}\007".format("/" if flip else "\\").encode())
                            if text:
                                draw_text(
                                    stdscr,
                                    rendered_text,
                                    color=base_color if flip else 4,
                                    fallback=text,
                                )
                            else:
                                draw_text(stdscr, "", color=base_color if flip else 4)
                        if blink:
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
    finally:
        with curses_lock:
            if not no_window_title:
                os.write(stdout.fileno(), "\033]2;\007".encode())
            if outfile:
                os.remove(outfile)
        quit_event.set()
        input_thread.join()


@graceful_ctrlc
def stopwatch(
    stdscr,
    alt_format=False,
    font=DEFAULT_FONT,
    no_figlet=False,
    no_seconds=False,
    quit_after=None,
    title=None,
    outfile=None,
    no_window_title=False,
    **kwargs
):
    curses_lock, input_queue, quit_event = setup(stdscr)
    figlet = Figlet(font=font)

    if title and not no_figlet:
        try:
            title = figlet.renderText(title)
        except CharNotPrinted:
            title = ""

    input_thread = Thread(
        args=(stdscr, input_queue, quit_event, curses_lock),
        target=input_thread_body,
    )
    input_thread.start()

    try:
        sync_start = datetime.now()
        pause_start = None
        seconds_elapsed = 0
        laps = []
        while quit_after is None or seconds_elapsed < int(quit_after):
            figlet.width = stdscr.getmaxyx()[1]
            if alt_format:
                countdown_text = format_seconds_alt(seconds_elapsed, 0, hide_seconds=no_seconds)
            else:
                countdown_text = format_seconds(seconds_elapsed, hide_seconds=no_seconds)
            with curses_lock:
                if not no_window_title:
                    os.write(stdout.fileno(), "\033]2;{0}\007".format(countdown_text).encode())
                if outfile:
                    with open(outfile, 'w') as f:
                        f.write("{}\n{}\n".format(countdown_text, seconds_elapsed))
                stdscr.erase()
                try:
                    draw_text(
                        stdscr,
                        countdown_text if no_figlet else figlet.renderText(countdown_text),
                        fallback=countdown_text,
                        title=title,
                    )
                except CharNotPrinted:
                    draw_text(stdscr, "E")
            sleep_target = sync_start + timedelta(seconds=seconds_elapsed + 1)
            now = datetime.now()
            if sleep_target > now:
                try:
                    input_action = input_queue.get(True, (sleep_target - now).total_seconds())
                except Empty:
                    input_action = None
                if input_action == INPUT_PAUSE:
                    pause_start = datetime.now()
                    with curses_lock:
                        if not no_window_title:
                            os.write(stdout.fileno(), "\033]2;{0}\007".format(countdown_text).encode())
                        if outfile:
                            with open(outfile, 'w') as f:
                                f.write("{}\n{}\n".format(countdown_text, seconds_elapsed))
                        stdscr.erase()
                        try:
                            draw_text(
                                stdscr,
                                countdown_text if no_figlet else figlet.renderText(countdown_text),
                                color=3,
                                fallback=countdown_text,
                                title=title,
                            )
                        except CharNotPrinted:
                            draw_text(stdscr, "E")
                    input_action = input_queue.get()
                    if input_action == INPUT_PAUSE:
                        sync_start += (datetime.now() - pause_start)
                        pause_start = None
                if input_action == INPUT_EXIT:  # no elif here! input_action may have changed
                    if pause_start:
                        sync_start += (datetime.now() - pause_start)
                        pause_start = None
                    break
                elif input_action == INPUT_RESET:
                    sync_start = datetime.now()
                    laps = []
                    seconds_elapsed = 0
                elif input_action == INPUT_LAP:
                    if pause_start:
                        sync_start += (datetime.now() - pause_start)
                        pause_start = None
                    laps.append((datetime.now() - sync_start).total_seconds())
                    sync_start = datetime.now()
                    seconds_elapsed = 0
            seconds_elapsed = int((datetime.now() - sync_start).total_seconds())
    finally:
        with curses_lock:
            if not no_window_title:
                os.write(stdout.fileno(), "\033]2;\007".encode())
            if outfile:
                os.remove(outfile)
        quit_event.set()
        input_thread.join()
    return (datetime.now() - sync_start).total_seconds(), laps


def input_thread_body(stdscr, input_queue, quit_event, curses_lock):
    while not quit_event.is_set():
        try:
            with curses_lock:
                key = stdscr.getkey()
        except:
            key = None
        if key in ("q", "Q"):
            input_queue.put(INPUT_EXIT)
        elif key == " ":
            input_queue.put(INPUT_PAUSE)
        elif key in ("r", "R"):
            input_queue.put(INPUT_RESET)
        elif key in ("l", "L"):
            input_queue.put(INPUT_LAP)
        sleep(0.01)


@click.command()
@click.option("-a", "--alt-format", default=False, is_flag=True,
              help="Use colon-separated time format")
@click.option("-b", "--blink", default=False, is_flag=True,
              help="Flash terminal at end of countdown")
@click.option("-c", "--critical", default=3, metavar="N",
              help="Draw final N seconds in red (defaults to 3)")
@click.option("-f", "--font", default=DEFAULT_FONT, metavar="FONT",
              help="Choose from http://www.figlet.org/examples.html")
@click.option("-p", "--voice-prefix", metavar="TEXT",
              help="Add TEXT to the beginning of --voice announciations "
                   "(except per-second ones)")
@click.option("-q", "--quit-after", metavar="N",
              help="Quit N seconds after countdown (use with -b or -t) "
                   "or terminate stopwatch after N seconds")
@click.option("-s", "--no-seconds", default=False, is_flag=True,
              help="Don't show seconds until last minute")
@click.option("-t", "--text",
              help="Text to display at end of countdown")
@click.option("-T", "--title",
              help="Text to display on top of countdown/stopwatch")
@click.option("-W", "--no-window-title", default=False, is_flag=True,
              help="Don't update terminal title with remaining/elapsed time")
@click.option("-v", "--voice", metavar="VOICE",
              help="Spoken countdown "
                   "(at fixed intervals with per-second announciations starting at --critical; "
                   "requires `espeak` on Linux or `say` on macOS; "
                   "choose VOICE from `say -v '?'` or `espeak --voices`)")
@click.option("-o", "--outfile", metavar="PATH", callback=verify_outfile,
              help="File to write current remaining/elapsed time to")
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
    10, '1h 5m 30s', '12:00', '2020-01-01', '2020-01-01 14:00 UTC'.
    \b
    If TIMESPEC is not given, termdown will operate in stopwatch mode
    and count forward.
    \b
    Hotkeys:
    \tL\tLap (stopwatch mode only)
    \tR\tReset
    \tSPACE\tPause (will delay absolute TIMESPEC)
    \tQ\tQuit
    """
    if kwargs['timespec']:
        curses.wrapper(countdown, **kwargs)
    else:
        seconds_elapsed, laps = curses.wrapper(stopwatch, **kwargs)

        for lap_index, lap_time in enumerate(laps):
            stderr.write("{:.3f}\t{}\tlap {}\n".format(
                lap_time,
                format_seconds(int(lap_time)),
                lap_index + 1,
            ))

        if laps:
            stderr.write("{:.3f}\t{}\tlap {}\n".format(
                seconds_elapsed,
                format_seconds(int(seconds_elapsed)),
                len(laps) + 1,
            ))
            laps.append(seconds_elapsed)
            total_seconds = sum(laps)
            average_seconds = total_seconds / len(laps)
            stderr.write("{:.3f}\t{}\tlap avg\n".format(
                average_seconds,
                format_seconds(int(average_seconds)),
            ))
            stderr.write("{:.3f}\t{}\ttotal\n".format(
                total_seconds,
                format_seconds(int(total_seconds)),
            ))
        else:
            stderr.write("{:.3f}\t{}\ttotal\n".format(
                seconds_elapsed,
                format_seconds(int(seconds_elapsed)),
            ))
        stderr.flush()


if __name__ == '__main__':
    main()
