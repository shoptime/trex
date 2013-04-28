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
import datetime
import subprocess

class Manager(script.Manager):
    def __init__(self, *args, **kwargs):
        # These are loaded here so that the calling script has time to load the
        # app for us
        from trex.test import run_selenium_tests, TestFailedException
        import trex.support.cron

        super(Manager, self).__init__(*args, **kwargs)

        @self.command
        def runserver():
            "Run the development server"
            self.app.run()

        @self.command
        def compile_static():
            "Compile static files"

            # Switch to static dir
            os.chdir(os.path.join(self.app.root_path, 'cdn'))

            # Compile less
            subprocess.check_call(['../../node_modules/.bin/lessc', '-x', 'less/app.less', 'less/app.css'])

        @self.shell
        def make_context():
            context = dict(
                app       = self.app,
                datetime  = datetime.datetime,
                timedelta = datetime.timedelta,
            )
            try:
                fp, pathname, description = imp.find_module('model', [self.app.root_path])
                context['m'] = imp.load_module('model', fp, pathname, description)
            except ImportError:
                pass

            return context

        @self.command
        def test():
            "Run the test suite"
            self.app.switch_to_test_mode()
            try:
                run_selenium_tests()
            except TestFailedException:
                sys.exit(1)

        @self.command
        def cron(job_name):
            "Run cron jobs"

            fp, pathname, description = imp.find_module('support/cron', [self.app.root_path])
            module = imp.load_module('support/cron', fp, pathname, description)

            cls = None
            jobs = {}

            for k, v in module.__dict__.items():
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

    def run(self, *args, **kwargs):
        if 'default_command' not in kwargs:
            kwargs['default_command'] = 'runserver'
        try:
            super(Manager, self).run(*args, **kwargs)
        finally:
            self.app.shutdown()
