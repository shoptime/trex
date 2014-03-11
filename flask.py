from __future__ import absolute_import

from decorator import decorator
import flask
import os.path
from ConfigParser import ConfigParser, NoOptionError
import codecs
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
from .support.configparser import TrexConfigParser
import base64
import hashlib
import random
import urllib
import csv
import StringIO
import inspect

app = None

# This exists so some of the support code can easily access the running
# application for settings etc
def register_app(app_to_register):
    global app
    app = app_to_register

def flash(message, category=None):
    if not hasattr(flask.g, 'identity'):
        raise Exception("No identity exists")
    flask.g.identity.flash(message, category)

def render_html(template=None, add_etag=False, stream=False):
    def decorated(f, *args, **kwargs):
        response = f(*args, **kwargs)

        if type(response) != dict:
            return response

        response.update(getattr(flask.g, 'stash', {}))

        template_name = template
        if template_name is None:
            template_name = "%s/%s.jinja2" % (f.__module__.split('.', 3)[2], response.get('_template', f.__name__))

        response['app'] = app
        response['trex_bootstrap_version'] = app.settings.getint('trex', 'bootstrap_version')

        if flask.request.blueprint:
            response['html_classes'] = [ 'blueprint-%s' % x for x in [ flask.request.blueprint.replace('.', '-') ] ]
        if flask.request.endpoint:
            response['html_id'] = 'endpoint-%s' % flask.request.endpoint.replace('.', '-')

        try:
            if stream:
                app.update_template_context(response)
                t = app.jinja_env.get_template(template_name)
                ts = t.stream(response)
                ts.enable_buffering(5)
                out = flask.Response(flask.stream_with_context(ts))
            else:
                out = flask.render_template(template_name, **response)
        except TemplateNotFound:
            if response.get('_wiki'):
                return flask.abort(404)
            raise

        status  = response.get('_status', 200)
        headers = response.get('_headers', {})

        default_headers = {
            'Cache-Control': 'private, no-cache, no-store, must-revalidate',
            'Expires': 'Sat, 01 Jan 2000 00:00:00 GMT',
            'Pragma': 'no-cache',
        }
        headers = dict(default_headers.items() + headers.items())

        if add_etag:
            etag = md5.new(out.encode('utf-8')).hexdigest()
            if 'If-None-Match' in flask.request.headers and flask.request.headers['If-None-Match'] == etag:
                return app.response_class('', 304)
            headers['ETag'] = etag

        return (out, status, headers)

    return decorator(decorated)

def render_modal_form(template=None):
    def decorated(f, *args, **kwargs):
        response = f(*args, **kwargs)

        if type(response) != dict:
            raise Exception("Must return a dict to render_modal_form")

        if 'state' not in response:
            template_name = template
            if template_name is None:
                template_name = 'trex/templates/modal_form.jinja2'

            out = flask.render_template(template_name, trex_bootstrap_version=app.settings.getint('trex', 'bootstrap_version'), **response)
            response = dict(state='render', content=out)

        http_response = flask.Response(ejson.dumps(response), 200)
        http_response.content_type = 'application/json'
        http_response.headers.set('Cache-Control', 'private, no-cache, no-store, must-revalidate')
        http_response.headers.set('Expires', 'Sat, 01 Jan 2000 00:00:00 GMT')
        http_response.headers.set('Pragma', 'no-cache')

        return http_response

    return decorator(decorated)

def render_upload():
    def decorated(f, *args, **kwargs):
        upload = f(*args, **kwargs)

        if upload is None:
            return flask.abort(404)

        if not isinstance(upload, trex.support.model.TrexUpload):
            raise Exception("Can't render upload from %s" % upload)

        return trex.support.mongoengine.serve_file(upload, 'file')

    return decorator(decorated)

def render_thumbnail(width=None, height=None, fit="contain"):
    if width is None and height is None:
        raise Exception("Must specify at least one of width/height for render_thumbnail")

    if fit not in ["cover", "contain", "stretch"]:
        raise Exception("fit must be one of cover, contain, or stretch for render_thumbnail")

    if fit in ["cover", "stretch"] and (width is None or height is None):
        raise Exception("fit=%s requires both width and height to be set for render_thumbnail" % fit)

    def decorated(f, *args, **kwargs):
        upload = f(*args, **kwargs)

        if upload is None:
            return flask.abort(404)

        if isinstance(upload, app.response_class):
            return upload

        if not isinstance(upload, trex.support.model.TrexUpload):
            raise Exception("Can't render upload from %s" % upload)

        if not upload.can_thumbnail():
            raise Exception("Upload doesn't support thumbnailing" % upload)

        return upload.generate_thumbnail_response(width=width, height=height, fit=fit)

    return decorator(decorated)

