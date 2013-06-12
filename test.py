import traceback
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver import Remote
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support.select import Select
from selenium.webdriver.remote.webdriver import WebDriver, WebElement
from multiprocessing import Process
from trex.flask import app
from furl.furl import furl
from time import sleep
import logging
import sys
import re
import imp
import os
import inspect
import copy
import json
from termcolor import colored
import inspect
from collections import defaultdict

class TestRunner:
    """Manages running a test suite.

    The test suite is a series of classes that extend TestBase, in some directory.

    This class knows how to run those tests.

    It may be "automatically" configured with the assumption that this trex
    checkout is part of a flask application, or it may be manually configured
    with the assumption that something else has already set up the webapp to
    test against."""

    configured           = False
    test_dir             = None
    server_url           = None
    selenium_server_url  = None
    selenium_browser     = None
    test_cases           = []
    server_process       = None
    wait_after_exception = None

    def __init__(self, wait_after_exception=False):
        self.wait_after_exception = wait_after_exception

    def configure(self, server_url, selenium_server_url, selenium_browser, test_dir):
        self.server_url          = server_url
        self.selenium_server_url = selenium_server_url
        self.selenium_browser    = selenium_browser
        self.test_dir            = test_dir

        self.test_cases = [ x(server_url, test_dir) for x in self._load_test_cases(test_dir) ]

        if len(self.test_cases) == 0:
            sys.stderr.write("No tests to run\n")

        self.configured = True

    def configure_for_flask(self):
        app.switch_to_test_mode()

        if not re.search(r'test', app.db.name):
            raise Exception("Mongo database '%s' doesn't have 'test' in its name. Refusing to run tests" % app.db.name)

        server_url = furl(app.settings.get('server', 'url'))

        selenium_server_url = 'http://%s:%d/wd/hub' % (app.settings.get('test', 'selenium_server_host'), int(app.settings.get('test', 'selenium_server_port')))
        selenium_browser = app.settings.get('test', 'browser')

        sys.stderr.write("Tests will run against: %s\n" % server_url)
        sys.stderr.write("Tests will use mongodb: %s\n" % app.db.name)

        # This just stops the "accesslog" output from the server
        logging.getLogger('werkzeug').setLevel(logging.ERROR)

        self.configure(
            server_url          = server_url,
            selenium_server_url = selenium_server_url,
            selenium_browser    = selenium_browser,
            test_dir            = os.path.join(app.root_path, 'test'),
        )

        if not self.configured:
            return

        # Empty the test database to get things rolling
        app.db.connection.drop_database(app.db.name)

        # Start the server
        self.server_process = Process(target=self._start_flask_app)
        self.server_process.start()

        # This is a dodgy way of ensuring the server is running
        sleep(1)
        if not self.server_process.is_alive():
            raise Exception("Server failed to start")

    def run(self, test_list=None, shared_data=None):
        global _current_test_case

        if not self.configured:
            raise Exception("TestRunner was not configured before run() was called")

        # Big try block to make sure we shut down the server if anything goes
        # wrong.
        failed = 0
        browser = None
        try:
            # Do some stuff
            browser = Remote(
                self.selenium_server_url,
                desired_capabilities = {
                    'browserName': self.selenium_browser,
                },
            )
            if shared_data is None:
                shared_data = dict()
            for test_case in self.test_cases:
                if test_list:
                    # Only run the named tests, plus those on the "critical path"
                    skip = True

                    if test_case.critical_path:
                        skip = False
                    elif test_list:
                        for test_name in test_list:
                            if test_name == test_case.__class__.__name__:
                                skip = False

                    if skip:
                        continue

                test_case.browser = browser
                if self.selenium_browser == 'firefox':
                    test_case.slowdown = .5
                test_case.shared = shared_data
                test_case.banner()
                _current_test_case = test_case
                test_case.run()
                test_case.done()
                _current_test_case = None
                failed += test_case.failed
        except KeyboardInterrupt:
            print "interrupt"
            failed += 1
        except:
            failed += 1
            traceback.print_exc()
            if self.wait_after_exception:
                print "press <enter> to exit ..."
                sys.stdin.readline()

        if browser:
            browser.quit()
        self._shutdown()
        return failed

    def _shutdown(self):
        if self.server_process:
            self.server_process.terminate()
            self.server_process.join()

    def _start_flask_app(self):
        log_handler = logging.StreamHandler(sys.stderr)
        log_handler.setLevel(logging.DEBUG)
        log_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'
        ))
        app.logger.addHandler(log_handler)
        app.logger.setLevel(logging.DEBUG)
        app.run(debug=False)

    def _load_test_cases(self, test_dir):
        scripts = defaultdict(list)

        # Creative mechanism for loading scripts
        for root, dirs, files in os.walk(test_dir):
            for name in files:
                if name.endswith(".py") and not name.startswith("__"):
                    name = name.rsplit('.', 1)[0]
                    fp, pathname, description = imp.find_module(name, [test_dir])
                    module = imp.load_module(name, fp, pathname, description)
                    for k, v in module.__dict__.items():
                        if not inspect.isclass(v) or not issubclass(v, TestBase):
                            continue
                        if v == TestBase:
                            continue
                        if not hasattr(v, 'order'):
                            raise Exception("Test case %s does not have an 'order' set" % v.__name__)
                        if isinstance(v.order, list):
                            for o in v.order:
                                scripts[o].append(v)
                        else:
                            scripts[v.order].append(v)

        tests = []
        for testlist in sorted(scripts.items()):
            for test in testlist[1]:
                tests.append(test)
        return tests

