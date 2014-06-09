#!/usr/bin/env python
VERSION = "1.3.0"

import curses
from datetime import datetime, timedelta
from math import ceil
import re
from subprocess import Popen
from time import sleep

import click
from dateutil.parser import parse
from pyfiglet import Figlet

DEFAULT_FONT = "univers"
TIMEDELTA_REGEX = re.compile(r'((?P<years>\d+)y ?)?'
                             r'((?P<days>\d+)d ?)?'
                             r'((?P<hours>\d+)h ?)?'
                             r'((?P<minutes>\d+)m ?)?'
                             r'((?P<seconds>\d+)s ?)?')


def curses_setup():
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_RED, -1)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_RED)
    curses.curs_set(False)


def draw_blink(stdscr, flipflop):
    y, x = stdscr.getmaxyx()
    for i in range(y):
        if flipflop:
            stdscr.addstr(i, 0, " " * (x-1), curses.color_pair(2))
        else:
            stdscr.addstr(i, 0, " " * (x-1))
    stdscr.refresh()


def draw_text(stdscr, text, color=0):
    y, x = stdscr.getmaxyx()
    lines = pad_to_size(text, x-1, y-1).rstrip("\n").split("\n")
    i = 0
    for line in lines:
        stdscr.addstr(i, 0, line, curses.color_pair(color))
        i += 1
    stdscr.refresh()


def format_seconds(seconds):
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
        if seconds >= period_seconds:
            output += str(int(seconds / period_seconds))
            output += period
            output += " "
            seconds = seconds % period_seconds
    return output.strip()


def graceful_ctrlc(func):
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except KeyboardInterrupt:
            pass
    return wrapper


def pad_to_size(text, x, y):
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
        sync_start,
        target,
        font=DEFAULT_FONT,
        blink=False,
        quit_after=None,
        text=None,
        voice=None,
        **kwargs
    ):
    curses_setup()
    f = Figlet(font=font)

    seconds_left = int(ceil((target - datetime.now()).total_seconds()))

    while seconds_left > 0:
        stdscr.erase()
        draw_text(
            stdscr,
            f.renderText(format_seconds(seconds_left)),
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
            sleep((sleep_target - now).total_seconds())
        sync_start = sleep_target

        seconds_left = int(ceil((target - datetime.now()).total_seconds()))

    curses.beep()

    if blink:
        flip = True
        slept = 0
        while True:
            draw_blink(stdscr, flip)
            flip = not flip
            sleep(0.5)
            slept += 0.5
            if quit_after and slept >= float(quit_after):
                return

    elif text:
        draw_text(stdscr, f.renderText(text))
        if quit_after:
            sleep(int(quit_after))
        else:
            while True:
                sleep(47)


@graceful_ctrlc
def stopwatch(stdscr, font=DEFAULT_FONT, quit_after=None, **kwargs):
    curses_setup()
    f = Figlet(font=font)

    sync_start = datetime.now()
    seconds_elapsed = 0
    while quit_after is None or seconds_elapsed < int(quit_after):
        stdscr.erase()
        draw_text(
            stdscr,
            f.renderText(format_seconds(seconds_elapsed)),
        )
        sleep_target = sync_start + timedelta(seconds=seconds_elapsed + 1)
        now = datetime.now()
        if sleep_target > now:
            sleep((sleep_target - now).total_seconds())
        seconds_elapsed = int((datetime.now() - sync_start).total_seconds())


@click.command()
@click.option("-b", "--blink", default=False, is_flag=True,
              help="Flash terminal at end of countdown")
@click.option("-f", "--font", default=DEFAULT_FONT, metavar="FONT",
              help="Choose from http://www.figlet.org/examples.html")
@click.option("-q", "--quit-after", metavar="N",
              help="Quit N seconds after countdown (use with -b or -t) "
                   "or terminate stopwatch after N seconds")
@click.option("-t", "--text",
              help="Text to display at end of countdown")
@click.option("-v", "--voice", metavar="VOICE",
              help="Mac OS X only: spoken countdown (starting at 10), "
                   "choose VOICE from `say -v '?'`")
@click.option("--version", is_flag=True, callback=print_version,
              expose_value=False, is_eager=True,
              help="Show version and exit")
@click.argument('time', required=False)
def main(**kwargs):
    """
    \b
    Starts a countdown to or from TIME. Example values for TIME:
    10, '1h 5m 30s', '12:00', '2020-01-01', '2020-01-01 14:00'.
    \b
    If TIME is not given, termdown will operate in stopwatch mode
    and count forward.
    """
    if kwargs['time']:
        try:
            sync_start, target = parse_timestr(kwargs['time'])
        except ValueError:
            click.echo("Unable to parse TIME value '{}'".format(kwargs['time']))
            exit(1)
        curses.wrapper(countdown, sync_start, target, **kwargs)
    else:
        curses.wrapper(stopwatch, **kwargs)


if __name__ == '__main__':
    main()
