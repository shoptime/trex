from trex.flask import app
import requests

def error(site, tag, message):
    if app.settings.getboolean('notify', 'enabled'):
        requests.post(
            app.settings.get('notify', 'url'),
            data = {
                'channel': app.settings.get('notify', 'channel'),
                'message': '[[colour=light_blue]%s[colour=reset]] [colour=light_red]%s[colour=reset]: %s' % (site, tag, message),
                'method': 'msg',
            },
        )
    else:
        app.logger.error("NOTIFY [%s]: %s" % (tag, message))

def info(site, tag, message):
    if app.settings.getboolean('notify', 'enabled'):
        requests.post(
            app.settings.get('notify', 'url'),
            data = {
                'channel': app.settings.get('notify', 'channel'),
                'message': '[[colour=light_blue]%s[colour=reset]] %s: %s' % (site, tag, message),
                'method': 'msg',
            },
        )
    else:
        app.logger.info("NOTIFY [%s]: %s" % (tag, message))
