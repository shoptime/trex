from __future__ import absolute_import

import os
import sys

if 'VIRTUAL_ENV' not in os.environ:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    activate_this = os.path.join(project_root, 'bin', 'activate_this.py')
    execfile(activate_this, dict(__file__=activate_this))

from app import app
from flask.ext import script
import imp
import inspect
import importlib
import datetime
from . import quantum
import subprocess
import requests
from furl import furl
from multiprocessing import Process
import signal
import time
from glob import glob
import re
import logging
c_logger = logging.getLogger('app.lessc')

class Manager(script.Manager):
    def __init__(self, *args, **kwargs):
        # These are loaded here so that the calling script has time to load the
        # app for us
        from trex.test import TestRunner
        import trex.support.cron

        super(Manager, self).__init__(*args, **kwargs)

        @self.command
        def runserver():
            "Run the development server"
            self.app.run()

        @self.command
        def testserver():
            "Run the development server using test mode"
            self.app.switch_to_test_mode()
            self.app.run()

        @self.command
        def wsgi_reload():
            "Reloads the site for production deployment"
            # Touch the WSGI file
            os.utime(os.path.join(self.app.root_path, '..', 'site.wsgi'), None)
            # Hit the site to actually trigger the reload
            r = requests.get(app.settings.get('trex', 'deploy_ping_url'), headers={'Host': furl(self.app.settings.get('server', 'url')).host})
            r.raise_for_status()

        @self.command
        def compile_static():
            "Compile static files"

            # Switch to static dir
            os.chdir(os.path.join(self.app.root_path, 'cdn'))

            # Compile less
            compile_application_less_to_css()

        @self.command
        def watch_static():
            "Compile static files (watching for changes with inotify)"

            app = self.app

            # Switch to static dir
            os.chdir(os.path.join(self.app.root_path, 'cdn'))

            import time
            from watchdog.observers import Observer
            from watchdog.events import FileModifiedEvent

            observer = Observer()
            class EventHandler(object):
                def dispatch(self, event):
                    if event.is_directory:
                        return

                    if event.src_path[-5:] != '.less':
                        return

                    if not isinstance(event, FileModifiedEvent):
                        # Only care if the file was actually modified
                        return

                    less_file = event.src_path
                    c_logger.info("Building (%s changed)", less_file)

                    if re.search('app[^/]*\.less$', less_file):
                        # Compile it
                        css_file  = '%s.css' % less_file[0:-5]
                        compile_less_to_css(less_file, css_file)
                    else:
                        # Compile all app less files, in the hope they'll
                        # include this one
                        compile_application_less_to_css()

            c_logger.info("Building")
            compile_application_less_to_css()
            observer.schedule(EventHandler(), path='.', recursive=True)
            observer.start()
            c_logger.info("Began listening")
            try:
                while True:
                    time.sleep(0.5)
            except KeyboardInterrupt:
                observer.stop()
            observer.join()

        @self.shell
        def make_context():
            context = dict(
                app       = self.app,
                quantum   = quantum,
            )
            try:
                context['m'] = importlib.import_module('app.model', 'app')
            except ImportError:
                pass

            return context

        @self.option('-w', '--wait', action='store_true', default=False, help='Wait for keypress on test failure')
        @self.option('-t', '--test', action='store', default=[], help='Execute specific test')
        def test(wait=False, test=None):
            "Run the test suite"
            t = TestRunner(wait_after_exception=wait)
            t.configure_for_flask()
            if test:
                failed = t.run(test_list=[t.strip() for t in test.split(',')])
            else:
                failed = t.run()
            if failed:
                sys.exit(1)

        @self.option('-p', '--processes', action='store', default=1, help='How many parallel processes to run')
        @self.option('-f', '--fail-method', action='store', default=None, help='What to do on a test/assertion failure [exception|ipdb|print]')
        @self.option('-m', '--debug-mail', action='store_true', default=False, help='Dump debug info about emails that the app tries to send')
        @self.option('-r', '--resume', action='store_true', default=False, help='Resume from the last test which failed')
        @self.option('-l', '--list-tests', action='store_true', default=False, help='List all tests')
        @self.option('tests', action='store', nargs='*', default=None)
        def rubble(processes, fail_method, debug_mail, resume, tests, list_tests):
            """Run the new test harness"""
            import trex.rubble

            if list_tests:
                test_classes = trex.rubble.load_all_tests()
                for cls in test_classes:
                    print cls.__name__
                sys.exit(0)

            start_time = time.time()

            if fail_method is None:
                fail_method = 'exception'
            processes = int(processes)

            exclude_tests = []
            if resume:
                if os.path.isfile(trex.rubble.PASSED_TESTS_FILE):
                    with open(trex.rubble.PASSED_TESTS_FILE, 'r') as fh:
                        exclude_tests = [line.strip() for line in fh.readlines()]
            else:
                try:
                    os.unlink(trex.rubble.PASSED_TESTS_FILE)
                except OSError:
                    pass

            if len(tests):
                test_classes = trex.rubble.load_tests_by_names(tests, exclude=exclude_tests)
            else:
                test_classes = trex.rubble.load_all_tests(exclude=exclude_tests)

            def run_tests(instance_number, instance_total):
                def sig_quit_handler(signum, frame):
                    print "[%d] Got SIGQUIT - exiting now" % os.getpid()
                    raise SystemExit(3)
                signal.signal(signal.SIGQUIT, sig_quit_handler)
                tests = trex.rubble.split_tests_by_instance_number(test_classes, instance_number, instance_total)
                harness = trex.rubble.Harness(instance_number=instance_number, fail_method=fail_method, debug_mail=debug_mail)
                harness.run(tests)
                if harness.error_count:
                    print "[%d] Process complete with errors" % os.getpid()
                    raise SystemExit(1)
                else:
                    print "[%d] Process complete" % os.getpid()

            print "Initialising the harness"
            for function in trex.rubble._global_init_harness_methods:
                function()

            if processes > 1:
                procs = []
                for i in range(processes):
                    proc = Process(
                        target = run_tests,
                        name   = "Test Harness %d of %d" % (i, processes),
                        args   = (i, processes)
                    )
                    proc.start()
                    if not proc.is_alive():
                        raise Exception("Failed to start %d" % proc.name)
                    procs.append(proc)

                failed = False
                while len(procs):
                    #print "%d processes alive. Failed=%s (%s)" % (len(procs), failed, ", ".join([str(proc.pid) for proc in procs]))
                    for proc in procs:
                        proc.join(0.5)
                        if not proc.is_alive():
                            procs.remove(proc)
                            if proc.exitcode and not failed:
                                failed = True
                                for proc in procs:
                                    os.kill(proc.pid, signal.SIGQUIT)

                if failed:
                    raise SystemExit(1)
            else:
                run_tests(0, 1)

            end_time = time.time()
            print "Total time: %0.1f seconds" % (end_time-start_time)

        @self.command
        def cron(job_name):
            "Run cron jobs"

            cls = None
            jobs = {}

            possible_jobs = trex.support.cron.__dict__.items()
            try:
                cron_module = importlib.import_module('app.support.cron', 'app.support')
                possible_jobs.extend(cron_module.__dict__.items())
            except ImportError:
                pass

            for k, v in possible_jobs:
                if not inspect.isclass(v) or not issubclass(v, trex.support.cron.CronJob):
                    continue
                if v == trex.support.cron.CronJob:
                    continue
                if v == trex.support.cron.QueuedCronJob:
                    continue
                jobs[k] = v
                if k == job_name:
                    cls = v

            if job_name == 'help' or not cls:
                if job_name == 'help':
                    print "app cron <jobname>"
                    print "\nwhere <jobname> is one of:\n"
                else:
                    print "No job found named %s" % job_name
                for name, cls in jobs.items():
                    print "    %s - %s" % (name, cls.__doc__)
                sys.exit(1)

            cronjob = cls(self.app)
            cronjob.run_wrapped()

        if os.path.exists(os.path.join(self.app.root_path, 'support', 'run.py')):
            app_run = importlib.import_module('app.support.run', 'app.support')
            app_run.register_methods(self)

    def handle(self, prog, name, *args, **kwargs):
        if name == 'runserver':
            self.app.log_to_papertrail('app')
        else:
            self.app.log_to_papertrail(name)
        super(Manager, self).handle(prog, name, *args, **kwargs)


    def run(self, *args, **kwargs):
        if 'default_command' not in kwargs:
            kwargs['default_command'] = 'runserver'
        try:
            super(Manager, self).run(*args, **kwargs)
        finally:
            self.app.shutdown()

def compile_less_to_css(less_file, css_file):
    c_logger.debug('%s => %s' % (less_file, css_file))
    try:
        subprocess.check_call(['../../node_modules/.bin/lessc', '-x', less_file, css_file])
    except subprocess.CalledProcessError as e:
        c_logger.error("lessc exited with error code %d" % e.returncode)

def compile_application_less_to_css():
    for less_file in glob('less/app*.less'):
        css_file = '%s.css' % less_file[0:-5]
        compile_less_to_css(less_file, css_file)
