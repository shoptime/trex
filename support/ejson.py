from __future__ import absolute_import

import bson
import mongoengine
import json
import datetime
from . import quantum

def filter_json_encoder(o):
    if hasattr(o, 'to_ejson'):
        return o.to_ejson()

    if isinstance(o, mongoengine.queryset.QuerySet):
        return list(o)

    if isinstance(o, mongoengine.Document):
        return o.to_mongo().to_dict()

    if isinstance(o, mongoengine.EmbeddedDocument):
        return o.to_mongo().to_dict()

    if isinstance(o, bson.ObjectId):
        return str(o)

    if isinstance(o, bson.DBRef):
        return str(o.id)

    if isinstance(o, datetime.datetime):
        return o.isoformat() + 'Z'

    if isinstance(o, quantum.Quantum):
        if o.tz:
            return {'$quantum': o.as_unix(), '$timezone': o.tz.zone}
        else:
            return {'$quantum': o.as_unix(), '$timezone': o.tz}

    if isinstance(o, set):
        return list(o)

    raise TypeError(repr(o) + " is not JSON serializable")

def dumps(*args, **kwargs):
    kwargs['default'] = kwargs.get('default', filter_json_encoder)
    return json.dumps(*args, **kwargs)
