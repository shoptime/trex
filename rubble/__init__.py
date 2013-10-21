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

def split_tests_by_instance_number(test_classes, number, total):
    return sorted(test_classes, key=lambda x: x.__name__)[number::total]

def load_all_tests():
    scripts = {}

    test_dir = os.path.join(app.root_path, 'test')

    # Creative mechanism for loading scripts
    for root, dirs, files in os.walk(test_dir):
        if root == os.path.join(test_dir, 'helpers'):
            continue
        for name in files:
            if name.endswith(".py") and not name.startswith("__"):
                name = name.rsplit('.', 1)[0]
                import importlib
                module = importlib.import_module('app.test.%s' % name, 'app.test')
                for k, v in module.__dict__.items():
                    # Only want subclasses of a test
                    if not inspect.isclass(v) or not issubclass(v, Test):
                        continue
                    # But not the test class itself
                    if v == Test:
                        continue
                    if not v.abstract:
                        if k in scripts:
                            raise Exception("Duplicate test named: %s" % k)
                        scripts[k] = v

    return set(scripts.values())

def load_tests_by_names(test_names):
    test_names = set(test_names)
    tests = set()
    for test in load_all_tests():
        if test.__name__ in test_names:
            test_names.remove(test.__name__)
            tests.add(test)

    if len(test_names):
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
    def __init__(self, instance_number=None, fail_method='exception'):
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
            # Call init_harness methods
            for function in _global_init_harness_methods:
                function()
            for cls in test_classes:
                self.current_test_object = obj = cls(harness=self)
                try:
                    for function in _global_init_test_methods:
                        function(obj)
                    obj.setup()
                    banner = "%s - %s" % (obj.__class__.__name__, obj.run.__code__.co_filename)
                    print
                    print banner
                    print re.sub('.', '-', banner)
                    # TODO - timing for each test?
                    start_time = time.time()
                    obj.run()
                    obj.post_run()
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
            observed_out = re.sub(r'(?!\A)^', '              ', pformat(self.observed), flags=re.MULTILINE)
            expected_out = re.sub(r'(?!\A)^', '              ', pformat(self.expected), flags=re.MULTILINE)
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
