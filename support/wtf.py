# coding=utf-8

from __future__ import absolute_import
from wtforms import *
from flask.ext.wtf import Form
import mongoengine
from flask import url_for, abort, request, g
from ..flask import AuthBlueprint, render_json, render_html
from app.support import auth
from app import app
from .mongoengine import QuantumField
from .model import TrexUpload, TrexUploadTemporaryAccess
from . import token, ejson, quantum, tjson
from datetime import date
import json
import pytz
import operator
import re
from cgi import escape
import magic
import logging
log = logging.getLogger(__name__)

# Stolen from mongoengine
EMAIL_REGEX = re.compile(
    r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*"  # dot-atom
    r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-011\013\014\016-\177])*"'  # quoted-string
    r')@(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?$', re.IGNORECASE  # domain
)

class AttrDict(dict):
    def __init__(self, _proxy=None, **kwargs):
        self.__dict__ = self
        self._proxy = _proxy
        self.update(kwargs)

    def __getattr__(self, name):
        if self._proxy:
            return getattr(self._proxy, name)
        raise AttributeError

def country_choices():
    country_names = dict(pytz.country_names)
    country_names['GS'] = 'South Georgia' # no South Sandwich Islands for you!
    return [('', '-- select --')] + sorted(country_names.items(), key=operator.itemgetter(1))

def timezone_dependent_choices():
    choices = dict()
    for country_code, timezone_list in pytz.country_timezones.items():
        choices[country_code] = []
        for tz in timezone_list:
            choices[country_code].append((tz, tz))
        choices[country_code].sort(key=operator.itemgetter(0))

    return choices


class BareListWidget(object):
    """
    Renders a list of fields with no supporting markup
    """
    def __init__(self, label_position=None):
        self.label_position = label_position

    def __call__(self, field, **kwargs):
        html = []
        for subfield in field:
            if self.label_position == 'before':
                html.append('%s %s' % (subfield.label, subfield(**kwargs)))
            elif self.label_position == 'after':
                html.append('%s %s' % (subfield(**kwargs), subfield.label))
            else:
                html.append(subfield(**kwargs))
        return widgets.HTMLString(''.join(html))


class BootstrapCheckboxInput(widgets.Input):
    """
    Render a checkbox (with the label wrapped around the input
    """
    input_type = 'checkbox'

    def __call__(self, field, **kwargs):
        if getattr(field, 'checked', field.data):
            kwargs['checked'] = True

        kwargs.pop('class', None)

        html_string = super(BootstrapCheckboxInput, self).__call__(field, **kwargs)
        return widgets.HTMLString('<label class="checkbox">%s %s</label>' % (html_string.__html__(), field.label.text))


class BootstrapRadioInput(widgets.Input):
    """
    Render a radio (with the label wrapped around the input
    """
    input_type = 'radio'

    def __call__(self, field, **kwargs):
        if getattr(field, 'checked', field.data):
            kwargs['checked'] = True

        kwargs.pop('class', None)

        html_string = super(BootstrapRadioInput, self).__call__(field, **kwargs)
        return widgets.HTMLString('<label class="radio">%s %s</label>' % (html_string.__html__(), field.label.text))

class TextAreaListWidget(object):
    def __call__(self, field, **kwargs):
        output = '<div class="trex-textarea-list-widget" %s>' % widgets.html_params(id=field.id)

        def render_item(value):
            output = '<div class="item">'
            output += '<button type="button" class="btn btn-danger pull-right">&times</button>'
            output += '<textarea class="form-control" %s>%s</textarea>' % (widgets.html_params(name=field.name), value)
            output += '</div>'
            return output

        for value in kwargs.get('value', field._value()):
            output += render_item(value)

        output += '<div class="add-item" %s>' % widgets.html_params(**{'data-template': render_item('')})
        output += '<button type="button" class="btn btn-default btn-block">%s</button>' % field.add_label
        output += '</div>'
        output += '</div>'

        return widgets.HTMLString(output)


class TextAreaListField(Field):
    widget = TextAreaListWidget()

    def __init__(self, label='', validators=None, add_label='Add item', **kwargs):
        self.add_label = add_label
        super(TextAreaListField, self).__init__(label, validators, **kwargs)

    def _value(self):
        if self.data:
            return self.data
        else:
            return []

    def process_formdata(self, valuelist):
        if valuelist:
            self.data = valuelist
        else:
            self.data = []

