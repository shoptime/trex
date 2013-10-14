# coding: utf8

from __future__ import absolute_import
from trex.rubble import global_harness as harness, TestFailureException
from .browser import *
from .assertions import *

def fill(_selector='[name="%(key)s"]', **kwargs):
    for key, value in kwargs.items():
        el = find(_selector % dict(key=key)).filter_by_lambda(lambda el: el.get_attribute('type') != 'hidden')
        is_equal(el.length() > 0, True, "Couldn't find form element: %s" % key)
        if el[0].tag_name() == 'select':
            el.select_by_value(value)
        elif el[0].attr('type') == 'radio':
            el = find('[name="%s"][value="%s"]' % (key, value))
            el.length_is(1, message="Couldn't find radio button %s=%s" % (key, value))
            el.click()
        elif el[0].attr('type') == 'checkbox':
            for subel in el.filter_by_selected():
                subel.click()
            el = find('[name="%s"][value="%s"]' % (key, value))
            el.length_is(1, message="Couldn't find checkbox %s=%s" % (key, value))
            el.click()
        else:
            el.type(value)

def submit():
    find('.form-group button[type="submit"]').length_is(1).click()

def check_errors(_selector='.has-error [name="%(key)s"]', **kwargs):
    find('.form-group.has-error').length_is(len(kwargs.keys()), message="Correct number of errors")
    for key, value in kwargs.items():
        el = find(_selector % dict(key=key)).filter_by_lambda(lambda el: el.get_attribute('type') != 'hidden')
        if not len(el):
            failure("Couldn't find form element: %s" % key)
        parent = el.parent()
        while not re.search(r'\bform-group\b', parent.attr('class')):
            parent = parent.parent()
        parent.find('.help-block').text_is(value)
