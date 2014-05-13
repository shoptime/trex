from __future__ import absolute_import
import httpagentparser
from flask import request, g

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
