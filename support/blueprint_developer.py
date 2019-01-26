# coding=utf-8


from trex.flask import app
from trex.flask import AuthBlueprint, render_html
from .. import auth
from . import mail
from collections import OrderedDict

blueprint = AuthBlueprint('trex.developer', __name__, url_prefix='/__developer__')

@blueprint.route('/email', auth=auth.has_flag('trex.developer'))
@render_html('trex/developer/email.jinja2')
def email():
    templates = []

    for name in mail.all_template_names():
        try:
            template = mail.get_template(name).create_sample()
            templates.append((name, dict(
                subject     = template.subject(),
                description = template.__class__.__doc__,
            )))
        except Exception as e:
            templates.append((name, dict(
                error     = str(e),
            )))

    return dict(
        templates = OrderedDict(sorted(templates)),
    )

@blueprint.route('/email/<template>', auth=auth.has_flag('trex.developer'))
@render_html('trex/developer/email_template.jinja2')
def email_template(template):
    return dict(
        template = template,
        email    = mail.get_template(template).create_sample()
    )

@blueprint.route('/email/<template>/<fmt>', auth=auth.has_flag('trex.developer'))
def email_sample(template, fmt):
    if fmt not in ['text', 'html']:
        raise Exception("Invalid format: %s" % fmt)

    email = mail.get_template(template).create_sample()

    if fmt == 'html':
        return app.response_class(
            email.html_body(),
            200,
            {
                'Content-Type': 'text/html',
            },
        )
    else:
        return app.response_class(
            email.text_body(),
            200,
            {
                'Content-Type': 'text/plain',
            },
        )

app.register_blueprint(blueprint)
