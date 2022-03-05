#!/usr/bin/env python
VERSION = "1.18.0"

import curses
from datetime import datetime, timedelta
from functools import wraps
from math import ceil
from queue import Empty, Queue
import re
import os
from os.path import abspath, dirname
from subprocess import DEVNULL, Popen, STDOUT
from sys import exit, stderr, stdout
from threading import Event, Lock, Thread
from time import sleep
import unicodedata

import click
from dateutil import tz
from dateutil.parser import parse
from pyfiglet import CharNotPrinted, Figlet


DEFAULT_FONT = "univers"
DEFAULT_TIME_FORMAT = "%H:%M:%S"  # --no-seconds expects this to end with :%S
DEFAULT_DATE_FORMAT = "%Y-%m-%d"
TIMEDELTA_REGEX = re.compile(r'((?P<years>\d+)y ?)?'
                             r'((?P<days>\d+)d ?)?'
                             r'((?P<hours>\d+)h ?)?'
                             r'((?P<minutes>\d+)m ?)?'
                             r'((?P<seconds>\d+)s ?)?')
INPUT_PAUSE = 1
INPUT_RESET = 2
INPUT_EXIT = 3
INPUT_LAP = 4
INPUT_PLUS = 5
INPUT_MINUS = 6
INPUT_END = 7


def setup(stdscr):
    # curses
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
    stdscr.timeout(0)

    # prepare input thread mechanisms
    curses_lock = Lock()
    input_queue = Queue()
    quit_event = Event()
    return (curses_lock, input_queue, quit_event)


def draw_text(stdscr, text, color=0, fallback=None, title=None, no_figlet_y_offset=-1, end=None):
    """
    Draws text in the given color. Duh.
    """
    if fallback is None:
        fallback = text
    y, x = stdscr.getmaxyx()
    effective_y = (y if no_figlet_y_offset < 0 else 1)
    y_delta = (0 if no_figlet_y_offset < 0 else no_figlet_y_offset)
    if title:
        title = pad_to_size(title, x, 1)
        if "\n" in title.rstrip("\n"):
            # hack to get more spacing between title and body for figlet
            title += "\n" * 5
        text = title + "\n" + pad_to_size(text, x, len(text.split("\n")))
    if end:
        end = pad_to_size(end, x, 1)
        text = pad_to_size(text, x, len(text.split("\n"))) + "\n" + end
    lines = pad_to_size(text, x, effective_y).rstrip("\n").split("\n")

    try:
        for i, line in enumerate(lines):
            stdscr.insstr(i + y_delta, 0, line, curses.color_pair(color))
    except:
        lines = pad_to_size(fallback, x, effective_y).rstrip("\n").split("\n")
        try:
            for i, line in enumerate(lines[:]):
                stdscr.insstr(i + y_delta, 0, line, curses.color_pair(color))
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
        if hide_seconds and period_seconds == 1 and total_seconds > 60:
            break
        actual_period_value = int(seconds / period_seconds)
        if actual_period_value > 0:
            output += str(actual_period_value).zfill(2) + ":"
        elif start > period_seconds or total_seconds > period_seconds:
            output += "00:"
        seconds = seconds % period_seconds
    return output.rstrip(":")


