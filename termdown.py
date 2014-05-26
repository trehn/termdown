import curses
from sys import argv
from time import sleep

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
    stdscr.erase()
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

def main(stdscr):
    count = 5
    f = Figlet(font='ogre')
    i = count
    while i > 0:
        draw_text(stdscr, f.renderText(str(i)))
        i -= 1
        sleep(1)


curses.wrapper(main)