class DateField(DateField):
    def __init__(self, label='', validators=None, date_format='yyyy-mm-dd', default_mode='day', **kwargs):
        self.default_mode = default_mode
        self.js_date_format = date_format
        self.py_date_format = self._calculate_strftime_format()

        kwargs['format'] = self.py_date_format
        super(DateField, self).__init__(label, validators, **kwargs)

    def _calculate_strftime_format(self):
        if self.js_date_format == 'yyyy-mm-dd':
            return '%Y-%m-%d'
        elif self.js_date_format == 'dd-mm-yyyy':
            return '%d-%m-%Y'
        else:
            raise ValueError("Invalid date format for trex.support.wtf.DateField: %s" % self.js_date_format)

    def _value(self):
        if self.raw_data:
            return ' '.join(self.raw_data)
        else:
            return self.data and self.data.strftime(self.format) or ''

    def process_formdata(self, valuelist):
        if valuelist:
            date_str = ' '.join(valuelist)
            if date_str.strip():
                try:
                    self.data = quantum.parse_date(date_str, format=self.format)
                except ValueError:
                    self.data = None
                    raise ValueError(self.gettext('Not a valid date value'))
            else:
                self.data = None

    def __call__(self, *args, **kwargs):
        kwargs['class'] = 'trex-date-field form-control'
        if self.default_mode == 'month':
            kwargs['data-date-viewmode'] = 1
        elif self.default_mode == 'year':
            kwargs['data-date-viewmode'] = 2

        kwargs['data-date-format'] = self.js_date_format
        return super(DateField, self).__call__(*args, **kwargs)

class DateTimeWidget(object):
    def __call__(self, field, **kwargs):
        date_viewmode = 0
        if field.date_default_mode == 'month':
            date_viewmode = 1
        elif field.date_default_mode == 'year':
            date_viewmode = 2

        value = field._value()
        date_value = time_value = ''
        if value:
            value = value.at(field.timezone)
            date_value = value.strftime('%Y-%m-%d')
            time_value = value.strftime('%H:%M %p')

        data = dict(
            widget_args = widgets.html_params(**{
                'class':'trex-date-time-widget',
            }),
            date_input_args = widgets.html_params(**{
                'id': '%s-date' % field.id,
                'name': field.name,
                'class': 'input-date form-control trex-date-field',
                'data-date-viewmode': date_viewmode,
                'data-date-format': field.js_date_format,
                'value': date_value,
                'autocomplete': 'off',
            }),
            time_input_args = widgets.html_params(**{
                'id': '%s-time' % field.id,
                'name': field.name,
                'class': 'input-time form-control trex-time-field',
                'data-step': field.time_step,
                'data-lower-bound': field.time_lower_bound and field.time_lower_bound or '',
                'data-upper-bound': field.time_upper_bound and field.time_upper_bound or '',
                'data-24h': field.time_24h and 'true' or '',
                'value': time_value,
            }),
        )

        return widgets.HTMLString("""
<div %(widget_args)s>
    <input %(date_input_args)s>
    <input %(time_input_args)s>
</div>
""" % data)

class DateTimeField(Field):
    widget = DateTimeWidget()

    def __init__(self, label='', validators=None, timezone=None, date_format='yyyy-mm-dd', date_default_mode='day', time_step=30, time_lower_bound=None, time_upper_bound='23:59', time_24h=True, **kwargs):
        if not timezone:
            raise Exception("Must specify a timezone when using a DateTimeField")
        self.timezone = timezone

        self.date_default_mode = date_default_mode
        self.js_date_format = date_format
        self.py_date_format = self._calculate_strftime_format()

        if time_step < 0 or time_step > 3600:
            raise Exception("time_step is out of range")
        self.time_step = time_step

        self.time_lower_bound = time_lower_bound
        self.time_upper_bound = time_upper_bound
        self.time_24h = time_24h

        super(DateTimeField, self).__init__(label, validators, **kwargs)

    def _calculate_strftime_format(self):
        if self.js_date_format == 'yyyy-mm-dd':
            return '%Y-%m-%d'
        elif self.js_date_format == 'dd-mm-yyyy':
            return '%d-%m-%Y'
        else:
            raise ValueError("Invalid date format for trex.support.wtf.DateTimeField: %s" % self.js_date_format)

    # Called to calculate the value to send to the widget, in this case we're
    # just sendin the Quantum object (or None)
    def _value(self):
        return self.data

    # Called to calculate the new value based on the form data
    def process_formdata(self, valuelist):
        if valuelist:
            try:
                if len(valuelist) == 2 and len(filter(lambda x: re.search(r'\S', x), valuelist)):
                    # Only try to process it if there's actually something in one of the input boxes
                    self.data = self._valuelist_to_quantum(valuelist)
                else:
                    self.data = None
            except ValueError:
                self.data = None
                raise ValueError(self.gettext('Not a valid datetime value'))

    def _valuelist_to_quantum(self, valuelist):
        if len(valuelist) != 2:
            raise ValueError(self.gettext('Not a valid datetime value'))
        date_str = '%s %s' % tuple(valuelist)
        return quantum.parse(date_str, timezone=self.timezone, relaxed=True)

    def __call__(self, *args, **kwargs):
        kwargs['class'] = 'trex-select-date-field'
        return super(DateTimeField, self).__call__(*args, **kwargs)

