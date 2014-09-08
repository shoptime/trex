from __future__ import absolute_import

import os
import sys

if 'VIRTUAL_ENV' not in os.environ:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    activate_this = os.path.join(project_root, 'bin', 'activate_this.py')
    execfile(activate_this, dict(__file__=activate_this))

import click
from app import app
import inspect
import importlib
import subprocess
import requests
from furl import furl
from multiprocessing import Process
import signal
import time
from glob import glob
import re
from operator import attrgetter
import logging
c_logger = logging.getLogger('app.lessc')

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """app command line interface"""

    if ctx.invoked_subcommand is None:
        app.log_to_papertrail('app')
        runserver()
    else:
        app.log_to_papertrail('ctx.invoked_subcommand')

@cli.resultcallback()
def after_cli(ret_val):
    app.shutdown()

@cli.command()
def runserver():
    "Run the development server"
    app.run()

@cli.command()
def testserver():
    "Run the development server using test mode"
    app.switch_to_test_mode()
    app.run()

@cli.command()
def wsgi_reload():
    "Reloads the site for production deployment"
    # Touch the WSGI file
    os.utime(os.path.join(app.root_path, '..', 'site.wsgi'), None)
    # Hit the site to actually trigger the reload
    r = requests.get(app.settings.get('trex', 'deploy_ping_url'), headers={'Host': furl(app.settings.get('server', 'url')).host})
    r.raise_for_status()

@cli.command()
def compile_static():
    "Compile static files"

    # Switch to static dir
    os.chdir(os.path.join(app.root_path, 'cdn'))

    # Compile less
    compile_application_less_to_css()

@cli.command()
def watch_static():
    "Compile static files (watching for changes with inotify)"

    # Switch to static dir
    os.chdir(os.path.join(app.root_path, 'cdn'))

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

@cli.command()
def shell():
    """Start an interactive iPython shell"""

    from IPython.terminal.ipapp import TerminalIPythonApp
    import app.model as m
    from trex.support import quantum

    context = dict(
        app     = app,
        quantum = quantum,
        m       = m,
    )

    rc_file = os.path.normpath(os.path.join(app.root_path, os.pardir, 'shell.rc'))
    if os.access(rc_file, os.R_OK):
        execfile(rc_file, context, dict(context=context))

    shell = TerminalIPythonApp.instance(
        display_banner = False,
        quick          = True,
        user_ns        = context,
    )
    shell.initialize(argv=[])
    shell.shell.confirm_exit = False

    def pretty_print(self, arg):
        from pprint import pformat
        import mongoengine
        import texttable

        output = None
        for line in self.shell.history_manager.get_tail(50):
            try:
                output = self.shell.history_manager.output_hist[line[1]]
            except KeyError:
                pass

        if isinstance(output, mongoengine.QuerySet):
            table = texttable.Texttable(max_width=0)
            table.set_deco(texttable.Texttable.HEADER)
            fields = output[0]._fields.keys()
            table.add_row(fields)
            for obj in output:
                table.add_row([str(getattr(obj, field)) for field in fields])
            pretty_output = table.draw()
        elif isinstance(output, mongoengine.Document):
            pretty_output = pformat(output.to_mongo().to_dict())
        else:
            pretty_output = pformat(output)

        print pretty_output

        return None

    shell.shell.define_magic('pp', pretty_print)

    context = app.test_request_context('__shell__', base_url=app.settings.get('server', 'url'))
    context.push()
    shell.start()
    context.pop()

@cli.command()
@click.option('-p', '--processes', default=1, help='How many parallel processes to run')
@click.option('-f', '--fail-method', default='exception', type=click.Choice(['exception', 'ipdb', 'print']), help='What to do on a test/assertion failure')
@click.option('-m', '--debug-mail', default=False, help='Dump debug info about emails that the app tries to send')
@click.option('-r', '--resume', default=False, help='Resume from the last test which failed')
@click.option('-l', '--list-tests', default=False, help='List all tests')
@click.option('--test-dir', default=None, type=click.Path(exists=True, file_okay=False, resolve_path=True), help='Override dir to tests (also required --test-module)')
@click.option('--test-module', default=None, help='Override module name for tests (also required --test-dir)')
@click.argument('tests', nargs=-1)
def rubble(processes, fail_method, debug_mail, resume, list_tests, tests, test_dir, test_module):
    """Run the new test harness"""
    import trex.rubble

    if list_tests:
        test_classes = trex.rubble.load_all_tests(test_dir=test_dir, test_module=test_module)
        for cls in sorted(test_classes, key=attrgetter('__name__')):
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
                print "Resuming from previous run, ignoring the following tests:"
                for test_name in sorted(exclude_tests):
                    print test_name
    else:
        try:
            os.unlink(trex.rubble.PASSED_TESTS_FILE)
        except OSError:
            pass

    if len(tests):
        test_classes = trex.rubble.load_tests_by_names(tests, exclude=exclude_tests, test_dir=test_dir, test_module=test_module)
    else:
        test_classes = trex.rubble.load_all_tests(test_dir=test_dir, test_module=test_module)

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
    print "Total time: %0.1f seconds" % (end_time - start_time)

class CronJobCLI(click.MultiCommand):
    def __init__(self, *args, **kwargs):
        import trex.support.cron

        possible_jobs = trex.support.cron.__dict__.items()
        self.jobs = {}
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
            self.jobs[k] = v

        super(CronJobCLI, self).__init__(*args, **kwargs)

    def list_commands(self, ctx):
        return self.jobs.keys()

    def get_command(self, ctx, name):
        @click.command(help=self.jobs[name].__doc__)
        def run_cron_job():
            job = self.jobs[name](app)
            job.run_wrapped()

        return run_cron_job

@cli.command(cls=CronJobCLI)
def cron():
    """Run cron jobs"""

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

if os.path.exists(os.path.join(app.root_path, 'support', 'run.py')):
    app_run = importlib.import_module('app.support.run', 'app.support')
