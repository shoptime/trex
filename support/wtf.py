# coding=utf-8

from __future__ import absolute_import
from flask.ext import wtf
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
                html.append('%s %s' % (subfield.label, subfield()))
            elif self.label_position == 'after':
                html.append('%s %s' % (subfield(), subfield.label))
            else:
                html.append(subfield())
        return wtf.widgets.HTMLString(''.join(html))


class BootstrapCheckboxInput(wtf.Input):
    """
    Render a checkbox (with the label wrapped around the input
    """
    input_type = 'checkbox'

    def __call__(self, field, **kwargs):
        if getattr(field, 'checked', field.data):
            kwargs['checked'] = True

        html_string = super(BootstrapCheckboxInput, self).__call__(field, **kwargs)
        return wtf.widgets.HTMLString('<label class="checkbox">%s %s</label>' % (html_string.__html__(), field.label.text))


class BootstrapRadioInput(wtf.Input):
    """
    Render a radio (with the label wrapped around the input
    """
    input_type = 'radio'

    def __call__(self, field, **kwargs):
        if getattr(field, 'checked', field.data):
            kwargs['checked'] = True

        html_string = super(BootstrapRadioInput, self).__call__(field, **kwargs)
        return wtf.widgets.HTMLString('<label class="radio">%s %s</label>' % (html_string.__html__(), field.label.text))

class DateField(wtf.DateField):
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
            try:
                self.data = quantum.parse_date(date_str, format=self.format)
            except ValueError:
                self.data = None
                raise ValueError(self.gettext('Not a valid date value'))

    def __call__(self, *args, **kwargs):
        kwargs['class'] = 'trex-date-field'
        if self.default_mode == 'month':
            kwargs['data-date-viewmode'] = 1
        elif self.default_mode == 'year':
            kwargs['data-date-viewmode'] = 2

        kwargs['data-date-format'] = self.js_date_format
        return super(DateField, self).__call__(*args, **kwargs)