class TimeWidget(object):
    def __call__(self, field, **kwargs):
        value = field._value()

        widget_params = {
            'id': '%s-time' % field.id,
            'name': field.name,
            'class': 'input-time form-control trex-time-field',
            'data-step': field.time_step,
            'data-lower-bound': field.time_lower_bound and field.time_lower_bound or '',
            'data-upper-bound': field.time_upper_bound and field.time_upper_bound or '',
            'data-24h': field.time_24h and 'true' or '',
            'value': value is not None and value or '',
        }

        if 'placeholder' in kwargs:
            widget_params['placeholder'] = kwargs['placeholder']
        if 'class' in kwargs:
            classes = widget_params['class'].split(' ')
            classes += kwargs['class'].split(' ')
            widget_params['class'] = ' '.join(set(classes))

        data = dict(
            widget_args = widgets.html_params(**{
                'class':'trex-time-widget',
            }),
            time_input_args = widgets.html_params(**widget_params),
        )

        return widgets.HTMLString("""
<div %(widget_args)s>
    <input %(time_input_args)s>
</div>
""" % data)

class TimeField(Field):
    widget = TimeWidget()

    def __init__(self, label='', validators=None, time_step=30, time_lower_bound=None, time_upper_bound='23:59', time_24h=True, **kwargs):
        if time_step < 0 or time_step > 3600:
            raise Exception("time_step is out of range")
        self.time_step = time_step

        self.time_lower_bound = time_lower_bound
        self.time_upper_bound = time_upper_bound
        self.time_24h = time_24h

        super(TimeField, self).__init__(label, validators, **kwargs)

    # Called to calculate the value to send to the widget, in this case we're
    # just sending the string we were given (or None)
    def _value(self):
        return self.data

    # Called to calculate the new value based on the form data
    def process_formdata(self, valuelist):
        if valuelist:
            try:
                if len(valuelist) == 1:
                    self.data = valuelist[0]
                else:
                    self.data = None
            except ValueError:
                self.data = None
                raise ValueError(self.gettext('Not a valid time value'))

    def __call__(self, *args, **kwargs):
        if 'class' in kwargs and False:
            kwargs['class'] += ' trex-select-time-field'
        else:
            kwargs['class'] = 'trex-select-time-field'
        return super(TimeField, self).__call__(*args, **kwargs)

