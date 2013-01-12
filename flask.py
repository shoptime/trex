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
from .support.mongosession import MongoSessionInterface
from .cdn import FlaskCDN
from furl import furl

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

        out     = flask.render_template(template_name, **response)
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
        for section in ['server', 'mongo']:
            assert self.settings.has_section(section), "Section [%s] doesn't exist in config" % section
        for option in ['host', 'port', 'debug', 'url', 'enable_csrf']:
            assert option in self.settings.options('server'), "Option %s exists in [server] section" % option

        assert 'url' in self.settings.options('mongo'), "Option url exists in [mongo] section"
        mongo_url = furl(self.settings.get('mongo', 'url'))
        assert mongo_url.scheme == 'mongodb', "mongo.url is a valid mongodb:// url: %s" % mongo_url
        assert len(mongo_url.path.segments) == 1, "mongo.url %s has a database set" % mongo_url
        assert mongo_url.path.segments[0] != '', "mongo.url %s has a database set" % mongo_url


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

        self.session_interface = MongoSessionInterface()

        self.settings.read([
            os.path.join(self.root_path, 'default.ini'),
            os.path.join(self.root_path, 'local.ini'),
        ])

        self.assert_valid_config()

        self.select_jinja_autoescape = True

        self.jinja_env.filters['tojson'] = lambda o: ejson.dumps(o)
        self.jinja_env.filters['moment_stamp'] = lambda dt: dt.isoformat()+'Z'
        self.jinja_env.filters['textarea2html'] = lambda text: parser.textarea2html(text)
        self.jinja_env.filters['english_join'] = lambda items: ', '.join(items[0:-1]) + ' and ' + items[-1]
        self.jinja_env.filters['oxford_join'] = lambda items: len(items) == 2 and ' and '.join(items) or ', '.join(items[0:-1]) + ', and ' + items[-1]

        self.jinja_env.globals['hostname'] = os.uname()[1]

        if self.settings.getboolean('server', 'enable_csrf'):
            self.csrf = SeaSurf(self)
            self.csrf_token = self.csrf._get_token
        else:
            def nothing():
                return ''
            self.csrf_token = nothing
            self.jinja_env.globals['csrf_token'] = nothing

        FlaskCDN(self)

        self.init_application()

    def init_application(self):
        self.debug = self.settings.getboolean('server', 'debug')
        self.logger.setLevel(logging.DEBUG)

        if self.settings.get('server', 'url').startswith('https:'):
            self.logger.info("Detected SSL service URL, enabling secure cookies")
            self.config['SESSION_COOKIE_SECURE'] = True

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

    def shutdown(self):
        # This funky cleanup code is necessary to ensure that we nicely kill off any
        # mongo replicaset connection monitoring threads
        db = mongoengine.connection.get_connection('default')
        if db:
            db.close()