class SelectDateWidget(object):
    def __call__(self, field, **kwargs):
        data = dict(
            widget_args = wtf.widgets.html_params(**{
                'class':'trex-select-date-widget',
            }),
            day_select_args = wtf.widgets.html_params(**{
                'id': '%s-day' % field.id,
                'name': field.name,
                'class': 'input-day',
            }),
            month_select_args = wtf.widgets.html_params(**{
                'id': '%s-month' % field.id,
                'name': field.name,
                'class': 'input-month',
            }),
            year_select_args = wtf.widgets.html_params(**{
                'id': '%s-year' % field.id,
                'name': field.name,
                'class': 'input-year',
            }),
            day_select_options = self.day_select_options(field),
            month_select_options = self.month_select_options(field),
            year_select_options = self.year_select_options(field),
        )

        return wtf.widgets.HTMLString("""
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
            result.append('<option %s>%s</option>' % (wtf.widgets.html_params(**options), str(day)))

        return '\n'.join(result)

    def month_select_options(self, field):
        result = []

        value = field._value()
        for month in range(1, 13):
            options = dict(value=str(month))
            if value and value.month == month:
                options['selected'] = True
            result.append('<option %s>%s</option>' % (wtf.widgets.html_params(**options), quantum.from_date(date(year=2013, month=month, day=1), timezone='UTC').strftime('%B')))

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
            result.append('<option %s>%s</option>' % (wtf.widgets.html_params(**options), str(year)))

        return '\n'.join(result)

class SelectDateField(wtf.Field):
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

class RadioField(wtf.RadioField):
    widget = BareListWidget()
    option_widget = BootstrapRadioInput()

class CheckListField(wtf.SelectMultipleField):
    widget = BareListWidget()
    option_widget = BootstrapCheckboxInput()

class StarRatingField(wtf.IntegerField):
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

class DependentSelectField(wtf.SelectField):
    def __init__(self, label='', validators=None, parent_field=None, select_text='-- select --', **kwargs):
        super(DependentSelectField, self).__init__(label, validators, **kwargs)
        if parent_field is None:
            raise Exception("You must specify a parent field")
        self.parent_field = parent_field
        self.select_text = select_text
        self.choice_dict = self.choices
        self.choices = []

    def pre_validate(self, form):
        parent_field = form._fields.get(self.parent_field)
        if not parent_field:
            raise Exception("Couldn't find parent field on form")

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
            raise ValueError(self.gettext('Not a valid choice'))

    def __call__(self, *args, **kwargs):
        if 'class' in kwargs:
            kwargs['class'] += ' trex-dependent-select-field'
        else:
            kwargs['class'] = 'trex-dependent-select-field'
        kwargs['data-parent'] = self.parent_field
        kwargs['data-choices'] = json.dumps(self.choice_dict)
        kwargs['data-select-text'] = self.select_text
        return super(DependentSelectField, self).__call__(*args, **kwargs)

class ChosenSelectField(wtf.SelectField):
    def __call__(self, **kwargs):
        kwargs['class'] = 'trex-chosen-select-field'
        return super(ChosenSelectField, self).__call__(**kwargs)

class FileListWidget(object):
    def __call__(self, field, **kwargs):
        data = dict(
            widget_args = wtf.widgets.html_params(**{
                'class':'trex-file-list-widget',
                'data-xhr-url': url_for('trex.upload.xhr'),
                'data-iframe-url': url_for('trex.upload.iframe'),
            }),
            input_args = wtf.widgets.html_params(**{
                'id': field.id,
                'name': field.name,
                'type': 'hidden',
                'value': kwargs.get('value', field._value()),
            }),
            file_input_name = "%s_file_input" % field.name,
        )

        return wtf.widgets.HTMLString("""
<div %(widget_args)s>
    <input %(input_args)s>
    <div class="files"></div>
    <a class="add-file btn btn-default">Add File <input name="%(file_input_name)s" type="file" multiple></a>
</div>
""" % data)

class FileListField(wtf.Field):
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

class ImageWidget(object):
    def __init__(self, width=120, height=120):
        self.width = int(width)
        self.height = int(height)

    def __call__(self, field, **kwargs):
        data = dict(
            widget_args = wtf.widgets.html_params(**{
                'class':'trex-image-widget',
                'data-xhr-url': url_for('trex.upload.xhr'),
                'data-iframe-url': url_for('trex.upload.iframe'),
            }),
            thumbnail_args = wtf.widgets.html_params(**{
                'class': 'thumbnail',
                'style': 'max-width: %dpx; max-height: %dpx' % (self.width, self.height),
                'data-width': str(self.width),
                'data-height': str(self.height),
            }),
            span_args = wtf.widgets.html_params(**{
                'style': 'width: %dpx; height: %dpx' % (self.width, self.height),
            }),
            input_args = wtf.widgets.html_params(**{
                'id': field.id,
                'name': field.name,
                'type': 'hidden',
                'value': kwargs.get('value', field._value()),
            }),
            file_input_name = "%s_file_input" % field.name,
        )

        return wtf.widgets.HTMLString("""
<div %(widget_args)s>
    <span %(thumbnail_args)s><span %(span_args)s></span></span>
    <a class="add-file btn btn-default">Upload Image <input name="%(file_input_name)s" type="file"></a>
    <button type="button" class="btn btn-default">Clear image</button>
    <span class="uploading"></span>
    <input %(input_args)s>
</div>
""" % data)

class ImageField(wtf.Field):
    widget = ImageWidget()

    def _value(self):
        if self.data:
            return ejson.dumps(self.data)
        else:
            return ''

    def process(self, *args, **kwargs):
        super(ImageField, self).process(*args, **kwargs)
        if isinstance(self.data, TrexUpload) and g.user and self.data.user != g.user:
            # Provide temporary access to the upload for this user (so they can
            # view the existing image)
            TrexUploadTemporaryAccess(upload=self.data, user=g.user).save()


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

class PhoneNumberWidget(object):
    def __call__(self, field, **kwargs):
        value = field._value()
        data = dict(
            widget_args = wtf.widgets.html_params(**{
                'class':'trex-phone-number-widget',
            }),
            cc_select_args = wtf.widgets.html_params(**{
                'id': '%s-country-code' % field.id,
                'name': field.name,
                'class': 'input-country-code',
            }),
            number_input_args = wtf.widgets.html_params(**{
                'id': '%s-number' % field.id,
                'name': field.name,
                'class': 'input-number',
                'type': 'text',
                'value': value[1],
            }),
            cc_select_options = self.cc_select_options(field)
        )

        return wtf.widgets.HTMLString("""
<div %(widget_args)s>
    <select %(cc_select_args)s>
        <option value="">Country</option>
        %(cc_select_options)s
    </select>
    <input %(number_input_args)s>
</div>
""" % data)

    def cc_select_options(self, field):
        result = []

        value = field._value()
        for code in field.country_codes:
            options = dict(value=code)
            if value and value[0] and value[0] == code:
                options['selected'] = True
            result.append('<option %s>+%s</option>' % (wtf.widgets.html_params(**options), str(code)))

        return '\n'.join(result)

class PhoneNumberField(wtf.Field):
    widget = PhoneNumberWidget()

    def __init__(self, label='', validators=None, country_codes=[], **kwargs):
        self.country_codes = country_codes

        super(PhoneNumberField, self).__init__(label, validators, **kwargs)

    def _value(self):
        if self.raw_data:
            return self.raw_data
        else:
            if self.data:
                parts = self.data.split(' ', 2)
                parts[0] = parts[0][1:]
                return parts
            else:
                return ('', '')

    def process_formdata(self, valuelist):
        if valuelist:
            try:
                self.data = self._valuelist_to_phone_number(valuelist)
            except ValueError:
                self.data = None
                raise ValueError(self.gettext('Not a valid phone number'))
            if valuelist[1]:
                if not valuelist[0] or valuelist[0] not in self.country_codes:
                    raise ValueError(self.gettext('Please select a country code'))


    def _valuelist_to_phone_number(self, valuelist):
        if len(valuelist) != 2:
            raise ValueError(self.gettext('Not a valid phone number'))
        if valuelist[0] and valuelist[1]:
            phone_str = '+%s %s' % tuple(valuelist)
            return phone_str
        return None

    def __call__(self, *args, **kwargs):
        return super(PhoneNumberField, self).__call__(*args, **kwargs)


blueprint = AuthBlueprint('trex.upload', __name__, url_prefix='/trex/upload')

@blueprint.route('/xhr', methods=['POST'], endpoint='xhr', auth=auth.login)
@render_json()
def upload_xhr():
    upload = TrexUpload(user=g.user)
    upload.file.put(
        request.data,
        content_type = request.content_type,
        filename     = request.headers.get('X-FileName'),
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

    upload.file.put(
        file.stream,
        content_type = file.content_type,
        filename     = file.filename,
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

app.register_blueprint(blueprint)
