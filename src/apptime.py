"""Current date and time in the plant's timezone.

The container's clock runs on UTC, so `datetime.now()` recorded check-ins five hours
behind the wall clock in Pakistan, and `date.today()` filed anything between midnight
and 05:00 local under the previous day. Attendance is inherently local — a shift
belongs to the day the plant says it does — so every "now" in the app comes from here.

Values stay naive (no tzinfo) because the columns are plain DATE/TIME, but they are
always read in APP_TIMEZONE. Set APP_TIMEZONE to move the plant to another zone.
"""
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

APP_TIMEZONE = os.environ.get('APP_TIMEZONE', 'Asia/Karachi').strip() or 'Asia/Karachi'

# Pakistan is UTC+5 year-round, so a fixed offset is a faithful last resort if the tz
# database is unavailable. Nothing here may raise: this module is imported at startup,
# and an exception would take the whole API down rather than just shifting a clock.
_FALLBACK = timezone(timedelta(hours=5))


def _zone(name):
    try:
        return ZoneInfo(name)
    except Exception:
        return None


_TZ = _zone(APP_TIMEZONE) or _zone('Asia/Karachi') or _FALLBACK


def now():
    """Local wall-clock datetime, naive, in APP_TIMEZONE."""
    return datetime.now(_TZ).replace(tzinfo=None)


def today():
    """Local calendar date in APP_TIMEZONE."""
    return now().date()


def now_time():
    """Local wall-clock time in APP_TIMEZONE."""
    return now().time()
