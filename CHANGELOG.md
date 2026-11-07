# unreleased

* fixed unknown font names silently falling back to a different font
* fixed font path missing from TTF/OTF loading error
* fixed display lagging behind when holding down keys (#107)
* fixed stopwatch going negative when reset while paused (#109)
* fixed stopwatch going negative when taking a lap while paused
* fixed stopwatch total including paused time when quitting while paused
* fixed countdown ending up to a second late after pausing or resetting
* fixed clock updating late after pausing
* fixed time paused before a reset being added to the countdown when unpausing
* fixed countdown restarting paused when it reached zero while paused
* fixed countdown announcing 4/9/29 minutes instead of 5/10/30
* fixed `--exec-cmd` receiving fractional seconds as `{0}`
* fixed announcements and `--exec-cmd` repeating on keypresses
* fixed random fonts (e.g. `-f random`) being rejected, they're now picked once at startup
* fixed non-ASCII characters in `--title` not being replaced
* fixed durations like `1h30` silently ignoring everything after the first match
* fixed past dates without a year (e.g. `5th 10:00`) being moved by one day
* fixed past times being moved to tomorrow off by an hour across DST changes


# 2.0.0

2026-01-31

* added TTF/OTF support
* added exit code 1 for premature countdown cancellation
* added min/max for stopwatch lap times
* changed outfile to being kept after exit
* changed past times being interpreted as tomorrow if no date given
* fixed incorrect countdown duration during DST changes
* rewrite with lots of internal changes


# 1.18.0

2021-11-10

* added `--end` and E hotkey
* added `--no-figlet-y-offset`
* added support for `espeak-ng`
* changed paused text color to blue
* fixed high CPU usage with `--time`
* fixed delayed countdown after repeatedly pausing and unpausing


# 1.17.0

2020-04-10

* removed support for Python 2
* added - hotkey


# 1.16.0

2019-07-25

* added + hotkey
* now works on Windows


# 1.15.0

2019-06-17

* added `--exec-cmd`


# 1.14.1

2018-07-20

* fixed `--no-seconds` not playing nice with `--time` and `--alt-format`


# 1.14.0

2018-07-15

* added `--time` and `--time-format`
* added `--no-bell`


# 1.13.0

2018-03-18

* added voice announciations at fixed intervals
* added `--voice-prefix`
* per-second voice announciations now start at `--critical`


# 1.12.2

2018-02-26

* fixed lap times being recorded incorrectly while paused


# 1.12.1

2017-09-21

* fixed espeak output messing up ncurses
* fixed title not being included in non-figlet fallback text


# 1.12.0

2016-09-30

* added `--outfile`
* fixed exception in very small terminals
* fixed cursor-related exception in some terminals


# 1.11.0

2016-06-26

* added laps
* added support for espeak
* fixed window title not updating in some terminals


# 1.10.0

2016-03-29

* show remaining time in window title
* automatically fall back to --no-figlet if terminal is too small
* fixed Figlet rendering not being adjusted to terminal size


# 1.9.0

2015-10-24

* now returns exit code 1 on CTRL+C
* fixed drawing area being smaller than it could be


# 1.8.0

2015-02-15

* added ``--title``
* added ``--alt-format``
* fixed using dates in other timezones


# 1.7.2

2015-01-15

* ``--blink`` and ``--text`` can now be combined
* ``termdown --blink 0`` will now blink instead of exiting


# 1.7.1

2014-11-08

* stopwatch mode now prints elapsed time to stderr instead of stdout


# 1.7.0

2014-11-03

* added --critical
* hotkeys are now case-insensitive
* stopwatch mode will print elapsed time on exit
* draw counter in green while paused


# 1.6.0

2014-10-21

* added hotkeys
* added --no-figlet


# 1.5.0

2014-08-05

* --no-seconds
* fixed import error in setup.py


# 1.4.0

2014-07-24

* deal with non-ASCII characters


# 1.3.0

2014-06-09

* stopwatch mode
* fixed formatting of 61 second display


# 1.2.0

2014-06-08

* support for Python 3
* --version


# 1.1

2014-06-06

* --quit-after
* --voice
* packaging changes to better suit virtualenv


# 1.0

2014-06-02

* countdowns \o/
* blinking
* text after countdown
