import random
from unidecode import unidecode
import re

default_token_chars = "abcdefhijklmnopqrstuvwxyzABCDEFHIJKLMNOPQRSTUVWXYZ0123456789_-"
human_token_chars = "BCDFGHKMNPQRTWXYZ2346789"

def create_token(length=32, chars=default_token_chars):
    """Create a random token"""
    token = ''

    for i in xrange(0, length):
        token += chars[random.randint(0, len(chars)-1)]

    return token

def create_url_token(length=16):
    return create_token(length, "abcdefhijklmnopqrstuvwxyzABCDEFHIJKLMNOPQRSTUVWXYZ0123456789")

def create_token_factory(**factory_args):
    """Create a random token factory"""
    def _create_token(**call_args):
        kwargs = dict()
        kwargs.update(factory_args)
        kwargs.update(call_args)
        return create_token(**kwargs)

    return _create_token

def generate_slug(source):
    slug = unidecode(unicode(source)).lower()
    slug = re.sub(r'\W+', '-', slug)
    return slug

class SlugList(object):
    def __init__(self, name):
        self.name = name
        self.count = 1

    def __iter__(self):
        yield generate_slug(self.name)
        # Potentially we could find some other variations on a name here
        while True:
            yield generate_slug("%s %d" % (self.name, self.count))
            self.count += 1


create_human_token = create_token_factory(chars=human_token_chars)
