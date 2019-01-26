# coding: utf8


from trex.rubble import global_harness as harness, TestFailureException
import sys
import re

def is_equal(observed, expected, message=None):
    if observed == expected:
        return

    if message is None:
        message = "is_equal check"

    harness().handle_error(TestFailureException(message, observed=observed, expected=expected))

def isnt_equal(observed, expected, message=None):
    if observed != expected:
        return

    if message is None:
        message = "isnt_equal check"

    harness().handle_error(TestFailureException(message, observed=observed, expected=expected))

def is_like(observed, regexp, message=None):
    if re.search(regexp, observed):
        return

    if message is None:
        message = "is_like check"

    harness().handle_error(TestFailureException(message, observed=observed, expected=regexp))

def isnt_like(observed, regexp, message=None):
    if not re.search(regexp, observed):
        return

    if message is None:
        message = "isnt_like check"

    harness().handle_error(TestFailureException(message, observed=observed, expected=regexp))

def failure(message):
    harness().handle_error(TestFailureException(message))

def message(message):
    frame = sys._getframe()

    depth = 0
    test_code = harness().current_test_object.__class__.run.__func__.__code__
    frame_code = frame.f_code
    while frame and (test_code.co_filename != frame_code.co_filename or test_code.co_firstlineno != frame_code.co_firstlineno):
        frame = frame.f_back
        if frame:
            frame_code = frame.f_code
        depth += 1

    for i in range(depth-1):
        print("    ", end=' ')
    print(message)
