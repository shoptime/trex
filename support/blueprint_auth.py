# coding=utf-8

from __future__ import absolute_import
from trex.flask import app
from trex.flask import AuthBlueprint, render_html
from .. import auth
from flask import g, redirect, url_for, request, session
from datetime import datetime
from flask.ext import wtf

# TODO - do we wanna import from app?
import app.model as m

@app.before_request
def check_authentication(*args, **kwargs):
    # Don't want auth for these
    if request.endpoint in ['static', 'cdn']:
        return

    # Don't want auth for routing exceptions
    if request.routing_exception:
        return

    g.user = None
    if 'user_id' in session:
        g.user = m.User.objects(id=session['user_id']).first()

blueprint = AuthBlueprint('trex.auth', __name__, url_prefix='/auth')

@blueprint.route('/login', methods=['GET', 'POST'], auth=auth.public)
@render_html('trex/auth/login.jinja2')
def login():
    return_to = request.args.get('return_to') or url_for('index.index')

    if g.user:
        return redirect(url_for('index.index'))

    class Form(wtf.Form):
        email = wtf.TextField('Email address', [wtf.Required(), wtf.Email()])
        password = wtf.PasswordField('Password', [wtf.Required()])

        def validate_email(form, field):
            user = m.User.objects(email=form.email.data).first()
            if not user or not user.check_login(form.password.data):
                raise wtf.ValidationError("Invalid email or password")

    form = Form()

    if form.validate_on_submit():
        user = m.User.objects.get(email=form.email.data)
        user.last_login = datetime.utcnow()
        user.save()
        session['user_id'] = user.id
        return redirect(return_to)

    return dict(form=form)

@blueprint.route('/logout', auth=auth.login)
def logout():
    return_to = request.args.get('return_to') or url_for('index.index')

    session.pop('user_id', None)
    return redirect(return_to)

@blueprint.route('/change-password', methods=['GET', 'POST'], auth=auth.login)
@render_html('trex/auth/change_password.jinja2')
def change_password():
    return_to = request.args.get('return_to') or url_for('index.index')

    class Form(wtf.Form):
        old_password = wtf.PasswordField('Old password', [wtf.Required()])
        new_password = wtf.PasswordField('New password', [wtf.Required(), wtf.Length(min=6)])
        confirm_password = wtf.PasswordField('Confirm password', [
            wtf.Required(),
            wtf.EqualTo('new_password', message='Passwords must match'),
        ])

        def validate_old_password(form, field):
            if not g.user.check_password(field.data):
                raise wtf.ValidationError("Invalid password")

    form = Form()

    if form.validate_on_submit():
        g.user.set_password(form.new_password.data)
        g.user.save()
        return redirect(return_to)

    return dict(form=form)

app.register_blueprint(blueprint)
