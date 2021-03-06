# coding=utf-8

from __future__ import absolute_import
from mongoengine import *
from .mongoengine import QuantumField
import os
from trex.support import pcrypt
from trex.support.mongoengine import LowerCaseEmailField, serve_file
from flask import g, url_for, abort
import re
import hashlib
from . import token, quantum
import magic
import random
from itertools import izip, cycle
import binascii
from jinja2 import Markup
import pytz
import shutil
from .thumbnailers import ImageThumbnailer, PDFThumbnailer

class CantGenerateThumbnail(Exception):
    pass

class BaseDocument(Document):
    meta = dict(abstract=True)

    @classmethod
    def get_404(cls, *args, **kwargs):
        """Identical to cls.objects.get(...) except raises a flask 404 instead of mongoengine DoesNotExist"""
        try:
            return cls.objects.get(*args, **kwargs)
        except DoesNotExist:
            abort(404)

    def __init__(self, *args, **kwargs):
        # This is to prevent mongoengine doing weird conversions on new values
        # passed in the constructor
        kwargs['__auto_convert'] = False
        return super(BaseDocument, self).__init__(*args, **kwargs)

class ForeverDocument(Document):
    meta = dict(abstract=True)

    _archived = QuantumField()

    def is_archived(self):
        return self._archived is not None

    def __init__(self, *args, **kwargs):
        # This is to prevent mongoengine doing weird conversions on new values
        # passed in the constructor
        kwargs['__auto_convert'] = False
        return super(ForeverDocument, self).__init__(*args, **kwargs)

    @queryset_manager
    def objects(cls, queryset):
        import mongoengine
        import inspect
        import os

        mongoengine_location = os.path.dirname(mongoengine.__file__)
        if inspect.currentframe().f_back.f_back.f_code.co_filename.startswith(mongoengine_location):
            return queryset()
        raise AttributeError("objects is disabled for ForeverDocuments. Please use either .active or .all")

    @queryset_manager
    def active(cls, queryset):
        return queryset.filter(_archived=None)

    @classmethod
    def get_active_404(cls, *args, **kwargs):
        """Identical to cls.objects.get(...) except raises a flask 404 instead of mongoengine DoesNotExist"""
        try:
            return cls.active.get(*args, **kwargs)
        except DoesNotExist:
            abort(404)

    @queryset_manager
    def all(cls, queryset):
        return queryset()

    @classmethod
    def get_all_404(cls, *args, **kwargs):
        """Identical to cls.objects.get(...) except raises a flask 404 instead of mongoengine DoesNotExist"""
        try:
            return cls.all.get(*args, **kwargs)
        except DoesNotExist:
            abort(404)

    def delete(self):
        raise Exception("delete is invalid for ForeverDocuments. Please use either real_delete() or archive()")

    def archive(self):
        self._archived = quantum.now()
        self.save()

    def real_delete(self, *args, **kwargs):
        super(ForeverDocument, self).delete(*args, **kwargs)

class InvalidRoleException(Exception):
    pass

class InvalidLoginException(Exception):
    pass

