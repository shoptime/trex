import random

default_token_chars = "abcdefhijklmnopqrstuvwxyzABCDEFHIJKLMNOPQRSTUVWXYZ0123456789_-"
human_token_chars = "bcdfghjkmnpqrtwxyzBCDFGHKMNPQRTWXYZ2346789"

def create_token(length=32, chars=default_token_chars):
    """Create a random token"""
    token = ''

    for i in xrange(0, length):
        token += chars[random.randint(0, len(chars)-1)]

    return token

def create_token_factory(**factory_args):
    """Create a random token factory"""
    def _create_token(**call_args):
        kwargs = dict()
        kwargs.update(factory_args)
        kwargs.update(call_args)
        return create_token(**kwargs)

    return _create_token

create_human_token = create_token_factory(chars=human_token_chars)
