# coding=utf-8

from __future__ import absolute_import
from trex.flask import app
from trex.flask import AuthBlueprint, render_html
from .. import auth
from flask import abort, redirect, url_for
from flask.ext import wtf
from trex.support import token
from .audit import audit
import app.model as m

blueprint = AuthBlueprint('trex.user_management', __name__, url_prefix='/admin/users')

@blueprint.route('/', auth=auth.has_flag('trex.user_management'))
@render_html('trex/user_management/index.jinja2')
def index():
    return dict(
        users=m.User.objects(),
    )

@blueprint.route('/add', methods=['GET', 'POST'], auth=auth.has_flag('trex.user_management'))
@blueprint.route('/<user_id>/edit', methods=['GET', 'POST'], auth=auth.has_flag('trex.user_management'))
@render_html('trex/user_management/edit.jinja2')
def edit(user_id=None):
    if user_id:
        try:
            user = m.User.objects.get(id=user_id)
        except m.DoesNotExist:
            abort(404)
    else:
        user = m.User()

    role_choices = [ (x[0], x[1]['label']) for x in sorted(m.User.roles().items(), key=lambda x: x[1]['level']) ]

    class Form(wtf.Form):
        display_name = wtf.TextField('Display name', [wtf.Required()])
        email        = wtf.TextField('Email address', [wtf.Required(), wtf.Email()])
        role         = wtf.SelectField('Role', [wtf.Required()], choices=role_choices)

    form = Form(obj=user)

    if form.validate_on_submit():
        user.display_name = form.display_name.data
        user.email = form.email.data
        user.role = form.role.data
        user.save()
        if user_id:
            audit("Updated user %s" % user.display_name, ['User Management'], [user])
        else:
            audit("Added user %s" % user.display_name, ['User Management'], [user])
        return redirect(url_for('.index'))

    return dict(form=form)

@blueprint.route('/<user_id>/delete', methods=['POST'], auth=auth.has_flag('trex.user_management'))
def delete(user_id):
    try:
        user = m.User.objects.get(id=user_id)
    except m.DoesNotExist:
        abort(404)

    user.delete()
    audit("Deleted user %s" % user.display_name, ['User Management'])

    return redirect(url_for('.index'))

@blueprint.route('/<user_id>/reset-password', methods=['POST'], auth=auth.has_flag('trex.user_management'))
def reset_password(user_id):
    try:
        user = m.User.objects.get(id=user_id)
    except m.DoesNotExist:
        abort(404)

    new_password = token.create_token(length=8)

    user.set_password(new_password)
    user.save()
    audit("Reset user password %s" % user.display_name, ['User Management'], [user])
    user.notify_password_reset(new_password)

    return redirect(url_for('.index'))

app.register_blueprint(blueprint)