class SelectDateWidget(object):
    def __call__(self, field, **kwargs):
        data = dict(
            widget_args = widgets.html_params(**{
                'class':'trex-select-date-widget',
            }),
            day_select_args = widgets.html_params(**{
                'id': '%s-day' % field.id,
                'name': field.name,
                'class': 'input-day',
            }),
            month_select_args = widgets.html_params(**{
                'id': '%s-month' % field.id,
                'name': field.name,
                'class': 'input-month',
            }),
            year_select_args = widgets.html_params(**{
                'id': '%s-year' % field.id,
                'name': field.name,
                'class': 'input-year',
            }),
            day_select_options = self.day_select_options(field),
            month_select_options = self.month_select_options(field),
            year_select_options = self.year_select_options(field),
        )

        return widgets.HTMLString("""
<div %(widget_args)s>
    <select %(day_select_args)s>
        %(day_select_options)s
    </select>
    <select %(month_select_args)s>
        %(month_select_options)s
    </select>
    <select %(year_select_args)s>
        %(year_select_options)s
    </select>
</div>
""" % data)

    def day_select_options(self, field):
        result = []

        value = field._value()
        for day in range(1, 32):
            options = dict(value=str(day))
            if value and value.day == day:
                options['selected'] = True
            result.append('<option %s>%s</option>' % (widgets.html_params(**options), str(day)))

        return '\n'.join(result)

    def month_select_options(self, field):
        result = []

        value = field._value()
        for month in range(1, 13):
            options = dict(value=str(month))
            if value and value.month == month:
                options['selected'] = True
            result.append('<option %s>%s</option>' % (widgets.html_params(**options), quantum.from_date(date(year=2013, month=month, day=1), timezone='UTC').strftime('%B')))

        return '\n'.join(result)

    def year_select_options(self, field):
        result = []

        min = field.minyear
        max = field.maxyear
        default = field.defaultyear

        value = field._value()
        for year in range(min, max + 1):
            options = dict(value=str(year))
            if value:
                if value.year == year:
                    options['selected'] = True
            else:
                if default == year:
                    options['selected'] = True
            result.append('<option %s>%s</option>' % (widgets.html_params(**options), str(year)))

        return '\n'.join(result)

class SelectDateField(Field):
    widget = SelectDateWidget()

    def __init__(self, label='', validators=None, minyear=1970, maxyear=None, defaultyear=1980, **kwargs):
        if maxyear == None:
            maxyear = quantum.now('UTC').as_local().year

        self.minyear = minyear
        self.maxyear = maxyear
        self.defaultyear = defaultyear

        super(SelectDateField, self).__init__(label, validators, **kwargs)

    def _value(self):
        if self.raw_data:
            return self._valuelist_to_quantum_date(self.raw_data)
        else:
            return self.data

    def process_formdata(self, valuelist):
        if valuelist:
            try:
                self.data = self._valuelist_to_quantum_date(valuelist)
            except ValueError:
                self.data = None
                raise ValueError(self.gettext('Not a valid datetime value'))

            if self.data.year > self.maxyear or self.data.year < self.minyear:
                raise ValueError(self.gettext('Not a valid date'))

    def _valuelist_to_quantum_date(self, valuelist):
        if len(valuelist) != 3:
            raise ValueError(self.gettext('Not a valid datetime value'))
        date_str = '%s-%s-%s' % tuple(reversed(valuelist))
        return quantum.parse_date(date_str, format='%Y-%m-%d')

    def __call__(self, *args, **kwargs):
        kwargs['class'] = 'trex-select-date-field'
        return super(SelectDateField, self).__call__(*args, **kwargs)

class RadioField(RadioField):
    widget = BareListWidget()
    option_widget = BootstrapRadioInput()

class CheckListField(SelectMultipleField):
    widget = BareListWidget()
    option_widget = BootstrapCheckboxInput()

class BooleanFieldWidget(object):
    def __call__(self, field, **kwargs):
        input_args = dict(
            id    = field.id,
            name  = field.name,
            type  = 'checkbox',
            value = 'checked',
        )
        if kwargs.get('value', field._value()):
            input_args['checked'] = 'checked'

        data = dict(
            input_args = widgets.html_params(**input_args),
        )

        if field.label_lhs:
            return widgets.HTMLString('<div class="checkbox"><input %(input_args)s></div>' % data)

        data['label'] = field.boolean_label
        return widgets.HTMLString('<label class="checkbox"><input %(input_args)s> %(label)s</label>' % data)

class BooleanField(Field):
    widget = BooleanFieldWidget()

    def __init__(self, label='', label_lhs=False, validators=None, **kwargs):
        self.label_lhs = label_lhs
        if label_lhs:
            super(BooleanField, self).__init__(label, validators, **kwargs)
        else:
            self.boolean_label = label
            super(BooleanField, self).__init__('', validators, **kwargs)

    def process_formdata(self, valuelist):
        if valuelist:
            self.data = valuelist[0] == 'checked'
        else:
            self.data = False

    def _value(self):
        if self.data:
            return self.data
        else:
            return None

