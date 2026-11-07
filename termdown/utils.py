import re
import unicodedata
from datetime import datetime, timedelta, timezone
from math import ceil

from dateutil import tz
from dateutil.parser import parse

NORMALIZE_TEXT_MAP = {
    "ä": "ae",
    "Ä": "Ae",
    "ö": "oe",
    "Ö": "Oe",
    "ü": "ue",
    "Ü": "Ue",
    "ß": "ss",
}
TIMEDELTA_REGEX = re.compile(
    r"((?P<years>\d+)y\s*)?"
    r"((?P<days>\d+)d\s*)?"
    r"((?P<hours>\d+)h\s*)?"
    r"((?P<minutes>\d+)m\s*)?"
    r"((?P<seconds>\d+)s\s*)?"
)


def format_seconds(seconds, hide_seconds=False):
    """
    Returns a human-readable string representation of the given amount
    of seconds.
    """
    seconds = int(ceil(seconds))
    if seconds <= 60:
        return str(seconds)
    output = ""
    for period, period_seconds in (
        ("y", 31557600),
        ("d", 86400),
        ("h", 3600),
        ("m", 60),
        ("s", 1),
    ):
        if seconds >= period_seconds and not (hide_seconds and period == "s"):
            output += str(int(seconds / period_seconds))
            output += period
            output += " "
            seconds = seconds % period_seconds
    return output.strip()


def format_seconds_alt(seconds, hide_seconds=False):
    output = ""
    seconds = int(ceil(seconds))
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
        elif 86400 > period_seconds or total_seconds > period_seconds:
            output += "00:"
        seconds = seconds % period_seconds
    return output.rstrip(":")


def format_target(target, time_format, date_format):
    """
    Returns a human-readable string representation of the countdown's target
    datetime. Converts UTC target to local time for display.
    """
    target = target.astimezone(tz.tzlocal())
    if datetime.now().date() != target.date():
        fmt = "{} {}".format(date_format, time_format)
    else:
        fmt = time_format
    return target.strftime(fmt)


def normalize_text(input_str):
    for char, replacement in NORMALIZE_TEXT_MAP.items():
        input_str = input_str.replace(char, replacement)
    return "".join(
        [
            c
            for c in unicodedata.normalize("NFD", input_str)
            if unicodedata.category(c) != "Mn"
        ]
    )


def pad_to_size(text, x, y):
    """
    Adds whitespace to text to center it within a frame of the given
    dimensions.
    """
    input_lines = text.rstrip("\n").split("\n")
    number_of_input_lines = len(input_lines)
    output = ""

    padding_top = int((y - number_of_input_lines) / 2)
    padding_bottom = y - number_of_input_lines - padding_top

    output += padding_top * (" " * x + "\n")
    for line in input_lines:
        padding_left = int((x - len(line)) / 2)
        output += (
            padding_left * " " + line + " " * (x - padding_left - len(line)) + "\n"
        )
    output += padding_bottom * (" " * x + "\n")
    return output


def parse_timestr(timestr):
    """
    Parse a string describing a point in time.
    Returns a timezone-aware datetime in UTC to avoid issues with DST changes.
    """
    timedelta_secs = parse_timedelta(timestr)

    if timedelta_secs is not None:
        return datetime.now(timezone.utc) + timedelta(seconds=timedelta_secs)
    if timestr.isdigit():
        return datetime.now(timezone.utc) + timedelta(seconds=int(timestr))

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        target = _parse_datetime(timestr, today)
        if target <= datetime.now(timezone.utc) and not _contains_date(
            timestr, today, target
        ):
            # User only gave us a time and it's in the past - probably
            # means that time tomorrow.
            target = _parse_datetime(timestr, today + timedelta(days=1))
    except Exception:
        # unfortunately, dateutil doesn't raise the best exceptions
        raise ValueError("Unable to parse '{}'".format(timestr))
    return target.astimezone(timezone.utc)


def _parse_datetime(timestr, default):
    """
    Parses timestr, filling in missing components from default. Returns a
    timezone-aware datetime, assuming local time if no timezone is given.
    """
    target = parse(timestr, default=default)
    if target.tzinfo is None:
        target = target.replace(tzinfo=tz.tzlocal())
    return target


def _contains_date(timestr, default, parsed):
    """
    Returns True if timestr specifies (part of) a date or a weekday, i.e.
    if parsing it doesn't just use the date from the given default.
    """
    if parsed.date() != default.date():
        return True
    # Parse again with a default that differs in year, month, day and weekday.
    for day in (1, 2, 3):
        other = datetime(default.year - 1, default.month % 12 + 1, day)
        if day != default.day and other.weekday() != default.weekday():
            break
    try:
        return parse(timestr, default=other).date() != other.date()
    except ValueError:
        # e.g. Feb 29 in a non-leap year, so there definitely is a date
        return True


def parse_timedelta(deltastr):
    """
    Parse a string describing a period of time. Returns None if deltastr
    doesn't look like one.
    """
    deltastr = deltastr.strip()
    matches = TIMEDELTA_REGEX.match(deltastr)
    if not matches.group(0):
        return None
    if matches.end() != len(deltastr):
        # e.g. "1h30", don't silently ignore the rest
        raise ValueError("Unable to parse '{}'".format(deltastr))
    components = {}
    for name, value in matches.groupdict().items():
        if value:
            components[name] = int(value)
    for period, hours in (("days", 24), ("years", 8766)):
        if period in components:
            components["hours"] = (
                components.get("hours", 0) + components[period] * hours
            )
            del components[period]
    return int(timedelta(**components).total_seconds())
