# coding: utf8


from flask import url_for
from trex.rubble import global_harness as harness
from .assertions import is_equal, is_like, message
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains as SeleniumActionChains
from selenium.webdriver.common.keys import Keys
from app import app
from furl import furl
import re

def browser_for(browser):
    if isinstance(browser, str):
        return harness().browser_for_key(browser)
    return harness().current_browser()

def current_url(browser=None):
    return browser_for(browser).url()

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

def get_for(ep, browser=None, _lazy=False, **kwargs):
    if _lazy and endpoint(browser) == ep:
        return
    get(url_for(ep, **kwargs))

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

def wait_for_element_visible(selector, browser=None):
    wait_for_element_exists(selector, browser)

    browser = browser_for(browser)
    def inner_wait(driver):
        return browser.find(selector)[0].visible()
    WebDriverWait(browser.selenium, 10).until(inner_wait)

def wait_for_element_invisible(selector, browser=None):
    wait_for_element_exists(selector, browser)

    browser = browser_for(browser)
    def inner_wait(driver):
        return not browser.find(selector)[0].visible()
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
    if app.settings.get('trex', 'bootstrap_version') == '2':
        expected = "^\xd7\s+%s$" % re.escape(expected)
        browser_for(browser).find('.flash').text_like(expected, message='Flash text matches')
    else:
        browser_for(browser).find('.flash>div').text_is(expected, message="Flash text matches")

def execute_script(script, browser=None):
    return browser_for(browser).execute_script(script)

def wait_for_ajax(browser=None):
    browser_for(browser).wait_for_ajax()

def wait_for_modal_form(browser=None):
    browser_for(browser).wait_for_bootstrap_modal()
    browser_for(browser).wait_for_ajax()

def screenshot(browser=None):
    browser_for(browser).screenshot()

def ActionChains(browser=None):
    return SeleniumActionChains(browser_for(browser).selenium)

def table_like(head, body, table=None):
    message("verifying table contents")
    if not table:
        table = find('.table').length_is(1, message="Get the only table on the page")

    if head is not None:
        head_cells = table.find('thead tr th')
        is_equal(len(head_cells), len(head), "Correct number of header cells")

    body_rows = table.find('tbody tr')

    is_equal(len(body_rows), len(body), "Correct number of body rows")

    retype = type(re.compile('a'))

    for observed_row, expected_row in zip(body_rows, body):
        observed_cells = observed_row.find('td, th')
        is_equal(len(observed_cells), len(expected_row), "Correct number of body cells")
        for observed_cell, expected_cell in zip(observed_cells, expected_row):
            if expected_cell is None:
                # Don't care about content
                continue
            if isinstance(expected_cell, retype):
                observed_cell.text_like(expected_cell)
            else:
                observed_cell.text_is(expected_cell)

def dl_like(contents, dl=None):
    message("verifying dl contents")
    if not dl:
        dl = find('dl').length_is(1, message="Get the only dl on the page")

    dts = dl.find('dt')
    dds = dl.find('dd')

    is_equal(len(dts), len(contents), "Correct number of definitions")
    is_equal(len(dds), len(contents), "Correct number of definitions")

    retype = type(re.compile('a'))

    for observed_dt, observed_dd, expected in zip(dts, dds, contents):
        if expected is None:
            # Don't care about this item
            continue

        expected_dt = expected[0]
        expected_dd = expected[1]

        if expected_dt is not None:
            if isinstance(expected_dt, retype):
                observed_dt.text_like(expected_dt)
            else:
                observed_dt.text_is(expected_dt)

        if expected_dd is not None:
            if isinstance(expected_dd, retype):
                observed_dd.text_like(expected_dd)
            else:
                observed_dd.text_is(expected_dd)
