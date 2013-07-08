# coding: utf-8

# TODO - some sort of .replace() support

from __future__ import absolute_import
import calendar
from datetime import datetime
import dateutil.parser
import dateutil.relativedelta
import pytz

override_timezone = []

class QuantumException(Exception):
    pass

def default_timezone():
    if len(override_timezone):
        return override_timezone[-1]
    return None

def get_timezone(tz):
    if isinstance(tz, basestring):
        tz = pytz.timezone(tz)

    if not (tz == pytz.utc or isinstance(tz, pytz.tzinfo.DstTzInfo)):
        raise ValueError("Not a valid timezone object: %s" % tz)

    return tz

class timezone(object):
    def __init__(self, timezone):
        self.tz = get_timezone(timezone)

    def __enter__(self):
        override_timezone.append(self.tz)

    def __exit__(self, type, value, tb):
        override_timezone.pop()

def now(timezone=None):
    if not timezone:
        timezone = default_timezone()
    return Quantum(datetime.utcnow(), timezone)

def parse(datestring, timezone=None, format='%Y-%m-%dT%H:%M:%S', relaxed=False):
    if not timezone:
        timezone = default_timezone()

    if not timezone:
        raise QuantumException("Can't parse without a valid timezone")

    if relaxed:
        dt = dateutil.parser.parse(datestring, ignoretz=True, dayfirst=True)
    else:
        dt = datetime.strptime(datestring, format)

    return Quantum(convert_timezone(dt, timezone, 'UTC'), timezone)

def from_date(dt, timezone=None):
    if not timezone:
        timezone = default_timezone()

    if not timezone:
        raise QuantumException("Can't parse without a valid timezone")

    return Quantum(convert_timezone(datetime(dt.year, dt.month, dt.day), timezone, 'UTC'), timezone)

def from_datetime(dt, timezone=None):
    if not timezone:
        timezone = default_timezone()

    if not timezone:
        raise QuantumException("Can't parse without a valid timezone")

    return Quantum(convert_timezone(dt, timezone, 'UTC'), timezone)

def from_unix(timestamp, timezone=None):
    if not timezone:
        timezone = default_timezone()

    return Quantum(datetime.utcfromtimestamp(timestamp), timezone)

def convert_timezone(dt, from_timezone, to_timezone):
    from_timezone = get_timezone(from_timezone)
    to_timezone = get_timezone(to_timezone)
    return from_timezone.localize(dt).astimezone(to_timezone).replace(tzinfo=None)

class Quantum(object):
    dt = None
    """datetime object representing the date/time of this object (always in UTC)"""

    @property
    def tz(self):
        """the timezone of this object, used for all formatting/manipulation"""
        if len(override_timezone):
            return override_timezone[-1]
        return self._tz

    @tz.setter
    def tz(self, value):
        if value is None:
            self._tz = None
            return

        self._tz = get_timezone(value)

    def __init__(self, dt, tz=None):
        if not isinstance(dt, datetime):
            raise ValueError("First argument to Quantum must be a datetime")
        self.dt = dt
        if tz is None:
            self.tz = None
        else:
            self.tz = tz

    def _check_comparison_type(self, other):
        if not isinstance(other, Quantum):
            raise TypeError("Expected a Quantum object for comparison")
        if self.tz != other.tz:
            raise ValueError("Timezones don't match in comparison")

    def __lt__(self, other):
        self._check_comparison_type(other)
        return self.dt < other.dt

    def __le__(self, other):
        self._check_comparison_type(other)
        return self.dt <= other.dt

    def __eq__(self, other):
        self._check_comparison_type(other)
        return self.dt == other.dt

    def __ne__(self, other):
        self._check_comparison_type(other)
        return self.dt != other.dt

    def __gt__(self, other):
        self._check_comparison_type(other)
        return self.dt > other.dt

    def __ge__(self, other):
        self._check_comparison_type(other)
        return self.dt >= other.dt

    def __repr__(self):
        return "<%s(%s, %s)>" % (self.__class__.__name__, self.dt, (self.tz or 'no timezone'))

    def __str__(self):
        if self.tz is None:
            return "%s (no timezone)" % self.as_utc()
        return "%s (%s)" % (self.as_local(), self.tz)

    def at(self, timezone):
        """Returns a new Quantum object with the applied timezone"""
        return Quantum(self.dt, timezone)

    def as_utc(self):
        """Returns UTC representation of this Quantum as a naive datetime"""
        # TODO - do we need to clone this before returning?, I don't think we
        # do because you can't modify a datetime in place
        return self.dt

    def as_local(self):
        """Returns a representation of this Quantum as a naive datetime"""
        if self.tz is None:
            raise QuantumException("Can't represent a Quantum as local time without a timezone")
        return convert_timezone(self.dt, 'UTC', self.tz)

    def as_unix(self):
        return calendar.timegm(self.as_utc().timetuple()) + float(self.as_utc().microsecond)/1000000

    def add(self, years=0, months=0, days=0, hours=0, minutes=0, seconds=0, microseconds=0):
        if self.tz is None:
            raise QuantumException("Can't manipulate a Quantum that has no timezone set")
        rd = dateutil.relativedelta.relativedelta(years=years, months=months, days=days, hours=hours, minutes=minutes, seconds=seconds, microseconds=microseconds)
        local_dt = self.as_local()
        local_dt += rd
        return Quantum(convert_timezone(local_dt, self.tz, 'UTC'), self.tz)

    def subtract(self, years=0, months=0, days=0, hours=0, minutes=0, seconds=0, microseconds=0):
        if self.tz is None:
            raise QuantumException("Can't manipulate a Quantum that has no timezone set")
        return self.add(years=-years, months=-months, days=-days, hours=-hours, minutes=-minutes, seconds=-seconds, microseconds=-microseconds)

    def format_short(self):
        return self.as_local().strftime("%-e %b %Y %H:%M")

    def format_date(self):
        return self.as_local().strftime("%-e %b %Y")