class StarRatingField(IntegerField):
    def __init__(self, label='', validators=None, low_label='Poor', high_label='Excellent', star_count=5, **kwargs):
        self.low_label = low_label
        self.high_label = high_label
        self.star_count = star_count
        super(StarRatingField, self).__init__(label, validators, **kwargs)

    def __call__(self, *args, **kwargs):
        kwargs['class'] = 'trex-star-rating-field'
        kwargs['type'] = 'hidden'
        kwargs['data-high-label'] = self.high_label
        kwargs['data-low-label'] = self.low_label
        kwargs['data-star-count'] = self.star_count
        return super(StarRatingField, self).__call__(*args, **kwargs)

class DependentSelectField(SelectField):
    def __init__(self, label='', validators=None, parent_field=None, select_text='-- select --', allow_unknown_parent_choices=False, _form=None, **kwargs):
        kwargs['coerce'] = lambda x: x is not None and str(x) or None
        super(DependentSelectField, self).__init__(label, validators, _form=_form, **kwargs)
        if parent_field is None:
            raise Exception("You must specify a parent field")
        self.parent_field = parent_field
        self.select_text = select_text
        self.choice_dict = self.choices
        self.allow_unknown_parent_choices = allow_unknown_parent_choices
        self._form = _form
        self.choices = []

    def pre_validate(self, form):
        parent_field = form._fields.get(self.parent_field)
        if not parent_field:
            raise Exception("Couldn't find parent field on form")

        if not self.data:
            return

        if parent_field.data in self.choice_dict:
            choices = self.choice_dict[parent_field.data]

            for v, _ in choices:
                if self.data == v:
                    break
            else:
                raise ValueError(self.gettext('Not a valid choice'))

            if self.select_text:
                self.choices = [('', self.select_text)]+choices
            else:
                self.choices = choices
        else:
            if not self.allow_unknown_parent_choices:
                raise ValueError(self.gettext('Not a valid choice'))

    def __call__(self, *args, **kwargs):
        if 'class' in kwargs:
            kwargs['class'] += ' trex-dependent-select-field'
        else:
            kwargs['class'] = 'trex-dependent-select-field'
        kwargs['data-parent'] = self.parent_field
        kwargs['data-choices'] = json.dumps(self.choice_dict)
        kwargs['data-select-text'] = self.select_text

        # Prepopulate the choices based on the current parent field value
        parent_field = self._form._fields.get(self.parent_field)
        if parent_field and parent_field.data in self.choice_dict:
            self.choices = self.choice_dict[parent_field.data]

        return super(DependentSelectField, self).__call__(*args, **kwargs)

class ChosenSelectField(SelectField):
    def __call__(self, **kwargs):
        kwargs['class'] = 'trex-chosen-select-field'
        return super(ChosenSelectField, self).__call__(**kwargs)

class FileListWidget(object):
    def __call__(self, field, **kwargs):
        data = dict(
            widget_args = widgets.html_params(**{
                'class':'trex-file-list-widget',
                'data-xhr-url': url_for('trex.upload.xhr'),
                'data-iframe-url': url_for('trex.upload.iframe'),
            }),
            input_args = widgets.html_params(**{
                'id': field.id,
                'name': field.name,
                'type': 'hidden',
                'value': kwargs.get('value', field._value()),
            }),
            file_input_name = "%s_file_input" % field.name,
        )

        return widgets.HTMLString("""
<div %(widget_args)s>
    <input %(input_args)s>
    <div class="files"></div>
    <a class="add-file btn btn-default">Add File <input name="%(file_input_name)s" type="file" multiple></a>
</div>
""" % data)

class FileListField(Field):
    widget = FileListWidget()

    def _value(self):
        if self.data:
            return ejson.dumps(self.data)
        else:
            return ejson.dumps([])

    def process_formdata(self, valuelist):
        if valuelist:
            data = json.loads(valuelist[0])
            self.data = []
            for upload_data in data:
                upload = TrexUpload.objects(user=g.user, id=upload_data['oid']).first()
                if upload:
                    self.data.append(upload)
        else:
            self.data = []

