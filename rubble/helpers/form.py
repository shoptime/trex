# coding: utf8

from __future__ import absolute_import
from trex.rubble import global_harness as harness, TestFailureException
from .browser import *
from .assertions import *
import os
from app import app
import re

def fill(_selector='[name="%(key)s"]', _date_format='%Y-%m-%d', _time_format='%H:%M %p', **kwargs):
    fields = [dict(key=x[0], value=x[1]) for x in kwargs.items()]

    for field in fields:
        el = find(_selector % dict(key=field['key']))

        is_equal(el.length() > 0, True, "Couldn't find form element: %s" % field['key'])

        if el[0].has_class('trex-phone-field'):
            el = el.parent().find('[type=text].trex-phone-field')
        else:
            el = el.filter_by_lambda(lambda el: el.get_attribute('type') != 'hidden')

        is_equal(el.length() > 0, True, "Couldn't find form element: %s" % field['key'])

        field['el'] = el

    # This makes sure we try to set values on trex-dependent-select-fields last
    # (i.e. after their parent field has had a value set)
    def compare_fields(a, b):
        a_value = 10
        b_value = 10

        if a['el'][0].has_class('trex-dependent-select-field'):
            a_value = 100
        if b['el'][0].has_class('trex-dependent-select-field'):
            b_value = 100

        return cmp(a_value, b_value)

    fields = sorted(fields, cmp=compare_fields)

    for field in fields:
        key = field['key']
        value = field['value']
        el = field['el']

        if el[0].tag_name() == 'select':
            el.select_by_value(value)
        elif el[0].attr('type') == 'radio':
            el = el.filter_by_lambda(lambda el: el.get_attribute('value') == value)
            el.length_is(1, message="Couldn't find radio button %s=%s" % (key, value))
            el.scroll_to().click()
        elif el[0].attr('type') == 'checkbox':
            for subel in el.filter_by_selected():
                subel.scroll_to().click()
            if value is not None:
                if not isinstance(value, list):
                    value = [value]
                for subvalue in value:
                    subel = el.filter_by_lambda(lambda el: el.get_attribute('value') == subvalue)
                    subel.length_is(1, message="Couldn't find checkbox %s=%s" % (key, subvalue))
                    subel.scroll_to().click()
        elif el[0].attr('type') == 'file':
            el.type(os.path.join(app.root_path, 'test', 'data', value), clear_first=False)
        elif el[0].has_class('trex-date-field'):
            el[0].type(value.strftime(_date_format))
            if el.length() == 2 and re.search(r'\btrex-time-field\b', el[1].attr('class')):
                el[1].type(value.strftime(_time_format))
                find('label[for="%s"]' % key).scroll_to().click()  # Unfocus the widgets
            else:
                el[0].click()  # Unfocus the date widget
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
            el = find(_selector % dict(key=key + '_file_input')).filter_by_lambda(lambda el: el.get_attribute('type') == 'file')
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
