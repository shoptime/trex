from __future__ import absolute_import

import re
import os
from os import path
import hashlib
from flask import Response, abort, request
import mimetypes
from werkzeug.http import http_date
from furl import furl

EXPIRE_SECONDS = 315576000  # ~ 10 years

class CDNNotFound(OSError):
    pass

class FlaskCDN(object):
    def __init__(self, app):
        self.app = app
        self.init_app()

    def init_app(self):
        self.cdn = CDN('%s/cdn' % self.app.root_path, '/cdn/')
        self.app.cdn = self.cdn.resolve
        self.app.jinja_env.globals['cdn'] = self.cdn.resolve

        @self.app.route('/cdn/<path:uri>', endpoint='cdn')
        def serve_file(uri):
            uri, hash = self.cdn.unhash_uri(uri)
            if uri is None:
                abort(404)
            try:
                info = self.cdn.info(uri)
            except OSError:
                abort(404)

            if info.hash != hash:
                abort(404)

            mtime = http_date(info.stat.st_mtime)

            if 'If-None-Match' in request.headers and request.headers['If-None-Match'] == info.hash:
                response = Response(None, 304)
            elif 'If-Modified-Since' in request.headers and request.headers['If-Modified-Since'] == mtime:
                response = Response(None, 304)
            else:
                response = Response(info.file_data(), 200)

            response.headers['Content-Type'] = info.mime
            response.headers['Cache-Control'] = 'max-age=%d, public' % EXPIRE_SECONDS
            response.headers['Last-Modified'] = mtime
            response.headers['Expires'] = http_date(info.stat.st_mtime + EXPIRE_SECONDS)
            response.headers['ETag'] = info.hash

            return response

    def __call__(self, uri, **kwargs):
        return self.cdn.resolve(uri, **kwargs)

class CDNPlugin(object):
    def __init__(self, cdn):
        self.cdn = cdn

    def preprocess(self, info):
        pass

class CDN_SourceMaps(CDNPlugin):
    def preprocess(self, info):
        self.info = info
        if self.info.mime in ['text/css', 'application/javascript']:
            info.data = re.sub(r'''((?:^//|/\*)# sourceMappingURL\s*=\s*)(\S+)''', self.url_replace, info.file_data(), flags=re.M)

    def url_replace(self, match):
        uri = match.group(2)
        uri_object = furl(uri)

        # data: URIs should be left alone
        if uri.startswith('data:'):
            return "%s%s" % (match.group(1), match.group(2))

        # Absolute links with a host just remain unchanged
        if uri_object.host:
            return "%s%s" % (match.group(1), match.group(2))

        if path.isabs(uri):
            cdn_uri = path.relpath(uri, '/')
        else:
            cdn_uri = path.normpath(path.join(path.relpath(path.dirname(self.info.full_path), self.cdn.root), uri))

        return "%s%s" % (match.group(1), self.cdn.resolve(cdn_uri))

class CDN_CSS(CDNPlugin):
    def preprocess(self, info):
        if info.mime != 'text/css':
            return
        self.info = info
        info.data = re.sub(r'''url \( (["']?) ([^)]+) \1 \)''', self.url_replace, info.file_data(), flags=re.X)

    def url_replace(self, match):
        quotes = match.group(1)
        uri = match.group(2)

        uri_object = furl(uri)

        # Absolute links with a host just remain unchanged
        if uri_object.host:
            return "url(%(quotes)s%(uri)s%(quotes)s)" % dict(quotes=quotes, uri=uri)

        # data uris also remain unchanged
        if uri.startswith('data:'):
            return "url(%(quotes)s%(uri)s%(quotes)s)" % dict(quotes=quotes, uri=uri)

        # Absolute links (i.e. those starting with /) are treated as
        # referencing the top of the CDN
        if path.isabs(uri):
            cdn_uri = path.relpath(uri, '/')
        else:
            cdn_uri = path.normpath(path.join(path.relpath(path.dirname(self.info.full_path), self.cdn.root), uri))

        # TODO - store dependancies

        return "url(%(quotes)s%(uri)s%(quotes)s)" % dict(quotes=quotes, uri=self.cdn.resolve(cdn_uri))

