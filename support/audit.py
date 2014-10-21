# coding=utf-8

from __future__ import absolute_import
from flask import g
import json
import sys
import os
import traceback
from werkzeug.wrappers import Request
from trex.support import quantum
import socket
import netaddr

def audit(description, tags, documents=None, user=None, system_action=False, moreinfo=None):
    import app.model as m  # We import this late so that the audit method can be loaded into the model

    if user is None and hasattr(g, 'user'):
        user = g.user

    if system_action:
        user = None

    if documents is None:
        documents = []

    audit = m.Audit(
        user        = user,
        tags        = tags,
        documents   = documents,
        description = description,
        moreinfo    = moreinfo,
    )
    audit.save()

class TrexAudit(object):

    def __init__(self, app):
        self.app = app
        self.super_wsgi_app = app.wsgi_app
        self.app.wsgi_app = self.wsgi_app
        self.fh = open(os.path.join(self.app.log_directory, 'trex-audit.log'), 'a')

    def wsgi_app(self, environ, start_response):
        if 'werkzeug.request' in environ:
            req = environ['werkzeug.request']
        else:
            req = Request(environ)

        session_id = 'identity' in req.cookies and req.cookies['identity'] or None

        audit_document = dict(
            # Fields present in all audit documents
            timestamp   = quantum.now().as_unix(),
            source      = 'request',
            actor       = None,
            real        = None,
            session_id  = session_id,
            app         = self.app.settings.get('app', 'slug'),
            level       = 'info',
            tags        = [],
            server      = socket.getfqdn(),
            remote_addr = req.remote_addr,
            ip          = req.remote_addr,

            # Fields present in documents from this source
            error      = None,
            request    = dict(
                method      = req.method,
                url         = req.url,
                host        = req.host,
                user_agent  = 'User-Agent' in req.headers and req.headers['User-Agent'] or None,
                headers     = [dict(k=h[0], v=h[1]) for h in req.headers],
            ),
        )

        remote_addr = netaddr.IPAddress(req.remote_addr)

        if len(req.access_route) and (remote_addr.is_private() or remote_addr.is_loopback()):
            audit_document['ip'] = req.access_route[-1]

        if session_id:
            import app.model as m
            identity = m.Identity.from_session_id(session_id)
            if identity.actor:
                audit_document['actor'] = dict(
                    token = identity.actor.token,
                    email = identity.actor.email,
                    display_name = identity.actor.display_name,
                )
                if identity.actor != identity.real:
                    audit_document['real'] = dict(
                        token = identity.real.token,
                        email = identity.real.email,
                        display_name = identity.real.display_name,
                    )

        response_data = []
        def detect_response_data(status, headers, *args, **kwargs):
            response_data[:] = status[:3], headers
            return start_response(status, headers, *args, **kwargs)

        e_type, e_value, e_traceback = None, None, None
        try:
            response = self.super_wsgi_app(environ, detect_response_data)
        except:
            e_type, e_value, e_traceback = sys.exc_info()
            raise
        finally:
            audit_document['error'] = e_type is not None

            if e_type:
                if not isinstance(e_type, str):
                    if e_type.__module__ not in ('__builtin__', 'exceptions'):
                        e_type = e_type.__module__ + '.' + e_type.__name__
                    else:
                        e_type = e_type.__name__

                audit_document['exception'] = dict(
                    type      = e_type,
                    value     = str(e_value),
                    traceback = [dict(file=f[0], line=f[1], func=f[2], text=f[3]) for f in traceback.extract_tb(e_traceback)],
                )
                audit_document['response'] = dict(
                    status = 500,
                )
                audit_document['level'] = 'error'
            else:
                audit_document['response'] = dict(
                    status  = int(response_data[0]),
                    headers = [dict(k=h[0], v=h[1]) for h in response_data[1]],
                )

            self.write_audit_data(audit_document)

        return response

    def write_audit_data(self, audit_data):
        self.fh.writelines([json.dumps(audit_data) + "\n"])
        self.fh.flush()
