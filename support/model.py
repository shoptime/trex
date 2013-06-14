# coding=utf-8

from __future__ import absolute_import
from mongoengine import *
from datetime import datetime
from trex.support import pcrypt
from trex.support.mongoengine import LowerCaseEmailField
from flask import flash

class InvalidRoleException(Exception):
    pass

class BaseUser(Document):
    meta = {
        'indexes': [('email',)],
        'abstract': True,
    }

    email      = LowerCaseEmailField(required=True, unique=True)
    password   = StringField()
    created    = DateTimeField(required=True, default=datetime.utcnow)
    last_login = DateTimeField()
    role       = StringField(required=True, default='user')

    def display_name(self):
        return self.email

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