def render_json(cachable=False):
    def decorated(f, *args, **kwargs):
        response = f(*args, **kwargs)

        if type(response) != dict and not isinstance(response, mongoengine.queryset.QuerySet) and not isinstance(response, mongoengine.Document) and type(response) != list:
            return response

        http_response = flask.Response(ejson.dumps(response), 200)
        http_response.content_type = 'application/json'

        if cachable == False:
            http_response.headers.set('Cache-Control', 'private, no-cache, no-store, must-revalidate')
            http_response.headers.set('Expires', 'Sat, 01 Jan 2000 00:00:00 GMT')
            http_response.headers.set('Pragma', 'no-cache')

        return http_response
    return decorator(decorated)

def render_csv():
    def decorated(f, *args, **kwargs):
        response = f(*args, **kwargs)

        if type(response) != dict:
            return response

        io = StringIO.StringIO()

        output = csv.writer(io)

        if 'headers' in response:
            output.writerow([unicode(x).encode('utf-8') for x in response['headers']])

        for row in response['rows']:
            output.writerow([unicode(x).encode('utf-8') for x in row])

        io.seek(0)
        http_response = flask.Response(io.getvalue(), 200)
        http_response.content_type = 'text/csv'
        if 'filename' in response:
            http_response.headers.set('Content-Disposition', 'attachment; filename=%s.csv' % response['filename'])
        http_response.headers.set('Cache-Control', 'private, no-cache, no-store, must-revalidate')
        http_response.headers.set('Expires', 'Sat, 01 Jan 2000 00:00:00 GMT')
        http_response.headers.set('Pragma', 'no-cache')

        io.close()
        return http_response

    return decorator(decorated)

class TrexRequest(flask.Request):
    parameter_storage_class = OrderedMultiDict

