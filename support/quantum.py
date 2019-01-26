# coding: utf-8

# TODO - some sort of .replace() support


import calendar
import datetime
import dateutil.parser
import dateutil.relativedelta
import pytz

city_list = [  # {{{
    ("Accra", "Africa/Accra"),
    ("Addis Ababa", "Africa/Addis_Ababa"),
    ("Adelaide", "Australia/Adelaide"),
    ("Algiers", "Africa/Algiers"),
    ("Almaty", "Asia/Almaty"),
    ("Amman", "Asia/Amman"),
    ("Amsterdam", "Europe/Amsterdam"),
    ("Anadyr", "Asia/Anadyr"),
    ("Anchorage", "America/Anchorage"),
    ("Ankara", "Europe/Istanbul"),
    ("Antananarivo", "Indian/Antananarivo"),
    ("Asuncion", "America/Asuncion"),
    ("Athens", "Europe/Athens"),
    ("Atlanta", "America/New_York"),
    ("Auckland", "Pacific/Auckland"),
    ("Baghdad", "Asia/Baghdad"),
    ("Bangalore", "Asia/Kolkata"),
    ("Bangkok", "Asia/Bangkok"),
    ("Barcelona", "Europe/Madrid"),
    ("Beijing", "Asia/Shanghai"),
    ("Beirut", "Asia/Beirut"),
    ("Belgrade", "Europe/Belgrade"),
    ("Berlin", "Europe/Berlin"),
    ("Bogota", "America/Bogota"),
    ("Boston", "America/New_York"),
    ("Brasilia", "America/Sao_Paulo"),
    ("Brisbane", "Australia/Brisbane"),
    ("Brussels", "Europe/Brussels"),
    ("Bucharest", "Europe/Bucharest"),
    ("Budapest", "Europe/Budapest"),
    ("Buenos Aires", "America/Argentina/Buenos_Aires"),
    ("Cairo", "Africa/Cairo"),
    ("Calgary", "America/Edmonton"),
    ("Canberra", "Australia/Sydney"),
    ("Cape Town", "Australia/Sydney"),
    ("Caracas", "America/Caracas"),
    ("Casablanca", "Africa/Casablanca"),
    ("Chicago", "America/Chicago"),
    ("Columbus", "America/New_York"),
    ("Copenhagen", "Europe/Copenhagen"),
    ("Dallas", "America/Chicago"),
    ("Dar es Salaam", "Africa/Dar_es_Salaam"),
    ("Darwin", "Australia/Darwin"),
    ("Denver", "America/Denver"),
    ("Detroit", "America/Detroit"),
    ("Dhaka", "Asia/Dhaka"),
    ("Doha", "Asia/Qatar"),
    ("Dubai", "Asia/Dubai"),
    ("Dublin", "Europe/Dublin"),
    ("Edmonton", "America/Edmonton"),
    ("Frankfurt", "Europe/Berlin"),
    ("Guatemala", "America/Guatemala"),
    ("Halifax", "America/Halifax"),
    ("Hanoi", "Asia/Ho_Chi_Minh"),
    ("Harare", "Africa/Harare"),
    ("Havana", "America/Havana"),
    ("Helsinki", "Europe/Helsinki"),
    ("Hong Kong", "Asia/Hong_Kong"),
    ("Honolulu", "Pacific/Honolulu"),
    ("Houston", "America/Chicago"),
    ("Indianapolis", "America/Indiana/Indianapolis"),
    ("Islamabad", "Asia/Karachi"),
    ("Istanbul", "Europe/Istanbul"),
    ("Jakarta", "Asia/Jakarta"),
    ("Jerusalem", "Asia/Jerusalem"),
    ("Johannesburg", "Africa/Johannesburg"),
    ("Kabul", "Asia/Kabul"),
    ("Karachi", "Asia/Karachi"),
    ("Kathmandu", "Asia/Kathmandu"),
    ("Khartoum", "Africa/Khartoum"),
    ("Kingston", "America/Denver"),
    ("Kinshasa", "Africa/Kinshasa"),
    ("Kiritimati", "Pacific/Kiritimati"),
    ("Kolkata", "Asia/Kolkata"),
    ("Kuala Lumpur", "Asia/Kuala_Lumpur"),
    ("Kuwait City", "Asia/Kuwait"),
    ("Kyiv", "Europe/Kiev"),
    ("Lagos", "Africa/Lagos"),
    ("Lahore", "Asia/Karachi"),
    ("La Paz", "America/La_Paz"),
    ("Las Vegas", "America/Los_Angeles"),
    ("Lima", "America/Lima"),
    ("Lisbon", "Europe/Lisbon"),
    ("London", "Europe/London"),
    ("Los Angeles", "America/Los_Angeles"),
    ("Madrid", "Europe/Madrid"),
    ("Managua", "America/Managua"),
    ("Manila", "Asia/Manila"),
    ("Melbourne", "Australia/Melbourne"),
    ("Mexico City", "America/Mexico_City"),
    ("Miami", "America/New_York"),
    ("Minneapolis", "America/Chicago"),
    ("Minsk", "Europe/Minsk"),
    ("Montevideo", "America/Montevideo"),
    ("Montreal", "America/Montreal"),
    ("Moscow", "Europe/Moscow"),
    ("Mumbai", "Asia/Kolkata"),
    ("Nairobi", "Africa/Nairobi"),
    ("Nassau", "America/Nassau"),
    ("New Delhi", "Asia/Kolkata"),
    ("New Orleans", "America/Chicago"),
    ("New York", "America/New_York"),
    ("Oslo", "Europe/Oslo"),
    ("Ottawa", "America/Toronto"),
    ("Paris", "Europe/Paris"),
    ("Perth", "Australia/Perth"),
    ("Philadelphia", "America/New_York"),
    ("Phoenix", "America/Phoenix"),
    ("Prague", "Europe/Prague"),
    ("Reykjavik", "Atlantic/Reykjavik"),
    ("Rio de Janeiro", "America/Sao_Paulo"),
    ("Riyadh", "Asia/Riyadh"),
    ("Rome", "Europe/Rome"),
    ("Salt Lake City", "America/Denver"),
    ("San Francisco", "America/Los_Angeles"),
    ("San Juan", "America/Puerto_Rico"),
    ("San Salvador", "America/El_Salvador"),
    ("Santiago", "America/Santiago"),
    ("Santo Domingo", "America/Santo_Domingo"),
    ("São Paulo", "America/Sao_Paulo"),
    ("Seattle", "America/Los_Angeles"),
    ("Seoul", "Asia/Seoul"),
    ("Shanghai", "Asia/Shanghai"),
    ("Singapore", "Asia/Singapore"),
    ("Sofia", "Europe/Sofia"),
    ("St. John's", "America/St_Johns"),
    ("Stockholm", "Europe/Stockholm"),
    ("Suva", "Pacific/Fiji"),
    ("Sydney", "Australia/Sydney"),
    ("Taipei", "Asia/Taipei"),
    ("Tallinn", "Europe/Tallinn"),
    ("Tashkent", "Asia/Tashkent"),
    ("Tegucigalpa", "America/Tegucigalpa"),
    ("Tehran", "Asia/Tehran"),
    ("Tokyo", "Asia/Tokyo"),
    ("Toronto", "America/Toronto"),
    ("Vancouver", "America/Vancouver"),
    ("Vienna", "Europe/Vienna"),
    ("Warsaw", "Europe/Warsaw"),
    ("Washington DC", "America/New_York"),
    ("Winnipeg", "America/Winnipeg"),
    ("Yangon", "Asia/Rangoon"),
    ("Zagreb", "Europe/Zagreb"),
    ("Zürich", "Europe/Zurich"),
]  # }}}

