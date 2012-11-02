from __future__ import absolute_import

from flask.sessions import SecureCookieSessionInterface
from uuid import uuid4
from datetime import datetime
from flask import request

class MongoSessionInterface(SecureCookieSessionInterface):

    def _ignore_req(self, path):
        if request.endpoint == 'cdn':
            return True

        if request.path == '/favicon.ico':
            return True

        return False

    def open_session(self, *args, **kwargs):
        app, request = args

        # Some paths we don't do sessions for
        # NOTE: commented out until we get a new version of SeaSurf that doesn't store stuff in the session
        #if self._ignore_req(request.path):
        #    return None

        session = super(MongoSessionInterface, self).open_session(*args, **kwargs)

        if 'session_id' in session:
            # Existing session_id, retrieve and init session
            data = app.db.session.find_one({ 'session_id': session['session_id'] })
            if data:
                # Session exists in database, use it
                if request.user_agent.string != data.get('user_agent', ''):
                    data['user_agent'] = request.user_agent.string
                return self.session_class(data, secret_key=app.secret_key, new=False)

        # Couldn't load existing session
        return self.session_class(
            dict(
                session_id = str(uuid4()),
                ctime = datetime.utcnow(),
                user_agent = request.user_agent.string,
            ),
            secret_key=app.secret_key,
            new=True,
        )

    def save_session(self, *args, **kwargs):
        app, session, response = args

        # Some paths we don't do sessions for
        if self._ignore_req(request.path):
            return

        # The data to save is whatever the session has accumulated this request
        data = dict(session)

        if session.new:
            # Hack until we get mongoengine doing this
            data['_cls'] = 'Session'
            data['_types'] = ['Session']

        if session.modified or session.new:
            data['mtime'] = datetime.utcnow()
            app.db.session.update({ 'session_id': data['session_id'] }, data, upsert=True, multi=False, safe=True)

        # The session cookie itself only remembers the session ID
        for k in session.keys():
            if k != 'session_id':
                del session[k]

        # "Permanent" sessions last about a month
        session.permanent = True

        return super(MongoSessionInterface, self).save_session(app, session, response, **kwargs)
