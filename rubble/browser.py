# coding: utf8

from __future__ import absolute_import

from selenium.webdriver.remote.webdriver import WebDriver, WebElement
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver import Remote
from selenium.webdriver.support.select import Select
import copy
from furl import furl
from app import app
from .helpers.assertions import *
import boto.s3.connection
from ..support import token

class Browser(object):
    def __init__(self, harness, selenium_server_url, selenium_browser, width=1024, height=600):
        self.harness = harness
        self.selenium_server_url = selenium_server_url
        self.selenium_browser = selenium_browser
        self.width = 1024
        self.height = 600

        self.selenium = Remote(
            self.selenium_server_url.encode('ascii'),
            desired_capabilities = {
                'browserName': self.selenium_browser,
            },
        )
        self.selenium.set_window_size(width, height)

    def __enter__(self):
        self.harness.browser_stack.append(self)
        return self

    def __exit__(self, type, value, traceback):
        if self.harness.browser_stack[-1] != self:
            raise Exception("Unexpected browser on the top of the stack")
        self.harness.browser_stack.pop()
        return

    def shutdown(self):
        self.selenium.quit()

    def back(self):
        self.selenium.back()

    def refresh(self):
        self.selenium.refresh()

    def source(self):
        return self.selenium.page_source

    def get(self, uri):
        self.selenium.get(uri)

    def find(self, selector):
        return WebElementSet(self, elements=self.selenium).find(selector)

    def add_cookie(self, cookie_dict):
        self.selenium.add_cookie(cookie_dict)

    def get_cookie(self, name):
        return self.selenium.get_cookie(name)

    def endpoint(self):
        return self.find('html').attr('id').replace('endpoint-', '').replace('-', '.')

    def endpoint_is(self, endpoint):
        is_equal(self.endpoint(), endpoint, "Endpoint is correct")

    def wait_for_bootstrap_modal(self):
        last = [None]

        def inner_wait(driver):
            value = self.find('.modal')[-1].css('top')
            if last[0] and last[0] == value:
                return True
            last[0] = value
            return False
        WebDriverWait(self.selenium, 2).until(inner_wait)
        return self

    def url(self):
        return furl(self.selenium.current_url)

    def execute_script(self, script):
        return self.selenium.execute_script(script)

    def wait_for_ajax(self):
        WebDriverWait(self.selenium, 10).until_not(lambda x: x.execute_script('return jQuery.active'))
        return self

    def screenshot(self, message="Screenshot: "):
        if 's3_access_key' not in app.settings.options('test'):
            print "No screenshot S3 instance configured - skipping screenshot"
            return

        if not hasattr(self, 's3_connection'):
            if 's3_host' in app.settings.options('test'):
                self.s3_connection = boto.s3.connection.S3Connection(
                    app.settings.get('test', 's3_access_key'),
                    app.settings.get('test', 's3_secret_key'),
                    host = app.settings.get('test', 's3_host'),
                )
            else:
                self.s3_connection = boto.s3.connection.S3Connection(
                    app.settings.get('test', 's3_access_key'),
                    app.settings.get('test', 's3_secret_key'),
                )

        bucket = self.s3_connection.get_bucket(app.settings.get('test', 's3_bucket'))
        filename = "%s-%s.png" % (token.create_url_token(), self.harness.current_test_object.__class__.__name__)

        key = bucket.new_key(filename)
        key.metadata['Content-Type'] = 'image/png'
        key.metadata['Cache-Control'] = 'public, max-age=86400'
        key.set_contents_from_string(self.selenium.get_screenshot_as_png())
        key.make_public()
        print "%s%s" % (message, key.generate_url(expires_in=0, query_auth=False))

