import os
from argparse import ArgumentParser, RawTextHelpFormatter
from curses import wrapper
from functools import wraps
from os.path import abspath, dirname
from sys import stderr

from . import VERSION
from .modes import clock, countdown, stopwatch
from .ui import Ui
from .utils import format_seconds, normalize_text

DEFAULT_FONT = "univers"
DEFAULT_TIME_FORMAT = "%H:%M:%S"  # --no-seconds expects this to end with :%S
DEFAULT_DATE_FORMAT = "%Y-%m-%d"


def _escape_percent_for_argparse_help(text):
    """Escapes literal percent signs in text for argparse help messages."""
    return text.replace("%", "%%")


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


parser = ArgumentParser(
    prog="termdown",
    description="""
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
    \tQ\tQuit""",
    epilog="Tempus fugit.",
    formatter_class=RawTextHelpFormatter,
)
parser.add_argument(
    "-a",
    "--alt-format",
    action="store_true",
    help="Use colon-separated time format",
)
parser.add_argument(
    "-b", "--blink", action="store_true", help="Flash terminal at end of countdown"
)
parser.add_argument(
    "-B",
    "--no-bell",
    action="store_true",
    help="Don't ring terminal bell at end of countdown",
)
parser.add_argument(
    "-c",
    "--critical",
    type=int,
    default=3,
    metavar="N",
    help="Draw final N seconds in red and announce them individually with --voice "
    "or --exec-cmd (defaults to 3)",
)
parser.add_argument(
    "-e",
    "--end",
    action="store_true",
    help="Display target datetime of unpaused countdown",
)
parser.add_argument(
    "-f",
    "--font",
    default=DEFAULT_FONT,
    metavar="FONT",
    help="Choose from https://www.ascii-art.site/FontList.html or provide a full path to an OTF/TTF file",
)
parser.add_argument(
    "--font-charset",
    default=" ░▒▓█",
    metavar="CHARSET",
    help='Provide a string of characters of increasing visual density (e.g. " .oO#@") to render OTF/TTF pixels',
)
parser.add_argument(
    "--font-size",
    type=int,
    default=24,
    metavar="N",
    help="Set font size when using OTF/TTF",
)
parser.add_argument(
    "-p",
    "--voice-prefix",
    metavar="TEXT",
    help="Add TEXT to the beginning of --voice and --exec annunciations "
    "(except per-second ones)",
)
parser.add_argument(
    "-q",
    "--quit-after",
    type=int,
    metavar="N",
    help="Quit N seconds after countdown (use with -b or -t) "
    "or terminate stopwatch after N seconds",
)
parser.add_argument(
    "-s",
    "--no-seconds",
    action="store_true",
    help="Don't show seconds (except for last minute of countdown "
    "and first minute of stopwatch)",
)
parser.add_argument("-t", "--text", help="Text to display at end of countdown")
parser.add_argument(
    "-T", "--title", help="Text to display on top of countdown/stopwatch"
)
parser.add_argument(
    "-W",
    "--no-window-title",
    action="store_true",
    help="Don't update terminal title with remaining/elapsed time",
)
parser.add_argument(
    "-v",
    "--voice",
    metavar="VOICE",
    help="Spoken countdown "
    "(at fixed intervals with per-second annunciations starting at --critical; "
    "requires `espeak` on Linux or `say` on macOS; "
    "choose VOICE from `say -v '?'` or `espeak --voices`)",
)
parser.add_argument(
    "-o",
    "--outfile",
    metavar="PATH",
    help="File to write current remaining/elapsed time to",
)
parser.add_argument(
    "--exec-cmd",
    metavar="CMD",
    help="Runs CMD every second. '{0}' and '{1}' in CMD will be replaced with the "
    "remaining/elapsed number of seconds and a more sparse annunciation as in "
    "--voice, respectively. For example, to get a callout at five seconds only, "
    "use: --exec-cmd \"if [ '{0}' == '5' ]; then say -v Alex {1}; fi\"",
)
parser.add_argument(
    "--no-art", action="store_true", help="Don't use ASCII art for display"
)
parser.add_argument(
    "--no-text-magic",
    action="store_true",
    help="Don't try to replace non-ASCII characters (use with -t)",
)
parser.add_argument(
    "-z",
    "--time",
    action="store_true",
    help="Show current time instead of countdown/stopwatch",
)
parser.add_argument(
    "-Z",
    "--time-format",
    default=None,
    help=f'Format for --time/--end (defaults to "{_escape_percent_for_argparse_help(DEFAULT_TIME_FORMAT)}", ignores --no-seconds)',
)
parser.add_argument(
    "-D",
    "--date-format",
    default=None,
    help=f'Format for --end (defaults to "{_escape_percent_for_argparse_help(DEFAULT_DATE_FORMAT)}")',
)
parser.add_argument(
    "timespec",
    nargs="?",
    default=None,
    help="TIME to countdown to. Example values: 10, '1h 5m 30s', '12:00', "
    "'2020-01-01', '2020-01-01 14:00 UTC'. If not given, operates in stopwatch mode.",
)
parser.add_argument(
    "--version",
    action="version",
    version=f"%(prog)s {VERSION}",
    help="Show version and exit",
)