class BaseUser(BaseDocument):
    meta = {
        'ordering': ['display_name'],
        'indexes': [('email',), ('token',)],
        'abstract': True,
    }

    token        = StringField(required=True, unique=True, default=token.create_url_token)
    email        = LowerCaseEmailField(required=True, unique=True)
    display_name = StringField(required=True)
    password     = StringField()
    created      = QuantumField(required=True, default=quantum.now)
    last_login   = QuantumField()
    role         = StringField(required=True, default='user')
    is_active    = BooleanField(required=True, default=True)
    country      = StringField(required=True, choices=pytz.country_names.keys())
    timezone     = StringField(required=True, choices=[x for y in pytz.country_timezones.values() for x in y])

    @queryset_manager
    def active(cls, queryset):
        return queryset.filter(is_active=True)

    @queryset_manager
    def inactive(cls, queryset):
        return queryset.filter(is_active=False)

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
                flags       = ['trex.user_management', 'trex.audit_log', 'trex.developer'],
                level       = 100,
            ),
        )

    def clean(self):
        if self.role not in self.__class__.roles().keys():
            raise ValidationError("Invalid role %s for User" % self.role)

    def default_after_login_url(self):
        return url_for('index.index')

    def default_after_logout_url(self):
        return url_for('index.index')

    def default_after_change_password_url(self):
        return url_for('index.index')

    @classmethod
    def url_for_add_user(cls, **kwargs):
        return url_for('trex.user_management.add', **kwargs)

    def url_for_edit_user(self, **kwargs):
        return url_for('trex.user_management.edit', user_token=self.token, **kwargs)

    def role_label(self):
        return self.roles()[self.role]['label']

    @classmethod
    def role_data_for(cls, role):
        try:
            return cls.roles()[role]
        except KeyError:
            raise InvalidRoleException("Invalid role: %s" % role)

    def has_role(self, role):
        if self.role == role:
            return True

        my_role = self.role_data_for(self.role)
        target_role = self.role_data_for(role)

        return my_role['level'] > target_role['level']

    def is_role(self, role):
        return self.role == role

    def has_flag(self, flag):
        my_role = self.role_data_for(self.role)
        if flag in my_role.get('flags', []):
            return True

        for role in self.roles().values():
            if role['level'] < my_role['level'] and flag in role.get('flags', []):
                return True

        return False

    def country_label(self):
        return pytz.country_names[self.country]

    def check_login(self, entered_password):
        if not self.is_active:
            raise InvalidLoginException("This account is disabled")
        if not self.check_password(entered_password):
            raise InvalidLoginException("Invalid email or password")

    def set_password(self, password, rounds=10001):
        self.password = pcrypt.hash(password, rounds)

    def check_password(self, entered_password):
        return pcrypt.verify(entered_password, self.password)

    def notify_password_reset(self, new_password):
        from trex.support import mail
        from app import app
        mail.send(
            to        = self.email,
            subject   = 'Your password on %s was reset' % app.settings.get('app', 'name'),
            text_body = "Hi,\n\nYou have a new password on %(app_name)s. Your login details are:\n\nEmail: %(email)s\nPassword: %(password)s\n\nYou can log in at: %(app_url)s\n\n--\n%(app_name)s" % dict(
                app_name = app.settings.get('app', 'name'),
                app_url  = url_for('index.index', _external=True),
                email    = self.email,
                password = new_password,
            )
        )
        return "Password emailed to %s" % self.email

    def reactivate(self, actor):
        """Re-activates this user account."""

        new_password = token.create_token(length=8)
        self.set_password(new_password)
        self.is_active = True
        self.save()

        from .audit import audit
        audit("Reactivated user %s and issued new password" % self.display_name, ['User Management'], [self])
        self.notify_password_reset(new_password)

    def deactivate(self, actor):
        """Deactivates this user account."""

        self.is_active = False
        self.password = None
        self.save()

        import app.model as m
        m.Identity.destroy_sessions_for_user(self)

        from .audit import audit
        audit("Deactivated user %s" % self.display_name, ['User Management'], [self], user=actor)

    def to_ejson(self):
        data = self.to_mongo().to_dict()
        data.pop('password', None)
        return data

class UserAccountRecovery(BaseDocument):
    created = QuantumField(required=True, default=quantum.now)
    user    = ReferenceField('User')
    code    = StringField(required=True, unique=True, default=lambda: token.create_human_token(length=8))

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

    created     = QuantumField(required=True, default=quantum.now)
    user        = ReferenceField('User')
    tags        = ListField(StringField(), required=True)
    description = StringField(required=True)
    moreinfo    = StringField()
    documents   = ListField(GenericReferenceField())

    def linkable_documents(self):
        docs = []
        for doc in self.documents:
            if isinstance(doc, BaseUser) and hasattr(g, 'user') and g.user.has_flag('trex.user_management'):
                docs.append(dict(
                    url   = doc.url_for_edit_user(),
                    label = doc.display_name,
                    type  = '%s user' % doc.role,
                ))

        return docs


def generate_session_id():
    """
    Securely generate a random token of the correct length for a session ID
    """
    # QUESTION: Sign it?
    return hashlib.sha256(hashlib.sha256(os.urandom(32)).digest()).hexdigest()


def generate_puffer():
        """
        Provides a random-content, psuedo-random-length string to be placed in responses to prevent the application
        from returning a predictable compressed length response.

        The objective is to ensure that attacks that use the length of the response as an oracle for figuring out
        matched text by compression face a more difficult task due to the ever-changing length of responses.

        It does not resolve the issue, only mitigate it to the extent that many more tests are required to achieve
        statistical certainty that a guess is correct.
        """
        return hashlib.sha256(hashlib.sha256(os.urandom(32)).digest()).hexdigest()[:random.randint(16,64)]

def verify_session_id(s):
    """
    Check whether it's a valid session ID
    """
    if len(s) != 64:
        return False

    if not re.search(r'^[0-9a-f]+$', s):
        return False

    return True

def verify_csrf_token(s):
    """
    Check whether it's likely to be a valid CSRF token
    """
    if settings.getboolean('security', 'shadow_csrf'):
        if len(s) != 128:
            return False
    else:
        if len(s) != 64:
            return False

    if not re.search(r'^[0-9a-f]+$', s):
        return False

    return True

