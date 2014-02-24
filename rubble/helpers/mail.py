# coding: utf8

from __future__ import absolute_import
from trex.rubble import global_harness as harness, TestFailureException
from trex.support.mail import CapturedEmail
import re
from .assertions import *

def assert_no_unchecked_emails():
    email_count = CapturedEmail.objects.count()
    is_equal(email_count, 0, "No unchecked emails")
    CapturedEmail.objects.delete()

def begin_capturing():
    assert_no_unchecked_emails()

def check(*matches, **kwargs):
    """Checks what emails the system has sent.

    Pass a series of dicts, one for each email you wish to check. For details on what keys the dict can have for
    matching checks, see compare().

    Checking has two modes: "absolute" (the default), and "incremental".

    In absolute mode, you must pass a dict describing every single email the system has sent since
    begin_capturing() was called.

    In incremental mode, you can pass dicts describing any of the emails that have been sent. You don't have to
    describe them all. Emails that are matched will be taken off the list to be checked, allowing you to do this:

        mail.begin_capturing()
        operation_that_sends_four_emails()
        mail.check(incremental=True, dict(... one of the emails...))
        mail.check(incremental=True, dict(... one of the other emails...))
        mail.check(dict(... one of the last two ...), dict(... the last one left ...))
    """

    incremental = kwargs.get('incremental', False)
    message("Checking emails (incremental=%s)" % incremental)

    emails = set(CapturedEmail.objects)

    if not incremental:
        is_equal(len(emails), len(matches), "Correct number of emails")

    emails_to_delete = set()

    for match in matches:
        found_match = False
        for email in emails:
            if compare(email, match):
                emails.remove(email)
                emails_to_delete.add(email.id)
                found_match = True
                break
        if not found_match:
            harness().handle_error(TestFailureException("Failed to find match for specified email", observed=[x.as_string() for x in emails], expected=match))

    for email_id in emails_to_delete:
        CapturedEmail.objects.get(id=email_id).delete()

    return emails

def compare(email, match):
    if 'to' in match and email.to != match['to']:
        return False

    if 'subject' in match and email.subject != match['subject']:
        return False

    if 'subject_re' in match and not re.search(match['subject_re'], email.subject):
        return False

    if 'body' in match and email.text_body != match['body']:
        return False

    if 'body_re' in match and not re.search(match['body_re'], email.text_body, re.S):
        return False

    if 'reply_to' in match and not email.reply_to == match['reply_to']:
        return False

    valid_keys = set(['to', 'subject', 'subject_re', 'body', 'body_re', 'reply_to'])
    found_keys = set(match.keys())
    if found_keys - valid_keys != set():
        harness().handle_error(TestFailureException("Developer mistake: trying to use a key to check emails with that doesn't exist: %s" % (found_keys - valid_keys), observed=found_keys, expected=valid_keys))

    return True
