# coding: utf8

from __future__ import absolute_import
from flask import url_for
from trex.rubble import global_harness as harness
from .assertions import is_equal, is_like, message
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.keys import Keys
from furl import furl

def browser_for(browser):
    if isinstance(browser, basestring):
        return harness().browser_for_key(browser)
    return harness().current_browser()

def back(browser=None):
    browser_for(browser).back()

def refresh(browser=None):
    browser_for(browser).refresh()

def title(browser=None):
    return browser_for(browser).title()

def title_is(expected, browser=None):
    is_equal(title(browser), expected, message="Title is_equal")

def source(browser=None):
    return browser_for(browser).source()

def get(path, browser=None):
    browser = browser_for(browser)
    uri = harness().base_uri.copy().join(str(path))
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

def wait_for_element_exists(selector, browser=None):
    browser = browser_for(browser)
    def inner_wait(driver):
        return browser.find(selector).length() > 0
    WebDriverWait(browser.selenium, 10).until(inner_wait)

def wait_for_lambda(l, browser=None):
    browser = browser_for(browser)
    WebDriverWait(browser.selenium, 10).until(l)

def current_url(browser=None):
    return browser_for(browser).url()

def url_is(expected, browser=None):
    expected = furl(expected)
    is_equal(current_url(browser), expected, message="Browser URL is_equal")

def url_like(expected, browser=None):
    is_like(str(current_url(browser)), expected, message="Browser URL is_like")

def flash_is(expected, browser=None):
    browser_for(browser).find('.flash>div').text_is(expected, message="Flash text matches")

def execute_script(script, browser=None):
    return browser_for(browser).execute_script(script)

def wait_for_ajax(browser=None):
    browser_for(browser).wait_for_ajax()

def screenshot(browser=None):
    browser_for(browser).screenshot()

def table_like(head, body, table=None):
    message("verifying table contents")
    if not table:
        table = find('.table').length_is(1, message="Get the only table on the page")

    head_cells = table.find('thead tr th')

    is_equal(len(head_cells), len(head), "Correct number of header cells")

    body_rows = table.find('tbody tr')

    is_equal(len(body_rows), len(body), "Correct number of body rows")

    for observed_row, expected_row in zip(body_rows, body):
        observed_cells = observed_row.find('td, th')
        is_equal(len(observed_cells), len(expected_row), "Correct number of body cells")
        for observed_cell, expected_cell in zip(observed_cells, expected_row):
            if expected_cell is None:
                # Don't care about content
                continue
            observed_cell.text_is(expected_cell)

