1.12.0
======

2016-09-30

* added `--outfile`
* fixed exception in very small terminals
* fixed cursor-related exception in some terminals


1.11.0
======

2016-06-26

* added laps
* added support for espeak
* fixed window title not updating in some terminals


1.10.0
======

2016-03-29

* show remaining time in window title
* automatically fall back to --no-figlet if terminal is too small
* fixed Figlet rendering not being adjusted to terminal size


1.9.0
=====

2015-10-24

* now returns exit code 1 on CTRL+C
* fixed drawing area being smaller than it could be


1.8.0
=====

2015-02-15

* added ``--title``
* added ``--alt-format``
* fixed using dates in other timezones


1.7.2
=====

2015-01-15

* ``--blink`` and ``--text`` can now be combined
* ``termdown --blink 0`` will now blink instead of exiting


1.7.1
=====

2014-11-08

* stopwatch mode now prints elapsed time to stderr instead of stdout


1.7.0
=====

2014-11-03

* added --critical
* hotkeys are now case-insensitive
* stopwatch mode will print elapsed time on exit
* draw counter in green while paused


1.6.0
=====

2014-10-21

* added hotkeys
* added --no-figlet


1.5.0
=====

2014-08-05

* --no-seconds
* fixed import error in setup.py


1.4.0
=====

2014-07-24

* deal with non-ASCII characters


1.3.0
=====

2014-06-09

* stopwatch mode
* fixed formatting of 61 second display


1.2.0
=====

2014-06-08

* support for Python 3
* --version


1.1
===

2014-06-06

* --quit-after
* --voice
* packaging changes to better suit virtualenv


1.0
===

2014-06-02

* countdowns \o/
* blinking
* text after countdown