class WebElementExpectedOneElement(Exception):
    pass

class WebElementSet(object):
    def __init__(self, elements=None, context=None, test_dir=None, selector=None):
        self.context  = context
        self.test_dir = test_dir
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
            if len(self.elements) != 1:
                raise WebElementExpectedOneElement("Expected exactly 1 element")
            return f(self, *args, **kwargs)

        return decorator

    def require_context(f):
        def decorator(self, *args, **kwargs):
            assert self.context, "Need a test class supplied to emit test results"
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
        return self.__class__(self._verify_elements(elements), context=self.context, test_dir=self.test_dir, selector=new_selector)

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

    def __call__(self, *args, **kwargs):
        return self.find(*args, **kwargs)

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

    def parent(self):
        return self.find('xpath:..', selector_desc='parent')

    def __getitem__(self, index):
        return self.new(self.elements[index], selector="[%d]" % index)

    def __len__(self):
        return len(self.elements)

    def text(self):
        text = ''
        for el in self.elements:
            text += el.text
        return text

    @require_context
    def text_is(self, expected, message=None):
        if message is None:
            message = "%s text is: %s" % (self, expected)
        self.context.is_equal(self.text(), expected, message=message)
        return self

    @require_context
    def text_like(self, regexp, message=None):
        if message is None:
            message = "%s text like: %s" % (self, regexp)
        self.context.is_like(self.text(), regexp, message=message)
        return self

    @require_context
    def text_unlike(self, regexp, message=None):
        if message is None:
            message = "%s text like: %s" % (self, regexp)
        self.context.isnt_like(self.text(), regexp, message=message)
        return self

    @require_one_element
    def clear(self):
        self.elements[0].clear()
        return self

    @require_one_element
    def click(self):
        self.elements[0].click()
        return self

    @require_context
    def click_ok(self, message=None):
        if message is None:
            message = "Click: %s" % self
        try:
            self.click()
            self.context.fakepause()
            self.context.ok(message)
        except WebElementExpectedOneElement:
            self.context.failure("%s (Expected 1 element, got %d)" % (message, len(self.elements)))
        return self

    @require_one_element
    def select(self, option):
        select = Select(self.elements[0])
        select.select_by_value(option)
        return self

    @require_context
    def select_ok(self, option, message=None):
        if message is None:
            message = "Select: %s value=%s" % (self, option)
        try:
            self.select(option)
            self.context.ok(message)
        except WebElementExpectedOneElement:
            self.context.failure("%s (Expected 1 element, got %d)" % (message, len(self.elements)))
        except NoSuchElementException:
            self.context.failure('%s (%s)' % (message, 'no such option'))
            return
        return self

    @require_one_element
    @require_context
    def hover(self):
        ActionChains(self.context.browser).move_to_element(self.elements[0]).perform()
        return self

    @require_context
    def hover_ok(self, message=None):
        if message is None:
            message = "Hover: %s" % self
        try:
            self.hover()
            self.context.ok(message)
        except WebElementExpectedOneElement:
            self.context.failure("%s (Expected 1 element, got %d)" % (message, len(self.elements)))
        return self

    @require_one_element
    def attr(self, name):
        return self.elements[0].get_attribute(name)

    @require_context
    def attr_is(self, name, expected, message=None):
        if message is None:
            message = "%s attr(%s) is: %s" % (self, name, expected)
        try:
            self.context.is_equal(self.attr(name), expected, message=message)
        except WebElementExpectedOneElement:
            self.context.failure("%s (Expected 1 element, got %d)" % (message, len(self.elements)))
        return self

    @require_context
    def attr_like(self, name, regexp, message=None):
        if message is None:
            message = "%s attr(%s) like: %s" % (self, name, regexp)
        try:
            self.context.is_like(self.attr(name), regexp, message=message)
        except WebElementExpectedOneElement:
            self.context.failure("%s (Expected 1 element, got %d)" % (message, len(self.elements)))
        return self

    @require_one_element
    def is_visible(self):
        return self.elements[0].is_displayed()

    @require_one_element
    def is_enabled(self):
        return self.elements[0].is_enabled()

    @require_context
    def is_enabled_ok(self, message=None):
        if message is None:
            message = "Is enabled: %s" % self
        try:
            self.context.is_equal(self.is_enabled(), True, message)
        except:
            self.context.failure("%s (Expected 1 element, got %d)" % (message, len(self.elements)))
        return self

    @require_context
    def is_disabled_ok(self, message=None):
        if message is None:
            message = "Is disabled: %s" % self
        try:
            self.context.is_equal(self.is_enabled(), False, message)
        except:
            self.context.failure("%s (Expected 1 element, got %d)" % (message, len(self.elements)))
        return self

    @require_one_element
    def is_selected(self):
        return self.elements[0].is_selected()

    @require_context
    def is_selected_ok(self, message=None):
        if message is None:
            message = "Is selected: %s" % self
        try:
            self.context.is_equal(self.is_selected(), True, message)
        except:
            self.context.failure("%s (Expected 1 element, got %d)" % (message, len(self.elements)))
        return self

    @require_context
    def isnt_selected_ok(self, message=None):
        if message is None:
            message = "Isn't selected: %s" % self
        try:
            self.context.is_equal(self.is_selected(), False, message)
        except:
            self.context.failure("%s (Expected 1 element, got %d)" % (message, len(self.elements)))
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

    @require_context
    def type_ok(self, keys, message=None, clear_first=True):
        if message is None:
            message = "Typing: %s %s" % (self, json.dumps(keys))
        try:
            self.type(keys, clear_first)
            self.context.ok(message)
        except WebElementExpectedOneElement:
            self.context.failure("%s (Expected 1 element, got %d)" % (message, len(self.elements)))
        return self

    def length(self):
        return len(self)

    def length_ok(self, length, message=None):
        if message is None:
            message = "Length: %s '%d'" % (self, length)

        self.context.is_equal(len(self), length, message=message)
        return self

    def set_file_to_upload(self, filename, message=None):
        """
        On a file element, sets its path so that a file upload can occur.

        Use of this method probably immediately disqualifies your test suite
        from running in htmlunit, but it'll run in chrome (and probably other
        browsers) fine.

        @param filename: The file to upload, path is relative from the test dir of your app
        @type filename: str
        """
        if message is None:
            message = "Setting file to upload: %s %s" % (self, json.dumps(filename))
        try:
            self.type(os.path.join(self.test_dir, filename), clear_first=False)
            self.context.ok(message)
        except WebElementExpectedOneElement:
            self.context.failure("%s (Expected 1 element, got %d)" % (message, len(self.elements)))
        return self

