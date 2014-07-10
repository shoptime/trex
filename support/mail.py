"""
Email abstraction, although it's pretty thin over postmark

To send:

import support.mail as mail
mail.send(to="nigel@shoptime.co.nz", subject="Hai!", text_body="Your preference regarding mudkipz?")

See mail.tpl_send() to send HTML mail.

Errors will generate exceptions as per https://github.com/themartorana/python-postmark/ - this lib does not
attempt to wrap those at this time.

"""

from __future__ import absolute_import
import postmark
from postmark.core import PMMailUnprocessableEntityException
import sendgrid
import pickle
from trex.flask import app
from mongoengine import Document, StringField, ValidationError
from flask import render_template
from premailer import transform
import re
from email.utils import parseaddr
from .mongoengine import QuantumField
from . import quantum
import json
import logging

log = logging.getLogger(__name__)

# Signals whether we're sending emails or just capturing them to mongo (for the
# test suite mainly)
capturing = False

def get_template(name):
    subclasses = dict([(x.__name__, x) for x in MailTemplate.__subclasses__()])
    template = subclasses.get(name)
    if not template:
        raise Exception("No email template named %s found" % name)
    return template

def all_template_names():
    return [x.__name__ for x in MailTemplate.__subclasses__()]

class MailTemplate(object):
    """Base class for all templated emails"""

    def __init__(self, **kwargs):
        self.tplvars = kwargs

    @classmethod
    def create_sample(cls):
        return cls(**cls.sample_tplvars())

    @classmethod
    def sample_tplvars(cls):
        raise NotImplementedError("You need to implement sample_tplvars")

    @property
    def name(self):
        return self.__class__.__name__

    def subject(self):
        raise NotImplementedError("You must implement subject()")

    def text_body(self):
        return render_template('email/%s-text.jinja2' % self.name, **self.tplvars)

    def html_body(self):
        return html_to_emailhtml(render_template('email/%s-html.jinja2' % self.name, **self.tplvars))

    def send(self, **kwargs):
        kwargs['subject'] = self.subject()
        kwargs['text_body'] = self.text_body()
        kwargs['html_body'] = self.html_body()
        send(**kwargs)

def send(
        sender         = None,
        to             = None,
        cc             = None,
        bcc            = None,
        reply_to       = None,
        subject        = None,
        tag            = None,
        html_body      = None,
        text_body      = None,
        custom_headers = None,
        attachments    = None,
        test           = False,
        service        = None,
        ):
    """
    Send email immediately. If postmark.test_override is set in the config then it will always generate test mode regardless
    of the test setting

    @param sender: Email from, defaults to configuration choice
    @param to: Email to, "name@email.com" or "First Last <name@email.com>" format
    @param cc: Email cc
    @param bcc: Email bcc
    @param reply_to: Email reply to, "name@email.com" or "First Last <name@email.com>" format
    @param subject: Subject line
    @param tag: PostMark/Processor tags
    @param html_body: HTML body
    @param text_body: Text body
    @param custom_headers: custom headers as a dictionary of key=value
    @param attachments: A list of tuples or email.mime.base.MIMEBase objects as attachments
    @param test: Whether to simply dump the results in the log instead of sending.
    @param service: Which email service to use. Supported: postmark, sendgrid
    @return:
    """

    ignore_send_regex = app.settings.get('mail', 'ignore_send_regex')
    if ignore_send_regex and re.search(ignore_send_regex, to):
        if test:
            log.debug('Not sending to %s, this address matches ignore_send_regex' % to)
        return

    if service is None:
        service = app.settings.get('mail', 'default_service')

    if service == 'postmark':
        return _send_postmark(
            sender         = sender,
            to             = to,
            cc             = cc,
            bcc            = bcc,
            reply_to       = reply_to,
            subject        = subject,
            tag            = tag,
            html_body      = html_body,
            text_body      = text_body,
            custom_headers = custom_headers,
            attachments    = attachments,
            test           = test
        )

    if service == 'sendgrid':
        return _send_sendgrid(
            sender         = sender,
            to             = to,
            cc             = cc,
            bcc            = bcc,
            reply_to       = reply_to,
            subject        = subject,
            tag            = tag,
            html_body      = html_body,
            text_body      = text_body,
            custom_headers = custom_headers,
            attachments    = attachments,
            test           = test
        )

    raise Exception("Unknown service for sending email")

def _send_postmark(
        sender         = None,
        to             = None,
        cc             = None,
        bcc            = None,
        reply_to       = None,
        subject        = None,
        tag            = None,
        html_body      = None,
        text_body      = None,
        custom_headers = None,
        attachments    = None,
        test           = False
        ):
    api_key = app.settings.get('postmark', 'api_key')
    sender  = sender or app.settings.get('postmark', 'sender')
    test    = test or app.settings.getboolean('postmark', 'test')
    if not reply_to and 'reply_to' in app.settings.options('postmark'):
        reply_to = app.settings.get('postmark', 'reply_to')

    if custom_headers is None:
        custom_headers = {}
    if attachments is None:
        attachments = []

    pm = postmark.PMMail(
        api_key        = api_key,
        sender         = sender,
        to             = to,
        cc             = cc,
        bcc            = bcc,
        reply_to       = reply_to,
        subject        = subject,
        tag            = tag,
        html_body      = html_body,
        text_body      = text_body,
        custom_headers = custom_headers,
        attachments    = attachments
    )

    if capturing or app.in_test_mode:
        CapturedEmail.from_postmark_object(pm)

    if test:
        log.info("email content: %s" % json.dumps(pm.to_json_message(), cls=postmark.PMJSONEncoder, indent=4))
        return

    pm.send()

