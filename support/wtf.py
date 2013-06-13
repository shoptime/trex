# coding=utf-8

from __future__ import absolute_import
from flask.ext import wtf
import mongoengine
from flask import url_for, abort, request, g
from ..flask import AuthBlueprint, render_json
from app.support import auth
from app import app
from datetime import datetime
from . import token, ejson
import json

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


class RadioField(wtf.RadioField):
    widget = BareListWidget()
    option_widget = BootstrapRadioInput()

class CheckListField(wtf.SelectMultipleField):
    widget = BareListWidget()
    option_widget = BootstrapCheckboxInput()

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
        kwargs['class'] = 'trex-dependent-select-field'
        kwargs['data-parent'] = self.parent_field
        kwargs['data-choices'] = json.dumps(self.choice_dict)
        kwargs['data-select-text'] = self.select_text
        return super(DependentSelectField, self).__call__(*args, **kwargs)

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
        )

        return wtf.widgets.HTMLString("""
<div %(widget_args)s>
    <input %(input_args)s>
    <div class="files"></div>
    <a class="add-file btn">Add File <input name="file" type="file" multiple></a>
</div>
""" % data)

class Upload(mongoengine.Document):
    meta = dict(
        collection = 'trex.upload',
        indexes    = [('token',)],
    )
    user    = mongoengine.ReferenceField('User', required=True)
    file    = mongoengine.FileField(required=True, collection_name='trex.upload')
    data    = mongoengine.DictField()
    created = mongoengine.DateTimeField(required=True, default=datetime.utcnow)
    token   = mongoengine.StringField(required=True, default=token.create_url_token)

    def delete(self):
        self.file.delete()
        super(Upload, self).delete()

    def to_ejson(self):
        return dict(
            oid      = self.id,
            filename = self.file.filename,
            size     = self.file.length,
            mime     = self.file.content_type,
            url      = url_for('trex.upload.view', token=self.token)
        )

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
                upload = Upload.objects(user=g.user, id=upload_data['oid']).first()
                if upload:
                    self.data.append(upload)
        else:
            self.data = []


blueprint = AuthBlueprint('trex.upload', __name__, url_prefix='/trex/upload')

@blueprint.route('/xhr', methods=['POST'], endpoint='xhr', auth=auth.login)
@render_json()
def upload_xhr():
    upload = Upload(user=g.user)
    upload.file.put(
        request.data,
        content_type = request.content_type,
        filename     = request.headers.get('X-FileName'),
    )
    upload.save()

    return dict(
        url = url_for('trex.upload.view', token=upload.token),
        oid = str(upload.id),
    )

@blueprint.route('/iframe', methods=['POST'], endpoint='iframe', auth=auth.login)
def upload_iframe():
    return

@blueprint.route('/view/<token>', methods=['GET'], endpoint='view', auth=auth.login)
def upload_view(token):
    try:
        upload = Upload.objects.get(user=g.user, token=token)
    except mongoengine.DoesNotExist:
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