settings = None


def default_expiry():
    return quantum.now('UTC').add(seconds=settings.getint('identity', 'activity_timeout'))

def xor_hex_string(s, key):
    """
    XOR a string using the given key string
    """
    s = bytearray(binascii.unhexlify(s))
    key = bytearray(binascii.unhexlify(key))

    return binascii.hexlify(''.join([chr(a ^ b) for (a, b) in izip(s, cycle(key))]))

class FlashMessage(EmbeddedDocument):
    message  = StringField(required=True)
    category = StringField(required=True, default='success')
    markup   = BooleanField(required=True, default=False)

    def get_message(self):
        if self.markup:
            return Markup(self.message)
        return self.message

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

    Additional security features

    * Retrieves session from data store via hashed ID instead of session ID to mitigate timing attacks based on index
      retrieval
    * Adds puffer to session headers to help mitigate SSL CRIME attacks
    * Shadows CSRF to prevent BREACH SSL attack against CSRF token

    Possible further features:

    * Rotation of session ID after a certain amount of time
    * Verify no-cache of session credentials
    * Explicit config permit of fields that survive credential transition
    * Integrated audit or notify for error conditions such as manipulated session ID
    * Set index to perform automatic removal of expired sessions

    References:

    * https://www.owasp.org/index.php/Session_Management_Cheat_Sheet

    """
    meta = {
        'indexes': [('session_id',),('hashed_id',),('real',),],
        'abstract': True
    }

    created = QuantumField(required=True, default=quantum.now)
    session_id = StringField(required=True)
    hashed_id = StringField(required=True)
    csrf_token = StringField(required=True, default=generate_session_id)
    expires = QuantumField(required=True, default=default_expiry)
    real = ReferenceField('User')
    actor = ReferenceField('User')
    logged_out = BooleanField(required=True, default=False)
    flashes = ListField(EmbeddedDocumentField(FlashMessage))

    def flash(self, message, category=None):
        flash = FlashMessage(message=message, category=category)
        if isinstance(message, Markup):
            flash.markup = True
        self.flashes.append(flash)
        self.save()

    def get_flashes(self):
        if not self.flashes:
            return []
        flashes = self.flashes
        self.flashes = []
        self.save()
        return flashes

    def rotate_session(self):
        """
        Rotate the session ID and CSRF token
        """
        self.session_id = generate_session_id()
        self.hashed_id = hashlib.sha256(self.session_id).hexdigest()
        self.csrf_token = generate_session_id()

    def reset_csrf(self):
        self.csrf_token = generate_session_id()
        self.save()

    def get_csrf(self):
        """
        Return CSRF suitable for insertion into a response. May use shadowing
        """
        token = self.csrf_token
        if settings.getboolean('security','shadow_csrf'):
            shadow = generate_session_id()
            return shadow + xor_hex_string(token, shadow)
        return token

    def check_csrf(self, s):
        """
        Check a (possibly shadowed) CSRF token
        """
        if not s or not verify_csrf_token(s):
            return False

        s = s.decode('ascii')

        if settings.getboolean('security','shadow_csrf'):
            token_length = len(generate_session_id())
            shadow = s[:token_length]
            token = xor_hex_string(s[token_length:], shadow)
        else:
            token = s

        # Hash for comparison prevents string timing attacks
        return hashlib.sha256(token).digest() == hashlib.sha256(self.csrf_token).digest()

    @classmethod
    def from_request(cls, request):
        """
        Load the session from the request
        """

        # Get session ID from cookie
        session_id = request.cookies.get(settings.get('identity', 'cookie_key'))

        return cls.from_session_id(session_id)

    @classmethod
    def from_session_id(cls, session_id):
        """
        Load the session from the supplied session_id
        """

        #   No session ID? return new session
        if not session_id:
            return cls.create()

        # Invalid session ID? return new session
        if not verify_session_id(session_id):
            return cls.create()

        # Got session id in cookie, look in DB
        session = cls.objects(hashed_id=hashlib.sha256(session_id).hexdigest()).first()

        # Not in DB? create new session.
        if not session:
            return cls.create()

        # Expired? new session
        if session.is_expired():
            return cls.create()

        # return doc
        return session

    @classmethod
    def create(cls):
        session_id = generate_session_id()
        return cls(session_id = session_id, hashed_id = hashlib.sha256(session_id).hexdigest())

    def set_cookie(self, response):
        """
        Set the cookie with the current session
        """
        # Update expiry so session stays valid
        activity_timeout_key = 'anonymous_activity_timeout'
        if self.real:
            activity_timeout_key = '%s_activity_timeout' % self.real.role
            if not settings.has_option('identity', activity_timeout_key):
                activity_timeout_key = 'activity_timeout'

        self.set_expiry(settings.getint('identity', activity_timeout_key))

        # Ensure we're setting the cookie matching the stored session
        self.save()

        # QUESTION: autorotate after given time?

        try:
            max_age = settings.getint('identity', 'cookie_expiry')
        except ValueError:
            max_age = None

        domain = settings.get('identity', 'domain')
        if len(domain) == 0:
            domain = None
        if settings.getboolean('security', 'puffer_headers'):
            # Set puffer cookie first, content is irrelevant
            response.set_cookie(settings.get('identity', 'cookie_key')+'-puff', generate_puffer(),
                            max_age=max_age,
                            path=settings.get('identity', 'path'),
                            domain=domain,
                            httponly=settings.get('identity', 'http_only'),
                            secure=settings.get('server', 'url').startswith('https:'))

        response.set_cookie(settings.get('identity', 'cookie_key'), self.session_id,
                            max_age=max_age,
                            path=settings.get('identity', 'path'),
                            domain=domain,
                            httponly=settings.get('identity', 'http_only'),
                            secure=settings.get('server', 'url').startswith('https:'))

    def set_expiry(self, seconds_from_now):
        """
        Set the expiry time to N seconds from now
        """
        self.expires = quantum.now('UTC').add(seconds=seconds_from_now)

    def is_expired(self):
        """
        Check whether this session is expired
        """
        # Has the session passed its activity expiry?
        if self.expires < quantum.now():
            return True

        # What about its final session expiry?
        session_timeout_key = 'session_timeout'
        if self.real:
            role_session_timeout_key = '%s_session_timeout' % self.real.role
            if settings.has_option('identity', role_session_timeout_key):
                session_timeout_key = role_session_timeout_key

        if self.created.at('UTC').add(seconds=settings.getint('identity', session_timeout_key)) < quantum.now('UTC'):
            return True

        return False

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

        self.__class__.objects(real=self.real, id__ne=self.id).update(set__actor=None, set__real=None)

    @classmethod
    def destroy_sessions_for_user(cls, user):
        """
        Log out all sessions for this user
        """
        for session in cls.objects(Q(real=user.id) | Q(actor=user.id)):
            session.logout()

class TrexUpload(BaseDocument):
    thumb_plugins = [ImageThumbnailer, PDFThumbnailer]

    meta = dict(
        collection = 'trex.upload',
        indexes    = [('token',)],
    )
    user      = ReferenceField('User', required=True)
    file      = FileField(required=True, collection_name='trex.upload')
    data      = DictField()
    created   = QuantumField(required=True, default=quantum.now)
    token     = StringField(required=True, default=token.create_url_token)
    preserved = BooleanField(required=True, default=False)

    def delete(self):
        self.file.delete()
        super(TrexUpload, self).delete()

    def url(self):
        return url_for('trex.upload.view', token=self.token)

    def can_thumbnail(self):
        for plugin in self.thumb_plugins:
            if plugin.can_thumbnail(self):
                return True
        return False

    def generate_thumbnail_response(self, width, height, fit):
        try:
            thumbnail = TrexUploadThumbnail.objects.get(upload=self, width=width, height=height, fit=fit)
        except DoesNotExist:
            thumbnail = self._create_thumbnail_model(width, height, fit)

        return serve_file(thumbnail, 'file')

    def _create_thumbnail_model(self, width, height, fit):
        for plugin in self.thumb_plugins:
            if plugin.can_thumbnail(self):
                return plugin.generate_thumbnail(self, width, height, fit)

        raise CantGenerateThumbnail("Can't thumbnail type %s" % self.file.content_type)

    def to_ejson(self):
        return dict(
            oid      = self.id,
            filename = self.file.filename,
            size     = self.file.length,
            mime     = self.file.content_type,
            url      = self.url(),
        )

    @classmethod
    def copy_from(cls, document, field_name, for_user=None, data=None):
        if not for_user:
            for_user = g.user
        if not data:
            data = {}
        field = document._fields[field_name]
        is_list = False
        if isinstance(field, ListField):
            field = field.field
            is_list = True
        if not isinstance(field, FileField):
            raise Exception("Can't copy uploads from non-FileFields")
        if is_list:
            raise NotImplementedError("Creating upload lists isn't yet implemented")
        else:
            upload = cls(
                user = for_user,
                data = data,
            )
            field_attr = getattr(document, field_name)
            upload.file.put(
                field_attr.get(),
                content_type = field_attr.content_type,
                filename = field_attr.filename,
            )
            upload.save()
            return upload

    @classmethod
    def from_file(cls, filename, for_user=None, data=None, content_type=None):
        if content_type is None:
            content_type = magic.from_file(filename, mime=True)
        with open(filename, 'r') as fh:
            return cls.from_file_handle(fh, for_user=for_user, data=data, filename=os.path.basename(filename), content_type=content_type)

    def to_file(self, filename):
        with open(filename, 'w') as fh:
            shutil.copyfileobj(self.file.get(), fh)
        return

    @classmethod
    def from_file_handle(cls, fh, for_user=None, data=None, filename=None, content_type=None):
        if not for_user:
            for_user = g.user
        if not data:
            data = {}
        upload = cls(
            user = for_user,
            data = data,
        )
        if content_type is None:
            content_type = magic.from_buffer(fh.read(65536), mime=True)
            fh.seek(0)
        upload.file.put(
            fh,
            content_type = content_type,
            filename     = filename,
        )
        upload.save()
        return upload

    @classmethod
    def from_buffer(cls, buf, filename=None, for_user=None, data=None):
        if not for_user:
            for_user = g.user
        if not data:
            data = {}
        upload = cls(
            user = for_user,
            data = data,
        )
        content_type = magic.from_buffer(str(buf), mime=True)
        upload.file.put(
            str(buf),
            content_type = content_type,
            filename     = filename,
        )
        upload.save()
        return upload

    @classmethod
    def from_filestorage(cls, data, for_user=None):
        """Imports from werkzeug FileStorage objects (e.g. those returned by WTForm's FileField object)"""
        return cls.from_file_handle(
            data.stream,
            filename     = data.filename,
            for_user     = for_user,
        )

    def update_reference(self, document, field_name):
        field = document._fields[field_name]
        if not isinstance(field, ReferenceField):
            raise Exception("Can't update reference on non-reference field")
        existing = getattr(document, field_name)
        if existing and existing != self:
            existing.release()
        setattr(document, field_name, self)
        self.preserve()

    def preserve(self):
        self.update(set__preserved=True)

    def release(self):
        self.update(set__preserved=False)

    def copy_to(self, document, field_name):
        field = document._fields[field_name]
        is_list = False
        if isinstance(field, ListField):
            field = field.field
            is_list = True
        if not isinstance(field, FileField):
            raise Exception("Can't copy uploads to non-FileFields")

        if is_list:
            gfproxy = GridFSProxy(key=field_name, collection_name=field.collection_name)
            gfproxy.put(
                self.file.get(),
                content_type = self.file.content_type,
                filename = self.file.filename,
            )
            getattr(document, field_name).append(gfproxy)
        else:
            getattr(document, field_name).put(
                self.file.get(),
                content_type = self.file.content_type,
                filename = self.file.filename,
            )

class TrexUploadTemporaryAccess(BaseDocument):
    """
    This class provides non-owner access to TrexUpload objects temporarily.

    For example, if an admin needs to edit a user's profile, they would need to
    be able to see the existing profile image on the form, this mechanism
    allows that.

    It is used automatically by the trex wtf widgets
    """
    meta = dict(
        collection = 'trex.upload.temporary_access',
    )

    # Slightly creative hack to get expireAfterSeconds index support
    @classmethod
    def ensure_indexes(cls, *args, **kwargs):
        super(TrexUploadTemporaryAccess, cls).ensure_indexes(*args, **kwargs)
        cls._get_collection().ensure_index('created', expireAfterSeconds=60)

    created = QuantumField(required=True, default=quantum.now)
    upload  = ReferenceField('TrexUpload', required=True, reverse_delete_rule=CASCADE)
    user    = ReferenceField('User', required=True)

class TrexUploadThumbnail(BaseDocument):
    meta = dict(
        collection = 'trex.upload.thumbnail',
        indexes    = [('upload',)],
    )

    created = QuantumField(required=True, default=quantum.now)
    width   = IntField()
    height  = IntField()
    fit     = StringField(required=True, choices=['stretch', 'cover', 'contain'])
    upload  = ReferenceField('TrexUpload', required=True, reverse_delete_rule=CASCADE, unique_with=['width', 'height', 'fit'])
    file    = FileField(required=True, collection_name='trex.upload.thumbnail')

    def delete(self):
        self.file.delete()
        super(TrexUploadThumbnail, self).delete()

class RateLimitBuffer(Document):
    meta = dict(
        indexes = [('bucket',), ('ip',)],
    )

    created  = QuantumField(required=True, default=quantum.now)
    bucket   = StringField(required=True)
    ip       = StringField(required=True)
    notified = BooleanField()
