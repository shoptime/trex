from __future__ import absolute_import

import bson
import mongoengine
import json
import datetime

def filter_json_encoder(o):
    if isinstance(o, mongoengine.queryset.QuerySet):
        return list(o)

    if isinstance(o, mongoengine.Document):
        if hasattr(o, 'to_json'):
            return o.to_json()
        return o.to_mongo()

    if isinstance(o, mongoengine.EmbeddedDocument):
        if hasattr(o, 'to_json'):
            return o.to_json()
        return o.to_mongo()

    if isinstance(o, bson.ObjectId):
        return str(o)

    if isinstance(o, bson.DBRef):
        return str(o.id)

    if isinstance(o, datetime.datetime):
        return o.isoformat()+'Z'

    if isinstance(o, set):
        return list(o)

    raise TypeError(repr(o) + " is not JSON serializable")

def dumps(*args, **kwargs):
    kwargs['default'] = kwargs.get('default', filter_json_encoder)
    return json.dumps(*args, **kwargs)
