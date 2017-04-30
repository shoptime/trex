# coding: utf-8

from __future__ import absolute_import

from attest import Tests, Assert
from trex.support import quantum
import pytz
from datetime import datetime
tests = Tests()

# TODO - tests around the "magic" hour when DST changes and adding/removing
# time that lands/leaves that spot

@tests.test
def basic_creation():
    q = quantum.now()

    Assert(q.tz) == None
    Assert.isinstance(q.as_utc(), datetime)
    with Assert.raises(quantum.QuantumException):
        Assert.isinstance(q.as_local(), datetime)

    q = quantum.parse('2013-06-27T12:27:54', timezone='UTC')

    Assert(q.tz) == pytz.utc
    Assert.isinstance(q.as_utc(), datetime)
    Assert(q.as_utc()) == datetime(2013, 6, 27, 12, 27, 54)
    Assert(q.as_local()) == datetime(2013, 6, 27, 12, 27, 54)

    q = quantum.parse('2013-06-27T12:27:54', timezone='Pacific/Auckland')

    Assert(q.tz) == pytz.timezone('Pacific/Auckland')
    Assert.isinstance(q.dt, datetime)
    Assert(q.as_utc()) == datetime(2013, 6, 27, 0, 27, 54)
    Assert(q.as_local()) == datetime(2013, 6, 27, 12, 27, 54)

    q = quantum.parse('2013-06-26 3:27pm', timezone='UTC', relaxed=True)

    Assert(q.tz) == pytz.utc
    Assert.isinstance(q.dt, datetime)
    Assert(q.as_utc()) == datetime(2013, 6, 26, 15, 27, 0)
    Assert(q.as_local()) == datetime(2013, 6, 26, 15, 27, 0)

    q = quantum.parse('2013-06-26 3:27pm', relaxed=True, timezone='Pacific/Auckland')

    Assert(q.tz) == pytz.timezone('Pacific/Auckland')
    Assert.isinstance(q.dt, datetime)
    Assert(q.as_utc()) == datetime(2013, 6, 26, 3, 27, 0)
    Assert(q.as_local()) == datetime(2013, 6, 26, 15, 27, 0)

@tests.test
def applying_deltas():
    start = quantum.parse('2013-06-27T12:27:54', timezone='UTC')
    end   = start.add(months=6)

    assert end.as_local() == datetime(2013,12,27,12,27,54)

    start = quantum.parse('2013-06-27T12:27:54', timezone='Pacific/Auckland')
    end   = start.add(months=6)

    assert end.as_utc() == datetime(2013,12,26,23,27,54)
    assert end.as_local() == datetime(2013,12,27,12,27,54)

@tests.test
def leap_years():
    q = quantum.parse('01-03-2013', relaxed=True, timezone='UTC')
    assert q.subtract(days=1).as_utc() == datetime(2013,2,28)

    q = quantum.parse('01-02-2013', relaxed=True, timezone='UTC')
    assert q.add(months=1).as_utc() == datetime(2013,3,1)

    q = quantum.parse('01-03-2016', relaxed=True, timezone='UTC')
    assert q.subtract(days=1).as_utc() == datetime(2016,2,29)

    q = quantum.parse('01-02-2016', relaxed=True, timezone='UTC')
    assert q.add(months=1).as_utc() == datetime(2016,3,1)

@tests.test
def formatting():
    with Assert.raises(quantum.QuantumException):
        quantum.now().format_date() == '1 Feb 2013'

    q = quantum.parse('01-02-2013', relaxed=True, timezone='UTC')
    assert q.format_date() == '1 Feb 2013'

if __name__ == '__main__':
    tests.run()
