from __future__ import absolute_import
from mongoengine import EmailField

class LowerCaseEmailField(EmailField):
    def to_mongo(self, *args, **kwargs):
        return super(self.__class__, self).to_mongo(*args, **kwargs).lower()

    def prepare_query_value(self, *args, **kwargs):
        return super(self.__class__, self).prepare_query_value(*args, **kwargs).lower()