class FileWidget(object):
    def __init__(self, class_name='trex-file-widget'):
        self.class_name = class_name

    def file_display(self, field):
        if not field.data:
            return ''
        return escape(field.data.file.filename)

    def __call__(self, field, **kwargs):
        options = dict(
            allow_clear = field.allow_clear,
        )

        type_validators = [x for x in field.validators if isinstance(x, FileType)]
        if len(type_validators):
            options['type_validators'] = type_validators[0].for_browser()

        data = dict(
            widget_args = widgets.html_params(**{
                'class': self.class_name,
                'data-xhr-url': url_for('trex.upload.xhr'),
                'data-iframe-url': url_for('trex.upload.iframe'),
                'data-options': tjson.dumps(options),
            }),
            input_args = widgets.html_params(**{
                'id': field.id,
                'name': field.name,
                'type': 'hidden',
                'value': kwargs.get('value', field._value()),
            }),
            button_args = widgets.html_params(**{
                'type': 'button',
                'class': 'btn btn-default',
                'style': not (field.allow_clear and field.data) and 'display: none;' or '',
            }),
            file_display_args = widgets.html_params(**{
                'class': 'file-display',
                'style': not self.file_display(field) and 'display: none;' or '',
            }),
            file_input_name = "%s_file_input" % field.name,
            file_display = self.file_display(field),
        )

        return widgets.HTMLString("""
<div %(widget_args)s>
    <div %(file_display_args)s">%(file_display)s</div>
    <a class="add-file btn btn-default">Upload file <input name="%(file_input_name)s" type="file"></a>
    <button %(button_args)s>Clear file</button>
    <span class="uploading"></span>
    <input %(input_args)s>
</div>
""" % data)

class FileField(Field):
    widget = FileWidget()

    def _value(self):
        if self.data:
            return ejson.dumps(self.data)
        else:
            return ''

    def process_formdata(self, valuelist):
        if valuelist:
            if valuelist[0]:
                data = json.loads(valuelist[0])
                if isinstance(self.object_data, TrexUpload) and str(self.object_data.id) == data['oid']:
                    # Even if we don't own this one, it was provided as the form
                    # default, so we'll let the user pass it through untouched.
                    self.data = self.object_data
                else:
                    self.data = TrexUpload.objects(user=g.user, id=data['oid']).first()
            else:
                self.data = None
        else:
            self.data = None

    def __init__(self, label='', validators=None, allow_clear=True, **kwargs):
        super(FileField, self).__init__(label, validators, **kwargs)
        self.allow_clear = allow_clear

class ImageWidget(FileWidget):
    def __init__(self, class_name='trex-file-widget trex-image-widget', **kwargs):
        super(ImageWidget, self).__init__(class_name=class_name, *kwargs)

    def file_display(self, field):
        if not field.data:
            return '<div class="thumbnail"><span class="no-image">No image</span></div>'
        return '<div class="thumbnail"><img %s></div>' % widgets.html_params(src=field.data.url())

class ImageField(FileField):
    widget = ImageWidget()

    def process(self, *args, **kwargs):
        super(ImageField, self).process(*args, **kwargs)
        if isinstance(self.data, TrexUpload) and g.user and self.data.user != g.user:
            # Provide temporary access to the upload for this user (so they can
            # view the existing image)
            TrexUploadTemporaryAccess(upload=self.data, user=g.user).save()

class PhoneField(TextField):
    def __init__(self, label='', validators=None, country=None, country_field=None, display_placeholder=True, **kwargs):
        self.country_field = country_field
        self.country = country
        self.display_placeholder = display_placeholder
        super(PhoneField, self).__init__(label, validators, **kwargs)

    def _value(self):
        if self.raw_data:
            return self.raw_data[0].replace('invalid:', '')
        else:
            return self.data or ''

    def process_formdata(self, valuelist):
        if valuelist:
            phone = ' '.join(valuelist)
            if phone.strip().startswith('invalid:'):
                self.data = phone.replace('invalid:', '')
                raise ValueError("Invalid phone number")
            else:
                self.data = phone

    def __call__(self, **kwargs):
        kwargs['disabled'] = 'disabled'

        if 'class' in kwargs:
            kwargs['class'] = ' '.join(kwargs['class'].split(' ') + ['trex-phone-field'])
        else:
            kwargs['class'] = 'trex-phone-field'

        if self.country_field:
            kwargs['data-country-field'] = self.country_field

        if self.country:
            kwargs['data-country'] = self.country

        if self.raw_data and self.raw_data[0].startswith('invalid:'):
            kwargs['data-keep-raw-value'] = 'true'

        if self.display_placeholder:
            kwargs['data-display-placeholder'] = True

        return super(PhoneField, self).__call__(**kwargs)

