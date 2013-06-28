from __future__ import absolute_import

from decorator import decorator
import flask
from flask.ext.seasurf import SeaSurf
import os.path
from ConfigParser import ConfigParser
import md5
import warnings
import pymongo
import mongoengine
import logging
from werkzeug.datastructures import OrderedMultiDict
from .support import ejson
from .support import parser
from .cdn import FlaskCDN
from furl import furl
import sys
import copy
import re
import traceback
from jinja2.exceptions import TemplateNotFound
import trex.support.model
import trex.support.format

app = None

# This exists so some of the support code can easily access the running
# application for settings etc
def register_app(app_to_register):
    global app
    app = app_to_register

def render_html(template=None, add_etag=False):
    def decorated(f, *args, **kwargs):
        response = f(*args, **kwargs)

        if type(response) != dict:
            return response

        response.update(getattr(flask.g, 'stash', {}))

        template_name = template
        if template_name is None:
            template_name = "%s/%s.jinja2" % (f.__module__.split('.', 3)[2], response.get('_template', f.__name__))

        response['app'] = app

        if flask.request.blueprint:
            response['html_classes'] = [ 'blueprint-%s' % x for x in [ flask.request.blueprint ] ]
        if flask.request.endpoint:
            response['html_id'] = 'endpoint-%s' % flask.request.endpoint.replace('.', '-')

        try:
            out = flask.render_template(template_name, **response)
        except TemplateNotFound:
            if response.get('_wiki'):
                return flask.abort(404)
            raise

        status  = response.get('_status', 200)
        headers = response.get('_headers', {})

        if add_etag:
            etag = md5.new(out.encode('utf-8')).hexdigest()
            if 'If-None-Match' in flask.request.headers and flask.request.headers['If-None-Match'] == etag:
                return app.response_class('', 304)
            headers['ETag'] = etag

        return (out, status, headers)

    return decorator(decorated)


def render_json():
    def decorated(f, *args, **kwargs):
        response = f(*args, **kwargs)

        if type(response) != dict and not isinstance(response, mongoengine.queryset.QuerySet) and not isinstance(response, mongoengine.Document) and type(response) != list:
            return response

        http_response = flask.Response(ejson.dumps(response), 200)
        http_response.content_type = 'application/json'
        return http_response
    return decorator(decorated)

class DinoRequest(flask.Request):
    parameter_storage_class = OrderedMultiDict

