# coding: utf8

from __future__ import absolute_import
from trex.rubble import global_harness as harness, TestFailureException
from .browser import *
from .assertions import *

def fill(**kwargs):
    for key, value in kwargs.items():
        el = find('[name="%s"]' % key).length_is(1, message="Couldn't find form element: %s" % key)
        if el.tag_name() == 'select':
            el.select_by_value(value)
        elif el.attr('type') == 'checkbox':
            for subel in el.filter_by_selected():
                subel.click()
            el = find('[name="%s"][value="%s"]' % (key, value))
            el.length_is(1, message="Couldn't find checkbox %s=%s" % (key, value))
            el.click()
        else:
            el.type(value)

def submit():
    find('.form-group button[type="submit"]').length_is(1).click()

def check_errors(**kwargs):
    find('.form-group.has-error').length_is(len(kwargs.keys()), message="Correct number of errors")
    for key, value in kwargs.items():
        el = find('.has-error [name="%s"]' % key)
        if not len(el):
            failure("Couldn't find form element: %s" % key)
        parent = el.parent()
        while not re.search(r'\bform-group\b', parent.attr('class')):
            parent = parent.parent()
        parent.find('.help-block').text_is(value)
