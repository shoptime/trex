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

blueprint = AuthBlueprint('trex.audit_log', __name__, url_prefix='/admin/audit')

@blueprint.route('/', auth=auth.has_flag('trex.audit_log'))
@render_html('trex/audit_log/index.jinja2')
def index():
    return dict(entries=m.Audit.objects)

app.register_blueprint(blueprint)