# This could work for on-the-fly javascript minification
#from slimit import minify
#class CDNJavascriptMinifier(CDNPlugin):
#    def preprocess(self, info):
#        if info.mime != 'application/javascript':
#            return
#        info.data = minify(info.file_data(), mangle=True)

class CDN_LessProcessor(CDNPlugin):
    def __init__(self, *args, **kwargs):
        mimetypes.add_type('text/less', '.less')
        mimetypes.add_type('application/json', '.map')
        super(self.__class__, self).__init__(*args, **kwargs)

    def preprocess(self, info):
        if info.mime != 'text/less':
            return
        print "PROCESS LESS"

class CDN(object):
    def __init__(self, root, base=None):
        self.root = root
        self.base = base
        self._cache = {}
        self.plugins = []
        self.plugins.append(CDN_CSS(self))
        self.plugins.append(CDN_SourceMaps(self))
        #self.plugins.append(CDNJavascriptMinifier(self))

    def resolve(self, uri, base=None):
        if base is None:
            base = self.base
        info = self.update(uri)
        return "%s%s" % (base, info.cdn_file)

    def unhash_uri(self, uri):
        components = re.split(r'\.', uri)
        if len(components) < 3:
            return None, None
        hash = components[-2]
        url = ".".join(components[:-2])
        url += ".%s" % components[-1]
        return url, hash

    def info(self, uri):
        return self.update(uri)

    def update(self, uri):
        if not uri:
            raise Exception("No URI specified")

        force_update = False

        match = re.split('#', uri, maxsplit=2)
        if len(match) > 1:
            fragment = "#%s" % match[1]
        else:
            fragment = None
        uri = match[0]

        match = re.split('\?', uri, maxsplit=2)
        if len(match) > 1:
            query = "#%s" % match[1]
        else:
            query = None
        uri = match[0]

        uri = self.cleanup_uri(uri)

        info = self.cache_get(uri)

        if fragment != info.fragment:
            info.fragment = fragment
            force_update = True

        info.full_path = info.full_path or self.full_path(uri)

        try:
            stat = os.stat(info.full_path)
        except OSError, e:
            raise CDNNotFound(e)

        if force_update or not info.stat or info.stat.st_mtime != stat.st_mtime:
            info.data = None
            info.dependancies = {}
            info.uri = uri
            filename_components = re.split(r'\.', uri)
            info.extension = filename_components[-1]
            info.basename = ".".join(filename_components[:-1])

            info.calculate_mime()

            for plugin in self.plugins:
                plugin.preprocess(info)

            info.calculate()

        info.stat = stat

        return info

    def cache_get(self, uri):
        if uri not in self._cache:
            self._cache[uri] = CDNFile()
        return self._cache[uri]

    def full_path(self, uri):
        return path.join(self.root, uri)

    def cleanup_uri(self, uri):
        return path.relpath(path.abspath(path.join(self.root, uri)), self.root)

class CDNFile(object):
    def __init__(self):
        self.cdn_file = None
        self.fragment = None
        self.full_path = None
        self.stat = None
        self.data = None
        self.dependancies = {}
        self.extension = None
        self.basename = None
        self.mime = None

    def __repr__(self):
        return "<trex.cdn.CDNFile object \"%s\">" % self.uri

    def file_data(self):
        if self.data is not None:
            return self.data

        with open(self.full_path) as fh:
            data = fh.read()

        if self.mime.startswith('text/') or self.mime == 'application/javascript':
            data = data.decode('utf8')

        return data

    def calculate_mime(self):
        self.mime = mimetypes.guess_type(self.full_path)[0] or "application/octet-stream"

    def calculate(self):
        data = self.file_data()
        if isinstance(data, unicode):
            data = data.encode('utf8')
        self.hash = hashlib.md5(data).hexdigest()
        self.hash = self.hash[:12]
        self.cdn_file = "%s.%s.%s" % (self.basename, self.hash, self.extension)
        if self.fragment:
            self.cdn_file += self.fragment
