# coding: utf8
from __future__ import absolute_import

from app import app
import traceback
import re
import os
import sys
import logging
import inspect
from multiprocessing import Process
from furl import furl
from pprint import pformat
from termcolor import colored
import time

_global_harness = None
def global_harness():
    return _global_harness
_global_init_harness_methods = []
_global_teardown_harness_methods = []
_global_init_test_methods = []
_global_teardown_test_methods = []

PASSED_TESTS_FILE = os.path.join(app.root_path, '..', '.rubble_passed_tests')


def split_tests_by_instance_number(test_classes, number, total):
    return sorted(test_classes, key=lambda x: x.__name__)[number::total]

def load_all_tests(exclude=None, test_dir=None, test_module=None):
    import importlib
    import glob

    if test_dir is None or test_module is None:
        test_dir = os.path.join(app.root_path, 'test')
        test_module = 'app.test'

    if not os.path.isabs(test_dir):
        test_dir = os.path.join(app.root_path, test_dir)

    for filename in glob.glob(os.path.join(test_dir, '*.py')):
        importlib.import_module('%s.%s' % (test_module, os.path.splitext(os.path.basename(filename))[0]))

    test_classes = set()

    def collect_classes(base_class):
        sub_classes = [c for c in base_class.__subclasses__()]
        test_classes.update([c for c in sub_classes if not c.abstract])
        for c in sub_classes:
            collect_classes(c)

    collect_classes(Test)

    return test_classes

def load_tests_by_names(test_names, exclude=None, test_dir=None, test_module=None):
    test_names = set(test_names)
    tests = set()
    for test in load_all_tests(exclude=exclude, test_dir=test_dir, test_module=test_module):
        if test.__name__ in test_names:
            test_names.remove(test.__name__)
            tests.add(test)

    if len(test_names):
        # If all test names haven't been consumed, then we were asked to load a test
        # that doesn't exist - except if those tests were also in the list of ones to
        # deliberately exclude.
        if not exclude or not test_names.issubset(set(exclude)):
            raise Exception("Couldn't find named tests: %s" % test_names)

    return tests

def init_harness():
    global _global_init_harness_methods

    def decorator(f):
        _global_init_harness_methods.append(f)
        return f

    return decorator

def init_test():
    global _global_init_test_methods

    def decorator(f):
        _global_init_test_methods.append(f)
        return f

    return decorator

def teardown_harness():
    global _global_teardown_harness_methods

    def decorator(f):
        _global_teardown_harness_methods.append(f)
        return f

    return decorator

def teardown_test():
    global _global_teardown_test_methods

    def decorator(f):
        _global_teardown_test_methods.append(f)
        return f

    return decorator

