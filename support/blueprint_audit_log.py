# coding=utf-8


from trex.flask import app
from trex.flask import AuthBlueprint, render_html
from .. import auth
from flask import request
import app.model as m
from .pager import Pager

blueprint = AuthBlueprint('trex_audit_log', __name__, url_prefix='/admin/audit')

@blueprint.route('/', auth=auth.has_flag('trex.audit_log'))
@blueprint.route('/utc', endpoint="utc", auth=auth.has_flag('trex.audit_log'))
@render_html('trex/audit_log/index.jinja2')
def index():
    pager = Pager(
        m.Audit.objects.count(),
        page     = int(request.args.get('page', 1)),
        base_uri = request.url,
        per_page = 30,
    )

    return dict(
        utc     = request.endpoint == 'trex_audit_log.utc',
        pager   = pager,
        entries = m.Audit.objects.skip(pager.skip()).limit(pager.limit())
    )

app.register_blueprint(blueprint)
