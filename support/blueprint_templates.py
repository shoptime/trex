# coding=utf-8


from ..flask import AuthBlueprint, render_html, app
from flask import render_template, abort, request
from .. import auth
from jinja2.exceptions import TemplateNotFound
import json
import hashlib

blueprint = AuthBlueprint('trex_templates', __name__, url_prefix='/trex/templates')

@blueprint.route('/<path:template>', methods=['GET', 'POST'], auth=auth.public)
@render_html()
def template(template):
    try:
        out = "Trex.Templates[%s] = %s;" % (
            json.dumps(template),
            json.dumps(render_template("trex/templates/%s.jinja2" % template))
        )
    except TemplateNotFound:
        abort(404)

    etag = hashlib.md5(out).hexdigest()

    if 'If-None-Match' in request.headers and request.headers['If-None-Match'] == etag:
        return app.response_class('', 304)

    response = app.response_class(out, 200)
    response.headers['Content-Type'] = 'text/javascript'
    response.headers['ETag'] = etag

    return response


app.register_blueprint(blueprint)
