import os
from curses import beep
from datetime import datetime, timedelta, timezone
from math import ceil
from queue import Empty
from subprocess import DEVNULL, STDOUT, Popen
from sys import exit, stdout
from threading import Timer
from time import monotonic, time

from .events import (
    INPUT_END,
    INPUT_EXIT,
    INPUT_LAP,
    INPUT_MINUS,
    INPUT_PAUSE,
    INPUT_PLUS,
    INPUT_RESET,
    TIME_TICK,
)
from .ticker import Metronome
from .utils import (
    format_seconds,
    format_seconds_alt,
    format_target,
    parse_timestr,
)


def _wake_up_in(seconds, ui):
    """
    Makes sure the mode loop runs again after the given number of seconds,
    if that is before the next regular tick.
    """
    if seconds < 1:
        timer = Timer(seconds, ui.input_queue.put, (TIME_TICK,))
        timer.daemon = True
        timer.start()


def countdown(ui, args):
    target_time = parse_timestr(args.timespec)
    # tick whenever the number of seconds left crosses a whole number
    ticker = Metronome(ui.input_queue, offset=target_time.timestamp())
    ticker.start()
    last_announced = None

    while True:  # Outer loop to allow restarting countdown from scratch
        while True:  # Active countdown loop
            seconds_left = (target_time - datetime.now(timezone.utc)).total_seconds()
            if seconds_left <= 0:
                # If seconds_left is zero or negative, immediately break to handle the
                # "finished" state. This prevents displaying "0" for an entire second
                # while waiting for the next tick.
                break

            if args.alt_format:
                countdown_text = format_seconds_alt(
                    seconds_left, hide_seconds=args.no_seconds
                )
            else:
                countdown_text = format_seconds(
                    seconds_left, hide_seconds=args.no_seconds
                )

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
                color = 0
                if ticker.is_paused:
                    color = 3
                elif seconds_left <= args.critical:
                    color = 1
                ui.draw_text(countdown_text, color=color, end=end_text)

            # the number of seconds as displayed
            whole_seconds_left = int(ceil(seconds_left))
            annunciation = None
            if whole_seconds_left <= args.critical:
                annunciation = str(whole_seconds_left)
            elif whole_seconds_left in (5, 10, 20, 30, 60):
                annunciation = "{} {} seconds".format(
                    args.voice_prefix, whole_seconds_left
                )
            elif whole_seconds_left in (300, 600, 1800):
                annunciation = "{} {} minutes".format(
                    args.voice_prefix, whole_seconds_left // 60
                )
            elif whole_seconds_left == 3600:
                annunciation = "{} one hour".format(args.voice_prefix)
            # don't repeat ourselves when redrawing due to keypresses
            if whole_seconds_left != last_announced:
                last_announced = whole_seconds_left
                if (
                    annunciation and args.voice_cmd
                ):  # Only announce if there is something to say
                    Popen(
                        [args.voice_cmd, "-v", args.voice, annunciation.strip()],
                        stdout=DEVNULL,
                        stderr=STDOUT,
                    )
                if args.exec_cmd:
                    # Pass annunciation even if it's empty, format() handles it.
                    Popen(
                        args.exec_cmd.format(
                            whole_seconds_left, annunciation or ""
                        ),
                        stdout=DEVNULL,
                        stderr=STDOUT,
                        shell=True,
                    )

            for input_action in ui.get_input_actions():
                if input_action == INPUT_PAUSE:
                    duration = ticker.pause()
                    if duration:
                        target_time += timedelta(seconds=duration)
                        ticker.align(target_time.timestamp())
                elif input_action == INPUT_EXIT:
                    exit(1)
                elif input_action == INPUT_RESET:
                    target_time = parse_timestr(args.timespec)
                    ticker.align(target_time.timestamp())
                    # don't add time paused before the reset when unpausing
                    ticker.restart_pause()
                elif input_action == INPUT_PLUS:
                    target_time += timedelta(seconds=10)
                elif input_action == INPUT_MINUS:
                    target_time -= timedelta(seconds=10)
                elif input_action == INPUT_END:
                    args.end = not args.end

        # After the active countdown loop, handle the "time is up" state.

        if not args.no_bell:
            with ui.curses_lock:
                beep()

        if args.outfile:
            with open(args.outfile, "w") as f:
                f.write("{}\n{}\n".format(args.text if args.text else "DONE", 0))

        if args.blink or args.text:
            base_color = 1 if args.blink else 0
            flip = True
            if not ticker.is_paused:  # we might have reached zero while paused
                ticker.pause()  # Pause ticker during blinking phase
            while True:
                if args.quit_after and (
                    datetime.now(timezone.utc) - target_time
                ).total_seconds() > float(args.quit_after):
                    return
                with ui.curses_lock:
                    ui.set_window_title("/" if flip else "\\")
                    if args.text:
                        ui.draw_text(args.text, color=base_color if flip else 4)
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
                    ticker.align(target_time.timestamp())
                    ticker.pause()  # resume
                    break  # Break out of the blinking loop to restart the main countdown
        else:
            break


