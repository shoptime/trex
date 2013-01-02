from __future__ import absolute_import
import httpagentparser
from flask import request, g
from trex.flask import app

def detect():
    """Returns whatever httpagentparser detects as the client based on request UA"""
    if not hasattr(g, '__browser_detect'):
        b = httpagentparser.detect(request.user_agent.string)

        if not 'dist' in b:
            b['dist'] = {}

        g.__browser_detect = b

    return g.__browser_detect

def simple_detect():
    """Returns whatever httpagentparser detects as the client based on request UA, using simpledetect"""
    if not hasattr(g, '__browser_simple_detect'):
        g.__browser_simple_detect = httpagentparser.simple_detect(request.user_agent.string)

    return g.__browser_simple_detect

def is_mobile():
    """Returns whether the UA is a mobile device (NOT tablet)"""

    if is_iphone():
        return True

    # TODO more checks here

    return False

def is_tablet():
    """Returns whether the UA is a tablet device"""

    if is_ipad():
        return True

    # TODO more checks here

    return False

def is_desktop():
    """Returns whether the UA is a desktop device"""
    # This is the default if we can't establish that the device is
    # mobile/tablet
    return not is_tablet() and not is_mobile()

def is_iphone():
    """Returns whether the UA looks like an iPhone"""
    b = detect()
    return b['dist'].get('name') == 'IPhone'

def is_ipad():
    """Returns whether the UA looks like an iPad"""
    b = detect()
    return b['dist'].get('name') == 'IPad'

def is_ios():
    """Returns whether the UA looks like it runs iOS"""
    return is_iphone() or is_ipad()

def supports_buzzumi():
    """Returns whether we think this browser supports buzzumi (the marlin2 implementation)"""
    b = detect()['browser']

    # httpagentparser has a weird return for browsers it doesn't know
    if type(b) == str:
        return True

    # if we have no configuration about supported browsers, we're done
    if not app.settings.has_section('browser_minversions'):
        print "WARNING: You're calling supports_buzzumi() when no browser_minversions section is present in your config"
        return True

    minversions = {}
    for i in app.settings.items('browser_minversions'):
        minversions[i[0]] = i[1]
    print minversions

    if not b['name'].lower() in minversions.keys():
        # No idea what this browser is, let them in
        return True
    elif _browser_min(minversions[b['name'].lower()], b['version']):
        # Browser is newer than min version
        return True

    return False

def _browser_min(v1, v2):
    """
    >>> browser_min("10","10.9.2.1")
    True

    >>> browser_min("10.4.2","10.4.1.1")
    False

    >>> browser_min("3.0.4", "3.6")
    True

    >>> browser_min("9.1.2", "9.1.2.2")
    True

    >>> browser_min("9.1", "9.10.0")
    True

    >>> browser_min("9.1", "8.1A.3")
    False

    >>> browser_min("9.1", "9.1A.3")
    True

    >>> browser_min("3.6", "10.0")
    True

    """
    set1 = str(v1).split('.')
    set2 = str(v2).split('.')
    try:
        for i in range(0, min(len(set1), len(set2))):
            if int(set1[i]) > int(set2[i]):
                return False
            if int(set1[i]) < int(set2[i]):
                return True
    except ValueError:
        # In the event of a bad version number, we safe to True
        return True

    return True
