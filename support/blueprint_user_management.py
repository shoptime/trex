# coding=utf-8

from __future__ import absolute_import
from trex.flask import app
from trex.flask import AuthBlueprint, render_html
from .. import auth
from flask import abort, redirect, url_for, g
from flask.ext import wtf
from trex.support import token, wtf as twtf
from .audit import audit
import app.model as m

blueprint = AuthBlueprint('trex.user_management', __name__, url_prefix='/admin/users')

@blueprint.route('/', auth=auth.has_flag('trex.user_management'))
@render_html('trex/user_management/index.jinja2')
def index():
    return dict(
        add_url = m.User.url_for_add_user(),
        users   = m.User.active(),
    )

@blueprint.route('/add', methods=['GET', 'POST'], endpoint='add', auth=auth.has_flag('trex.user_management'))
@blueprint.route('/<user_token>/edit', methods=['GET', 'POST'], auth=auth.has_flag('trex.user_management'))
@render_html('trex/user_management/edit.jinja2')
def edit(user_token=None):
    if user_token:
        try:
            user = m.User.active.get(token=user_token)
        except m.DoesNotExist:
            abort(404)
    else:
        user = m.User()

    if not g.user.has_role(user.role):
        return abort(404)

    role_choices = [ (x[0], x[1]['label']) for x in sorted(m.User.roles().items(), key=lambda x: x[1]['level']) if g.user.has_role(x[0]) ]

    class Form(wtf.Form):
        display_name = wtf.TextField('Display name', [wtf.Required()])
        email        = wtf.TextField('Email address', [wtf.Required(), wtf.Email()])
        role         = wtf.SelectField('Role', [wtf.Required()], choices=role_choices)
        country      = wtf.SelectField('Country', [wtf.Required()], choices=twtf.country_choices())
        timezone     = twtf.DependentSelectField(
            'Time Zone',
            [wtf.Required()],
            parent_field = 'country',
            select_text = '',
            choices = twtf.timezone_dependent_choices(),
        )

        def validate_email(form, field):
            existing = m.User.objects(email=field.data).first()
            if existing and existing.token != user.token:
                raise wtf.ValidationError("This email address is already used")

    form = Form(obj=user)

    if form.validate_on_submit():
        user.display_name = form.display_name.data
        user.email        = form.email.data
        user.role         = form.role.data
        user.country      = form.country.data
        user.timezone     = form.timezone.data
        user.save()
        if user_token:
            audit("Updated user %s" % user.display_name, ['User Management'], [user])
        else:
            audit("Added user %s" % user.display_name, ['User Management'], [user])
        return redirect(url_for('.index'))

    return dict(form=form, add=user_token is None)

@blueprint.route('/<user_token>/deactivate', methods=['POST'], auth=auth.has_flag('trex.user_management'))
def deactivate(user_token):
    try:
        user = m.User.active.get(token=user_token)
    except m.DoesNotExist:
        abort(404)

    if not g.user.has_role(user.role):
        return abort(404)

    user.is_active = False
    user.password = None
    user.save()
    m.Identity.destroy_sessions_for_user(user)
    audit("Deactivated user %s" % user.display_name, ['User Management'], [user])

    return redirect(url_for('.index'))

@blueprint.route('/<user_token>/reset-password', methods=['POST'], auth=auth.has_flag('trex.user_management'))
def reset_password(user_token):
    try:
        user = m.User.active.get(token=user_token)
    except m.DoesNotExist:
        abort(404)

    if not g.user.has_role(user.role):
        return abort(404)

    new_password = token.create_token(length=8)

    user.set_password(new_password)
    user.save()
    audit("Reset user password %s" % user.display_name, ['User Management'], [user])
    user.notify_password_reset(new_password)

    return redirect(url_for('.index'))

app.register_blueprint(blueprint)
