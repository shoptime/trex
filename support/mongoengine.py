from __future__ import absolute_import
import mongoengine
from flask import request, abort
from . import quantum
from datetime import datetime

class LowerCaseEmailField(mongoengine.EmailField):
    def to_mongo(self, *args, **kwargs):
        return super(self.__class__, self).to_mongo(*args, **kwargs).lower()

    def prepare_query_value(self, *args, **kwargs):
        return super(self.__class__, self).prepare_query_value(*args, **kwargs).lower()

class QuantumField(mongoengine.fields.BaseField):
    """A Quantum field.

    Uses the trex.support.quantum library. Stores raw datetimes in mongo
    (always as UTC)
    """

    def validate(self, value):
        new_value = self.to_mongo(value)
        if not isinstance(new_value, datetime):
            self.error(u'cannot parse quantum "%s"' % value)

    def to_mongo(self, value):
        if value is None:
            return value
        if isinstance(value, quantum.Quantum):
            return value.as_utc()

        if not isinstance(value, basestring):
            return None

    def to_python(self, value):
        return quantum.Quantum(value, 'UTC')

    def prepare_query_value(self, op, value):
        return self.to_mongo(value)

def serve_file(document, field, index=None, set_filename=True):
    from app import app
    try:
        file = getattr(document, field)
        if index is not None:
            file = file[int(index)]
    except IndexError:
        abort(404)

    if 'If-None-Match' in request.headers and request.headers['If-None-Match'] == str(file._id):
        return app.response_class('', 304)

    response = app.response_class(file.get(), 200)
    response.headers['Content-Type'] = file.content_type
    response.headers['ETag'] = str(file._id)
    response.headers['Cache-Control'] = 'private, max-age=31622400'

    if set_filename:
        response.headers['Content-Disposition'] = 'filename=%s' % file.filename

    return response