def format_target(target, time_format, date_format):
    """
    Returns a human-readable string representation of the countdown's target
    datetime
    """
    if datetime.now().date() != target.date():
        fmt = "{} {}".format(date_format, time_format)
    else:
        fmt = time_format
    return target.strftime(fmt)


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
    end=None,
    voice=None,
    voice_prefix=None,
    exec_cmd=None,
    outfile=None,
    no_bell=False,
    no_seconds=False,
    no_text_magic=True,
    no_figlet=False,
    no_figlet_y_offset=-1,
    no_window_title=False,
    time=False,
    time_format=None,
    date_format=None,
    **kwargs
):
    try:
        sync_start, target = parse_timestr(timespec)
    except ValueError:
        raise click.BadParameter("Unable to parse TIME value '{}'".format(timespec))
    if exec_cmd and voice:  # prevent passing both --exec-cmd and --voice
        raise click.BadParameter("--exec-cmd and --voice are mutually exclusive")
    curses_lock, input_queue, quit_event = setup(stdscr)
    figlet = Figlet(font=font)
    if not no_figlet:
        no_figlet_y_offset = -1

    voice_cmd = None
    if voice:
        for cmd in ("/usr/bin/say", "/usr/bin/espeak", "/usr/bin/espeak-ng"):
            if os.path.exists(cmd):
                voice_cmd = cmd
                break
    if voice or exec_cmd:
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
            if time:
                countdown_text = datetime.now().strftime(time_format)
            elif alt_format:
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
                    end_text = format_target(
                        target,
                        time_format=time_format,
                        date_format=date_format,
                    ) if end else None
                    fallback = countdown_text
                    if title:
                        fallback = title + "\n" + fallback
                    if end:
                        fallback = fallback + "\n" + end_text
                    try:
                        draw_text(
                            stdscr,
                            countdown_text if no_figlet else figlet.renderText(countdown_text),
                            color=1 if seconds_left <= critical else 0,
                            fallback=fallback,
                            title=title if no_figlet or not title else figlet.renderText(title),
                            end=end_text,
                            no_figlet_y_offset=no_figlet_y_offset,
                        )
                    except CharNotPrinted:
                        draw_text(stdscr, "E")
            annunciation = None
            if seconds_left <= critical:
                annunciation = str(seconds_left)
            elif seconds_left in (5, 10, 20, 30, 60):
                annunciation = "{} {} seconds".format(voice_prefix, seconds_left)
            elif seconds_left in (300, 600, 1800):
                annunciation = "{} {} minutes".format(voice_prefix, int(seconds_left / 60))
            elif seconds_left == 3600:
                annunciation = "{} one hour".format(voice_prefix)
            if annunciation or exec_cmd:
                if exec_cmd:
                    Popen(
                        exec_cmd.format(seconds_left, annunciation or ""),
                        stdout=DEVNULL,
                        stderr=STDOUT,
                        shell=True,
                    )

                if voice_cmd:
                    Popen(
                        [voice_cmd, "-v", voice, annunciation.strip()],
                        stdout=DEVNULL,
                        stderr=STDOUT,
                    )

            # We want to sleep until this point of time has been
            # reached:
            sleep_target = sync_start + timedelta(seconds=1)
            if time:
                sleep_target = sleep_target.replace(microsecond=0)

            # If sync_start has microsecond=0, it might happen that we
            # need to skip one frame (the very first one). This occurs
            # when the program has been started at, say,
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
                                title=title if no_figlet or not title else figlet.renderText(title),
                                no_figlet_y_offset=no_figlet_y_offset,
                            )
                        except CharNotPrinted:
                            draw_text(stdscr, "E")
                    input_action = input_queue.get()
                    time_paused = datetime.now() - pause_start
                    sync_start += time_paused
                    target += time_paused
                if input_action == INPUT_EXIT:  # no elif here! input_action may have changed
                    break
                elif input_action == INPUT_PAUSE:
                    continue
                elif input_action == INPUT_RESET:
                    sync_start, target = parse_timestr(timespec)
                    seconds_left = int(ceil((target - datetime.now()).total_seconds()))
                    continue
                elif input_action == INPUT_PLUS:
                    target += timedelta(seconds=10)
                elif input_action == INPUT_MINUS:
                    target -= timedelta(seconds=10)
                elif input_action == INPUT_LAP:
                    continue
                elif input_action == INPUT_END:
                    end = not end
                    continue
            sync_start = sleep_target

            seconds_left = int(ceil((target - datetime.now()).total_seconds()))

            if seconds_left <= 0:
                # we could write this entire block outside the parent while
                # but that would leave us unable to reset everything

                if not no_bell:
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
                                    no_figlet_y_offset=no_figlet_y_offset,
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
    critical=3,
    exec_cmd=None,
    font=DEFAULT_FONT,
    no_figlet=False,
    no_figlet_y_offset=-1,
    no_seconds=False,
    quit_after=None,
    title=None,
    outfile=None,
    no_window_title=False,
    time=False,
    time_format=None,
    voice_prefix=None,
    **kwargs
):
    curses_lock, input_queue, quit_event = setup(stdscr)
    figlet = Figlet(font=font)

    if not no_figlet:
        no_figlet_y_offset = -1
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
            if time:
                stopwatch_text = datetime.now().strftime(time_format)
            elif alt_format:
                stopwatch_text = format_seconds_alt(seconds_elapsed, 0, hide_seconds=no_seconds)
            else:
                stopwatch_text = format_seconds(seconds_elapsed, hide_seconds=no_seconds)
            with curses_lock:
                if not no_window_title:
                    os.write(stdout.fileno(), "\033]2;{0}\007".format(stopwatch_text).encode())
                if outfile:
                    with open(outfile, 'w') as f:
                        f.write("{}\n{}\n".format(stopwatch_text, seconds_elapsed))
                stdscr.erase()
                try:
                    draw_text(
                        stdscr,
                        stopwatch_text if no_figlet else figlet.renderText(stopwatch_text),
                        fallback=stopwatch_text,
                        title=title,
                        no_figlet_y_offset=no_figlet_y_offset,
                    )
                except CharNotPrinted:
                    draw_text(stdscr, "E")
            if exec_cmd:
                voice_prefix = voice_prefix or ""
                annunciation = ""
                if seconds_elapsed <= critical and seconds_elapsed > 0:
                    annunciation = str(seconds_elapsed)
                elif seconds_elapsed in (5, 10, 20, 30, 40, 50, 60):
                    annunciation = "{} {} seconds".format(voice_prefix, seconds_elapsed)
                elif seconds_elapsed in (120, 180, 300, 600, 1800):
                    annunciation = "{} {} minutes".format(voice_prefix, int(seconds_elapsed / 60))
                elif seconds_elapsed == 3600:
                    annunciation = "{} one hour".format(voice_prefix)
                elif seconds_elapsed % 3600 == 0 and seconds_elapsed > 0:
                    annunciation = "{} {} hours".format(voice_prefix, int(seconds_elapsed / 3600))
                Popen(
                    exec_cmd.format(seconds_elapsed, annunciation),
                    stdout=DEVNULL,
                    stderr=STDOUT,
                    shell=True,
                )
            sleep_target = sync_start + timedelta(seconds=seconds_elapsed + 1)
            if time:
                sleep_target = sleep_target.replace(microsecond=0)
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
                            os.write(stdout.fileno(), "\033]2;{0}\007".format(stopwatch_text).encode())
                        if outfile:
                            with open(outfile, 'w') as f:
                                f.write("{}\n{}\n".format(stopwatch_text, seconds_elapsed))
                        stdscr.erase()
                        try:
                            draw_text(
                                stdscr,
                                stopwatch_text if no_figlet else figlet.renderText(stopwatch_text),
                                color=3,
                                fallback=stopwatch_text,
                                title=title,
                                no_figlet_y_offset=no_figlet_y_offset,
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
                elif input_action == INPUT_PLUS:
                    sync_start -= timedelta(seconds=10)
                elif input_action == INPUT_MINUS:
                    sync_start += timedelta(seconds=10)
                elif input_action == INPUT_LAP:
                    if pause_start:
                        sync_start += (datetime.now() - pause_start)
                        pause_start = None
                    laps.append((datetime.now() - sync_start).total_seconds())
                    sync_start = datetime.now()
                    seconds_elapsed = 0
            if time:
                seconds_elapsed = ceil((datetime.now() - sync_start).total_seconds())
            else:
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
        elif key in ("e", "E"):
            input_queue.put(INPUT_END)
        elif key in ("r", "R"):
            input_queue.put(INPUT_RESET)
        elif key in ("l", "L"):
            input_queue.put(INPUT_LAP)
        elif key == "+":
            input_queue.put(INPUT_PLUS)
        elif key == "-":
            input_queue.put(INPUT_MINUS)
        sleep(0.01)


@click.command()
@click.option("-a", "--alt-format", default=False, is_flag=True,
              help="Use colon-separated time format")
@click.option("-b", "--blink", default=False, is_flag=True,
              help="Flash terminal at end of countdown")
@click.option("-B", "--no-bell", default=False, is_flag=True,
              help="Don't ring terminal bell at end of countdown")
@click.option("-c", "--critical", default=3, metavar="N",
              help="Draw final N seconds in red and announce them individually with --voice "
                   "or --exec-cmd (defaults to 3)")
@click.option("-e", "--end", default=False, is_flag=True,
              help="Display target datetime of unpaused countdown")
@click.option("-f", "--font", default=DEFAULT_FONT, metavar="FONT",
              help="Choose from http://www.figlet.org/examples.html")
@click.option("-p", "--voice-prefix", metavar="TEXT",
              help="Add TEXT to the beginning of --voice and --exec annunciations "
                   "(except per-second ones)")
@click.option("-q", "--quit-after", metavar="N",
              help="Quit N seconds after countdown (use with -b or -t) "
                   "or terminate stopwatch after N seconds")
@click.option("-s", "--no-seconds", default=False, is_flag=True,
              help="Don't show seconds (except for last minute of countdown "
                   "and first minute of stopwatch)")
@click.option("-t", "--text",
              help="Text to display at end of countdown")
@click.option("-T", "--title",
              help="Text to display on top of countdown/stopwatch")
@click.option("-W", "--no-window-title", default=False, is_flag=True,
              help="Don't update terminal title with remaining/elapsed time")
@click.option("-v", "--voice", metavar="VOICE",
              help="Spoken countdown "
                   "(at fixed intervals with per-second annunciations starting at --critical; "
                   "requires `espeak` on Linux or `say` on macOS; "
                   "choose VOICE from `say -v '?'` or `espeak --voices`)")
@click.option("-o", "--outfile", metavar="PATH", callback=verify_outfile,
              help="File to write current remaining/elapsed time to")
@click.option("--exec-cmd", metavar="CMD",
              help="Runs CMD every second. '{0}' and '{1}' in CMD will be replaced with the "
                   "remaining/elapsed number of seconds and a more sparse annunciation as in "
                   "--voice, respectively. For example, to get a callout at five seconds only, "
                   "use: --exec-cmd \"if [ '{0}' == '5' ]; then say -v Alex {1}; fi\"")
@click.option("--no-figlet", default=False, is_flag=True,
              help="Don't use ASCII art for display")
@click.option("--no-figlet-y-offset", default=-1,
              help="Vertical offset within the terminal (only for --no-figlet)")
@click.option("--no-text-magic", default=False, is_flag=True,
              help="Don't try to replace non-ASCII characters (use with -t)")
@click.option("--version", is_flag=True, callback=print_version,
              expose_value=False, is_eager=True,
              help="Show version and exit")
@click.option("-z", "--time", default=False, is_flag=True,
              help="Show current time instead of countdown/stopwatch")
@click.option("-Z", "--time-format", default=None,
              help="Format for --time/--end (defaults to \"{}\", "
                   "ignores --no-seconds)".format(DEFAULT_TIME_FORMAT))
@click.option("-D", "--date-format", default=None,
              help="Format for --end (defaults to \"{}\")".format(DEFAULT_DATE_FORMAT))
@click.argument('timespec', metavar="[TIME]", required=False)
def main(**kwargs):
    """
    \b
    Starts a countdown to TIME. Example values for TIME:
    10, '1h 5m 30s', '12:00', '2020-01-01', '2020-01-01 14:00 UTC'.
    \b
    If TIME is not given, termdown will operate in stopwatch mode
    and count forward.
    \b
    Hotkeys:
    \tE\tShow end time (countdown mode only)
    \tL\tLap (stopwatch mode only)
    \tR\tReset
    \tSPACE\tPause (will delay absolute TIME)
    \t+\tPlus (will add 10 seconds)
    \t-\tMinus (will subtract 10 seconds)
    \tQ\tQuit
    """
    if kwargs['time_format'] is None:
        kwargs['time_format'] = \
                DEFAULT_TIME_FORMAT[:-3] if kwargs['no_seconds'] else DEFAULT_TIME_FORMAT
    if kwargs['date_format'] is None:
        kwargs['date_format'] = DEFAULT_DATE_FORMAT

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