class Flask(flask.Flask):
    settings = ConfigParser()
    db = None
    in_test_mode = False

    def assert_valid_config(self):
        for section in ['app', 'server', 'mongo']:
            assert self.settings.has_section(section), "Section [%s] doesn't exist in config" % section
        for option in ['host', 'port', 'debug', 'url', 'enable_csrf']:
            assert option in self.settings.options('server'), "Option %s exists in [server] section" % option

        assert 'url' in self.settings.options('mongo'), "Option 'url' exists in [mongo] section"
        mongo_url = furl(self.settings.get('mongo', 'url'))
        assert mongo_url.scheme == 'mongodb', "mongo.url is a valid mongodb:// url: %s" % mongo_url
        assert len(mongo_url.path.segments) == 1, "mongo.url %s has a database set" % mongo_url
        assert mongo_url.path.segments[0] != '', "mongo.url %s has a database set" % mongo_url

        assert 'name' in self.settings.options('app'), "Option 'name' exists in [app] section"


    def switch_to_test_mode(self):
        mongo_url = furl(self.settings.get('mongo', 'url'))
        mongo_url.path.segments[0] = "test_%s" % mongo_url.path.segments[0]
        self.settings.set('mongo', 'url', str(mongo_url))

        if 'server_port' in self.settings.options('test'):
            self.settings.set('server', 'port', self.settings.get('test', 'server_port'))

        if 'server_url' in self.settings.options('test'):
            self.settings.set('server', 'url', self.settings.get('test', 'server_url'))

        self.in_test_mode = True

        self.init_application()

    def switch_to_wsgi_mode(self):
        log_filename = os.path.abspath(os.path.join(self.root_path, '..', 'logs', 'application.log'))
        file_handler = logging.FileHandler(log_filename)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'
        ))
        self.logger.addHandler(file_handler)

    def __init__(self, *args, **kwargs):
        super(Flask, self).__init__(*args, **kwargs)

        self.request_class = DinoRequest
        # Add trex/templates to the jinja2 search path
        self.jinja_loader.searchpath.append(os.path.join(os.path.dirname(__file__), 'templates'))

        self.settings.read([
            os.path.join(self.root_path, '..', 'trex', 'base.ini'),
            os.path.join(self.root_path, 'default.ini'),
            os.path.join(self.root_path, 'local.ini'),
        ])

        self.assert_valid_config()

        self.select_jinja_autoescape = True

        self.jinja_env.filters['tojson'] = lambda o: ejson.dumps(o)
        self.jinja_env.filters['moment_stamp'] = lambda dt: dt.isoformat()+'Z'
        self.jinja_env.filters['textarea2html'] = lambda text: parser.textarea2html(text)
        self.jinja_env.filters['english_join'] = lambda items: ', '.join(items[0:-1]) + ' and ' + items[-1]

        def oxford_join(items):
            if len(items) == 1:
                return items[0]
            if len(items) == 2:
                return ' and '.join(items)
            return ', '.join(items[0:-1]) + ', and ' + items[-1]

        self.jinja_env.filters['oxford_join'] = oxford_join

        self.jinja_env.globals['hostname'] = os.uname()[1]

        self.jinja_env.globals['format'] = trex.support.format

        def csrf_token():
            if flask.g.identity:
                return flask.g.identity.csrf_token
            return ''

        self.jinja_env.globals['csrf_token'] = csrf_token

        FlaskExceptionReporter(self)

        FlaskCDN(self)

        trex.support.model.settings = self.settings

        self.init_application()

    def init_application(self):
        self.debug = self.settings.getboolean('server', 'debug')
        self.logger.setLevel(logging.DEBUG)

        if self.settings.get('server', 'url').startswith('https:'):
            self.logger.info("Detected SSL service URL, enabling secure cookies")
            self.config['SESSION_COOKIE_SECURE'] = True
            self.config['PREFERRED_URL_SCHEME'] = 'https'

        mongo_url = furl(self.settings.get('mongo', 'url'))
        mongo_db = mongo_url.path.segments[0]

        if 'username' in self.settings.options('mongo') and 'password' in self.settings.options('mongo'):
            mongo_url.username = self.settings.get('mongo', 'username')
            mongo_url.password = self.settings.get('mongo', 'password')

        # This warning catcher is here because pymongo emits a UserWarning if
        # you don't specify a username/password (even if you don't want to use
        # authentication).
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning)
            self.db = pymongo.Connection(str(mongo_url))[mongo_db]

        mongoengine.register_connection('default', mongo_db, host=str(mongo_url))

        config = self.db.config.find_one()
        if config is None:
            config = {
                'secret_key': os.urandom(20).encode('hex')
            }
            self.db.config.insert(config)

        self.secret_key = config['secret_key'].encode('ascii')

        register_app(self)

    def run(self, host=None, port=None, debug=None, **options):
        if host is None:
            host = self.settings.get('server', 'host')

        if port is None:
            port = int(self.settings.get('server', 'port'))

        if debug is None:
            debug = self.settings.getboolean('server', 'debug')

        if options.get('threaded', None) is None:
            options['threaded'] = True

        if options.get('extra_files', None) is None:
            options['extra_files'] = []

        options['extra_files'].append(os.path.join(self.root_path, 'default.ini'))
        options['extra_files'].append(os.path.join(self.root_path, 'local.ini'))

        super(Flask, self).run(host, port, debug, **options)

    def wsgi_app(self, environ, start_response):
        if self.config.get('PREFERRED_URL_SCHEME'):
            environ['wsgi.url_scheme'] = self.config['PREFERRED_URL_SCHEME']

        return super(Flask, self).wsgi_app(environ, start_response)

    def shutdown(self):
        # This funky cleanup code is necessary to ensure that we nicely kill off any
        # mongo replicaset connection monitoring threads
        db = mongoengine.connection.get_connection('default')
        if db:
            db.close()