def _send_sendgrid(
        sender         = None,
        to             = None,
        cc             = None,
        bcc            = None,
        reply_to       = None,
        subject        = None,
        tag            = None,
        html_body      = None,
        text_body      = None,
        custom_headers = None,
        attachments    = None,
        test           = False
):
    username = app.settings.get('sendgrid', 'username')
    password = app.settings.get('sendgrid', 'password')
    test     = test or app.settings.getboolean('sendgrid', 'test')

    if not sender:
        sender = parseaddr(app.settings.get('sendgrid', 'sender'))
        sender = (sender[1], sender[0])
    if not reply_to and 'reply_to' in app.settings.options('sendgrid'):
        reply_to = app.settings.get('sendgrid', 'reply_to')

    s = sendgrid.SendGridClient(username, password, secure=False, raise_errors=True)

    message = sendgrid.Mail(from_email=sender[0], from_name=sender[1], subject=subject, text=text_body, html=html_body)
    message.set_replyto(reply_to)
    message.add_to(to)
    if cc:
        raise NotImplementedError("Sendgrid doesn't appear to support CC at the moment")
    if bcc:
        message.add_bcc(bcc)

    if capturing or app.in_test_mode:
        CapturedEmail.from_sendgrid_object(message)

    if test:
        app.logger.info(
            'Sendgrid message: to=%(to)s subject=%(subject)s html=%(html_chars)s chars text: \n%(text)s',
            dict(
                to=message.to,
                subject=message.subject,
                html_chars=message.html and len(message.html) or 0,
                text=_truncate(message.text)
            )
        )
        return

    categories = app.settings.getlist('sendgrid', 'categories')
    if categories:
        for category in categories:
            message.add_category(category)

    s.send(message)

def _truncate(string):
    string = unicode(string)
    if len(string) > 200:
        return string[0:200] + '...'
    return string

def html_sample(template, tplvars):
    return html_to_emailhtml(render_template('email/%s-html.jinja2' % template, **tplvars))

def text_sample(template, tplvars):
    return render_template('email/%s-text.jinja2' % template, **tplvars)

def tpl_send(template, *args, **kwargs):
    tplvars = kwargs['tplvars']
    del kwargs['tplvars']

    kwargs['html_body'] = html_to_emailhtml(render_template('email/%s-html.jinja2' % template, **tplvars))
    kwargs['text_body'] = render_template('email/%s-text.jinja2' % template, **tplvars)

    return send(*args, **kwargs)

def html_to_emailhtml(html):
    emailhtml = transform(html, base_url=app.settings.get('server', 'url'))

    # Remove <head> node that is utterly useless (email clients ignore/mess up)
    emailhtml = re.sub(r'<head>.*</head>', '', emailhtml)
    # Add semi-colon after last style rule in style attrs - some email clients need this
    emailhtml = re.sub(r'(style="[^"]*)"', r'\1;"', emailhtml)

    return emailhtml

def begin_capturing():
    global capturing
    capturing = True
    CapturedEmail.objects.delete()

def end_capturing():
    global capturing
    capturing = False
    return CapturedEmail.objects

class CapturedEmail(Document):
    created   = QuantumField(required=True, default=quantum.now)

    to        = StringField(required=True)
    sender    = StringField(required=True)
    reply_to  = StringField()
    cc        = StringField(required=True)
    bcc       = StringField(required=True)
    subject   = StringField(required=True)
    text_body = StringField(required=True)
    html_body = StringField()

    def as_string(self):
        data = {}
        for key in ['to', 'cc', 'bcc', 'subject', 'text_body']:
            if getattr(self, key, None):
                data[key] = getattr(self, key)
        return json.dumps(data)

    @classmethod
    def from_postmark_object(cls, obj):
        email = cls(
            sender    = obj.sender,
            reply_to  = obj.reply_to,
            to        = obj.to,
            cc        = obj.cc or '',
            bcc       = obj.bcc or '',
            subject   = obj.subject,
            text_body = obj.text_body,
            html_body = obj.html_body,
        )

        email.save()
        return email

    @classmethod
    def from_sendgrid_object(cls, obj):
        email = cls(
            sender    = '%s <%s>' % (obj.from_name, obj.from_email),
            reply_to  = obj.reply_to,
            to        = ", ".join(obj.to),
            cc        = "",  # Sendgrid doesn't support CC it seems
            bcc       = ", ".join(obj.bcc),
            subject   = obj.subject,
            text_body = obj.text,
            html_body = obj.html,
        )

        email.save()
        return email