@graceful_ctrlc
def curses_ui(stdscr, mode, args):
    ui = Ui(stdscr, args)
    ui.start_input_thread()
    try:
        return mode(ui, args)
    finally:
        with ui.curses_lock:
            if not args.no_window_title:
                ui.set_window_title("")


def main():
    args = parser.parse_args()
    if args.exec_cmd and args.voice:  # prevent passing both --exec-cmd and --voice
        raise RuntimeError("--exec-cmd and --voice are mutually exclusive")

    if args.time_format is None:
        args.time_format = (
            DEFAULT_TIME_FORMAT[:-3] if args.no_seconds else DEFAULT_TIME_FORMAT
        )
    if args.date_format is None:
        args.date_format = DEFAULT_DATE_FORMAT

    if args.outfile:
        if os.path.exists(args.outfile):
            raise RuntimeError("File already exists: {}".format(args.outfile))
        if not os.access(dirname(abspath(args.outfile)), os.W_OK):
            raise RuntimeError("Unable to write file: {}".format(args.outfile))

    if args.text and not args.no_text_magic:
        args.text = normalize_text(args.text)

    args.voice_cmd = None
    if args.voice:
        for cmd in ("/usr/bin/say", "/usr/bin/espeak", "/usr/bin/espeak-ng"):
            if os.path.exists(cmd):
                args.voice_cmd = cmd
                break
    if args.voice or args.exec_cmd:
        args.voice_prefix = args.voice_prefix or ""

    if args.time:
        wrapper(curses_ui, clock, args)
    elif args.timespec:
        wrapper(curses_ui, countdown, args)
    else:
        seconds_elapsed, laps = wrapper(curses_ui, stopwatch, args)

        for lap_index, lap_time in enumerate(laps):
            stderr.write(
                "{:.3f}\t{}\tlap {}\n".format(
                    lap_time,
                    format_seconds(int(lap_time)),
                    lap_index + 1,
                )
            )

        if laps:
            stderr.write(
                "{:.3f}\t{}\tlap {}\n".format(
                    seconds_elapsed,
                    format_seconds(int(seconds_elapsed)),
                    len(laps) + 1,
                )
            )
            laps.append(seconds_elapsed)
            total_seconds = sum(laps)
            average_seconds = total_seconds / len(laps)
            stderr.write(
                "{:.3f}\t{}\tlap min\n".format(
                    min(laps),
                    format_seconds(int(min(laps))),
                )
            )
            stderr.write(
                "{:.3f}\t{}\tlap max\n".format(
                    max(laps),
                    format_seconds(int(max(laps))),
                )
            )
            stderr.write(
                "{:.3f}\t{}\tlap avg\n".format(
                    average_seconds,
                    format_seconds(int(average_seconds)),
                )
            )
            stderr.write(
                "{:.3f}\t{}\ttotal\n".format(
                    total_seconds,
                    format_seconds(int(total_seconds)),
                )
            )
        else:
            stderr.write(
                "{:.3f}\t{}\ttotal\n".format(
                    seconds_elapsed,
                    format_seconds(int(seconds_elapsed)),
                )
            )
        stderr.flush()
