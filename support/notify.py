from trex.flask import app
import requests
import socket
fqdn = socket.getfqdn()
import logging
log = logging.getLogger(__name__)

def raw(message, channel=None):
    if channel is None:
        channel = app.settings.get('notify', 'channel')

    if app.settings.getboolean('notify', 'enabled'):
        try:
            requests.post(
                app.settings.get('notify', 'url'),
                data = dict(
                    channel = channel,
                    message = message,
                    method = 'msg',
                ),
                timeout = 2,
            )
        except Exception as e:
            log.info('Notify: %s' % message)
            log.error("Last notify was logged because request to the notify bot failed: %s" % e)
    else:
        import termcolor
        import re

        def replacer(matches):
            if matches.group(2) == 'reset':
                return '\033[0m'

            out = ''
            if matches.group(1):
                out += '\033[1m'

            out += '\033[%dm' % termcolor.COLORS[matches.group(2)]

            return out

        log.debug("notify: %s" % re.sub(r'\[colour=(?:(light)_)?(\w+)\]', replacer, message))

def error(tag, message):
    raw('[[colour=light_blue]%s@%s[colour=reset]] [colour=light_red]%s[colour=reset]: %s' % (app.settings.get('app', 'slug'), fqdn, tag, message))

def info(tag, message):
    raw('[[colour=light_blue]%s@%s[colour=reset]] %s: %s' % (app.settings.get('app', 'slug'), fqdn, tag, message))