override_timezone = []


class QuantumException(Exception):
    pass


class InsufficientHolidaysException(Exception):
    pass


def default_timezone():
    if len(override_timezone):
        return override_timezone[-1]
    return None

def get_timezone(tz):
    if isinstance(tz, str):
        tz = pytz.timezone(tz)

    if not (tz == pytz.utc or isinstance(tz, pytz.tzinfo.DstTzInfo) or isinstance(tz, pytz.tzinfo.StaticTzInfo)):
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
    return Quantum(datetime.datetime.utcnow(), timezone)

def today(timezone=None):
    if not timezone:
        timezone = default_timezone()
    if not timezone:
        raise QuantumException("Can't get current date without specifying a timezone to get it in")
    return Quantum(datetime.datetime.utcnow(), timezone).date()

def parse(datestring, timezone=None, format='%Y-%m-%dT%H:%M:%S', relaxed=False):
    if not timezone:
        timezone = default_timezone()

    if not timezone:
        raise QuantumException("Can't parse without a valid timezone")

    if relaxed:
        dt = dateutil.parser.parse(datestring, ignoretz=True, dayfirst=True)
    else:
        dt = datetime.datetime.strptime(datestring, format)

    return Quantum(convert_timezone(dt, timezone, 'UTC'), timezone)

