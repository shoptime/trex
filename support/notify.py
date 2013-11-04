from trex.flask import app
import requests
import logging
log = logging.getLogger(__name__)

def error(site, tag, message):
    if app.settings.getboolean('notify', 'enabled'):
        try:
            requests.post(
                app.settings.get('notify', 'url'),
                data = {
                    'channel': app.settings.get('notify', 'channel'),
                    'message': '[[colour=light_blue]%s[colour=reset]] [colour=light_red]%s[colour=reset]: %s' % (site, tag, message),
                    'method': 'msg',
                },
            )
            raise Exception("break")
        except Exception as e:
            log.error("NOTIFY [%s]: %s" % (tag, message))
            log.error("Last notify was logged because request to the notify bot failed: %s" % e)
    else:
        log.error("NOTIFY [%s]: %s" % (tag, message))

def info(site, tag, message):
    if app.settings.getboolean('notify', 'enabled'):
        try:
            requests.post(
                app.settings.get('notify', 'url'),
                data = {
                    'channel': app.settings.get('notify', 'channel'),
                    'message': '[[colour=light_blue]%s[colour=reset]] %s: %s' % (site, tag, message),
                    'method': 'msg',
                },
            )
        except Exception as e:
            log.info("NOTIFY [%s]: %s" % (tag, message))
            log.error("Last notify was logged because request to the notify bot failed: %s" % e)
    else:
        log.info("NOTIFY [%s]: %s" % (tag, message))
