from __future__ import absolute_import

import os
import sys

if 'VIRTUAL_ENV' not in os.environ:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    activate_this = os.path.join(project_root, 'bin', 'activate_this.py')
    execfile(activate_this, dict(__file__=activate_this))

from flask.ext import script
import imp
import inspect
import importlib
import datetime
from . import quantum
import subprocess
import requests
from furl import furl

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
            r = requests.get('http://localhost/', headers={'Host': furl(self.app.settings.get('server', 'url')).host})
            r.raise_for_status()

        @self.command
        def compile_static():
            "Compile static files"

            # Switch to static dir
            os.chdir(os.path.join(self.app.root_path, 'cdn'))

            # Compile less
            subprocess.check_call(['../../node_modules/.bin/lessc', '-x', 'less/app.less', 'less/app.css'])

        @self.command
        def watch_static():
            "Compile static files (watching for changes with inotify)"

            app = self.app

            # Switch to static dir
            os.chdir(os.path.join(self.app.root_path, 'cdn'))

            import time
            from watchdog.observers import Observer

            observer = Observer()
            class EventHandler(object):
                def dispatch(self, event):
                    if event.is_directory:
                        return

                    if event.src_path[-5:] != '.less':
                        return

                    app.logger.info("Building (%s changed)", event.src_path)
                    try:
                        subprocess.check_call(['../../node_modules/.bin/lessc', '-x', 'less/app.less', 'less/app.css'])
                    except subprocess.CalledProcessError as e:
                        app.logger.error("lessc exited with error code %d" % e.returncode)

            app.logger.info("Building")
            try:
                subprocess.check_call(['../../node_modules/.bin/lessc', '-x', 'less/app.less', 'less/app.css'])
            except subprocess.CalledProcessError as e:
                app.logger.error( "lessc exited with error code %d" % e.returncode)
            observer.schedule(EventHandler(), path='.', recursive=True)
            observer.start()
            app.logger.info("Began listening")
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

        try:
            app_run = importlib.import_module('app.support.run', 'app.support')
            app_run.register_methods(self)
        except ImportError:
            pass

    def run(self, *args, **kwargs):
        if 'default_command' not in kwargs:
            kwargs['default_command'] = 'runserver'
        try:
            super(Manager, self).run(*args, **kwargs)
        finally:
            self.app.shutdown()