class InviteField(TextAreaField):
    def __init__(self, label='', validators=None, placeholder_text=None, contacts=None, **kwargs):
        self.placeholder_text = placeholder_text
        self.contacts = contacts
        if not contacts:
            self.contacts = []

        super(self.__class__, self).__init__(label, validators, **kwargs)

    def __call__(self, **kwargs):
        if self.placeholder_text:
            kwargs['data-placeholder'] = self.placeholder_text
        kwargs['data-contacts'] = json.dumps(self.contacts)
        kwargs['class'] = 'form-control trex-invite-field'
        kwargs['data-existing'] = json.dumps(self.data)
        return super(InviteField, self).__call__(**kwargs)

    def _value(self):
        return u''

    def process_formdata(self, valuelist):
        if valuelist:
            emails = json.loads(valuelist[0])
            invalid = []
            self.data = []
            for invite in emails:
                if bool(EMAIL_REGEX.match(invite)):
                    self.data.append(invite)
                else:
                    invalid.append(invite)
            if len(invalid):
                raise ValidationError("Invalid emails: %s" % ", ".join(invalid))
        else:
            self.data = []

class TagField(TextAreaField):
    def __init__(self, label='', validators=None, source_data=None, behaviour=None, **kwargs):
        self.source_data = source_data
        if not source_data:
            self.source_data = []
        self.behaviour = behaviour

        super(TagField, self).__init__(label, validators, **kwargs)

    def __call__(self, **kwargs):
        kwargs['data-source-data'] = json.dumps(self.source_data)
        kwargs['data-existing'] = json.dumps(self.data)
        kwargs['class'] = 'trex-tag-field form-control'
        kwargs['disabled'] = 'disabled'
        if self.behaviour:
            kwargs['data-behaviour'] = self.behaviour
        return super(TagField, self).__call__(**kwargs)

    def _value(self):
        return u''

    def process_formdata(self, valuelist):
        if valuelist:
            self.data = json.loads(valuelist[0])
        else:
            self.data = []

class EmailTagField(TagField):
    def __init__(self, label='', validators=None, behaviour=None, **kwargs):
        if behaviour is None:
            behaviour = 'email'
        super(EmailTagField, self).__init__(label, validators, behaviour=behaviour, **kwargs)

    def process_formdata(self, valuelist):
        super(EmailTagField, self).process_formdata(valuelist)
        invalid = []
        for email in self.data:
            if not bool(EMAIL_REGEX.match(email)):
                invalid.append(email)
        if len(invalid):
            raise ValidationError("Invalid emails: %s" % ", ".join(invalid))

class BrainTreeEncryptedTextInput(widgets.TextInput):
    def __call__(self, field, **kwargs):
        kwargs.setdefault('id', field.id)
        kwargs.setdefault('type', self.input_type)
        kwargs['data-encrypted-name'] = field.name
        return widgets.HTMLString('<input %s>' % self.html_params(**kwargs))

class BrainTreeTextField(TextField):
    widget = BrainTreeEncryptedTextInput()

class BrainTreeEncryptedSelect(widgets.Select):
    def __call__(self, field, **kwargs):
        kwargs.setdefault('id', field.id)
        if self.multiple:
            kwargs['multiple'] = True
        kwargs['data-encrypted-name'] = field.name
        html = ['<select %s>' % html_params(**kwargs)]
        for val, label, selected in field.iter_choices():
            html.append(self.render_option(val, label, selected))
        html.append('</select>')
        return widgets.HTMLString(''.join(html))

class BrainTreeSelectField(SelectField):
    widget = BrainTreeEncryptedSelect()

    def pre_validate(self, form):
        pass

