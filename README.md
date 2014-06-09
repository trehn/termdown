![termdown demo](/termdown.gif?raw=true)

```
Usage: termdown [OPTIONS] [TIME]

  Starts a countdown to or from TIME. Example values for TIME:
  10, '1h 5m 30s', '12:00', '2020-01-01', '2020-01-01 14:00'.

  If TIME is not given, termdown will operate in stopwatch mode
  and count forward.

Options:
  -b, --blink         Flash terminal at end of countdown
  -f, --font FONT     Choose from http://www.figlet.org/examples.html
  -q, --quit-after N  Quit N seconds after countdown (use with -b or -t) or
                      terminate stopwatch after N seconds
  -t, --text TEXT     Text to display at end of countdown
  -v, --voice VOICE   Mac OS X only: spoken countdown (starting at 10), choose
                      VOICE from `say -v '?'`
  --version           Show version and exit
  --help              Show this message and exit
```

```
pip install termdown
```

------------------------------------------------------------------------

![PyPI downloads](https://pypip.in/download/termdown/badge.png) &nbsp; ![PyPI version](https://pypip.in/version/termdown/badge.png) &nbsp; ![PyPI license](https://pypip.in/license/termdown/badge.png)