#
# Exception handling
#

def _exception_handler(app, exception):

    exc_type, exc_value, tb = sys.exc_info()

    exc_type_name = exc_type.__name__
    if exc_type.__module__ not in ('__builtin__', 'exceptions'):
        exc_type_name = "%s.%s" % (exc_type.__module__, exc_type_name)

    env_data = copy.copy(flask.request.environ)

    for key in env_data.keys():
        if not re.search(r'^[A-Z_]+$', key):
            del env_data[key]

    data = {
        'url': flask.request.url,
        'type': exc_type_name,
        'value': str(exc_value),
        'traceback': traceback.extract_tb(tb),
        'environ': env_data,
    }

    from trex.support import notify
    try:
        last_frame = data['traceback'][-1]
        file = last_frame[0]
        line = last_frame[1]
        notify.error('instantpredict.com', data['type'], '%s at %s:%s' % (data['value'], file, line))
    except:
        notify.error('instantpredict.com', data['type'], '%s (no file/line info available)' % data['value'])


class FlaskExceptionReporter(object):
    def __init__(self, app=None):
        flask.got_request_exception.connect(_exception_handler)


"""Extends flask.Blueprint to add in declarative authentication handling for endpoints.

Instead of doing auth checking in an endpoint or a before_request handler,
you declare your auth intentions like so:

    @blueprint.route('/open/<chat_id>', methods=["POST"], auth=auth.chat_owner)
    def open(chat):

The auth functions can abort(), redirect() or otherwise return a response
that terminates the request. They can also return an instance of new_args,
to rewrite chat arguments - for example, to turn chat_id into an actual
chat object in the example above."""
class AuthBlueprint(flask.Blueprint):
    def add_url_rule(self, rule, endpoint, view_func, **options):
        if 'auth' not in options:
            raise Exception("No authentication handler supplied for %s.%s" % (self.name, endpoint))

        authfunc = options['auth']

        if hasattr(view_func, '__authblueprint_authfunc__'):
            existing_authfunc = view_func.__authblueprint_authfunc__
            existing_endpoint = view_func.__authblueprint_endpoint__
            if existing_authfunc != authfunc and existing_endpoint == endpoint:
                raise Exception("Can't use different auth methods (%s and %s) for the same endpoint: %s.%s" % (
                    existing_authfunc,
                    authfunc,
                    self.name,
                    endpoint,
                ))

        if hasattr(view_func, '__authblueprint_unwrapped__'):
            view_func = view_func.__authblueprint_unwrapped__

        def view_func_authed(**kwargs):
            response = authfunc(**kwargs)
            if isinstance(response, new_args):
                # Auth OK; authfunc rewrote some arguments
                return view_func(**response)
            elif response:
                # Auth not ok (returned some kind of response, e.g. 404/403 or redirect)
                return response
            else:
                # Auth OK; no args rewritten so just pass 'em through
                return view_func(**kwargs)

        setattr(view_func_authed, '__authblueprint_unwrapped__', view_func)
        setattr(view_func_authed, '__authblueprint_authfunc__', authfunc)
        setattr(view_func_authed, '__authblueprint_endpoint__', endpoint)
        del options['auth']
        view_func_authed.__name__ = view_func.__name__

        super(AuthBlueprint, self).add_url_rule(rule, endpoint, view_func_authed, **options)

        return view_func_authed

    def route(self, rule, **options):
        """Overrides route() to allow the auth wrapper function created in
        add_url_rule to be returned from the route decorator.

        In particular, this means that SeaSurf knows which view functions are
        exempted from CSRF checking."""
        def decorator(f):
            endpoint = options.pop("endpoint", f.__name__)
            return self.add_url_rule(rule, endpoint, f, **options)
        return decorator

class new_args(dict):
    pass