class Flask(flask.Flask):
    settings = TrexConfigParser()
    db = None
    in_test_mode = False

    def check_default_config(self):
        """Asserts that the config in default.ini/base.ini is sane"""
        assert self.settings.has_section('server'), "Section [server] doesn't exist in config"
        assert 'url' not in self.settings.options('server'), "Option url exists in [server] section"

    def check_local_config(self):
        """Asserts that the config in local.ini is sane"""
        for section in ['app', 'server', 'mongo', 'notify']:
            assert self.settings.has_section(section), "Section [%s] doesn't exist in config" % section
        for option in ['host', 'port', 'debug', 'url']:
            assert option in self.settings.options('server'), "Option %s exists in [server] section" % option

        assert 'url' in self.settings.options('mongo'), "Option 'url' exists in [mongo] section"
        mongo_url = furl(self.settings.get('mongo', 'url'))
        assert mongo_url.scheme == 'mongodb', "mongo.url is a valid mongodb:// url: %s" % mongo_url
        assert len(mongo_url.path.segments) == 1, "mongo.url %s has a database set" % mongo_url
        assert mongo_url.path.segments[0] != '', "mongo.url %s has a database set" % mongo_url

        assert 'name' in self.settings.options('app'), "Option 'name' exists in [app] section"
        assert 'slug' in self.settings.options('app'), "Option 'slug' exists in [app] section"

        assert 'enabled' in self.settings.options('notify')
        if self.settings.getboolean('notify', 'enabled'):
            assert 'url' in self.settings.options('notify'), "URL not set in [notify] section"
            assert 'channel' in self.settings.options('notify'), "channel not set in [notify] section"


    def switch_to_test_mode(self, instance_number=None):
        mongo_url   = furl(self.settings.get('mongo', 'url'))
        server_port = self.settings.getint('test', 'server_port')
        server_url  = furl(self.settings.get('test', 'server_url'))

        if instance_number is not None:
            mongo_url.path.segments[0] = "test_%d_%s" % (instance_number, mongo_url.path.segments[0])
            server_port += instance_number
            if not server_url.port or server_url.port != self.settings.getint('test', 'server_port'):
                raise Exception("Can't detect how to adjust server url for instance: %d" % instance_number)
            server_url.port = server_port
        else:
            mongo_url.path.segments[0] = "test_%s" % mongo_url.path.segments[0]

        self.settings.set('mongo', 'url', str(mongo_url))
        self.settings.set('server', 'port', str(server_port))
        self.settings.set('server', 'url', str(server_url))

        self.in_test_mode = True
        self.init_application()

    def switch_to_wsgi_mode(self):
        self.log_to_file('application.log')
        self.logger.debug('Switched to WSGI mode')


    def log_to_file(self, filename):
        log_filename = os.path.abspath(os.path.join(self.root_path, '..', 'logs', filename))
        file_handler = logging.FileHandler(log_filename)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(self.logger_formatter)
        if self.settings.getboolean('server', 'debug'):
            self.logger.debug("Logging to file: %s" % filename)
        else:
            # Nuke the existing StreamHandler
            logging.root.handlers = []
        logging.root.addHandler(file_handler)

    def __init__(self, *args, **kwargs):
        super(Flask, self).__init__(*args, **kwargs)

        self.request_class = TrexRequest
        # Add trex/templates to the jinja2 search path
        self.jinja_loader.searchpath.append(os.path.join(os.path.dirname(__file__), 'templates'))

        self.settings.readfp(codecs.open(os.path.join(self.root_path, '..', 'trex', 'base.ini'), 'r', 'utf8'))
        self.settings.readfp(codecs.open(os.path.join(self.root_path, 'default.ini'), 'r', 'utf8'))
        self.check_default_config()
        self.settings.readfp(codecs.open(os.path.join(self.root_path, 'local.ini'), 'r', 'utf8'))
        self.check_local_config()

        self.init_jinja()
        self.exception_reporter = FlaskExceptionReporter(self)

        FlaskCDN(self)

        trex.support.model.settings = self.settings

        self.init_application()

    def init_jinja(self):
        self.select_jinja_autoescape = True

        # Filters
        @self.template_filter()
        def tojson(o):
            return ejson.dumps(o)

        @self.template_filter()
        def moment_stamp(dt):
            return '%sZ' % dt.isoformat()

        @self.template_filter()
        def textarea2html(text):
            return parser.textarea2html(text)

        @self.template_filter()
        def english_join(items):
            return ', '.join(items[0:-1]) + ' and ' + items[-1]

        @self.template_filter()
        def oxford_join(items):
            num = len(items)
            if num == 0:
                return ''
            if num == 1:
                return items[0]
            if num == 2:
                return ' and '.join(items)
            return ', '.join(items[0:-1]) + ', and ' + items[-1]

        @self.template_filter()
        def page_title(title, default=None, strict=True):
            if strict:
                if not title:
                    raise Exception("No page title set for this page")

                if default:
                    return '%s - %s' % (title, default)

                return title

            if title:
                if default:
                    return '%s - %s' % (title, default)
                return title

            return default

        @self.template_filter()
        def quantum(q, format, empty_text='-', user=None, timezone=None):
            try:
                format_str = app.settings.get('quantum', 'format_%s' % format)
            except NoOptionError:
                raise Exception('Tried to use format type "%s" for the quantum filter, which is not defined in configuration' % format)
            if not q:
                return empty_text
            if not timezone:
                if not user:
                    timezone = flask.g.user.timezone
            return q.at(timezone).as_local().strftime(format_str)

        def puffer():
            """
            Provides a random-content, psuedo-random-length string to be placed in responses to prevent the application
            from returning a predictable compressed length response.

            The objective is to ensure that attacks that use the length of the response as an oracle for figuring out
            matched text by compression face a more difficult task due to the ever-changing length of responses.

            It does not resolve the issue, only mitigate it to the extent that many more tests are required to achieve
            statistical certainty that a guess is correct.
            """
            if not app.settings.getboolean('security','puffer_response'):
                return ''
            return base64.b64encode(hashlib.sha256(hashlib.sha256(os.urandom(32)).digest()).digest())[:random.randint(16,32)]

        # Globals (note: from 0.10, we will be able to use @self.template_global())
        self.jinja_env.globals['hostname'] = os.uname()[1]
        self.jinja_env.globals['format'] = trex.support.format
        self.jinja_env.globals['puffer'] = puffer
        self.jinja_env.globals['urlencode'] = urllib.quote


        def csrf_token():
            if hasattr(flask.g, 'identity'):
                return flask.g.identity.get_csrf()
            return ''

        self.jinja_env.globals['csrf_token'] = csrf_token

    def init_application(self):
        self.debug = self.settings.getboolean('server', 'debug')
        self.logger_formatter = logging.Formatter(
            '%(asctime)s [%(process)5d] [%(name)20.20s] %(levelname)8s - %(message)s '
            '[in %(pathname)s:%(lineno)d]'
        )
        self.logger.setLevel(logging.DEBUG)
        log_handler = logging.StreamHandler()
        log_handler.setLevel(logging.DEBUG)
        if sys.stdout.isatty():
            from termcolor import colored

            class ColoredFormatter(logging.Formatter):
                def format(self, record):
                    levelname = record.levelname
                    formatted = logging.Formatter.format(self, record)
                    if levelname == 'INFO':
                        return colored(formatted, 'green')
                    if levelname in ['WARNING', 'ERROR', 'CRITICAL']:
                        return colored(formatted, 'red')

                    return formatted

            log_handler.setFormatter(ColoredFormatter(
                '%(asctime)s [%(process)5d] [%(name)20.20s] %(levelname)8s - %(message)s '
                '[in %(pathname)s:%(lineno)d]'
            ))
        else:
            log_handler.setFormatter(self.logger_formatter)

        # Set the root handler, and clear the app-specific one
        logging.root.handlers = []  # When init_application is called more than once, we don't want to acrue handlers
        logging.root.addHandler(log_handler)
        logging.root.setLevel(logging.DEBUG)
        self.logger.handlers = []

        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.setLevel(logging.INFO)
        werkzeug_logger.propagate = False
        werkzeug_logger.addHandler(logging.StreamHandler())

        logging.getLogger('requests.packages.urllib3.connectionpool').setLevel(logging.WARNING)

        # Identity does this, we don't want whatever flask might be doing
        self.config['CSRF_ENABLED'] = False

        server_url = furl(self.settings.get('server', 'url'))
        self.config['SERVER_NAME'] = server_url.netloc
        self.config['SESSION_COOKIE_DOMAIN'] = server_url.host

        if server_url.scheme == 'https':
            self.config['SESSION_COOKIE_SECURE'] = True
            self.config['PREFERRED_URL_SCHEME'] = 'https'

            def add_security_headers(response):
                # See https://en.wikipedia.org/wiki/Strict_Transport_Security
                response.headers.set('Strict-Transport-Security', 'max-age=31536000')

                if self.settings.get('security','frames') == 'deny':
                    response.headers.set('X-Frame-Options','DENY')
                elif self.settings.get('security', 'frames') == 'sameorigin':
                    response.headers.set('X-Frame-Options','SAMEORIGIN')

                return response

            self.after_request(add_security_headers)

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
        mongoengine.connection.get_db(reconnect=True)

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

    def drop_collections(self):
        for model in self.enumerate_models():
            if issubclass(model, trex.support.model.ForeverDocument):
                model.all.delete()
            else:
                model.objects.delete()

        # Chop any gridfs support collections
        for name in app.db.collection_names():
            if re.search(r'\.(files|chunks)$', name):
                app.db.drop_collection(name)

    def enumerate_models(self):
        import app.model
        import trex.support.model
        import trex.support.cron
        import trex.support.mail
        for module in [app.model, trex.support.model, trex.support.cron, trex.support.mail]:
            for name, cls in inspect.getmembers(module, inspect.isclass):
                if isinstance(cls, mongoengine.base.metaclasses.TopLevelDocumentMetaclass) and cls._meta['abstract'] == False:
                    yield cls

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
        notify.error(app.settings.get('app', 'slug'), data['type'], '%s at %s:%s' % (data['value'], file, line))
    except:
        notify.error(app.settings.get('app', 'slug'), data['type'], '%s (no file/line info available)' % data['value'])


class FlaskExceptionReporter(object):
    def __init__(self, app=None):
        self.reporter = _exception_handler
        flask.got_request_exception.connect(self.invoke)

    def invoke(self, app, exception):
        self.reporter(app, exception)


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
        view_func_authed.allow_cors = options.pop('allow_cors', False)

        if view_func_authed.allow_cors:
            options['methods'] = ('OPTIONS',) + tuple(options.get('methods', ('GET',)))

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
