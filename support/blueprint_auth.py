# coding=utf-8

from __future__ import absolute_import
from trex.flask import app
from trex.flask import AuthBlueprint, render_html, flash
from .. import auth
from flask import g, redirect, url_for, request, abort
from trex.support import wtf
from .audit import audit
import app.model as m
from . import quantum, model as trex_model
from furl import furl

@app.before_request
def check_authentication(*args, **kwargs):
    g.is_cors_request = False

    # Don't want auth for these
    if request.endpoint in ['static', 'cdn']:
        return

    # Don't want auth for routing exceptions
    if request.routing_exception:
        return

    view_func = app.view_functions.get(request.endpoint, None)

    # Deal with allowing CORS requests. This is implemented such that each
    # request falls in to one of two categories:
    # 1. It's a regular request from a browser on the same domain. These
    #    requests continue untouched and have no additional response headers
    #    set.
    # 2. It's a CORS request (i.e. a request from a different domain). These
    #    requests have all request cookies stripped (to prevent accidently
    #    granting access where it shouldn't be) and the appropriate response
    #    headers returned.
    # The decision on which of the 2 cases any given request should use is
    # decided by comparing the Origin request header with the server.url
    # configuration option.
    if view_func and getattr(view_func, 'allow_cors', False):
        if request.method == 'OPTIONS' and 'Access-Control-Request-Method' in request.headers:
            return app.response_class('', status=200, headers={
                'Allow': ', '.join(request.url_rule.methods),
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': request.headers.get('Access-Control-Request-Headers'),
            })
        elif request.method in request.url_rule.methods and 'Origin' in request.headers:
            origin = furl(request.headers['Origin'])
            server = furl(app.settings.get('server', 'url'))
            origin.path = origin.query = origin.fragment = ''
            server.path = server.query = server.fragment = ''
            if str(origin) != str(server):
                # Before allowing CORS, we nuke all incoming cookies (of which
                # there shouldn't be any anyway)
                request.cookies = {}

                g.is_cors_request = True

    g.identity = m.Identity.from_request(request)

    g.user = None

    if g.identity:
        g.user = g.identity.actor

    if not request.method in ['GET', 'HEAD', 'OPTIONS'] and not getattr(view_func, 'csrf_exempt', False):
        # Check for CSRF token
        csrf_token = request.form.get('_csrf_token')
        if not csrf_token:
            csrf_token = request.headers.get('X-CSRFToken')

        if not g.identity.check_csrf(csrf_token):
            # Refuse submit
            flash("Please try again")
            # Reset CSRF to prevent discovery attacks
            g.identity.reset_csrf()

            # WARNING: Possible risk of using ?key=val to bypass url-based limiters on /foo/:key
            return redirect(request.url)

@app.after_request
def after_request(response):
    if g.is_cors_request:
        response.headers['Access-Control-Allow-Origin'] = '*'
    elif hasattr(g, 'identity'):
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
        email = wtf.TextField(
            'Email address',
            [wtf.validators.Required(), wtf.validators.Email()],
            filters = [lambda x: x and x.strip()],
        )
        password = wtf.PasswordField('Password', [wtf.validators.Required()])

        def validate_email(form, field):
            user = m.User.objects(email=form.email.data).first()

            if not user:
                raise wtf.ValidationError("Invalid email or password")

            if not user.is_active:
                if app.settings.getboolean('security', 'reveal_disabled_accounts'):
                    raise wtf.ValidationError("Your account has been disabled. If you think this is a mistake, please contact your manager.")
                # Vague message if we aren't revealing that the account is disabled
                raise wtf.ValidationError("Invalid email or password")


            try:
                user.check_login(form.password.data)
            except trex_model.InvalidLoginException as e:
                raise wtf.ValidationError(e.message)

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
        audit('User logged out: %s' % g.user.display_name, ['Authentication'])
        return_to = request.args.get('return_to') or g.user.default_after_logout_url()

    return redirect(return_to)

@blueprint.route('/change-password', methods=['GET', 'POST'], auth=auth.login)
@render_html('trex/auth/change_password.jinja2')
def change_password():
    return_to = request.args.get('return_to') or g.user.default_after_change_password_url()

    class Form(wtf.Form):
        old_password = wtf.PasswordField('Old password', [wtf.validators.Required()])
        new_password = wtf.PasswordField('New password', [wtf.validators.Required(), wtf.validators.Length(min=6)])
        confirm_password = wtf.PasswordField('Confirm password', [
            wtf.validators.Required(),
            wtf.validators.EqualTo('new_password', message='Passwords must match'),
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
        flash("Password successfully changed")
        return redirect(return_to)

    return dict(form=form)

@blueprint.route('/lost-password', methods=['GET', 'POST'], auth=auth.public)
@render_html('trex/auth/lost_password.jinja2')
def lost_password():
    class Form(wtf.Form):
        email = wtf.TextField('Email address', [wtf.validators.Required(), wtf.validators.Email()])

        def validate_email(form, field):
            if len(field.errors):
                # We don't need to check for account if the field is already invalid
                return
            try:
                m.User.active.get(email=field.data.lower())
            except m.DoesNotExist:
                raise wtf.ValidationError("No account for that email address exists")

    if not app.settings.getboolean('trex', 'notify_user_of_invalid_email_on_recovery_attempt'):
        delattr(Form, 'validate_email')

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
        code = wtf.TextField('Recovery code', [wtf.validators.Required()])

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
        new_password = wtf.PasswordField('New password', [wtf.validators.Required(), wtf.validators.Length(min=6)])
        confirm_password = wtf.PasswordField('Confirm password', [
            wtf.validators.Required(),
            wtf.validators.EqualTo('new_password', message='Passwords must match'),
        ])

    form = Form()

    if form.validate_on_submit():
        ar.user.set_password(form.new_password.data)
        ar.user.save()
        audit('User reset password: %s' % ar.user.display_name, ['Authentication'], [ar.user, ar], user=ar.user)
        g.identity.login(ar.user)
        g.identity.changed_credentials()
        flash("Your password has been successfully reset")
        return redirect(ar.user.default_after_login_url())

    return dict(form=form)

app.register_blueprint(blueprint)
