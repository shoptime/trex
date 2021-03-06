from __future__ import absolute_import

from trex.flask import app
import logging
log = logging.getLogger(__name__)
import os
import sys
import time
import traceback
from mongoengine import Document, StringField, IntField, DynamicDocument
import mongoengine
from .mongoengine import QuantumField
from . import quantum
from datetime import datetime

class CronLock(Document):
    name     = StringField(unique=True, required=True)
    started  = QuantumField(required=True, default=quantum.now)
    expires  = QuantumField(required=True)
    hostname = StringField(required=True)
    pid      = IntField(required=True)

class TimeoutException(Exception):
    pass

class CronJob(object):
    timeout = 60

    def __init__(self, app):
        self.app = app
        if not self.app.debug:
            self.app.log_to_file('cron.log')

    def run(self):
        raise NotImplementedError("Need to implement CronJob.run()")

    def _check_timeouts(self):
        old_job = CronLock.objects(name=self.__class__.__name__, expires__lt=quantum.now()).first()
        if old_job:
            old_job.delete()
            raise TimeoutException("%s timed out, forcing lock removal" % self.__class__.__name__)

    def run_wrapped(self):
        context = self.app.test_request_context('__cron__')
        context.push()

        lock = None

        try:
            try:
                self._check_timeouts()
            except TimeoutException:
                log.error(traceback.format_exc())

            try:
                lock = CronLock(
                    name = self.__class__.__name__,
                    expires = quantum.now('UTC').add(seconds=self.timeout),
                    hostname = os.uname()[1],
                    pid = os.getpid(),
                )
                lock.save()
            except mongoengine.queryset.NotUniqueError:
                log.debug('%s could not get lock, giving up', self.__class__.__name__)
                context.pop()
                return

            log.info('%s running', self.__class__.__name__)
            begin_time = time.time()

            self.run()

            run_time = time.time() - begin_time
            log.info('%s completed (%.2f secs)', self.__class__.__name__, run_time)
            if not sys.stdout.isatty():
                time.sleep(max(0, 15 - run_time))
        except Exception, e:
            log.error(traceback.format_exc())
            app.exception_reporter.invoke(app, e)

        context.pop()
        if lock:
            lock.delete()
        sys.exit(0)

class QueuedCronJob(CronJob):
    """Represents a cron job that may be queued.

    The jobs to be run are stored in the CronJobQueue collection (see
    mongoengine definition for more info). Jobs to be run can be scheduled
    using CronJobQueue.enqueue()"""

    def run(self):
        # make this go around processing for 40 seconds
        begin_time = time.time()

        while True:
            job = CronJobQueue.objects(type=self.__class__.__name__, started=None).first()

            if job:
                # handle it here
                self.lock_job(job)
                try:
                    self.process_job(job)
                except:
                    job.reset()
                    raise
                self.unlock_job(job)

                run_time = time.time() - begin_time
                if run_time > 40:
                    # we're done for this cronjob invocation
                    break
            else:
                # no jobs.. we're done for this time
                break

    def process_job(self, job):
        raise NotImplementedError("Need to implement QueuedCronJob.process_job()")

    def lock_job(self, job):
        job.started        = quantum.now()
        job.locked_by_host = os.uname()[1]
        job.locked_by_pid  = os.getpid()
        job.progress       = 1
        job.save(safe=True)

    def unlock_job(self, job):
        job.finished       = quantum.now()
        job.locked_by_host = None
        job.locked_by_pid  = None
        job.progress       = 100
        job.save(safe=True)

class CronJobQueue(DynamicDocument):
    meta = {
        'ordering': ['created'],
    }

    type           = StringField(required=True)
    created        = QuantumField(required=True, default=quantum.now)
    started        = QuantumField()
    locked_by_host = StringField()
    locked_by_pid  = IntField()
    progress       = IntField(default=0)
    finished       = QuantumField()

    @staticmethod
    def enqueue(type, **kwargs):
        job = CronJobQueue.objects(type=type, started=None, **kwargs).first()
        if job:
            # Recalculation already scheduled, let's not do it again
            return False, job

        job = CronJobQueue()
        job.type = type
        for k, v in kwargs.items():
            setattr(job, k, v)
        job.save()

        return True, job

    def reset(self):
        self.started = None
        self.locked_by_host = None
        self.locked_by_pid = None
        self.progress = 0
        self.save(safe=True)

class remove_old_file_uploads(CronJob):
    def run(self):
        from trex.support.model import TrexUpload
        cut_off = quantum.now('UTC').subtract(hours=24)
        for upload in TrexUpload.objects(created__lte=cut_off, preserved=False):
            log.debug("Removing upload: %s" % upload.token)
            upload.delete()

class remove_old_sessions(CronJob):
    """Remove old sessions"""

    def run(self):
        res = app.db.identity.remove({'expires': { '$lte': datetime.utcnow()}}, w=1)
        log.info(res or 'Nothing done')

class remove_old_user_account_recovery_requests(CronJob):
    """Remove old user account recovery requests"""

    def run(self):
        from trex.support.model import UserAccountRecovery
        cutoff = quantum.now('UTC').subtract(hours=24)
        for uar in UserAccountRecovery.objects(created__lte=cutoff):
            uar.delete()
            log.debug('Removed request %s for %s' % (uar.code, uar.user.email))

class remove_old_rate_limit_entries(CronJob):
    """Remote old entries in the rate limit buffer"""

    def run(self):
        # Hard coded 4 hour maximum buffer size for now
        cutoff = quantum.now('UTC').subtract(hours=4).as_local()
        res = app.db.rate_limit_buffer.remove({'created': { '$lte': cutoff}}, w=1)
        log.info(res or 'Nothing done')