class WebElementSet(object):
# TODO - implement these methods?
#element
#    wait_for_hidden
    def __init__(self, browser, elements=None, selector=None):
        self.browser  = browser
        if isinstance(selector, list):
            self.selector = selector
        elif selector:
            self.selector = [selector]
        else:
            self.selector = []
        if elements:
            self.elements = self._verify_elements(elements)
        else:
            self.elements = []

    def __repr__(self):
        return '<%s %s (%d element%s)>' % (
            self.__class__.__name__,
            " => ".join(self.selector),
            len(self.elements),
            len(self.elements) != 1 and 's' or '',
        )

    def require_one_element(f):
        def decorator(self, *args, **kwargs):
            is_equal(len(self), 1, "Expected exactly 1 element, got %d" % len(self))
            return f(self, *args, **kwargs)

        return decorator

    def _verify_elements(self, elements):
        if not isinstance(elements, list):
            elements = [elements]

        seen = {}
        validated = []
        for el in elements:
            assert isinstance(el, WebDriver) or isinstance(el, WebElement)
            if isinstance(el, WebDriver):
                if '__webdriver__' not in seen:
                    seen['__webdriver__'] = True
                    validated.append(el)
            else:
                if el.id not in seen:
                    seen[el.id] = True
                    validated.append(el)

        return validated

    def new(self, elements, selector=None):
        new_selector = copy.copy(self.selector)
        if selector:
            new_selector.append(selector)
        return self.__class__(self.browser, elements=self._verify_elements(elements), selector=new_selector)

    @require_one_element
    def tag_name(self):
        return self.elements[0].tag_name

    def find(self, selector, selector_desc=None):
        if not selector_desc:
            selector_desc = selector
        found = []
        for el in self.elements:
            if selector.startswith("xpath:"):
                [ found.append(x) for x in el.find_elements_by_xpath(selector[6:]) ]
            else:
                [ found.append(x) for x in el.find_elements_by_css_selector(selector) ]
        return self.new(found, selector=selector_desc)

    def filter_by_text(self, text, selector_desc=None):
        if not selector_desc:
            selector_desc = ":text(%s)" % text
        found = []
        for el in self.elements:
            if el.text == text:
                found.append(el)
        return self.new(found, selector=selector_desc)

    def filter_by_selected(self, selector_desc=None):
        if not selector_desc:
            selector_desc = ":selected()"
        found = []
        for el in self.elements:
            if el.is_selected():
                found.append(el)
        return self.new(found, selector=selector_desc)

    def filter_by_lambda(self, test, selector_desc=None):
        if not selector_desc:
            selector_desc = ":lambda(%s)" % test
        found = []
        for el in self.elements:
            if test(el):
                found.append(el)
        return self.new(found, selector=selector_desc)

    def parent(self):
        return self.find('xpath:..', selector_desc='parent')

    def next(self):
        return self.find('xpath:following-sibling::*[1]', selector_desc='next')

    def __iter__(self):
        # Because __getitem__ doesn't raise IndexError any more, we have to
        # define our own "iterator"
        return iter([self[x] for x in range(len(self))])

    def __getitem__(self, index):
        try:
            return self.new(self.elements[index], selector="[%d]" % index)
        except IndexError:
            self.browser.harness.handle_error(TestFailureException("Tried to access %s => [%d] but it doesn't exist" % (" => ".join(self.selector), index)))
            return self.new([], selector="[%d]" % index)

    def __len__(self):
        return len(self.elements)

    def length(self):
        return len(self)

    def length_is(self, length, message=None):
        if message is None:
            message = "Length: %s '%d'" % (self, length)

        is_equal(len(self), length, message=message)
        return self

    def text(self):
        return "".join([el.text for el in self.elements])

    def text_is(self, expected, message=None):
        if message is None:
            message = "%s text is: %s" % (self, expected)
        is_equal(self.text(), expected, message=message)
        return self

    def text_like(self, regexp, message=None):
        if message is None:
            message = "%s text like: %s" % (self, regexp)
        is_like(self.text(), regexp, message=message)
        return self

    def text_unlike(self, regexp, message=None):
        if message is None:
            message = "%s text like: %s" % (self, regexp)
        isnt_like(self.text(), regexp, message=message)
        return self

    @require_one_element
    def clear(self):
        self.elements[0].clear()
        return self

    @require_one_element
    def click(self):
        self.elements[0].click()
        return self

    @require_one_element
    def select_by_value(self, value):
        select = Select(self.elements[0])
        select.select_by_value(value)
        return self

    def select_by_label(self, label, message=None):
        if message is None:
            message = "Select: %s label=%s" % (self, label)

        options = self.find('option').filter_by_text(label)
        is_equal(len(options), 1, message)
        self.select_by_value(options[0].attr('value'))

        return self

    @require_one_element
    def hover(self):
        ActionChains(self.context.browser).move_to_element(self.elements[0]).perform()
        return self

    @require_one_element
    def attr(self, name):
        return self.elements[0].get_attribute(name)

    def attr_is(self, name, expected, message=None):
        if message is None:
            message = "%s attr(%s) is: %s" % (self, name, expected)

        is_equal(self.attr(name), expected, message=message)
        return self

    def attr_like(self, name, regexp, message=None):
        if message is None:
            message = "%s attr(%s) like: %s" % (self, name, regexp)

        is_like(self.attr(name), regexp, message=message)
        return self

    @require_one_element
    def visible(self):
        return self.elements[0].is_displayed()

    def is_visible(self, message=None):
        if message is None:
            message = "Is visible: %s" % self
        is_equal(self.visible(), True, message)
        return self

    def is_hidden(self, message=None):
        if message is None:
            message = "Is hidden: %s" % self
        is_equal(self.visible(), False, message)
        return self

    def wait_for_visible(self):
        def inner_wait(driver):
            return self.visible()
        WebDriverWait(self.browser.selenium, 30).until(inner_wait)
        return self

    @require_one_element
    def enabled(self):
        return self.elements[0].is_enabled()

    def is_enabled(self, message=None):
        if message is None:
            message = "Is enabled: %s" % self
        is_equal(self.enabled(), True, message)
        return self

    def is_disabled(self, message=None):
        if message is None:
            message = "Is disabled: %s" % self
        is_equal(self.enabled(), False, message)
        return self

    def selected(self):
        return self.elements[0].is_selected()

    def is_selected(self, message=None):
        if message is None:
            message = "Is selected: %s" % self
        is_equal(self.selected(), True, message)
        return self

    def isnt_selected(self, message=None):
        if message is None:
            message = "Isn't selected: %s" % self
        is_equal(self.selected(), False, message)
        return self

    @require_one_element
    def css(self, property_name):
        return self.elements[0].value_of_css_property(property_name)

    @require_one_element
    def type(self, keys, clear_first=True):
        if clear_first:
            self.clear()
        self.elements[0].send_keys(keys)
        return self

    @require_one_element
    def set_file_to_upload(self, filename):
        """
        On a file element, sets its path so that a file upload can occur.

        Use of this method probably immediately disqualifies your test suite
        from running in htmlunit, but it'll run in chrome (and probably other
        browsers) fine.

        @param filename: The file to upload, path is relative from the test dir of your app
        @type filename: str
        """

        self.type(self.browser.harness.upload_filename(filename), clear_first=False)
        return self

