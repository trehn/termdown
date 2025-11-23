import os
from curses import beep
from datetime import datetime, timedelta
from queue import Empty
from subprocess import DEVNULL, STDOUT, Popen
from sys import stdout
from time import time

from .events import (
    INPUT_END,
    INPUT_EXIT,
    INPUT_LAP,
    INPUT_MINUS,
    INPUT_PAUSE,
    INPUT_PLUS,
    INPUT_RESET,
)
from .ticker import Metronome
from .utils import (
    format_seconds,
    format_seconds_alt,
    format_target,
    parse_timestr,
)


def countdown(ui, args):
    target_time = parse_timestr(args.timespec)
    offset = (target_time.microsecond / 1_000_000) or None
    ticker = Metronome(ui.input_queue, offset)
    ticker.start()
    start_time = datetime.now()
    seconds_left = (target_time - start_time).total_seconds()

    while seconds_left > 0 or args.blink or args.text:
        seconds_left = (target_time - datetime.now()).total_seconds()
        countdown_text = format_seconds(seconds_left, hide_seconds=args.no_seconds)
        if seconds_left > 0:
            with ui.curses_lock:
                ui.set_window_title(countdown_text)
                if args.outfile:
                    with open(args.outfile, "w") as f:
                        f.write("{}\n{}\n".format(countdown_text, seconds_left))
                end_text = (
                    format_target(
                        target_time,
                        time_format=args.time_format,
                        date_format=args.date_format,
                    )
                    if args.end
                    else None
                )
                fallback = countdown_text
                if args.title:
                    fallback = args.title + "\n" + fallback
                if args.end:
                    fallback = args.fallback + "\n" + end_text
                color = 0
                if ticker.is_paused:
                    color = 3
                elif seconds_left <= args.critical:
                    color = 1
                ui.draw_text(
                    countdown_text,
                    color=color,
                    fallback=fallback,
                    end=end_text,
                )
        annunciation = None
        if seconds_left <= args.critical:
            annunciation = str(seconds_left)
        elif int(seconds_left) in (5, 10, 20, 30, 60):
            annunciation = "{} {} seconds".format(args.voice_prefix, seconds_left)
        elif int(seconds_left) in (300, 600, 1800):
            annunciation = "{} {} minutes".format(
                args.voice_prefix, int(seconds_left / 60)
            )
        elif int(seconds_left) == 3600:
            annunciation = "{} one hour".format(args.voice_prefix)
        if annunciation or args.exec_cmd:
            if args.exec_cmd:
                Popen(
                    args.exec_cmd.format(seconds_left, annunciation or ""),
                    stdout=DEVNULL,
                    stderr=STDOUT,
                    shell=True,
                )

            if args.voice_cmd:
                Popen(
                    [args.voice_cmd, "-v", args.voice, annunciation.strip()],
                    stdout=DEVNULL,
                    stderr=STDOUT,
                )

            input_action = ui.input_queue.get()
            if input_action == INPUT_PAUSE:
                duration = ticker.pause()
                if duration:
                    target_time += timedelta(seconds=duration)
            elif input_action == INPUT_EXIT:
                break
            elif input_action == INPUT_RESET:
                target_time = parse_timestr(args.timespec)
            elif input_action == INPUT_PLUS:
                target_time += timedelta(seconds=10)
            elif input_action == INPUT_MINUS:
                target_time -= timedelta(seconds=10)
            elif input_action == INPUT_END:
                args.end = not args.end
                continue

        if seconds_left <= 0:
            # we could write this entire block outside the parent while
            # but that would leave us unable to reset everything

            if not args.no_bell:
                with ui.curses_lock:
                    beep()

            if args.outfile:
                with open(args.outfile, "w") as f:
                    f.write("{}\n{}\n".format(args.text if args.text else "DONE", 0))

            if args.blink or args.text:
                base_color = 1 if args.blink else 0
                flip = True
                ticker.pause()  # don't flood queue while we're blinking
                while args.quit_after is None or (
                    datetime.now() - target_time
                ).total_seconds() < float(args.quit_after):
                    with ui.curses_lock:
                        ui.set_window_title("/" if flip else "\\")
                        if args.text:
                            ui.draw_text(
                                args.text,
                                color=base_color if flip else 4,
                                fallback=args.text,
                            )
                        else:
                            ui.draw_text("", color=base_color if flip else 4)
                    if args.blink:
                        flip = not flip
                    try:
                        input_action = ui.input_queue.get(True, 0.5)
                    except Empty:
                        input_action = None
                    if input_action == INPUT_EXIT:
                        return
                    elif input_action == INPUT_RESET:
                        target_time = parse_timestr(args.timespec)
                        ticker.pause()  # resume ticking
                        break