def parse_date(datestring, format='%Y-%m-%d', relaxed=False):
    if relaxed:
        dt = dateutil.parser.parse(datestring, ignoretz=True, dayfirst=True)
    else:
        dt = datetime.datetime.strptime(datestring, format)

    return QuantumDate(dt.date())

def delta(**kwargs):
    return QuantumDelta(dateutil.relativedelta.relativedelta(**kwargs))

def from_date(dt, timezone=None):
    if not timezone:
        timezone = default_timezone()

    if not timezone:
        raise QuantumException("Can't parse without a valid timezone")

    return Quantum(convert_timezone(datetime.datetime(dt.year, dt.month, dt.day), timezone, 'UTC'), timezone)

def from_datetime(dt, timezone=None):
    if not timezone:
        timezone = default_timezone()

    if dt.tzinfo:
        return Quantum(dt.astimezone(pytz.UTC).replace(tzinfo=None), timezone)

    if not timezone:
        raise QuantumException("Can't parse without a valid timezone")

    return Quantum(convert_timezone(dt, timezone, 'UTC'), timezone)

def from_unix(timestamp, timezone=None):
    if not timezone:
        timezone = default_timezone()

    return Quantum(datetime.datetime.utcfromtimestamp(timestamp), timezone)

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

    def __init__(self, dt, tz=None):
        if not isinstance(dt, datetime.datetime):
            raise ValueError("First argument to Quantum must be a datetime")
        self.dt = dt
        if tz is None:
            self._tz = None
        else:
            self._tz = get_timezone(tz)

    def __hash__(self):
        dt = self.as_utc()
        if self.tz:
            dt = dt.replace(tzinfo=self.tz)
        return dt.__hash__()

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
        if other is None:
            return False
        self._check_comparison_type(other)
        return self.dt == other.dt

    def __ne__(self, other):
        if other is None:
            return True
        self._check_comparison_type(other)
        return self.dt != other.dt

    def __gt__(self, other):
        self._check_comparison_type(other)
        return self.dt > other.dt

    def __ge__(self, other):
        self._check_comparison_type(other)
        return self.dt >= other.dt

    def __add__(self, other):
        if not isinstance(other, QuantumDelta):
            raise TypeError("Expected a QuantumDelta object for addition")
        if self.tz is None:
            raise QuantumException("Can't manipulate a Quantum with no timezone set")

        local_dt = self.as_local()
        local_dt += other.rd

        return Quantum(convert_timezone(local_dt, self.tz, 'UTC'), self.tz)

    def __sub__(self, other):
        if isinstance(other, Quantum):
            if self.tz is None:
                raise QuantumException("Can't calculate a QuantumDelta for Quantums with no timezone set")
            if self.tz != other.tz:
                raise ValueError("Timezones don't match for subtraction")
            return QuantumDelta(dateutil.relativedelta.relativedelta(self.as_local(), other.as_local()))
        elif isinstance(other, QuantumDelta):
            return self.__add__(-other)
        else:
            raise TypeError("Expected a Quantum or QuantumDelta object for subtraction")

    def __repr__(self):
        return "<%s(%s, %s)>" % (self.__class__.__name__, self.dt, (self.tz or 'no timezone'))

    def __str__(self):
        if self.tz is None:
            return "%s (no timezone)" % self.as_utc()
        return "%s (%s)" % (self.as_local(), self.tz)

    def at(self, timezone):
        """Returns a new Quantum object with the applied timezone"""
        return Quantum(self.dt, timezone)

    def as_utc(self, include_tzinfo=False):
        """Returns UTC representation of this Quantum as a naive datetime"""
        if include_tzinfo:
            return self.dt.replace(tzinfo=pytz.UTC)
        return self.dt

    def as_local(self, include_tzinfo=False):
        """Returns a representation of this Quantum as a naive datetime"""
        if self.tz is None:
            raise QuantumException("Can't represent a Quantum as local time without a timezone")
        dt = convert_timezone(self.dt, 'UTC', self.tz)
        if include_tzinfo:
            return self.tz.localize(dt)
        return dt

    def as_unix(self):
        return calendar.timegm(self.as_utc().timetuple()) + float(self.as_utc().microsecond) / 1000000

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

    def date(self):
        return QuantumDate(self.as_local().date())

    def start_of(self, period, first_day_of_week=1):
        valid_periods = ['second', 'minute', 'hour', 'day', 'week', 'month', 'year']
        if self.tz is None:
            raise QuantumException("Can't manipulate a Quantum that has no timezone set")
        if period not in valid_periods:
            raise ValueError("Invalid period for Quantum.start_of: %s" % period)

        local_dt = self.as_local()
        for p in valid_periods:
            if p == 'second':
                local_dt = local_dt.replace(microsecond=0)
            if p == 'minute':
                local_dt = local_dt.replace(second=0)
            if p == 'hour':
                local_dt = local_dt.replace(minute=0)
            if p == 'day':
                local_dt = local_dt.replace(hour=0)
            if p == 'month':
                local_dt = local_dt.replace(day=1)
            if p == 'year':
                local_dt = local_dt.replace(month=1)
            if p == period:
                break

        new = Quantum(convert_timezone(local_dt, self.tz, 'UTC'), self.tz)

        if period == 'week':
            if local_dt.isoweekday() < first_day_of_week:
                new = new.subtract(days = 7 - first_day_of_week + local_dt.isoweekday())
            if local_dt.isoweekday() > first_day_of_week:
                new = new.subtract(days = local_dt.isoweekday() - first_day_of_week)

        return new

    def strftime(self, format):
        local_dt = self.as_local(include_tzinfo=True)
        result   = local_dt.strftime(format)

        suffix_placeholder = '{TH}'
        if result.find(suffix_placeholder) != -1:
            day = local_dt.day

            if 4 <= day <= 20 or 24 <= day <= 30:
                suffix = 'th'
            else:
                suffix = ['st', 'nd', 'rd'][day % 10 - 1]

            result = result.replace(suffix_placeholder, suffix)

        return result

    def format_short(self):
        return self.as_local().strftime("%-e %b %Y %H:%M")

    def format_date(self):
        return self.as_local().strftime("%-e %b %Y")

