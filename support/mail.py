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
from mongoengine import Document, StringField
from flask import render_template
from premailer import transform
import re
from email.utils import parseaddr


# Signals whether we're sending emails or just capturing them to mongo (for the
# test suite mainly)
capturing = False


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
        service        = 'postmark'
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
        doc = CapturedEmail()
        doc.postmark_obj = pickle.dumps(pm)
        doc.save()

    if test:
        test = True

    pm.send(test=test)

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

    s = sendgrid.Sendgrid(username, password, secure=False)

    message = sendgrid.Message(sender, subject, text_body, html_body)
    message.set_replyto(reply_to)
    message.add_to(to)
    if cc:
        message.add_cc(cc)
    if bcc:
        message.add_bcc(bcc)

    if capturing or app.in_test_mode:
        doc = CapturedEmail()
        doc.sendgrid_obj = pickle.dumps(message)
        doc.save()

    if test:
        app.logger.info('Sendgrid message: to=%(to)s subject=%(subject)s html=%(html)s text=%(text)s', dict(to=message.to, subject=message.subject, html=_truncate(message.html), text=_truncate(message.text)))
        return

    s.web.send(message)

def _truncate(string):
    if len(string) > 100:
        return string[0:100] + '...'
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
    return [ x.get_postmark_obj() for x in CapturedEmail.objects.all() ]

class CapturedEmail(Document):
    postmark_obj = StringField(required=True)

    def get_postmark_obj(self):
        return pickle.loads(str(self.postmark_obj))