import time
from functools import partial

def timelog(message, start_time, tag):
    print "%s%.3f %s" % (tag and '%s: ' % tag or '', time.time() - start_time, message)

def new(tag=None):
    return partial(timelog, start_time=time.time(), tag=tag)
