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

def check(*matches):
    message("Checking emails")

    emails = set(CapturedEmail.objects)

    is_equal(len(emails), len(matches), "Correct number of emails")

    for match in matches:
        found_match = False
        for email in emails:
            if compare(email, match):
                emails.remove(email)
                found_match = True
                break
        if not found_match:
            harness().handle_error(TestFailureException("Failed to find match for specified email", observed=[x.as_string() for x in emails], expected=match))

    CapturedEmail.objects.delete()

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

    valid_keys = set(['to', 'subject', 'subject_re', 'body', 'body_re'])
    found_keys = set(match.keys())
    if found_keys - valid_keys != set():
        harness().handle_error(TestFailureException("Developer mistake: trying to use a key to check emails with that doesn't exist: %s" % (found_keys - valid_keys), observed=found_keys, expected=valid_keys))

    return True
