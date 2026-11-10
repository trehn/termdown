from datetime import datetime, timezone

from termdown.utils import parse_timestr


def test_parse_timestr__padded_seconds():
    """A plain-seconds spec with surrounding whitespace still means seconds."""
    before = datetime.now(timezone.utc)
    target = parse_timestr(" 10 ")
    after = datetime.now(timezone.utc)
    assert before.timestamp() + 10 <= target.timestamp() <= after.timestamp() + 10