class FileType(object):
    type_details = dict(
        pdf = dict(
            name = 'PDF',
            mime_types = ['application/pdf'],
            rules = [
                ('application/pdf', None),
                (None, 'pdf'),
            ]
        ),
        doc = dict(
            name = 'Word Document',
            mime_types = ['application/msword'],
            rules = [
                ('application/msword', None),
                (None, 'doc'),
                (None, 'docx'),
            ]
        ),
        ppt = dict(
            name = 'PowerPoint',
            mime_types = ['application/vnd.ms-powerpoint'],
            rules = [
                ('application/vnd.ms-powerpoint', None),
                (None, 'ppt'),
                (None, 'pptx'),
            ]
        ),
        image = dict(
            name = 'Image',
            subtypes = ['jpg', 'png'],
        ),
        jpg = dict(
            name = 'JPEG',
            mime_types = ['image/jpeg'],
            rules = [
                ('image/jpeg', None),
                (None, 'jpg'),
                (None, 'jpeg'),
            ]
        ),
        png = dict(
            name = 'PNG',
            mime_types = ['image/png'],
            rules = [
                ('image/png', None),
                (None, 'png'),
            ]
        ),
    )

    def __init__(self, types=[], message=None):
        self.types = types
        self.mime_types = []
        self.rules = []

        for type_name in self.types:
            self._add_type(type_name)

        if not message:
            if len(self.types) == 1:
                message = 'Uploaded file must be of type %s' % self.type_details[self.types[0]]['name']
            else:
                message = 'Uploaded file must be one of: %s' % ", ".join([self.type_details[x]['name'] for x in self.types])

        self.message = message

    def _add_type(self, type_name):
        if type_name not in self.type_details:
            raise Exception("Invalid type: %s" % type_name)

        type_data = self.type_details[type_name]
        self.mime_types.extend(type_data.get('mime_types', []))
        self.rules.extend(type_data.get('rules', []))
        if 'subtypes' in type_data:
            for subtype_name in type_data['subtypes']:
                self._add_type(subtype_name)

    def for_browser(self):
        return dict(
            rules   = self.rules,
            message = self.message,
        )

    def __call__(self, form, field):
        if not field.data:
            # Nothing to validate
            return

        if not isinstance(field.data, TrexUpload):
            raise TypeError("Can only validate TrexUpload objects")

        if field.data.file.content_type not in self.mime_types:
            raise ValidationError(self.message)

blueprint = AuthBlueprint('trex.upload', __name__, url_prefix='/trex/upload')

@blueprint.route('/xhr', methods=['POST'], endpoint='xhr', auth=auth.login)
@render_json()
def upload_xhr():
    upload = TrexUpload(user=g.user)
    upload.file.put(
        request.data,
        content_type         = magic.from_buffer(request.data[:1048576], mime=True),
        browser_content_type = request.content_type,
        filename             = request.headers.get('X-FileName'),
    )
    upload.save()

    return dict(
        url      = url_for('trex.upload.view', token=upload.token),
        oid      = str(upload.id),
        progress = 100,
    )

@blueprint.route('/iframe', methods=['POST'], endpoint='iframe', auth=auth.login)
@render_html('trex/upload/upload_iframe.jinja2')
def upload_iframe():
    upload = TrexUpload(user=g.user)

    file = request.files[request.form['_trex_file_field_name']]
    if not file:
        abort(500)

    content_type = magic.from_buffer(file.read(1048576), mime=True)
    file.seek(0)

    upload.file.put(
        file.stream,
        content_type         = content_type,
        browser_content_type = file.content_type,
        filename             = file.filename,
    )
    upload.save()

    return dict(
        file_info = dict(
            url      = url_for('trex.upload.view', token=upload.token),
            oid      = str(upload.id),
            size     = upload.file.length,
            progress = 100,
        )
    )

@blueprint.route('/view/<token>', methods=['GET'], endpoint='view', auth=auth.public)
def upload_view(token):
    upload = TrexUpload.get_404(token=token)

    if upload.user != g.user:
        if TrexUploadTemporaryAccess.objects(upload=upload, user=g.user).first() is None:
            abort(404)

    if 'If-None-Match' in request.headers and request.headers['If-None-Match'] == upload.token:
        return app.response_class('', 304)

    response = app.response_class(upload.file.get(), 200)
    response.headers['Content-Type'] = upload.file.content_type
    response.headers['ETag'] = upload.token
    response.headers['Cache-Control'] = 'private, max-age=31622400'
    response.headers['Content-Disposition'] = 'filename=%s' % upload.file.filename

    return response

class DecimalField(DecimalField):
    """
        Subclass of WTF's DecimalField to fix the weird interaction with
        validators.Required() and invalid Decimal values
    """

    def process_formdata(self, valuelist):
        try:
            super(DecimalField, self).process_formdata(valuelist)
        except ValueError:
            if valuelist:
                self.data = valuelist[0]
            raise

app.register_blueprint(blueprint)
