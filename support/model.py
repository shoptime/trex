# coding=utf-8

from __future__ import absolute_import
from mongoengine import *
from datetime import datetime, timedelta
from trex.support import pcrypt
from trex.support.mongoengine import LowerCaseEmailField
from flask import flash, g, url_for
import Crypto.Random.random
import re


class InvalidRoleException(Exception):
    pass

class BaseUser(Document):
    meta = {
        'indexes': [('email',)],
        'abstract': True,
    }

    email        = LowerCaseEmailField(required=True, unique=True)
    display_name = StringField(required=True)
    password     = StringField()
    created      = DateTimeField(required=True, default=datetime.utcnow)
    last_login   = DateTimeField()
    role         = StringField(required=True, default='user')

    @classmethod
    def roles(cls):
        return dict(
            user = dict(
                label       = 'User',
                description = 'Basic site user',
                level       = 0,
            ),
            admin = dict(
                label       = 'Administrator',
                description = 'Site administrator',
                level       = 10,

            ),
            developer = dict(
                label       = 'Developer',
                description = 'Site developer',
                flags       = ['trex.user_management'],
                level       = 100,
            ),
        )

    def get_role(self, role):
        try:
            return self.roles()[role]
        except KeyError:
            raise InvalidRoleException("Invalid role: %s" % role)

    def has_role(self, role):
        if self.role == role:
            return True

        my_role = self.get_role(self.role)
        target_role = self.get_role(role)

        return my_role['level'] > target_role['level']

    def is_role(self, role):
        return self.role == role

    def has_flag(self, flag):
        my_role = self.get_role(self.role)
        if flag in my_role.get('flags', []):
            return True

        for role in self.roles().values():
            if role['level'] < my_role['level'] and flag in role.get('flags', []):
                return True

        return False

    def check_login(self, entered_password):
        return self.check_password(entered_password)

    def set_password(self, password):
        self.password = pcrypt.hash(password)

    def check_password(self, entered_password):
        return pcrypt.verify(entered_password, self.password)

    def notify_password_reset(self, new_password):
        flash("Password for %s is: %s" % (self.email, new_password))

    def to_ejson(self):
        data = self.to_mongo()
        del data['password']
        return data

class BaseAudit(Document):
    meta = {
        'ordering': ['-created'],
        'abstract': True,
    }

    created     = DateTimeField(required=True, default=datetime.utcnow)
    user        = ReferenceField('User')
    tags        = ListField(StringField(), required=True)
    description = StringField(required=True)
    documents   = ListField(GenericReferenceField())

    def linkable_documents(self):
        docs = []
        for doc in self.documents:
            if isinstance(doc, BaseUser) and hasattr(g, 'user') and g.user.has_flag('trex.user_management'):
                docs.append(dict(
                    url   = url_for('trex.user_management.edit', user_id=doc.id),
                    label = doc.display_name,
                    type  = 'user',
                ))

        return docs


class SessionExpired(BaseException):
    """
    There's a session mentioned in the user cookie, but the entry has either been purged from the database or the entry
    is explicitly expired.
    """
    pass

class SessionLoggedOut(BaseException):
    """
    We found the session, but it had been logged out
    """
    pass


class BaseIdentity(Document):
    """
    Base identity session for trex
    """
    # QUESTION: Have user ID as part of the base?
    # QUESTION: Have actor as part of the base?
    # QUESTION: Add rotation for the key?
    meta = {
        'indexes': [('session_id',)],
        'abstract': True
    }

    created = DateTimeField(required=True, default=datetime.utcnow)
    session_id = StringField(required=True)
    expires = DateTimeField(required=True)
    real = ReferenceField('User')
    actor = ReferenceField('User')
    logged_out = BooleanField(required=True, default=False)


    @classmethod
    def config(cls):
        """
        Return a dictionary with the session configuration

        Keys:

        cookie_key: key to use in cookie when setting session. Defaults to 'identity'
        expiry: Number of seconds before the session expires in the database. Defaults to 24 hours
        cookie_expiry: Number of seconds before the cookie expires. Defaults to None (until browser closes)
        http_only: Whether to hide the session from javascript (Yes yes yes default True)
        domain: Domain for the cookie, default None (current page)
        path: Path limit for the cookie, default /
        secure: Whether to only deliver the session cookie in HTTPS, default True (set this False for dev)

        """
        # QUESTION: is this really the best way to do this?
        return {
            'cookie_key': 'identity',
            'expiry': 24*60*60,
            'cookie_expiry': None,
            'http_only': True,
            'domain': None,
            'path': '/',
            'secure': True
        }


    @classmethod
    def exempt_request(cls, path):
        """
        Return true if the given request should not have session processing/setting. Defaults to putting a session on
        everything.
        """
        # QUESTION: Ignore CDN by default? doesn't really matter since we only trigger on decorated functions anyway
        return False


    @classmethod
    def generate_session_id(cls):
        """
        Securely generate a random token of the correct length for a session ID
        :return:
        :rtype:
        """
        # QUESTION: Shield the RNG?
        # QUESTION: Sign it?
        return '%032x' % Crypto.Random.random.getrandbits(128)


    @classmethod
    def is_session_id(cls, s):
        """
        Check whether it's a valid session ID
        """
        if len(s) != 32:
            return False

        if not re.match(r'[0-9a-f]+', s):
            return False

        return True

    @classmethod
    def new_session(cls):
        """
        Create a new empty session with no credentials
        """

        session = cls(
            session_id=cls.generate_session_id(),
        )
        session.set_expiry(cls.config()['expiry'])
        return session

    def rotate_session(self):
        """
        Rotate the session ID. Could do this by logging out existing if we cared about using the session table as an
        audit but we don't.
        """
        self.session_id = self.generate_session_id()
        return self


    @classmethod
    def from_request(cls, request):
        """
        Load the session from the request
        """
        # Check whether the request is exempt, if so return None
        if cls.exempt_request(request.path):
            return None

        # Get session ID from cookie
        session_id = request.cookies.get(cls.config()['cookie_key'])

        #   No session ID? return new session
        if not session_id:
            return cls.new_session()

        # Invalid session ID? return new session
        if not cls.is_session_id(session_id):
            return cls.new_session()

        # Got session id in cookie, look in DB
        session = cls.objects(session_id=session_id).first()

        # Not in DB? create new session.
        if not session:
            return cls.new_session()

        # Expired? new session
        if session.is_expired():
            # QUESTION: Set flag on new session saying it's the result of an expiry so that login redirect can flash?
            return cls.new_session()

        # Logged out? new session
        if session.is_logged_out():
            return cls.new_session()

        # return doc
        return session

    def set_cookie(self, response):
        """
        Set the cookie with the current session
        """
        # Update expiry so session stays valid
        # QUESTION: autorotate after given time?
        self.set_expiry(self.config()['expiry'])

        # QUESTION: Add puffer?
        response.set_cookie(self.config()['cookie_key'], self.session_id,
                            max_age=self.config()['cookie_expiry'],
                            path=self.config()['path'],
                            domain=self.config()['domain'],
                            httponly=self.config()['http_only'],
                            secure=self.config()['secure'])

    def set_expiry(self, seconds_from_now):
        """
        Set the expiry time to N seconds from now
        """
        self.expires = datetime.utcnow()+timedelta(seconds=seconds_from_now)

    def is_expired(self):
        """
        Check whether this session is expired
        """
        if self.expires > datetime.utcnow():
            return False
        return True

    def is_logged_out(self):
        """
        Check whether this session is logged out
        """
        return self.logged_out

    def logout(self):
        """
        Log this session out
        """
        print "Logging out"
        self.logged_out = True
