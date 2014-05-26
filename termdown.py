#!/usr/bin/env python
import curses
from datetime import datetime
from time import sleep

import click
from dateutil.parser import parse
from pyfiglet import Figlet


def format_seconds(seconds):
    if seconds <= 60:
        return str(seconds)
    output = ""
    if seconds > 31557600:
        output += "{}y ".format(int(seconds / 31557600))
        seconds = seconds % 31557600
    if seconds > 86400:
        output += "{}d ".format(int(seconds / 86400))
        seconds = seconds % 86400
    if seconds > 3600:
        output += "{}h ".format(int(seconds / 3600))
        seconds = seconds % 3600
    if seconds > 60:
        output += "{}m ".format(int(seconds / 60))
        seconds = seconds % 60
    if seconds:
        output += "{}s".format(int(seconds))
    return output.strip()


def pad_to_size(text, x, y):
    input_lines = text.rstrip().split("\n")
    longest_input_line = max(map(len, input_lines))
    number_of_input_lines = len(input_lines)
    x = max(x, longest_input_line)
    y = max(y, number_of_input_lines)
    empty_line = " " * x + "\n"
    output = ""

    padding_top = int((y - number_of_input_lines) / 2)
    padding_bottom = y - number_of_input_lines - padding_top
    padding_left = int((x - longest_input_line) / 2)
    padding_right = x - longest_input_line - padding_left

    output += padding_top * empty_line
    for line in input_lines:
        output += padding_left * " " + line + padding_right * " " + "\n"
    output += padding_bottom * empty_line

    return output


def draw_blink(stdscr, flipflop):
    y, x = stdscr.getmaxyx()
    for i in range(y):
        if flipflop:
            stdscr.addstr(i, 0, " " * (x-1), curses.color_pair(1))
        else:
            stdscr.addstr(i, 0, " " * (x-1))
    stdscr.refresh()


def draw_text(stdscr, text):
    y, x = stdscr.getmaxyx()
    lines = pad_to_size(text, x-1, y-1).rstrip("\n").split("\n")
    i = 0
    for line in lines:
        stdscr.addstr(
            i,
            0,
            line,
        )
        i += 1
    stdscr.refresh()


def countdown(stdscr, **kwargs):
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_RED)

    f = Figlet(font='univers')

    if kwargs['start'].isdigit():
        i = int(kwargs['start'])
    else:
        date = parse(kwargs['start'])
        i = int((date - datetime.now()).total_seconds())


    while i > 0:
        draw_text(stdscr, f.renderText(format_seconds(i)))
        i -= 1
        sleep(1)

    if kwargs['blink']:
        flip = True
        while True:
            draw_blink(stdscr, flip)
            flip = not flip
            sleep(1)


@click.command()
@click.option("-b", "--blink", default=False, is_flag=True)
@click.argument('start')
def main(**kwargs):
    curses.wrapper(countdown, **kwargs)


if __name__ == '__main__':
    main()
