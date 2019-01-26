# coding: utf-8



from configparser import ConfigParser
from furl import furl

class TrexConfigParser(ConfigParser):
    def getlist(self, *args, **kwargs):
        value = self.get(*args, **kwargs)
        return [x.strip() for x in value.split(',')]

    def geturl(self, *args, **kwargs):
        value = self.get(*args, **kwargs)
        return furl(value)
