# coding: utf8

from __future__ import absolute_import
from trex.rubble import global_harness as harness, TestFailureException
from .browser import *
from .assertions import *
import os
from app import app
import re

def fill(_selector='[name="%(key)s"]', **kwargs):
    for key, value in kwargs.items():
        el = find(_selector % dict(key=key)).filter_by_lambda(lambda el: el.get_attribute('type') != 'hidden')
        is_equal(el.length() > 0, True, "Couldn't find form element: %s" % key)
        if el[0].tag_name() == 'select':
            el.select_by_value(value)
        elif el[0].attr('type') == 'radio':
            el = find('[name="%s"][value="%s"]' % (key, value))
            el.length_is(1, message="Couldn't find radio button %s=%s" % (key, value))
            el.scroll_to().click()
        elif el[0].attr('type') == 'checkbox':
            for subel in el.filter_by_selected():
                subel.scroll_to().click()
            if value is not None:
                if not isinstance(value, list):
                    value = [value]
                for subvalue in value:
                    el = find('[name="%s"][value="%s"]' % (key, subvalue))
                    el.length_is(1, message="Couldn't find checkbox %s=%s" % (key, subvalue))
                    el.scroll_to().click()
        elif el[0].attr('type') == 'file':
            el.type(os.path.join(app.root_path, 'test', 'data', value), clear_first=False)
        elif el[0].attr('class') is not None and re.search(r'\btrex-date-field\b', el[0].attr('class')):
            el[0].type(value.strftime('%Y-%m-%d'))
            if el.length() == 2 and re.search(r'\btrex-time-field\b', el[1].attr('class')):
                el[1].type(value.strftime('%H:%M %p'))
            find('label[for="%s"]' % key).scroll_to().click() # Unfocus the widgets
        else:
            el.type(value)

def fill_bs2(*args, **kwargs):
    fill(*args, **kwargs)

def select_by_label(select_name, label):
    select = find('[name="%s"]' % select_name).length_is(1)
    select.select_by_value(select.find('option').filter_by_text(label).attr('value'))

def submit():
    find('.form-group button[type="submit"]').filter_by_visible().length_is(1).scroll_to().click()

def submit_bs2():
    find('.form-actions button[type="submit"]').filter_by_visible().length_is(1).click()

def submit_modal():
    find('.modal .modal-footer button.btn-primary').length_is(1).click()
    wait_for_ajax()

def check_errors(_selector='.has-error [name="%(key)s"]', **kwargs):
    find('.form-group.has-error').length_is(len(kwargs.keys()), message="Correct number of errors")
    for key, value in kwargs.items():
        el = find(_selector % dict(key=key)).filter_by_lambda(lambda el: el.get_attribute('type') != 'hidden')
        if not len(el):
            failure("Couldn't find form element: %s" % key)
        parent = el.parent()
        while not re.search(r'\bform-group\b', parent.attr('class')):
            parent = parent.parent()
        parent.find('.help-block-error')[0].text_is(value)

def check_errors_bs2(**kwargs):
    find('.control-group.error').length_is(len(kwargs.keys()), message='Correct number of errors')
    for key, value in kwargs.items():
        el = find('.error [name="%(key)s"]' % dict(key=key)).filter_by_lambda(lambda el: el.get_attribute('type') != 'hidden')
        if not len(el):
            failure("Couldn't find form element: %s" % key)
        parent = el.parent()
        while not re.search(r'\bcontrol-group\b', parent.attr('class')):
            parent = parent.parent()
        parent.find('.help-inline').text_is(value)
