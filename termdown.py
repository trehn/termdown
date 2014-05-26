#!/usr/bin/env python
import curses
from time import sleep

import click
from pyfiglet import Figlet


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


def countdown(stdscr, start):
    f = Figlet(font='univers')
    i = int(start)
    while i > 0:
        draw_text(stdscr, f.renderText(str(i)))
        i -= 1
        sleep(1)


@click.command()
@click.argument('start')
def main(start):
    curses.wrapper(countdown, start)


if __name__ == '__main__':
    main()
