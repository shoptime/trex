# coding: utf-8

# The idea of this as that it's a lot like ejson, but bi-directional

from __future__ import absolute_import
from . import quantum
import json

def dumps(obj, timezone=None, **kwargs):
    if timezone:
        # Make sure we have an object
        timezone = quantum.get_timezone(timezone)

    def default(o):
        if isinstance(o, quantum.Quantum):
            if not timezone:
                raise quantum.QuantumException("Can't JSON serialize quantums without a timezone specified")
            if o.tz and o.tz != timezone:
                raise ValueError("Trying to JSON serialize a quantum that already has a different timezone: %s" % o)
            return { '$ltime': o.at(timezone).as_local().strftime('%Y-%m-%dT%H:%M:%S.%f') }

        raise TypeError(repr(o) + " is not JSON serializable")

    return json.dumps(obj, default=default, **kwargs)

def loads(s, timezone=None, **kwargs):
    if timezone:
        # Make sure we have an object
        timezone = quantum.get_timezone(timezone)

    def object_hook(o):
        if '$ltime' in o:
            if not timezone:
                raise quantum.QuantumException("Can't JSON parse local time without a timezone specified")
            return quantum.parse(o['$ltime'], timezone=timezone, format='%Y-%m-%dT%H:%M:%S.%f')
        return o

    return json.loads(s, object_hook=object_hook, **kwargs)
