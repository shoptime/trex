# coding: utf-8

from __future__ import absolute_import

from ConfigParser import ConfigParser
from furl import furl

class TrexConfigParser(ConfigParser):
    def getlist(self, *args, **kwargs):
        value = self.get(*args, **kwargs)
        return [x.strip() for x in value.split(',')]

    def geturl(self, *args, **kwargs):
        value = self.get(*args, **kwargs)
        return furl(value)
