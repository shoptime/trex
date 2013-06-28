# coding=utf-8

from __future__ import absolute_import
from mongoengine import *
from datetime import datetime, timedelta
import os
from trex.support import pcrypt
from trex.support.mongoengine import LowerCaseEmailField
from flask import flash, g, url_for, abort
import re
import hashlib
from . import token

class BaseDocument(Document):
    meta = dict(abstract=True)

    @classmethod
    def get_404(cls, *args, **kwargs):
        """Identical to cls.objects.get(...) except raises a flask 404 instead of mongoengine DoesNotExist"""
        try:
            return cls.objects.get(*args, **kwargs)
        except DoesNotExist:
            abort(404)

class InvalidRoleException(Exception):
    pass

class BaseUser(BaseDocument):
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
    is_active    = BooleanField(required=True, default=True)

    @queryset_manager
    def active(cls, queryset):
        return queryset.filter(is_active=True)

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
                flags       = ['trex.user_management', 'trex.audit_log'],
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
        return self.is_active and self.check_password(entered_password)

    def set_password(self, password, rounds=10001):
        self.password = pcrypt.hash(password, rounds)

    def check_password(self, entered_password):
        return pcrypt.verify(entered_password, self.password)

    def notify_password_reset(self, new_password):
        flash("Password for %s is: %s" % (self.email, new_password))

    def to_ejson(self):
        data = self.to_mongo()
        del data['password']
        return data

class UserAccountRecovery(BaseDocument):
    created = DateTimeField(required=True, default=datetime.utcnow)
    user    = ReferenceField('User')
    code    = StringField(required=True, unique=True, default=token.create_url_token)

    def send_recovery_email(self):
        from trex.support import mail
        from app import app
        mail.send(
            to        = self.user.email,
            subject   = 'Password reset email for %s' % app.settings.get('app', 'name'),
            text_body = "Hi,\n\nYou can reset your password by clicking on this link:\n %(direct_url)s\n\nOr, you can use the code %(code)s at this link: %(url)s\n\n--\n%(app_name)s" % dict(
                code       = self.code,
                direct_url = url_for('trex.auth.recover_password', _external=True, code=self.code),
                url        = url_for('trex.auth.lost_password_sent', _external=True),
                app_name   = app.settings.get('app', 'name'),
            )
        )

class BaseAudit(BaseDocument):
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


def generate_session_id():
    """
    Securely generate a random token of the correct length for a session ID
    """
    # QUESTION: Shield the RNG?
    # QUESTION: Sign it?
    return hashlib.sha256(hashlib.sha256(os.urandom(32)).digest()).hexdigest()


def verify_session_id(s):
    """
    Check whether it's a valid session ID
    """
    if len(s) != 64:
        return False

    if not re.search(r'^[0-9a-f]+$', s):
        return False

    return True

settings = None


def default_expiry():
    return datetime.utcnow()+timedelta(seconds=settings.getint('identity', 'activity_timeout'))


class BaseIdentity(BaseDocument):
    """
    Base identity session for trex

    This Identity Session system is intended to address all the standard conditions associated with an identity session.

    It can be used for general session actions as well, but its primary purpose is different and some actions may prove
    to cause issues versus normal session store.

    Standard session functions

    * Generates secure session tokens of suitable cryptographic strength and randomness
    * Stores specified session data
    * Expires session after a given amount of inactivity, and after a specified absolute time
    * Defends the session by using appropriate settings on the cookie, including HTTPS-Only for HTTPS sites

    Extended identity session functions

    * Provides explicit handlers for credential-changing operations such as login/logout
    * Rotates session IDs on credential change
    * Handles the concept of "su" natively
    * Offers global-logout for logging out all sessions by a given user
    * Correctly performs global logout on conditions such as password change

    Possible further features:

    * Puffers to provide assist against certain types of TLS attack
    * Rotation of session ID after a certain amount of time
    * Verify no-cache of session credentials
    * Explicit config permit of fields that survive credential transition
    * Integrated audit or notify for error conditions such as manipulated session ID
    * Set index to perform automatic removal of expired sessions

    References:

    * https://www.owasp.org/index.php/Session_Management_Cheat_Sheet

    """
    meta = {
        'indexes': [('session_id',)],
        'abstract': True
    }

    created = DateTimeField(required=True, default=datetime.utcnow)
    session_id = StringField(required=True, default=generate_session_id)
    expires = DateTimeField(required=True, default=default_expiry)
    real = ReferenceField('User')
    actor = ReferenceField('User')
    logged_out = BooleanField(required=True, default=False)

    def rotate_session(self):
        """
        Rotate the session ID. Could do this by logging out existing if we cared about using the session table as an
        audit but we don't.
        """
        self.session_id = generate_session_id()
        return self

    @classmethod
    def from_request(cls, request):
        """
        Load the session from the request
        """

        # Get session ID from cookie
        session_id = request.cookies.get(settings.get('identity', 'cookie_key'))

        #   No session ID? return new session
        if not session_id:
            return cls()

        # Invalid session ID? return new session
        if not verify_session_id(session_id):
            return cls()

        # Got session id in cookie, look in DB
        session = cls.objects(session_id=session_id).first()

        # Not in DB? create new session.
        if not session:
            return cls()

        # Expired? new session
        if session.is_expired():
            return cls()

        # return doc
        return session

    def set_cookie(self, response):
        """
        Set the cookie with the current session
        """
        # Ensure we're setting the cookie matching the stored session
        self.save()

        # Update expiry so session stays valid
        self.set_expiry(settings.getint('identity', 'activity_timeout'))

        # QUESTION: autorotate after given time?

        # QUESTION: Add puffer?
        try:
            max_age = settings.getint('identity', 'cookie_expiry')
        except ValueError:
            max_age = None

        domain = settings.get('identity', 'domain')
        if len(domain) == 0:
            domain = None
        response.set_cookie(settings.get('identity','cookie_key'), self.session_id,
                            max_age=max_age,
                            path=settings.get('identity', 'path'),
                            domain=domain,
                            httponly=settings.get('identity', 'http_only'),
                            secure=settings.get('server', 'url').startswith('https:'))

    def set_expiry(self, seconds_from_now):
        """
        Set the expiry time to N seconds from now
        """
        self.expires = datetime.utcnow()+timedelta(seconds=seconds_from_now)

    def is_expired(self):
        """
        Check whether this session is expired
        """
        # Has the session passed its activity expiry?
        if self.expires > datetime.utcnow():
            return False

        # What about its final session expiry?
        if self.created + timedelta(seconds=settings.getint('identity.session_timeout')) < datetime.utcnow():
            return False

        return True

    def login(self, user):
        """
        Log this session in as user
        """
        # These rotates should probably wipe everything except fields specified by config, in order to prevent info
        # leak across contexts.
        self.actor = user
        self.real = user
        self.rotate_session()
        self.save()

    def su(self, user):
        """
        Change this user to be another one
        """
        self.actor = user
        self.rotate_session()
        self.save()

    def unsu(self):
        """
        Change user back (un-su)
        """
        self.actor = self.real
        self.rotate_session()
        self.save()

    def logout(self):
        """
        Log this session out
        """
        self.actor = None
        self.real = None
        self.rotate_session()
        self.save()

    def changed_credentials(self):
        """
        Log out all other sessions for this user, rotate
        """
        self.rotate_session()
        self.save()

        for session in self.__class__.objects(real=self.real):
            if session != self:
                session.actor = None
                session.real = None
                session.save()
