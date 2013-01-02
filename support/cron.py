from __future__ import absolute_import

from trex.flask import app
import logging
import os
import sys
import time
import traceback
from datetime import datetime, timedelta
from mongoengine import Document, StringField, DateTimeField, IntField
import mongoengine

class CronLock(Document):
    name     = StringField(unique=True, required=True)
    started  = DateTimeField(required=True, default=datetime.utcnow)
    expires  = DateTimeField(required=True)
    hostname = StringField(required=True)
    pid      = IntField(required=True)

class TimeoutException(Exception):
    pass

class CronJob(object):
    timeout = 60

    def __init__(self, app):
        self.app = app

        log_file = os.path.abspath(os.path.join(app.root_path, '..', 'logs', 'cron.log'))
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'
        ))
        app.logger.addHandler(file_handler)

    def run():
        raise NotImplementedError("Need to implement CronJob.run()")

    def _check_timeouts(self):
        old_job = CronLock.objects(name=self.__class__.__name__, expires__lt=datetime.utcnow()).first()
        if old_job:
            old_job.delete()
            raise TimeoutException("%s timed out, forcing lock removal")

    def run_wrapped(self):
        context = self.app.test_request_context('__cron__', base_url=self.app.settings.get('server', 'url'))
        context.push()

        try:
            try:
                self._check_timeouts()
            except TimeoutException, e:
                self.app.logger.error(traceback.format_exc())

            try:
                lock = CronLock(
                    name = self.__class__.__name__,
                    expires = datetime.utcnow() + timedelta(seconds=self.timeout),
                    hostname = os.uname()[1],
                    pid = os.getpid(),
                )
                lock.save()
            except mongoengine.queryset.NotUniqueError:
                self.app.logger.debug('%s could not get lock, giving up', self.__class__.__name__)
                context.pop()
                return

            self.app.logger.info('%s running', self.__class__.__name__)
            begin_time = time.time()

            self.run()

            run_time = time.time() - begin_time
            self.app.logger.info('%s completed (%.2f secs)', self.__class__.__name__, run_time)
            if not sys.stdout.isatty():
                time.sleep(max(0, 15 - run_time))
        except Exception, e:
            self.app.logger.error(traceback.format_exc())

        context.pop()
        lock.delete()
        sys.exit(0)

def cron_daemon(cron_jobs, base_interval=60, max_interval=600, failure_multiplier=1.5):
    if app.debug:
        app.logger.handlers[0].setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'
        ))
    else:
        log_dir = os.path.abspath(os.path.join(app.root_path, '..', 'logs'))
        file_handler = logging.FileHandler(os.path.join(log_dir, 'cron.log'))
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'
        ))
        app.logger.addHandler(file_handler)

    app.logger.info('Starting cron daemon')

    interval = base_interval

    while True:
        context = app.test_request_context('__cron__', base_url=app.settings.get('server', 'url'))
        context.push()

        try:
            cron_jobs()
            interval = base_interval
        except Exception, e:
            app.logger.error(traceback.format_exc())
            interval *= failure_multiplier

        context.pop()
        if interval > max_interval:
            interval = max_interval

        time.sleep(interval)