class QuantumDate(object):
    date = None
    """
    Python date object representing the date of this object (Note that this
    doesn't represent any "real" point in time until you use the .at() method
    to convert it to a Quantum object in a particular timezone)
    """

    def __init__(self, date):
        if isinstance(date, datetime.datetime):
            raise ValueError("First argument to QuantumDate can not be a datetime")
        if not isinstance(date, datetime.date):
            raise ValueError("First argument to QuantumDate must be a date")
        self.date = date

    @property
    def day(self):
        return self.date.day

    @property
    def month(self):
        return self.date.month

    @property
    def year(self):
        return self.date.year

    def weekday(self):
        return self.date.weekday()

    def __hash__(self):
        return self.date.__hash__()

    def _check_comparison_type(self, other):
        if not isinstance(other, QuantumDate):
            raise TypeError("Expected a QuantumDate object for comparison")

    def __lt__(self, other):
        self._check_comparison_type(other)
        return self.date < other.date

    def __le__(self, other):
        self._check_comparison_type(other)
        return self.date <= other.date

    def __eq__(self, other):
        if other is None:
            return False
        self._check_comparison_type(other)
        return self.date == other.date

    def __ne__(self, other):
        if other is None:
            return True
        self._check_comparison_type(other)
        return self.date != other.date

    def __gt__(self, other):
        self._check_comparison_type(other)
        return self.date > other.date

    def __ge__(self, other):
        self._check_comparison_type(other)
        return self.date >= other.date

    def __repr__(self):
        return "<%s(%s)>" % (self.__class__.__name__, self.date)

    def __str__(self):
        return str(self.date)

    def at(self, timezone):
        """Returns a Quantum object representing this date in the supplied timezone"""
        dt = datetime.datetime.combine(self.date, datetime.time())
        return Quantum(convert_timezone(dt, timezone, 'UTC'), timezone)

    def add(self, years=0, months=0, days=0):
        rd = dateutil.relativedelta.relativedelta(years=years, months=months, days=days)
        return QuantumDate(self.date + rd)

    def subtract(self, years=0, months=0, days=0):
        rd = dateutil.relativedelta.relativedelta(years=years, months=months, days=days)
        return QuantumDate(self.date - rd)

    def add_working_days(self, days, holidays):
        """
        Adds a given number of working days. Holidays is supplied as an iterator and will discount those
        days also from the working day list.

        The holidays iterator MUST cover the full span of the calculation. If the calculation runs out of
        holidays it will assume the holiday data-set is incomplete and raise an exception

        >>> holidays = [QuantumDate(datetime.date(2014, 2, 1)), QuantumDate(datetime.date(2014, 2, 11)), QuantumDate(datetime.date(2014, 2, 12)), QuantumDate(datetime.date(2014, 3, 13))]

        Test 1 working day, which should be tomorrow from the 3rd of Feb 2014 (a Monday)

        >>> QuantumDate(datetime.date(2014, 2, 3)).add_working_days(1, holidays)
        <QuantumDate(2014-02-04)>

        Test 4 working days, which should give us Friday 7th

        >>> QuantumDate(datetime.date(2014, 2, 3)).add_working_days(4, holidays)
        <QuantumDate(2014-02-07)>

        Test 5 working days, which should give us Monday 10th

        >>> QuantumDate(datetime.date(2014, 2, 3)).add_working_days(5, holidays)
        <QuantumDate(2014-02-10)>

        Test 6 working days, which will have to jump over holidays on the 11th and 12th to give us the 13th

        >>> QuantumDate(datetime.date(2014, 2, 3)).add_working_days(6, holidays)
        <QuantumDate(2014-02-13)>

        :param days: Number of days to offset
        :type days: int
        :param holidays: An iterator of QuantumDate's that are to be treated as holidays
        :type holidays: iterator
        :return: End date
        :rtype: quantum
        """

        # TODO: Question: is it a working day the day it is received? what if it's received after 5PM?

        # First we iterate between holidays, so we go from today until the first holiday, then to the next,
        # each day we check the conditions and exit if we meet them.
        # We do it this way so we don't have to guess how many holidays to retrieve from the iterator.
        count = 0
        current = self
        for next_holiday in holidays:
            while current < next_holiday:
                if not current.weekday() in [5, 6]:
                    # Not a holiday, not a weekend, so it counts!
                    count += 1
                    if count > days:
                        return current
                current = current.add(0, 0, 1)

            # Skip the holiday if it's today
            if current == next_holiday:
                current = current.add(0, 0, 1)

        # If we reach this point it means we ran out of holidays but still have days to count. This is an error condition
        raise InsufficientHolidaysException("Attempted to calculate working days but ran out of holidays. Update your holiday data-set")

    def start_of(self, period, first_day_of_week=1):
        valid_periods = ['week', 'month', 'year']
        if period not in valid_periods:
            raise ValueError("Invalid period for QuantumDate.start_of: %s" % period)

        date = self.date
        for p in valid_periods:
            if p == 'month':
                date = date.replace(day=1)
            if p == 'year':
                date = date.replace(month=1)
            if p == period:
                break

        new = QuantumDate(date)

        if period == 'week':
            if date.isoweekday() < first_day_of_week:
                new = new.subtract(days = 7 - first_day_of_week + date.isoweekday())
            if date.isoweekday() > first_day_of_week:
                new = new.subtract(days = date.isoweekday() - first_day_of_week)

        return new

    def strftime(self, format):
        result   = self.date.strftime(format)

        suffix_placeholder = '{TH}'
        if result.find(suffix_placeholder) != -1:
            day = self.date.day

            if 4 <= day <= 20 or 24 <= day <= 30:
                suffix = 'th'
            else:
                suffix = ['st', 'nd', 'rd'][day % 10 - 1]

            result = result.replace(suffix_placeholder, suffix)

        return result

    def format_short(self):
        return self.date.strftime("%-e %b %Y")

class QuantumDelta(object):
    rd = None
    """relativedelta object representing the delta"""

    def __init__(self, rd):
        if not isinstance(rd, dateutil.relativedelta.relativedelta):
            raise ValueError("First argument to QuantumDelta must be a relativedelta")
        self.rd = rd

    def __neg__(self):
        return self.__class__(-self.rd)

    def __repr__(self):
        return "<%s(%s)>" % (self.__class__.__name__, self.rd)

    def format_summary(self, depth=1):
        rd = self.rd
        if rd.year or rd.month or rd.day or rd.hour or rd.minute or rd.second or rd.microsecond:
            raise ValueError("Can't format a QuantumDelta with absolute components")

        found_depth = 0
        found = []
        for attr in ['years', 'months', 'days', 'hours', 'minutes', 'seconds']:
            value = getattr(rd, attr)
            display_attr = attr
            if abs(value) == 1:
                display_attr = display_attr[:-1]
            if value or found_depth:
                found.append("%d %s" % (value, display_attr))
                found_depth += 1
            if found_depth >= depth:
                break

        if len(found) == 0:
            return ""

        return " ".join(found)