class TestBase(object):
    """
    Inherit from this class in order to encapsulate a selenium test run.

    The child class should override the property "order", in order to specify
    the priority for the test case relative to other tests. Lower numbers
    are run earlier.

    The child class should override the method "run" in which the sequence of tests, consisting of various calls
    to methods such as self.is_equal are performed.
    """

    critical_path = False

    """ @type Remote """
    browser = None

    def __init__(self, base_uri, test_dir):
        self.number = 0
        self.failed = 0
        self.shared = dict()
        self.base_uri = furl(base_uri)
        self.test_dir = test_dir
        self.slowdown = 0

    def find(self, *args, **kwargs):
        return WebElementSet(self.browser, context=self, test_dir=self.test_dir).find(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        return self.find(*args, **kwargs)

    def fakepause(self):
        sleep(self.slowdown)

    def wait(self, timeout=10):
        return WebDriverWait(self.browser, timeout)

    def wait_for_ajax(self, *args, **kwargs):
        self.wait(*args, **kwargs).until_not(lambda x: x.execute_script('return jQuery.active'))
        return self

    def wait_for_bootstrap_modal(self, *args, **kwargs):
        last = [None]

        def inner_wait(driver):
            value = self.find('.modal')[-1].css('top')
            if last[0] and last[0] == value:
                return True
            last[0] = value
            return False
        self.wait(*args, **kwargs).until(inner_wait)
        return self

    def wait_for_element_visible(self, element, *args, **kwargs):
        def inner_wait(driver):
            try:
                e = self.find(element)[-1]
            except IndexError:
                return False
            return e.is_visible()
        self.wait(*args, **kwargs).until(inner_wait)
        return self

    def wait_for_element_hidden(self, element, *args, **kwargs):
        def inner_wait(driver):
            try:
                e = self.find(element)[-1]
            except IndexError:
                return False
            return not e.is_visible()
        self.wait(*args, **kwargs).until(inner_wait)
        return self

    def banner(self):
        name = self.__class__.__name__
        file = os.path.basename(inspect.getsourcefile(self.__class__))
        self.diag("Test class: %s (%s)" % (name, file))

    def run(self):
        """
        This method must be implemented by the child class.
        """
        name = self.__class__.__name__
        raise Exception("Subclass %s needs to implement run()" % name)

    def ok(self, message=None):
        """
        Declare a test step immediately successful

        @param message: Message to display
        @type message: str
        """
        self.number += 1
        message = message or ''
        print "ok %d %s" % (self.number, message)

    def failure(self, message=None):
        """
        Declare a test step as an immediate failure

        @param message: Message to display
        @type message: str
        """
        self.number += 1
        self.failed += 1
        message = message or ''
        if sys.stdout.isatty():
            print colored("not ok %d %s" % (self.number, message), 'red')
        else:
            print "not ok %d %s" % (self.number, message)
        self.screenshot('%s-failure-%d.png' % (self.__class__.__name__, self.failed))

    def diag(self, message, indent=0):
        """
        Display diagnostics for a test

        @param message: Message to display
        @type message: str
        @param indent: Tabs to indent
        @type indent: int
        """
        space = ""
        for i in range(indent):
            space += "\t"

        for line in unicode(message).splitlines():
            print "# %s%s" % (space, line)

    def is_equal(self, got, expected, message=None):
        """
        Verify got == expected. If so, call self.ok, if not self.failure

        @param got: String retrieved from DOM
        @type got: str
        @param expected: String expected
        @type expected: str
        @param message: Message to be displayed
        @type message: str
        """
        if got == expected:
            return self.ok(message)

        self.failure(message)
        self.diag("Got: %s\nExpected: %s" % (got, expected), indent=1)

    def isnt_equal(self, got, expected, message=None):
        """
        Verify got != expected. If so, call self.ok, if not self.failure

        @param got: String retrieved from DOM
        @type got: str
        @param expected: String expected
        @type expected: str
        @param message: Message to be displayed
        @type message: str
        """
        if got != expected:
            return self.ok(message)

        self.failure(message)
        self.diag("Got: %s\nExpected: %s" % (got, expected), indent=1)

    def is_like(self, got, regexp, message=None):
        """
        Verify got re.search expected. If so, call self.ok, if not self.failure

        @param got: String retrieved from DOM
        @type got: str
        @param regexp: Regex to match
        @type regexp: str
        @param message: Message to be displayed
        @type message: str
        """
        if got is None:
            self.failure(message)
            self.diag("Got: %s\nExpected: %s" % ('<None>', regexp), indent=1)
            return

        if re.search(regexp, got):
            return self.ok(message)

        self.failure(message)
        self.diag("Got: %s\nExpected: %s" % (got, regexp), indent=1)

    def isnt_like(self, got, regexp, message=None):
        """
        Verify got not re.search expected. If so, call self.ok, if not self.failure

        @param got: String retrieved from DOM
        @type got: str
        @param regexp: Regex to match
        @type regexp: str
        @param message: Message to be displayed
        @type message: str
        """
        if got is None:
            self.failure(message)
            self.diag("Got: %s\nExpected: %s" % ('<None>', regexp), indent=1)
            return

        if not re.search(regexp, got):
            return self.ok(message)

        self.failure(message)
        self.diag("Got: %s\nExpected: %s" % (got, regexp), indent=1)

    def done(self):
        """
        Display final report
        """
        if self.number:
            print "1..%d" % self.number
            if self.failed:
                self.diag("Looks like you failed %d test(s) of %d." % (self.failed, self.number))
        else:
            print "1..0"
            self.diag("No tests run!")

    def refresh(self):
        """
        Reload the current page
        """
        self.browser.refresh()

    def source(self):
        """
        Return the source for the current page
        """
        return self.browser.page_source

    def back(self):
        """
        Press "back" button in the browser
        """
        self.browser.back()
        self.fakepause()

    def get(self, uri):
        full_uri = furl(self.base_uri).join(uri)
        self.browser.get(str(full_uri))

    def get_ok(self, uri, message=None):
        """
        Set the browser to load a given uri

        @param uri: URI to load
        @type uri: str
        @param message: Message to display
        @type message: str
        """
        if message is None:
            message = "Opened: %s" % uri
        full_uri = furl(self.base_uri).join(uri)
        try:
            self.browser.get(str(full_uri))
        except Exception, e:
            self.failure('%s (%s)' % (message, str(e)))
            return

        self.ok('Opened: %s' % message)
        self.url_is(uri)

    def url_is(self, uri, message=None):
        """
        Verify the current URI is as given

        @param uri: URI to match
        @type uri: str
        @param message: Message to display
        @type message: str
        """
        if message is None:
            message = "Current URL is: %s" % uri

        expected = furl(self.base_uri).join(uri)
        got = furl(self.browser.current_url).copy()
        expected.fragment = ''
        got.fragment = ''
        expected.query = None
        got.query = None

        self.is_equal(str(got), str(expected), message)

    def url_like(self, expected, message=None):
        """
        Verify the current URI matches the given regex

        @param expected: Regex of URI to match
        @type expected: regex
        @param message: Message to display
        @type message: str
        """
        if message is None:
            message = "Current URL matches: %s" % expected

        got = furl(self.browser.current_url).copy()
        got.fragment = ''
        got.query = None

        self.is_like(str(got), expected, message)

    def screenshot(self, filename):
        """
        Dump a screenshot of the current page to a file

        @param filename: File name to dump to; files will be placed in app.root_path/test/
        @type filename: str
        """
        try:
            return self.browser.get_screenshot_as_file(os.path.join(self.test_dir, filename))
        except:
            self.diag("Could not take screenshot (some drivers do not support screenshots, or maybe the file couldn't be written)")


# Create a series of helpers that will be exported when tests use:
# from trex.test import *
_helpers = [
    'find',
    'wait',
    'wait_for_ajax',
    'wait_for_bootstrap_modal',
    'wait_for_element_visible',
    'wait_for_element_hidden',
    'ok',
    'failure',
    'diag',
    'is_equal',
    'is_like',
    'refresh',
    'source',
    'back',
    'get',
    'get_ok',
    'url_is',
    'url_like',
    'screenshot',
]
__all__ = _helpers + ['TestBase']

_current_test_case = None

def _make_helper(name):
    def f(*args, **kwargs):
        return getattr(_current_test_case, name)(*args, **kwargs)
    return f

for helper in _helpers:
    vars()[helper] = _make_helper(helper)