def clock(ui, args):
    time_started = monotonic()
    seconds_elapsed = 0
    offset = timedelta(0)
    ticker = Metronome(ui.input_queue)
    ticker.start()
    while True:
        seconds_elapsed = monotonic() - time_started
        if args.quit_after:
            seconds_until_quit = float(args.quit_after) - seconds_elapsed
            if seconds_until_quit <= 0:
                return
            # ticks happen on full seconds of the clock, not since we started
            _wake_up_in(seconds_until_quit, ui)
        clock_text = (datetime.now() + offset).strftime(args.time_format)
        with ui.curses_lock:
            ui.set_window_title(clock_text)

            if args.outfile:
                with open(args.outfile, "w") as f:
                    f.write("{}\n{}\n".format(clock_text, seconds_elapsed))

            ui.draw_text(clock_text, color=3 if ticker.is_paused else 0)

        for input_action in ui.get_input_actions():
            if input_action == INPUT_EXIT:
                return
            if input_action == INPUT_PLUS:
                offset += timedelta(seconds=10)
            elif input_action == INPUT_MINUS:
                offset -= timedelta(seconds=10)
            elif input_action == INPUT_PAUSE:
                ticker.pause()
            elif input_action == INPUT_RESET:
                offset = timedelta(0)


def stopwatch(ui, args):
    time_started = monotonic()
    ticker = Metronome(ui.input_queue, offset=time() % 1.0)
    ticker.start()
    time_paused = None
    seconds_elapsed = 0
    last_announced = None
    laps = []

    def now():
        # while paused, time stands still at the moment we paused
        return monotonic() if time_paused is None else time_paused

    def align_ticker():
        # tick whenever the number of seconds elapsed crosses a whole number
        ticker.align(time() - (now() - time_started))

    while True:
        seconds_elapsed = now() - time_started

        if args.quit_after:
            # laps restart seconds_elapsed, but not the stopwatch as a whole
            seconds_until_quit = float(args.quit_after) - sum(laps) - seconds_elapsed
            if seconds_until_quit <= 0:
                return seconds_elapsed, laps
            if not ticker.is_paused:
                # after laps, ticks no longer line up with the total time
                _wake_up_in(seconds_until_quit, ui)

        if args.alt_format:
            stopwatch_text = format_seconds_alt(
                round(seconds_elapsed), hide_seconds=args.no_seconds
            )
        else:
            stopwatch_text = format_seconds(
                round(seconds_elapsed), hide_seconds=args.no_seconds
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

        whole_seconds_elapsed = int(seconds_elapsed)
        annunciation = None
        if 1 <= whole_seconds_elapsed <= args.critical:
            annunciation = str(whole_seconds_elapsed)
        elif whole_seconds_elapsed in (5, 10, 20, 30, 40, 50, 60):
            annunciation = "{} {} seconds".format(
                args.voice_prefix, whole_seconds_elapsed
            )
        elif whole_seconds_elapsed in (120, 180, 300, 600, 1800):
            annunciation = "{} {} minutes".format(
                args.voice_prefix, whole_seconds_elapsed // 60
            )
        elif whole_seconds_elapsed == 3600:
            annunciation = "{} one hour".format(args.voice_prefix)
        elif whole_seconds_elapsed % 3600 == 0 and whole_seconds_elapsed > 0:
            annunciation = "{} {} hours".format(
                args.voice_prefix, whole_seconds_elapsed // 3600
            )

        # don't repeat ourselves when redrawing due to keypresses
        if whole_seconds_elapsed != last_announced:
            last_announced = whole_seconds_elapsed
            if annunciation and args.voice_cmd:
                Popen(
                    [args.voice_cmd, "-v", args.voice, annunciation.strip()],
                    stdout=DEVNULL,
                    stderr=STDOUT,
                )
            if args.exec_cmd:
                Popen(
                    args.exec_cmd.format(whole_seconds_elapsed, annunciation or ""),
                    stdout=DEVNULL,
                    stderr=STDOUT,
                    shell=True,
                )

        for input_action in ui.get_input_actions():
            if input_action == INPUT_PLUS:
                time_started -= 10
            elif input_action == INPUT_MINUS:
                time_started += 10
            elif input_action == INPUT_PAUSE:
                duration = ticker.pause()
                if duration:  # unpaused
                    time_started += duration
                    time_paused = None
                    align_ticker()
                else:
                    time_paused = monotonic()
            elif input_action == INPUT_EXIT:
                return (now() - time_started, laps)
            elif input_action == INPUT_RESET:
                laps = []
                # If paused, this rebases the start to the pause instant so the
                # display resets to 0 instead of going negative by the time spent
                # paused before the reset.
                time_started = now()
                align_ticker()
            elif input_action == INPUT_LAP:
                lap_time = now()
                laps.append(lap_time - time_started)
                time_started = lap_time
                align_ticker()