def clock(ui, args):
    time_started = time()
    seconds_elapsed = 0
    offset = timedelta(0)
    ticker = Metronome(ui.input_queue, None)
    ticker.start()
    while args.quit_after is None or seconds_elapsed < float(args.quit_after):
        seconds_elapsed = time() - time_started
        clock_text = (datetime.now() + offset).strftime(args.time_format)
        with ui.curses_lock:
            ui.set_window_title(clock_text)

            if args.outfile:
                with open(args.outfile, "w") as f:
                    f.write("{}\n{}\n".format(clock_text, seconds_elapsed))

            ui.draw_text(clock_text, color=3 if ticker.is_paused else 0)

        input_action = ui.input_queue.get()
        if input_action == INPUT_EXIT:
            break
        if input_action == INPUT_PLUS:
            offset += timedelta(seconds=10)
        elif input_action == INPUT_MINUS:
            offset -= timedelta(seconds=10)
        elif input_action == INPUT_PAUSE:
            ticker.pause()
        elif input_action == INPUT_RESET:
            offset = timedelta(0)


def stopwatch(ui, args):
    time_started = time()
    ticker = Metronome(ui.input_queue, time_started % 1.0)
    ticker.start()
    time_paused = None
    seconds_elapsed = 0
    laps = []
    while args.quit_after is None or seconds_elapsed < int(args.quit_after):
        if not time_paused:
            seconds_elapsed = time() - time_started
        else:
            seconds_elapsed = time_paused - time_started

        if args.alt_format:
            stopwatch_text = format_seconds_alt(
                seconds_elapsed, 0, hide_seconds=args.no_seconds
            )
        else:
            stopwatch_text = format_seconds(
                seconds_elapsed, hide_seconds=args.no_seconds
            )
        with ui.curses_lock:
            if not args.no_window_title:
                os.write(
                    stdout.fileno(),
                    "\033]2;{0}\007".format(stopwatch_text).encode(),
                )
            if args.outfile:
                with open(args.outfile, "w") as f:
                    f.write("{}\n{}\n".format(stopwatch_text, seconds_elapsed))

            ui.draw_text(stopwatch_text, color=3 if ticker.is_paused else 0)

        if args.exec_cmd:
            voice_prefix = args.voice_prefix or ""
            annunciation = ""
            if seconds_elapsed <= args.critical and seconds_elapsed > 0:
                annunciation = str(int(seconds_elapsed))
            elif int(seconds_elapsed) in (5, 10, 20, 30, 40, 50, 60):
                annunciation = "{} {} seconds".format(voice_prefix, seconds_elapsed)
            elif int(seconds_elapsed) in (120, 180, 300, 600, 1800):
                annunciation = "{} {} minutes".format(
                    voice_prefix, int(seconds_elapsed / 60)
                )
            elif int(seconds_elapsed) == 3600:
                annunciation = "{} one hour".format(voice_prefix)
            elif int(seconds_elapsed) % 3600 == 0 and seconds_elapsed > 0:
                annunciation = "{} {} hours".format(
                    voice_prefix, int(seconds_elapsed / 3600)
                )
            Popen(
                args.exec_cmd.format(seconds_elapsed, annunciation),
                stdout=DEVNULL,
                stderr=STDOUT,
                shell=True,
            )

        input_action = ui.input_queue.get()
        if input_action == INPUT_PLUS:
            time_started -= 10
        elif input_action == INPUT_MINUS:
            time_started += 10
        elif input_action == INPUT_PAUSE:
            duration = ticker.pause()
            if duration:  # unpaused
                time_started += duration
                time_paused = None
            else:
                time_paused = time()
        elif input_action == INPUT_EXIT:
            break
        elif input_action == INPUT_RESET:
            laps = []
            time_started = time()
        elif input_action == INPUT_LAP:
            lap_time = time()
            laps.append(lap_time - time_started)
            time_started = lap_time

    return (time() - time_started, laps)
