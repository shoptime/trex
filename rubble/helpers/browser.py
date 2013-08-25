# coding: utf8

from __future__ import absolute_import
from flask import url_for
from trex.rubble import global_harness as harness
from .assertions import is_equal, is_like

def browser_for(browser):
    if isinstance(browser, basestring):
        return harness().browser_for_key(browser)
    return harness().current_browser()

def get(path, browser=None):
    browser = browser_for(browser)
    uri = harness().base_uri.copy().set(path=path)
    browser.get(str(uri))

def get_for(endpoint, browser=None, **kwargs):
    get(url_for(endpoint, **kwargs))

def add_cookie(name, value, browser=None):
    browser_for(browser).add_cookie(dict(name=name, value=value))

def get_cookie(name, browser=None):
    return browser_for(browser).get_cookie(name)

def find(selector, browser=None):
    return browser_for(browser).find(selector)

def endpoint(browser=None):
    return browser_for(browser).endpoint()

def endpoint_is(endpoint, browser=None):
    return browser_for(browser).endpoint_is(endpoint)

def wait_for_bootstrap_modal(browser=None):
    return browser_for(browser).wait_for_bootstrap_modal()

def current_url(browser=None):
    return browser_for(browser).url()

def url_is(expected, browser=None):
    is_equal(current_url(browser), expected, message="Browser URL is_equal")

def url_like(expected, browser=None):
    is_like(current_url(browser), expected, message="Browser URL is_like")


def execute_script(script, browser=None):
    return browser_for(browser).execute_script(script)

def wait_for_ajax(browser=None):
    browser_for(browser).wait_for_ajax()

# TODO - screenshot
