# coding=utf-8

from __future__ import absolute_import
from trex.flask import app
from trex.flask import AuthBlueprint, render_html
from .. import auth
from flask import g, redirect, url_for, request, flash, abort
from flask.ext import wtf
from .audit import audit
import app.model as m
from . import quantum, model as trex_model

@app.before_request
def check_authentication(*args, **kwargs):
    # Don't want auth for these
    if request.endpoint in ['static', 'cdn']:
        return

    # Don't want auth for routing exceptions
    if request.routing_exception:
        return

    g.identity = m.Identity.from_request(request)

    g.user = None

    if g.identity:
        g.user = g.identity.actor

    if not request.method in ['GET', 'HEAD']:
        # Check for CSRF token
        csrf_token = request.form.get('_csrf_token')
        if not csrf_token:
            csrf_token = request.headers.get('X-CSRFToken')

        if not csrf_token or csrf_token != g.identity.csrf_token:
            # Refuse submit
            flash("Please try again")
            # Reset CSRF to prevent discovery attacks
            g.identity.reset_csrf()

            # WARNING: Possible risk of using ?key=val to bypass url-based limiters on /foo/:key
            return redirect(request.url)

@app.after_request
def after_request(response):
    if hasattr(g, 'identity'):
        g.identity.set_cookie(response)
    return response

blueprint = AuthBlueprint('trex.auth', __name__, url_prefix='/auth')

@blueprint.route('/login', methods=['GET', 'POST'], auth=auth.public)
@render_html('trex/auth/login.jinja2')
def login():
    return_to = request.args.get('return_to')

    if g.user:
        return redirect(g.user.default_after_login_url())

    class Form(wtf.Form):
        email = wtf.TextField('Email address', [wtf.Required(), wtf.Email()])
        password = wtf.PasswordField('Password', [wtf.Required()])

        def validate_email(form, field):
            user = m.User.active(email=form.email.data).first()
            if not user or not user.check_login(form.password.data):
                raise wtf.ValidationError("Invalid email or password")

    form = Form()

    if form.validate_on_submit():
        user = m.User.active.get(email=form.email.data)
        user.last_login = quantum.now()
        user.save()

        # Credentials change
        g.identity.login(user)

        audit('User logged in: %s' % user.display_name, ['Authentication'], user=user)
        if return_to:
            return redirect(return_to)
        return redirect(user.default_after_login_url())

    return dict(form=form)

@blueprint.route('/login-as/<user_token>', methods=['POST'], auth=auth.has_flag('trex.user_management_login_as'))
def login_as(user_token):
    return_to = request.args.get('return_to')

    try:
        user = m.User.active.get(token=user_token)
    except m.DoesNotExist:
        abort(404)

    g.identity.su(user)

    flash("Logged in as %s" % user.display_name)
    audit('Logged in as: %s' % user.display_name, ['Authentication', 'User Management'], documents=[user])

    if return_to:
        return redirect(return_to)
    return redirect(user.default_after_login_url())

@blueprint.route('/logout', auth=auth.login)
def logout():
    if g.identity.real and g.identity.actor != g.identity.real:
        g.identity.unsu()
        return_to = request.args.get('return_to') or url_for('trex.user_management.index')
        audit('User ended log-in-as: %s' % g.user.display_name, ['Authentication', 'User Management'], user=g.identity.real, documents=[g.user])
    else:
        g.identity.logout()
        audit('User logged out in: %s' % g.user.display_name, ['Authentication'])
        return_to = request.args.get('return_to') or g.user.default_after_logout_url()

    return redirect(return_to)

@blueprint.route('/change-password', methods=['GET', 'POST'], auth=auth.login)
@render_html('trex/auth/change_password.jinja2')
def change_password():
    return_to = request.args.get('return_to') or g.user.default_after_change_password_url()

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
        g.identity.changed_credentials()
        audit('User changed password: %s' % g.user.display_name, ['Authentication'])
        return redirect(return_to)

    return dict(form=form)

@blueprint.route('/lost-password', methods=['GET', 'POST'], auth=auth.public)
@render_html('trex/auth/lost_password.jinja2')
def lost_password():
    class Form(wtf.Form):
        email = wtf.TextField('Email address', [wtf.Required(), wtf.Email()])

    form = Form()

    if form.validate_on_submit():
        user = m.User.active(email=form.email.data.lower()).first()
        if user:
            ar = trex_model.UserAccountRecovery(user=user)
            ar.save()
            ar.send_recovery_email()
            audit('User requested password reset: %s' % form.email.data, ['Authentication'], [ar])
        return redirect(url_for('.lost_password_sent'))

    return dict(form=form)

@blueprint.route('/lost-password-sent', methods=['GET', 'POST'], auth=auth.public)
@render_html('trex/auth/lost_password_sent.jinja2')
def lost_password_sent():
    class Form(wtf.Form):
        code = wtf.TextField('Recovery code', [wtf.Required()])

    form = Form()

    if form.validate_on_submit():
        return redirect(url_for('.recover_password', code=form.code.data))

    return dict(form=form)

@blueprint.route('/recover-password/<code>', methods=['GET', 'POST'], auth=auth.public)
@render_html('trex/auth/recover_password.jinja2')
def recover_password(code):
    valid_after = quantum.now('UTC').subtract(hours=1)
    try:
        ar = trex_model.UserAccountRecovery.objects.get(code=code, created__gte=valid_after)
    except m.DoesNotExist:
        flash("Unrecognised or unacceptable code. It may have timed out. Please check your code, or reset your account again", category="error")
        return redirect(url_for('.lost_password_sent'))

    class Form(wtf.Form):
        new_password = wtf.PasswordField('New password', [wtf.Required(), wtf.Length(min=6)])
        confirm_password = wtf.PasswordField('Confirm password', [
            wtf.Required(),
            wtf.EqualTo('new_password', message='Passwords must match'),
        ])

    form = Form()

    if form.validate_on_submit():
        ar.user.set_password(form.new_password.data)
        ar.user.save()
        audit('User reset password: %s' % ar.user.display_name, ['Authentication'], [ar.user, ar], user=ar.user)
        g.identity.login(ar.user)
        g.identity.changed_credentials()
        flash("Your password has been successfully reset")
        return redirect(url_for('index.index'))

    return dict(form=form)

app.register_blueprint(blueprint)
