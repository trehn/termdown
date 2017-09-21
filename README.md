![termdown demo](/termdown.gif?raw=true)

```
Usage: termdown [OPTIONS] [TIMESPEC]

  Starts a countdown to or from TIMESPEC. Example values for TIMESPEC:
  10, '1h 5m 30s', '12:00', '2020-01-01', '2020-01-01 14:00 UTC'.

  If TIMESPEC is not given, termdown will operate in stopwatch mode
  and count forward.

  Hotkeys:
      L       Lap (stopwatch mode only)
      R       Reset
      SPACE   Pause (will delay absolute TIMESPEC)
      Q       Quit

Options:
  -a, --alt-format       Use colon-separated time format
  -b, --blink            Flash terminal at end of countdown
  -c, --critical N       Draw final N seconds in red (defaults to 3)
  -f, --font FONT        Choose from http://www.figlet.org/examples.html
  -q, --quit-after N     Quit N seconds after countdown (use with -b or -t) or
                         terminate stopwatch after N seconds
  -s, --no-seconds       Don't show seconds until last minute
  -t, --text TEXT        Text to display at end of countdown
  -T, --title TEXT       Text to display on top of countdown/stopwatch
  -W, --no-window-title  Don't update terminal title with remaining/elapsed
                         time
  -v, --voice VOICE      Spoken countdown (starting at 10; requires `espeak`
                         on Linux or `say` on macOS; choose VOICE from `say -v
                         '?'` or `espeak --voices`)
  -o, --outfile PATH     File to write current remaining/elapsed time to
  --no-figlet            Don't use ASCII art for display
  --no-text-magic        Don't try to replace non-ASCII characters (use with
                         -t)
  --version              Show version and exit
  --help                 Show this message and exit
```

```
pip install termdown
```

------------------------------------------------------------------------

![PyPI version](http://img.shields.io/pypi/v/termdown.svg) &nbsp; ![Python 2.7](http://img.shields.io/badge/Python-2.7-green.svg) &nbsp; ![Python 3.x](http://img.shields.io/badge/Python-3.x-green.svg) &nbsp; ![PyPI license](http://img.shields.io/badge/License-GPLv3-red.svg)