class Harness(object):
    def __init__(self, instance_number=None, fail_method='exception', debug_mail=False):
        global _global_harness
        _global_harness = self

        if fail_method not in ['exception', 'ipdb', 'print']:
            raise Exception("Invalid fail_method: %s" % fail_method)

        self.fail_method = fail_method

        self.instance_number = instance_number
        app.switch_to_test_mode(instance_number=self.instance_number)

        if not re.search(r'test', app.db.name):
            raise Exception("Mongo database '%s' doesn't have 'test' in its name. Refusing to run tests" % app.db.name)

        sys.stderr.write("[%d] Tests will use mongo %s and server url %s\n" % (os.getpid(), app.db.name, app.settings.get('server', 'url')))

        self.selenium_server_url = 'http://%s:%d/wd/hub' % (app.settings.get('test', 'selenium_server_host'), int(app.settings.get('test', 'selenium_server_port')))
        self.selenium_browser = app.settings.get('test', 'browser')

        # Stops the "accesslog" output from the server
        logging.getLogger('werkzeug').setLevel(logging.ERROR)

        # Stops the excessive logging from boto
        logging.getLogger('boto').setLevel(logging.ERROR)

        # Stops lots of crappy selenium logging
        logging.getLogger('selenium.webdriver.remote.remote_connection').setLevel(logging.WARNING)

        # Stops verbose mail logging
        if not debug_mail:
            logging.getLogger('trex.support.mail').setLevel(logging.WARNING)

        # Empty the test database to get things rolling
        app.db.connection.drop_database(app.db.name)

        self.base_uri = furl(app.settings.get('server', 'url'))
        self.browsers = {}
        self.browser_stack = []

    def upload_filename(self, filename):
        return os.path.join(app.root_path, 'test', filename)

    def handle_error(self, exception):
        self.error_count += 1
        for key, browser in self.browsers.items():
            browser.screenshot(message="Exception screenshot (%s): " % key)
        if self.fail_method == 'exception':
            raise exception
        if self.fail_method == 'ipdb':
            print exception
            import ipdb
            frame = sys._getframe()
            rubble_base = os.path.dirname(__file__)
            while os.path.commonprefix([frame.f_code.co_filename, rubble_base]) == rubble_base:
                frame = frame.f_back
            ipdb.set_trace(frame=frame)
            return
        if self.fail_method == 'print':
            print exception
            return

    def ipdb(self):
        frame = sys._getframe().f_back
        import ipdb
        ipdb.set_trace(frame=frame)

    def run(self, test_classes):
        self.start_application()
        self.error_count = 0

        try:
            with app.test_request_context():
                if self.fail_method == 'ipdb':
                    from ipdb import launch_ipdb_on_exception
                    with launch_ipdb_on_exception():
                        self._run(test_classes)
                else:
                    self._run(test_classes)
        except Exception:
            traceback.print_exc()
            raise SystemExit(2)
        finally:
            self.cleanup_browsers()
            self.stop_application()

    def _run(self, test_classes):
        try:
            for cls in test_classes:
                self.current_test_object = obj = cls(harness=self)
                try:
                    for function in _global_init_test_methods:
                        function(obj)
                    obj.setup()
                    banner = "[%d] %s - %s" % (os.getpid(), obj.__class__.__name__, obj.run.__code__.co_filename)
                    print
                    print banner
                    print re.sub('.', '-', banner)
                    # TODO - timing for each test?
                    start_time = time.time()
                    obj.run()
                    obj.post_run()
                    with open(PASSED_TESTS_FILE, 'a') as fh:
                        fh.write("%s\n" % obj.__class__.__name__)
                    end_time = time.time()
                    print "# %s took %0.1f seconds" % (obj.__class__.__name__, end_time-start_time)
                except:
                    for key, browser in self.browsers.items():
                        browser.screenshot(message="Uncaught exception screenshot (%s): " % key)
                    raise
                finally:
                    obj.teardown()
                    for function in _global_teardown_test_methods:
                        function(obj)
        finally:
            # Call teardown_harness methods
            for function in _global_teardown_harness_methods:
                function()


    def browser_for_key(self, key):
        if key not in self.browsers:
            # TODO - want some sort of app input here potentially
            from .browser import Browser
            self.browsers[key] = Browser(
                harness = self,
                selenium_server_url = self.selenium_server_url,
                selenium_browser = self.selenium_browser,
            )

        return self.browsers[key]

    def current_browser(self):
        if len(self.browser_stack):
            return self.browser_stack[-1]
        return self.browser_for_key('default')

    def cleanup_browsers(self):
        for browser in self.browsers.values():
            browser.shutdown()

    def start_application(self):
        if self.instance_number is not None:
            process_name = "Application Server instance %d" % self.instance_number
        else:
            process_name = "Application Server"

        self.server_process = Process(target=self._start_application, name=process_name)
        self.server_process.start()

        if not self.server_process.is_alive():
            raise Exception("Server failed to start")

    def _start_application(self):
        app.run(debug=False)

    def stop_application(self):
        if self.server_process:
            self.server_process.terminate()
            self.server_process.join()

class TestFailureException(Exception):
    retype = type(re.compile('a'))

    def __init__(self, message, observed=None, expected=None):
        self.message = message
        self.observed = observed
        self.expected = expected

    def __str__(self):
        if sys.stdout.isatty():
            out = colored(self.message, 'red')
        else:
            out = self.message
        if self.observed is not None or self.expected is not None:
            if isinstance(self.expected, self.retype):
                expected = self.expected.pattern
            else:
                expected = self.expected
            observed_out = re.sub(r'(?!\A)^', '              ', pformat(self.observed), flags=re.MULTILINE)
            expected_out = re.sub(r'(?!\A)^', '              ', pformat(expected), flags=re.MULTILINE)
            out += "\n    Observed: %s" % observed_out
            out += "\n    Expected: %s" % expected_out
        return out

class Test(object):
    abstract = False

    def __init__(self, harness):
        self.harness = harness

    def run(self):
        raise NotImplementedError("You need to implement the run method for your test")

    def post_run(self):
        from .helpers import mail
        mail.assert_no_unchecked_emails()

    def setup(self):
        """This is run before every test"""
        pass

    def teardown(self):
        """This is run after every test"""
        pass
