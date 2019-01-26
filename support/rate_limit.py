# coding: utf-8



from app import app
from decorator import decorator
from flask import request, abort
from . import quantum, wtf, notify
from .model import RateLimitBuffer
import logging
log = logging.getLogger(__name__)


def rate_limit(bucket):

    def _rate_limit(f, *args, **kwargs):
        allowed_failures = app.settings.getint('ratelimit_%s' % bucket, 'allowed_failures')
        window_size      = app.settings.getint('ratelimit_%s' % bucket, 'window_size')
        remote_ip        = request.remote_ip

        # Did we hit the rate limit? If so, bail
        window_begin = quantum.now('UTC').subtract(seconds=window_size)
        if RateLimitBuffer.objects(bucket=bucket, ip=remote_ip, created__gte=window_begin).count() >= allowed_failures:
            add_to_buffer(bucket)
            notify_limit_exceeded(bucket)
            return abort(429)

        # Run the request
        try:
            response = f(*args, **kwargs)
        except:
            add_to_buffer(bucket)
            raise

        # Figure out whether the request failed
        status_code = None
        form_failed = False

        if type(response) == tuple:
            status_code = response[1]
        elif type(response) == dict:
            # If it's a dictionary, it's likely to be a response designed to be render_html()'d. We look for a form
            # in the response and use it to figure out what happened.
            for k, v in list(response.items()):
                if isinstance(v, wtf.Form):
                    if v.is_submitted() and v.errors:
                        form_failed = True
                        break
        else:
            # Duck typing guess.
            status_code = response.status_code

        # If the response was bad, add an entry to the buffer
        if form_failed or status_code and status_code >= 400:
            add_to_buffer(bucket)

        return response

        # TODO in cron, delete entries older than window_size * 2 from the bucket collection (?)
    return decorator(_rate_limit)

def add_to_buffer(bucket):
    """Adds an entry to the given rate limit bucket."""
    ip = request.remote_ip
    log.debug("Adding entry to the buffer (%s, %s)" % (bucket, ip))
    RateLimitBuffer(
        bucket = bucket,
        ip     = ip,
    ).save()

def notify_limit_exceeded(bucket):
    """Triggers a notification about a rate limit being exceeded.

    Notifications are debounced so we are not flooded with them."""
    ip = request.remote_ip
    previous_notify = RateLimitBuffer.objects(bucket=bucket, ip=ip, notified=True, created__gt=quantum.now('UTC').subtract(minutes=1))

    if not previous_notify:
        rlbuffer = RateLimitBuffer.objects(bucket=bucket, ip=ip).order_by('-created').first()
        if rlbuffer:
            rlbuffer.notified = True
            rlbuffer.save()

        message = 'IP %s has tripped the rate limit for the %s bucket in the last minute' % (ip, bucket)
        notify.info('rate_limit', message)
        log.warn(message)
